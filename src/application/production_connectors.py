from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol

from jsonschema import Draft202012Validator, FormatChecker

from src.infrastructure.secrets import GoogleSecretManagerResolver


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = ROOT / "config" / "production_connector_secret_broker.json"
DEFAULT_POLICY_SCHEMA = ROOT / "schemas" / "production_connector_secret_broker.schema.json"
_HEX40 = re.compile(r"^[a-f0-9]{40}$")


class ProductionConnectorPolicyError(ValueError):
    """Raised when a connector action violates the governed production boundary."""


class ConnectorAdapter(Protocol):
    def execute(
        self,
        *,
        operation_id: str,
        destination: str,
        payload: Mapping[str, Any],
        credential_material: bytes,
    ) -> Mapping[str, Any]: ...


class ConnectorIdempotencyStore(Protocol):
    def claim(self, *, key_digest: str, request_digest: str) -> bool: ...


@dataclass(frozen=True)
class ConnectorOperation:
    operation_id: str
    mode: str
    consequence: str
    approval_scope: str | None


@dataclass(frozen=True)
class ConnectorDefinition:
    connector_id: str
    platform: str
    enabled: bool
    official_api: bool
    secret_reference: str
    destination_allowlist: tuple[str, ...]
    operations: tuple[ConnectorOperation, ...]
    staging_verified: bool
    terms_approved: bool

    def operation(self, operation_id: str) -> ConnectorOperation:
        matches = [item for item in self.operations if item.operation_id == operation_id]
        if len(matches) != 1:
            raise ProductionConnectorPolicyError(
                f"Connector operation is not uniquely registered: {operation_id}"
            )
        return matches[0]


@dataclass(frozen=True)
class PreparedConnectorAction:
    request: dict[str, Any]
    payload: dict[str, Any]
    definition: ConnectorDefinition
    operation: ConnectorOperation


@dataclass(frozen=True)
class ConnectorBaselineEvaluation:
    status: str
    implemented_internal: bool
    production_complete: bool
    enabled_connectors: tuple[str, ...]
    blocking_evidence: tuple[str, ...]
    unresolved_configuration: tuple[str, ...]
    secret_access_authorized: bool
    production_connector_activation_authorized: bool
    production_external_action_authorized: bool
    external_action_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": "AIGC-PRODUCTION-CONNECTOR-EVALUATION-001",
            "contract_version": "1.0.0",
            "status": self.status,
            "implemented_internal": self.implemented_internal,
            "production_complete": self.production_complete,
            "enabled_connectors": list(self.enabled_connectors),
            "blocking_evidence": list(self.blocking_evidence),
            "unresolved_configuration": list(self.unresolved_configuration),
            "secret_access_authorized": self.secret_access_authorized,
            "production_connector_activation_authorized": (
                self.production_connector_activation_authorized
            ),
            "production_external_action_authorized": (
                self.production_external_action_authorized
            ),
            "external_action_performed": self.external_action_performed,
        }


class MemoryConnectorIdempotencyStore:
    """Process-local test baseline; production writes require durable storage."""

    def __init__(self) -> None:
        self._records: dict[str, str] = {}

    def claim(self, *, key_digest: str, request_digest: str) -> bool:
        existing = self._records.get(key_digest)
        if existing is None:
            self._records[key_digest] = request_digest
            return True
        if existing != request_digest:
            raise ProductionConnectorPolicyError(
                "Connector idempotency key was reused with different intent"
            )
        return False


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(value: Mapping[str, Any]) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_time(value: object) -> datetime:
    return _utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))


def _strict_validate(schema_name: str, value: Mapping[str, Any]) -> None:
    schema_path = ROOT / "schemas" / f"{schema_name}.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(dict(value)),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        messages: list[str] = []
        for error in errors[:10]:
            location = "$"
            if error.absolute_path:
                location += "".join(
                    f"[{part}]" if isinstance(part, int) else f".{part}"
                    for part in error.absolute_path
                )
            messages.append(f"{location}: {error.message}")
        raise ProductionConnectorPolicyError(
            f"{schema_name} validation failed: " + "; ".join(messages)
        )


def load_connector_policy(
    policy_path: str | Path = DEFAULT_POLICY_PATH,
    schema_path: str | Path = DEFAULT_POLICY_SCHEMA,
) -> dict[str, Any]:
    try:
        policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductionConnectorPolicyError(
            "Unable to load production connector policy"
        ) from exc
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(policy))
    if errors:
        raise ProductionConnectorPolicyError(
            "Production connector policy violates its schema"
        )
    connector_ids = [str(item["connector_id"]) for item in policy["connectors"]]
    if len(connector_ids) != len(set(connector_ids)):
        raise ProductionConnectorPolicyError("Connector IDs must be unique")
    return policy


def definitions_from_policy(
    policy: Mapping[str, Any],
) -> dict[str, ConnectorDefinition]:
    definitions: dict[str, ConnectorDefinition] = {}
    for raw in policy["connectors"]:
        connector = dict(raw)
        definition = ConnectorDefinition(
            connector_id=str(connector["connector_id"]),
            platform=str(connector["platform"]),
            enabled=bool(connector["enabled"]),
            official_api=bool(connector["official_api"]),
            secret_reference=str(connector["secret_reference"]),
            destination_allowlist=tuple(
                str(value) for value in connector["destination_allowlist"]
            ),
            operations=tuple(
                ConnectorOperation(
                    operation_id=str(item["operation_id"]),
                    mode=str(item["mode"]),
                    consequence=str(item["consequence"]),
                    approval_scope=(
                        str(item["approval_scope"])
                        if item["approval_scope"] is not None
                        else None
                    ),
                )
                for item in connector["operations"]
            ),
            staging_verified=(connector["staging_evidence_status"] == "VERIFIED"),
            terms_approved=(connector["terms_review_status"] == "APPROVED"),
        )
        definitions[definition.connector_id] = definition
    return definitions


def evaluate_connector_policy(
    policy: Mapping[str, Any],
) -> ConnectorBaselineEvaluation:
    definitions = definitions_from_policy(policy)
    authority = dict(policy["authority"])
    evidence = dict(policy["operational_evidence"])
    enabled = tuple(
        sorted(item.connector_id for item in definitions.values() if item.enabled)
    )
    blockers = tuple(name for name, observed in evidence.items() if observed is not True)
    unresolved: list[str] = []
    if policy["secret_manager"]["project_id"] is None:
        unresolved.append("secret_manager_project_id")
    if any("TBD_PROJECT" in item.secret_reference for item in definitions.values()):
        unresolved.append("connector_secret_references")
    if not all(item.terms_approved for item in definitions.values()):
        unresolved.append("connector_terms_reviews")
    if not all(item.staging_verified for item in definitions.values()):
        unresolved.append("connector_staging_evidence")
    if not enabled:
        unresolved.append("enabled_production_connectors")

    implemented = (
        policy.get("status") == "IMPLEMENTED_INTERNAL_PENDING_STAGING_EVIDENCE"
        and authority.get("internal_framework_implementation_authorized") is True
        and authority.get("offline_adapter_testing_authorized") is True
        and policy.get("external_action_performed") is False
    )
    complete = implemented and not blockers and not unresolved
    return ConnectorBaselineEvaluation(
        status="complete" if complete else "implemented_internal",
        implemented_internal=implemented,
        production_complete=complete,
        enabled_connectors=enabled,
        blocking_evidence=blockers,
        unresolved_configuration=tuple(unresolved),
        secret_access_authorized=bool(authority.get("secret_access_authorized")),
        production_connector_activation_authorized=bool(
            authority.get("production_connector_activation_authorized")
        ),
        production_external_action_authorized=bool(
            authority.get("production_external_action_authorized")
        ),
    )


class ProductionConnectorBroker:
    """Canonical fail-closed production connector execution boundary.

    The broker completes every local policy, approval, adapter, and idempotency
    precondition before secret access. For write operations, a failed adapter call
    is conservatively recorded as a possible external action only after the
    adapter was actually invoked.
    """

    def __init__(
        self,
        *,
        secret_resolver: GoogleSecretManagerResolver,
        adapters: Mapping[str, ConnectorAdapter],
        idempotency_store: ConnectorIdempotencyStore,
        execution_authorized: bool,
    ) -> None:
        self.secret_resolver = secret_resolver
        self.adapters = dict(adapters)
        self.idempotency_store = idempotency_store
        self.execution_authorized = execution_authorized

    def prepare(
        self,
        *,
        definition: ConnectorDefinition,
        operation_id: str,
        destination: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        exact_revision: str,
        now: datetime | None = None,
    ) -> PreparedConnectorAction:
        if not _HEX40.fullmatch(exact_revision):
            raise ProductionConnectorPolicyError(
                "Connector request requires an exact Git revision"
            )
        if destination not in set(definition.destination_allowlist):
            raise ProductionConnectorPolicyError(
                "Connector destination is not allowlisted"
            )
        operation = definition.operation(operation_id)
        current = _utc(now or datetime.now(timezone.utc))
        payload_value = dict(payload)
        payload_digest = _digest(payload_value)
        logical = {
            "exact_revision": exact_revision,
            "connector_id": definition.connector_id,
            "operation_id": operation.operation_id,
            "destination": destination,
            "idempotency_key": idempotency_key,
            "payload_digest": payload_digest,
            "mode": operation.mode,
            "consequence": operation.consequence,
            "approval_scope": operation.approval_scope,
            "dry_run_completed": True,
        }
        request_digest = _digest(logical)
        request = {
            "contract_id": "AIGC-CONNECTOR-ACTION-REQUEST-001",
            "contract_version": "1.0.0",
            "request_id": "CAR-" + request_digest[:24].upper(),
            **logical,
            "request_digest": request_digest,
            "created_at": current.isoformat(),
            "external_action_performed": False,
        }
        _strict_validate("connector_action_request", request)
        return PreparedConnectorAction(
            request=request,
            payload=payload_value,
            definition=definition,
            operation=operation,
        )

    def execute(
        self,
        prepared: PreparedConnectorAction,
        *,
        approval: Mapping[str, Any] | None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = _utc(now or datetime.now(timezone.utc))
        reasons: list[str] = []
        definition = prepared.definition
        operation = prepared.operation
        request = prepared.request

        if not self.execution_authorized:
            reasons.append("CONNECTOR_EXECUTION_UNAUTHORIZED")
        if not definition.enabled:
            reasons.append("CONNECTOR_DISABLED")
        if not definition.official_api:
            reasons.append("OFFICIAL_API_REQUIRED")
        if not definition.terms_approved:
            reasons.append("TERMS_REVIEW_INCOMPLETE")
        if not definition.staging_verified:
            reasons.append("STAGING_EVIDENCE_INCOMPLETE")
        if request["destination"] not in set(definition.destination_allowlist):
            reasons.append("DESTINATION_NOT_ALLOWED")

        approval_id: str | None = None
        if operation.approval_scope is not None:
            if approval is None:
                reasons.append("ACTION_APPROVAL_MISSING")
            else:
                approval_value = dict(approval)
                try:
                    _strict_validate("connector_action_approval", approval_value)
                    self._validate_approval(
                        request=request,
                        operation=operation,
                        approval=approval_value,
                        now=current,
                    )
                    approval_id = str(approval_value["approval_id"])
                except ProductionConnectorPolicyError:
                    reasons.append("ACTION_APPROVAL_INVALID")

        adapter = self.adapters.get(definition.connector_id)
        if adapter is None:
            reasons.append("CONNECTOR_ADAPTER_MISSING")

        if reasons:
            return self._receipt(
                prepared,
                result="DENY",
                reason_codes=tuple(dict.fromkeys(reasons)),
                approval_id=approval_id,
                secret_access_receipt=None,
                adapter_result_digest=None,
                now=current,
                external_action_performed=False,
            )

        key_digest = sha256(
            str(request["idempotency_key"]).encode("utf-8")
        ).hexdigest()
        try:
            first_execution = self.idempotency_store.claim(
                key_digest=key_digest,
                request_digest=str(request["request_digest"]),
            )
        except ProductionConnectorPolicyError:
            return self._receipt(
                prepared,
                result="DENY",
                reason_codes=("IDEMPOTENCY_CONFLICT",),
                approval_id=approval_id,
                secret_access_receipt=None,
                adapter_result_digest=None,
                now=current,
                external_action_performed=False,
            )
        if not first_execution:
            return self._receipt(
                prepared,
                result="DENY",
                reason_codes=("DUPLICATE_ACTION_BLOCKED",),
                approval_id=approval_id,
                secret_access_receipt=None,
                adapter_result_digest=None,
                now=current,
                external_action_performed=False,
            )

        resolved = None
        secret_receipt: dict[str, object] | None = None
        adapter_invoked = False
        try:
            resolved = self.secret_resolver.access(definition.secret_reference)
            secret_receipt = resolved.receipt.to_dict()
            adapter_invoked = True
            adapter_result = adapter.execute(
                operation_id=operation.operation_id,
                destination=str(request["destination"]),
                payload=prepared.payload,
                credential_material=resolved.bytes(),
            )
            adapter_result_digest = _digest(dict(adapter_result))
        except Exception:
            return self._receipt(
                prepared,
                result="FAILED",
                reason_codes=("CONNECTOR_EXECUTION_FAILED",),
                approval_id=approval_id,
                secret_access_receipt=secret_receipt,
                adapter_result_digest=None,
                now=current,
                external_action_performed=(
                    adapter_invoked and operation.mode == "write"
                ),
            )
        finally:
            if resolved is not None:
                resolved.close()

        return self._receipt(
            prepared,
            result="COMPLETED",
            reason_codes=(),
            approval_id=approval_id,
            secret_access_receipt=secret_receipt,
            adapter_result_digest=adapter_result_digest,
            now=current,
            external_action_performed=operation.mode == "write",
        )

    @staticmethod
    def _validate_approval(
        *,
        request: Mapping[str, Any],
        operation: ConnectorOperation,
        approval: Mapping[str, Any],
        now: datetime,
    ) -> None:
        expected = {
            "request_id": request["request_id"],
            "request_digest": request["request_digest"],
            "exact_revision": request["exact_revision"],
            "connector_id": request["connector_id"],
            "operation_id": request["operation_id"],
            "destination": request["destination"],
            "approval_scope": operation.approval_scope,
        }
        for key, expected_value in expected.items():
            if approval.get(key) != expected_value:
                raise ProductionConnectorPolicyError(
                    f"Connector approval {key} does not match request"
                )
        if approval.get("decision") != "APPROVED":
            raise ProductionConnectorPolicyError("Connector action was denied")
        issued_at = _parse_time(approval["issued_at"])
        expires_at = _parse_time(approval["expires_at"])
        if expires_at <= issued_at or now < issued_at or now >= expires_at:
            raise ProductionConnectorPolicyError(
                "Connector approval is not currently valid"
            )
        if (expires_at - issued_at).total_seconds() > 900:
            raise ProductionConnectorPolicyError(
                "Connector approval lifetime exceeds policy"
            )

    @staticmethod
    def _receipt(
        prepared: PreparedConnectorAction,
        *,
        result: str,
        reason_codes: tuple[str, ...],
        approval_id: str | None,
        secret_access_receipt: dict[str, object] | None,
        adapter_result_digest: str | None,
        now: datetime,
        external_action_performed: bool,
    ) -> dict[str, Any]:
        request = prepared.request
        receipt_material = {
            "request_digest": request["request_digest"],
            "result": result,
            "reason_codes": list(reason_codes),
            "approval_id": approval_id,
            "adapter_result_digest": adapter_result_digest,
        }
        receipt = {
            "contract_id": "AIGC-CONNECTOR-ACTION-RECEIPT-001",
            "contract_version": "1.0.0",
            "receipt_id": "COR-" + _digest(receipt_material)[:24].upper(),
            "request_id": request["request_id"],
            "request_digest": request["request_digest"],
            "exact_revision": request["exact_revision"],
            "connector_id": request["connector_id"],
            "operation_id": request["operation_id"],
            "destination": request["destination"],
            "idempotency_key_digest": sha256(
                str(request["idempotency_key"]).encode("utf-8")
            ).hexdigest(),
            "result": result,
            "reason_codes": list(reason_codes),
            "approval_id": approval_id,
            "secret_access_receipt": secret_access_receipt,
            "adapter_result_digest": adapter_result_digest,
            "created_at": now.isoformat(),
            "external_action_performed": external_action_performed,
        }
        _strict_validate("connector_action_receipt", receipt)
        return receipt
