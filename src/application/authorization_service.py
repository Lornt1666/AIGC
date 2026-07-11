from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
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

    @staticmethod
    def _receipt_id(request: Mapping[str, Any]) -> str:
        request_id = str(request.get("request_id") or "REQUEST-UNKNOWN")
        canonical = json.dumps(
            dict(request),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        digest = sha256(canonical.encode("utf-8")).hexdigest()
        return f"AUTHZ-{request_id}:{digest[:16]}"

    @staticmethod
    def _response(receipt_id: str, receipt: Mapping[str, Any]) -> dict[str, Any]:
        result = str(receipt.get("result") or "DENY")
        return {
            "result": result,
            "passed": result == "PERMIT",
            "reason_codes": list(receipt.get("reason_codes") or []),
            "receipt_id": receipt_id,
            "receipt": dict(receipt),
        }

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
        receipt_id = self._receipt_id(request)
        existing = self.receipt_repository.get(receipt_id)
        if existing is not None:
            return self._response(receipt_id, existing.payload)

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
        exact_revision = str(request.get("exact_revision") or "")
        request_digest = str(receipt.get("request_digest") or request.get("request_digest") or "")
        if not exact_revision or not request_digest:
            raise ValueError("Authorization request requires exact_revision and request_digest")

        stored = self.receipt_repository.append(
            receipt_id,
            receipt,
            exact_revision=exact_revision,
            request_digest=request_digest,
            idempotency_key=receipt_id,
        )
        return self._response(receipt_id, stored.payload)

    def get_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        stored = self.receipt_repository.get(receipt_id)
        return dict(stored.payload) if stored else None
