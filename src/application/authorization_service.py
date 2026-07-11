from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from src.core.identity.principal_authority_binding import PrincipalAuthorityBindingKernel
from src.domain.repositories import AuthorizationReceiptRepository


class AuthorizationApplicationService:
    """Coordinates authorization evaluation and durable receipt persistence."""

    def __init__(
        self,
        receipt_repository: AuthorizationReceiptRepository,
        *,
        kernel: PrincipalAuthorityBindingKernel | None = None,
    ) -> None:
        self.receipt_repository = receipt_repository
        self.kernel = kernel or PrincipalAuthorityBindingKernel()

    def authorize(
        self,
        *,
        request: Mapping[str, Any],
        principals: Sequence[Mapping[str, Any]],
        memberships: Sequence[Mapping[str, Any]],
        sessions: Sequence[Mapping[str, Any]],
        policies: Sequence[Mapping[str, Any]],
        approvals: Sequence[Mapping[str, Any]],
        revocations: Sequence[Mapping[str, Any]],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        decision = self.kernel.evaluate(
            request=request,
            principals=principals,
            memberships=memberships,
            sessions=sessions,
            policies=policies,
            approvals=approvals,
            revocations=revocations,
            now=now or datetime.now(timezone.utc),
        )
        receipt = dict(decision.receipt)
        receipt_id = str(
            receipt.get("receipt_id")
            or receipt.get("decision_id")
            or request.get("request_id")
        )
        if not receipt_id:
            raise ValueError("Authorization decision did not produce a receipt identifier")

        exact_revision = str(request.get("exact_revision") or "")
        request_digest = str(request.get("request_digest") or "")
        if not exact_revision or not request_digest:
            raise ValueError("Authorization request requires exact_revision and request_digest")

        stored = self.receipt_repository.append(
            receipt_id,
            receipt,
            exact_revision=exact_revision,
            request_digest=request_digest,
            idempotency_key=receipt_id,
        )
        return {
            "result": decision.result,
            "passed": decision.passed,
            "reason_codes": list(decision.reason_codes),
            "receipt_id": receipt_id,
            "receipt": stored.payload,
        }

    def get_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        stored = self.receipt_repository.get(receipt_id)
        return dict(stored.payload) if stored else None
