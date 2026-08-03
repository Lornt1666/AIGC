"""Canonical governed connector kernel for Ω Mission OS Increment 11.

The kernel centralizes policy, immutable packets, approvals, emergency-stop
checks, idempotency, replay protection, rate limits, redaction, and evidence.
Adapters remain provider-specific and authority-minimal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
from pathlib import Path
from typing import Any, Mapping, Protocol


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


class CredentialHandle(Protocol):
    """Opaque credential boundary. Tokens must never enter packets or evidence."""
    def available(self) -> bool: ...


class ConnectorAdapter(Protocol):
    connector_id: str
    capabilities: frozenset[str]
    def health(self) -> Mapping[str, Any]: ...
    def execute(self, capability: str, payload: Mapping[str, Any], idempotency_key: str) -> Mapping[str, Any]: ...


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
    def compile(
        cls,
        *,
        connector_id: str,
        capability: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        approval_id: str,
        approval_expires_at: str,
        policy_revision: str,
    ) -> "ExecutionPacket":
        if len(idempotency_key) != 64 or len(approval_id) < 8 or len(policy_revision) < 8:
            raise ValueError("bounded packet identifiers are required")
        body = {
            "schema_version": "1.0.0",
            "connector_id": connector_id,
            "capability": capability,
            "payload": dict(payload),
            "idempotency_key": idempotency_key,
            "approval_id": approval_id,
            "approval_expires_at": approval_expires_at,
            "policy_revision": policy_revision,
            "production_activation_authorized": False,
            "external_send_authorized": False,
        }
        _parse_utc(approval_expires_at, "approval_expires_at")
        return cls(**body, packet_sha256=digest(body))

    def verify(self) -> None:
        body = {key: value for key, value in self.__dict__.items() if key != "packet_sha256"}
        if not hmac.compare_digest(self.packet_sha256, digest(body)):
            raise PermissionError("execution packet integrity verification failed")
        if _parse_utc(self.approval_expires_at, "approval_expires_at") <= datetime.now(timezone.utc):
            raise PermissionError("execution approval expired")
        if self.production_activation_authorized or self.external_send_authorized:
            raise PermissionError("Increment 11 prohibits production and send authority")


class AppendOnlyEvidenceLedger:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def verify(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        records: list[dict[str, Any]] = []
        previous: str | None = None
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            supplied = record.get("record_sha256")
            body = {k: v for k, v in record.items() if k != "record_sha256"}
            if body.get("previous_record_sha256") != previous or not isinstance(supplied, str) or not hmac.compare_digest(supplied, digest(body)):
                raise ValueError("connector evidence ledger integrity failed")
            records.append(record)
            previous = supplied
        return records

    def append(self, event: Mapping[str, Any]) -> dict[str, Any]:
        records = self.verify()
        record = dict(event)
        record["previous_record_sha256"] = records[-1]["record_sha256"] if records else None
        record["record_sha256"] = digest(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        return record


class ConnectorKernel:
    """Fail-closed runtime shared by every connector adapter."""

    def __init__(self, *, emergency_stop_path: Path | str, ledger: AppendOnlyEvidenceLedger) -> None:
        self.emergency_stop_path = Path(emergency_stop_path)
        self.ledger = ledger
        self._adapters: dict[str, ConnectorAdapter] = {}
        self._policies: dict[str, KernelPolicy] = {}
        self._consumed_approvals: set[str] = set()
        self._idempotency: set[str] = set()
        self._hourly_counts: dict[tuple[str, str], int] = {}

    def register(self, adapter: ConnectorAdapter, policy: KernelPolicy) -> None:
        if adapter.connector_id != policy.connector_id:
            raise ValueError("connector and policy identifiers differ")
        if not adapter.capabilities.issubset(policy.allowed_capabilities):
            raise PermissionError("adapter declares capability outside policy")
        if policy.production_activation_authorized or policy.external_send_authorized:
            raise PermissionError("Increment 11 policies must remain non-production and no-send")
        self._adapters[adapter.connector_id] = adapter
        self._policies[adapter.connector_id] = policy

    def _stop_enabled(self) -> bool:
        value = json.loads(self.emergency_stop_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("enabled") is not True:
            raise PermissionError("connector emergency stop is not enabled")
        return True

    @staticmethod
    def redact(value: Mapping[str, Any]) -> dict[str, Any]:
        sensitive = {"access_token", "refresh_token", "authorization", "credential", "client_secret", "email"}
        return {k: ("[REDACTED]" if k.lower() in sensitive else v) for k, v in value.items()}

    def health(self, connector_id: str) -> Mapping[str, Any]:
        adapter = self._adapters.get(connector_id)
        if adapter is None:
            raise KeyError("connector is not registered")
        return self.redact(adapter.health())

    def execute(self, packet: ExecutionPacket) -> Mapping[str, Any]:
        packet.verify()
        self._stop_enabled()
        adapter = self._adapters.get(packet.connector_id)
        policy = self._policies.get(packet.connector_id)
        if adapter is None or policy is None:
            raise PermissionError("connector is not registered")
        if packet.capability not in adapter.capabilities or packet.capability not in policy.allowed_capabilities:
            raise PermissionError("capability is not authorized")
        if packet.approval_id in self._consumed_approvals:
            raise PermissionError("approval replay detected")
        if packet.idempotency_key in self._idempotency:
            raise PermissionError("idempotency replay detected")
        hour = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
        bucket = (packet.connector_id, hour)
        if self._hourly_counts.get(bucket, 0) >= policy.rate_limit_per_hour:
            raise PermissionError("connector rate limit exceeded")

        # Reserve before any adapter effect; uncertain outcomes cannot be retried.
        self._consumed_approvals.add(packet.approval_id)
        self._idempotency.add(packet.idempotency_key)
        self._hourly_counts[bucket] = self._hourly_counts.get(bucket, 0) + 1
        started = self.ledger.append({
            "schema_version": "1.0.0",
            "event": "CONNECTOR_EXECUTION_RESERVED",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "connector_id": packet.connector_id,
            "capability": packet.capability,
            "packet_sha256": packet.packet_sha256,
            "idempotency_key": packet.idempotency_key,
            "production_activation_authorized": False,
            "external_send_authorized": False,
        })
        try:
            result = adapter.execute(packet.capability, packet.payload, packet.idempotency_key)
        except Exception as exc:
            self.ledger.append({
                "schema_version": "1.0.0",
                "event": "CONNECTOR_EXECUTION_UNCERTAIN",
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "connector_id": packet.connector_id,
                "capability": packet.capability,
                "packet_sha256": packet.packet_sha256,
                "started_record_sha256": started["record_sha256"],
                "error_sha256": sha256(str(exc).encode("utf-8")).hexdigest(),
                "retry_authorized": False,
                "production_activation_authorized": False,
                "external_send_authorized": False,
            })
            raise
        redacted = self.redact(result)
        completed = self.ledger.append({
            "schema_version": "1.0.0",
            "event": "CONNECTOR_EXECUTION_COMPLETED",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "connector_id": packet.connector_id,
            "capability": packet.capability,
            "packet_sha256": packet.packet_sha256,
            "started_record_sha256": started["record_sha256"],
            "result_sha256": digest(redacted),
            "production_activation_authorized": False,
            "external_send_authorized": False,
        })
        return {"result": redacted, "evidence_record_sha256": completed["record_sha256"]}
