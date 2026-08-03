"""Canonical fail-closed connector kernel for Ω Mission OS Increment 11."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any, Iterator, Mapping, Protocol, Sequence


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parse_utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise PermissionError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PermissionError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise PermissionError(f"{field} must include timezone")
    return parsed.astimezone(timezone.utc)


def _atomic_json_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    temporary.write_text(json.dumps(dict(value), sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _redact(value: Any) -> Any:
    sensitive = {
        "access_token", "refresh_token", "authorization", "credential",
        "client_secret", "email", "account_email", "provider_object_id",
        "draft_id", "token", "password", "authority_signature",
    }
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"provider_object_id", "draft_id"}:
                redacted[f"{key}_sha256"] = sha256(str(item).encode("utf-8")).hexdigest()
            elif lowered in sensitive:
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = _redact(item)
        return redacted
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


class ConnectorAdapter(Protocol):
    connector_id: str
    capabilities: frozenset[str]
    def health(self) -> Mapping[str, Any]: ...
    def execute(self, capability: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]: ...


class ApprovalVerifier(Protocol):
    deployment_ready: bool
    def verify(self, approval: "ApprovalRecord", packet: "ExecutionPacket") -> bool: ...


@dataclass(frozen=True)
class KernelPolicy:
    connector_id: str
    allowed_capabilities: frozenset[str]
    rate_limit_per_hour: int
    production_activation_authorized: bool = False
    external_send_authorized: bool = False


@dataclass(frozen=True)
class ExecutionPacket:
    schema_version: str
    connector_id: str
    capability: str
    payload: Mapping[str, Any]
    idempotency_key: str
    approval_id: str
    approval_expires_at: str
    policy_revision: str
    production_activation_authorized: bool
    external_send_authorized: bool
    packet_sha256: str

    @classmethod
    def compile(cls, *, connector_id: str, capability: str, payload: Mapping[str, Any],
                idempotency_key: str, approval_id: str, approval_expires_at: str,
                policy_revision: str) -> "ExecutionPacket":
        if len(idempotency_key) != 64 or len(approval_id) < 8 or len(policy_revision) < 8:
            raise ValueError("bounded packet identifiers are required")
        body = {
            "schema_version": "1.0.0", "connector_id": connector_id,
            "capability": capability, "payload": dict(payload),
            "idempotency_key": idempotency_key, "approval_id": approval_id,
            "approval_expires_at": approval_expires_at,
            "policy_revision": policy_revision,
            "production_activation_authorized": False,
            "external_send_authorized": False,
        }
        _parse_utc(approval_expires_at, "approval_expires_at")
        return cls(**body, packet_sha256=digest(body))

    def verify(self) -> None:
        body = {k: v for k, v in self.__dict__.items() if k != "packet_sha256"}
        if not hmac.compare_digest(self.packet_sha256, digest(body)):
            raise PermissionError("execution packet integrity verification failed")
        if _parse_utc(self.approval_expires_at, "approval_expires_at") <= datetime.now(timezone.utc):
            raise PermissionError("execution approval expired")
        if self.production_activation_authorized or self.external_send_authorized:
            raise PermissionError("Increment 11 prohibits production and send authority")


@dataclass(frozen=True)
class ApprovalRecord:
    schema_version: str
    approval_id: str
    packet_sha256: str
    connector_id: str
    capability: str
    expires_at: str
    authority_id: str
    authority_signature: str
    approval_sha256: str

    @classmethod
    def compile(cls, *, approval_id: str, packet_sha256: str, connector_id: str,
                capability: str, expires_at: str, authority_id: str,
                authority_signature: str = "UNSIGNED-NONDEPLOYABLE") -> "ApprovalRecord":
        body = {
            "schema_version": "1.0.0", "approval_id": approval_id,
            "packet_sha256": packet_sha256, "connector_id": connector_id,
            "capability": capability, "expires_at": expires_at,
            "authority_id": authority_id,
        }
        _parse_utc(expires_at, "approval expires_at")
        return cls(**body, authority_signature=authority_signature, approval_sha256=digest(body))

    def verify_integrity(self) -> None:
        body = {
            "schema_version": self.schema_version, "approval_id": self.approval_id,
            "packet_sha256": self.packet_sha256, "connector_id": self.connector_id,
            "capability": self.capability, "expires_at": self.expires_at,
            "authority_id": self.authority_id,
        }
        if not hmac.compare_digest(self.approval_sha256, digest(body)):
            raise PermissionError("approval record integrity verification failed")
        if _parse_utc(self.expires_at, "approval expires_at") <= datetime.now(timezone.utc):
            raise PermissionError("approval record expired")


class HMACApprovalVerifier:
    """Authenticated verifier unavailable without trusted runtime configuration."""

    def __init__(self, *, secret: str, trusted_authority_ids: frozenset[str]) -> None:
        if len(secret) < 32 or not trusted_authority_ids:
            raise PermissionError("trusted approval authority configuration is unavailable")
        self._secret = secret.encode("utf-8")
        self._trusted = trusted_authority_ids
        self.deployment_ready = True

    @classmethod
    def from_environment(cls, *, secret_variable: str,
                         trusted_authority_ids: frozenset[str]) -> "HMACApprovalVerifier":
        return cls(
            secret=os.environ.get(secret_variable, ""),
            trusted_authority_ids=trusted_authority_ids,
        )

    def sign(self, approval_sha256: str, authority_id: str) -> str:
        if authority_id not in self._trusted:
            raise PermissionError("approval authority is not trusted")
        message = f"{authority_id}:{approval_sha256}".encode("utf-8")
        return hmac.new(self._secret, message, sha256).hexdigest()

    def verify(self, approval: ApprovalRecord, packet: ExecutionPacket) -> bool:
        if approval.authority_id not in self._trusted:
            return False
        expected = self.sign(approval.approval_sha256, approval.authority_id)
        return (
            hmac.compare_digest(approval.authority_signature, expected)
            and approval.packet_sha256 == packet.packet_sha256
        )


class AppendOnlyEvidenceLedger:
    def __init__(self, path: Path | str, *, lock_timeout_seconds: float = 10.0) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.lock_timeout_seconds = lock_timeout_seconds

    @contextmanager
    def transaction(self) -> Iterator[None]:
        deadline = time.monotonic() + self.lock_timeout_seconds
        while True:
            try:
                self.lock_path.mkdir(parents=True)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("connector evidence transaction lock timed out")
                time.sleep(0.01)
        try:
            yield
        finally:
            try:
                self.lock_path.rmdir()
            except FileNotFoundError:
                pass

    def _verify_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        records: list[dict[str, Any]] = []
        previous: str | None = None
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("connector evidence record must be an object")
            supplied = record.get("record_sha256")
            body = {k: v for k, v in record.items() if k != "record_sha256"}
            if body.get("previous_record_sha256") != previous or not isinstance(supplied, str) or not hmac.compare_digest(supplied, digest(body)):
                raise ValueError("connector evidence ledger integrity failed")
            records.append(record)
            previous = supplied
        return records

    def verify(self) -> list[dict[str, Any]]:
        with self.transaction():
            return self._verify_unlocked()

    def _append_unlocked(self, event: Mapping[str, Any], records: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        prior = list(records) if records is not None else self._verify_unlocked()
        record = dict(event)
        record["previous_record_sha256"] = prior[-1]["record_sha256"] if prior else None
        record["record_sha256"] = digest(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return record

    def append(self, event: Mapping[str, Any]) -> dict[str, Any]:
        with self.transaction():
            records = self._verify_unlocked()
            return self._append_unlocked(event, records)


class ConnectorKernel:
    def __init__(self, *, emergency_stop_path: Path | str,
                 ledger: AppendOnlyEvidenceLedger,
                 approval_verifier: ApprovalVerifier) -> None:
        if getattr(approval_verifier, "deployment_ready", False) is not True:
            raise PermissionError("authenticated approval verifier is not deployment ready")
        self.emergency_stop_path = Path(emergency_stop_path)
        self.ledger = ledger
        self.approval_verifier = approval_verifier
        self._adapters: dict[str, ConnectorAdapter] = {}
        self._policies: dict[str, KernelPolicy] = {}

    def register(self, adapter: ConnectorAdapter, policy: KernelPolicy) -> None:
        if adapter.connector_id != policy.connector_id:
            raise ValueError("connector and policy identifiers differ")
        if not adapter.capabilities.issubset(policy.allowed_capabilities):
            raise PermissionError("adapter declares capability outside policy")
        if policy.rate_limit_per_hour < 1:
            raise ValueError("positive rate limit is required")
        if policy.production_activation_authorized or policy.external_send_authorized:
            raise PermissionError("Increment 11 policies must remain non-production and no-send")
        self._adapters[adapter.connector_id] = adapter
        self._policies[adapter.connector_id] = policy

    def _verify_unlock(self, packet: ExecutionPacket) -> dict[str, Any]:
        try:
            value = json.loads(self.emergency_stop_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PermissionError("connector emergency stop is unavailable") from exc
        if not isinstance(value, dict):
            raise PermissionError("connector emergency stop is malformed")
        if value.get("enabled") is True:
            raise PermissionError("connector emergency stop is locked")
        required = {
            "packet_sha256": packet.packet_sha256,
            "approval_id": packet.approval_id,
            "connector_id": packet.connector_id,
            "capability": packet.capability,
            "production_activation_authorized": False,
            "external_send_authorized": False,
        }
        if any(value.get(k) != expected for k, expected in required.items()):
            raise PermissionError("connector unlock is not bound to the exact packet")
        if _parse_utc(value.get("expires_at"), "unlock expires_at") <= datetime.now(timezone.utc):
            raise PermissionError("connector unlock expired")
        if not isinstance(value.get("revision"), str) or len(value["revision"]) < 8:
            raise PermissionError("connector unlock revision is invalid")
        return value

    def _relock(self, *, packet: ExecutionPacket, prior_revision: str) -> dict[str, Any]:
        record = {
            "enabled": True,
            "revision": f"RELOCK-{secrets.token_hex(8)}",
            "prior_unlock_revision": prior_revision,
            "consumed_packet_sha256": packet.packet_sha256,
            "consumed_approval_id": packet.approval_id,
            "relocked_at": datetime.now(timezone.utc).isoformat(),
            "production_activation_authorized": False,
            "external_send_authorized": False,
        }
        _atomic_json_write(self.emergency_stop_path, record)
        return record

    @staticmethod
    def redact(value: Mapping[str, Any]) -> dict[str, Any]:
        result = _redact(value)
        if not isinstance(result, dict):
            raise TypeError("redacted connector record must remain an object")
        return result

    def health(self, connector_id: str) -> Mapping[str, Any]:
        adapter = self._adapters.get(connector_id)
        if adapter is None:
            raise KeyError("connector is not registered")
        return self.redact(adapter.health())

    def _durable_state(self, records: Sequence[Mapping[str, Any]]) -> tuple[set[str], set[str], dict[tuple[str, str], int]]:
        approvals: set[str] = set()
        idempotency: set[str] = set()
        hourly: dict[tuple[str, str], int] = {}
        for record in records:
            if record.get("event") != "CONNECTOR_EXECUTION_RESERVED":
                continue
            approval = record.get("approval_id")
            idem = record.get("idempotency_key")
            connector = record.get("connector_id")
            hour = record.get("rate_limit_hour")
            if isinstance(approval, str):
                approvals.add(approval)
            if isinstance(idem, str):
                idempotency.add(idem)
            if isinstance(connector, str) and isinstance(hour, str):
                key = (connector, hour)
                hourly[key] = hourly.get(key, 0) + 1
        return approvals, idempotency, hourly

    def _append_relocked_evidence(self, *, packet: ExecutionPacket,
                                  unlock_revision: str, relock_revision: str) -> None:
        self.ledger.append({
            "schema_version": "1.0.0", "event": "CONNECTOR_EMERGENCY_STOP_RELOCKED",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "connector_id": packet.connector_id, "capability": packet.capability,
            "packet_sha256": packet.packet_sha256,
            "approval_id": packet.approval_id,
            "unlock_revision": unlock_revision,
            "relock_revision": relock_revision,
            "enabled": True,
            "production_activation_authorized": False,
            "external_send_authorized": False,
        })

    def execute(self, packet: ExecutionPacket, approval: ApprovalRecord) -> Mapping[str, Any]:
        packet.verify()
        approval.verify_integrity()
        if approval.approval_id != packet.approval_id or approval.packet_sha256 != packet.packet_sha256:
            raise PermissionError("approval is not bound to the exact packet")
        if approval.connector_id != packet.connector_id or approval.capability != packet.capability:
            raise PermissionError("approval action binding mismatch")
        if not self.approval_verifier.verify(approval, packet):
            raise PermissionError("approval authority verification failed")
        unlock = self._verify_unlock(packet)

        terminal_error: BaseException | None = None
        result_value: Mapping[str, Any] | None = None
        try:
            adapter = self._adapters.get(packet.connector_id)
            policy = self._policies.get(packet.connector_id)
            if adapter is None or policy is None:
                raise PermissionError("connector is not registered")
            if packet.capability not in adapter.capabilities or packet.capability not in policy.allowed_capabilities:
                raise PermissionError("capability is not authorized")

            hour = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
            with self.ledger.transaction():
                records = self.ledger._verify_unlocked()
                approvals, idempotency, hourly = self._durable_state(records)
                if packet.approval_id in approvals:
                    raise PermissionError("approval replay detected")
                if packet.idempotency_key in idempotency:
                    raise PermissionError("idempotency replay detected")
                if hourly.get((packet.connector_id, hour), 0) >= policy.rate_limit_per_hour:
                    raise PermissionError("connector rate limit exceeded")
                started = self.ledger._append_unlocked({
                    "schema_version": "1.0.0", "event": "CONNECTOR_EXECUTION_RESERVED",
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "connector_id": packet.connector_id, "capability": packet.capability,
                    "packet_sha256": packet.packet_sha256,
                    "approval_id": packet.approval_id,
                    "approval_sha256": approval.approval_sha256,
                    "idempotency_key": packet.idempotency_key,
                    "rate_limit_hour": hour,
                    "production_activation_authorized": False,
                    "external_send_authorized": False,
                }, records)
                consumed = self.ledger._append_unlocked({
                    "schema_version": "1.0.0", "event": "CONNECTOR_UNLOCK_CONSUMED",
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "connector_id": packet.connector_id, "capability": packet.capability,
                    "packet_sha256": packet.packet_sha256,
                    "approval_id": packet.approval_id,
                    "unlock_revision": unlock["revision"],
                    "started_record_sha256": started["record_sha256"],
                    "production_activation_authorized": False,
                    "external_send_authorized": False,
                }, [*records, started])

            try:
                result = adapter.execute(packet.capability, packet.payload, packet.idempotency_key)
                redacted = self.redact(result)
                completed = self.ledger.append({
                    "schema_version": "1.0.0", "event": "CONNECTOR_EXECUTION_COMPLETED",
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "connector_id": packet.connector_id, "capability": packet.capability,
                    "packet_sha256": packet.packet_sha256,
                    "approval_id": packet.approval_id,
                    "idempotency_key": packet.idempotency_key,
                    "started_record_sha256": started["record_sha256"],
                    "unlock_consumed_record_sha256": consumed["record_sha256"],
                    "result_sha256": digest(redacted),
                    "production_activation_authorized": False,
                    "external_send_authorized": False,
                })
                result_value = {"result": redacted, "evidence_record_sha256": completed["record_sha256"]}
            except BaseException as exc:
                self.ledger.append({
                    "schema_version": "1.0.0", "event": "CONNECTOR_EXECUTION_UNCERTAIN",
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "connector_id": packet.connector_id, "capability": packet.capability,
                    "packet_sha256": packet.packet_sha256,
                    "approval_id": packet.approval_id,
                    "idempotency_key": packet.idempotency_key,
                    "started_record_sha256": started["record_sha256"],
                    "unlock_consumed_record_sha256": consumed["record_sha256"],
                    "error_sha256": sha256(str(exc).encode("utf-8")).hexdigest(),
                    "retry_authorized": False,
                    "production_activation_authorized": False,
                    "external_send_authorized": False,
                })
                raise
        except BaseException as exc:
            terminal_error = exc
        finally:
            relock = self._relock(packet=packet, prior_revision=str(unlock["revision"]))
            self._append_relocked_evidence(
                packet=packet,
                unlock_revision=str(unlock["revision"]),
                relock_revision=str(relock["revision"]),
            )

        if terminal_error is not None:
            raise terminal_error
        assert result_value is not None
        return result_value
