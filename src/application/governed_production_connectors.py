from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from .production_connectors import (
    PreparedConnectorAction,
    ProductionConnectorBroker,
    ProductionConnectorPolicyError,
    _digest,
    _strict_validate,
    _utc,
)


class GovernedProductionConnectorBroker(ProductionConnectorBroker):
    """Production connector broker with conservative execution evidence.

    All policy, approval, adapter, and idempotency checks complete before secret
    access. A failed write is marked as a possible external action only when the
    platform adapter was actually invoked.
    """

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
