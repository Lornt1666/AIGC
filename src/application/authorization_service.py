from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from src.core.identity.principal_authority_binding import (
    PERMIT,
    PrincipalAuthorityBindingKernel,
)
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
    def _receipt_id(
        *,
        request: Mapping[str, Any],
        principals: Sequence[Mapping[str, Any]],
        memberships: Sequence[Mapping[str, Any]],
        sessions: Sequence[Mapping[str, Any]],
        policies: Sequence[Mapping[str, Any]],
        approvals: Sequence[Mapping[str, Any]],
        revocations: Sequence[Mapping[str, Any]],
    ) -> str:
        request_id = str(request.get("request_id") or "REQUEST-UNKNOWN")
        authority_bundle = {
            "request": dict(request),
            "principals": [dict(item) for item in principals],
            "memberships": [dict(item) for item in memberships],
            "sessions": [dict(item) for item in sessions],
            "policies": [dict(item) for item in policies],
            "approvals": [dict(item) for item in approvals],
            "revocations": [dict(item) for item in revocations],
        }
        canonical = json.dumps(
            authority_bundle,
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
            "passed": result == PERMIT,
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
        receipt_id = self._receipt_id(
            request=request,
            principals=principals,
            memberships=memberships,
            sessions=sessions,
            policies=policies,
            approvals=approvals,
            revocations=revocations,
        )
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
        request_digest = str(
            receipt.get("request_digest")
            or request.get("request_digest")
            or ""
        )
        if not exact_revision or not request_digest:
            raise ValueError(
                "Authorization request requires exact_revision and request_digest"
            )

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

    def verify_permit_receipt(
        self,
        receipt_id: str,
        authorization_request: Mapping[str, Any],
        *,
        expected_exact_revision: str,
        expected_resource_id: str,
        expected_action: str,
        expected_scopes: Sequence[str],
        expected_purpose: str,
        required_evidence_ids: Sequence[str],
    ) -> dict[str, Any]:
        """Verify an immutable PERMIT receipt against exact transition intent."""

        request = dict(authorization_request)
        contract_errors = self.kernel.validator.errors("request", request)
        if contract_errors:
            raise ValueError(
                "Authorization request violates its contract: "
                + "; ".join(contract_errors[:5])
            )

        stored = self.receipt_repository.get(receipt_id)
        if stored is None:
            raise ValueError(f"Authorization receipt not found: {receipt_id}")
        receipt = dict(stored.payload)

        if receipt.get("result") != PERMIT:
            raise ValueError(
                "Authorization receipt must contain a PERMIT decision"
            )
        if receipt.get("external_action_performed") is not False:
            raise ValueError(
                "Authorization receipt cannot record an external action"
            )
        if receipt.get("state_changed") is not False:
            raise ValueError(
                "Authorization evaluation receipt cannot mutate Quest state"
            )

        computed_digest = self.kernel.request_digest(request)
        if request.get("request_digest") != computed_digest:
            raise ValueError("Authorization request digest is invalid")
        if receipt.get("request_digest") != computed_digest:
            raise ValueError(
                "Authorization receipt is not bound to the supplied request"
            )

        if request.get("exact_revision") != expected_exact_revision:
            raise ValueError(
                "Authorization request is not bound to the required revision"
            )
        if receipt.get("exact_revision") != expected_exact_revision:
            raise ValueError(
                "Authorization receipt is not bound to the required revision"
            )

        resource = request.get("resource")
        if not isinstance(resource, Mapping):
            raise ValueError("Authorization request lacks a resource binding")
        if resource.get("resource_id") != expected_resource_id:
            raise ValueError(
                "Authorization request is not bound to the target Quest"
            )
        if request.get("action") != expected_action:
            raise ValueError(
                "Authorization request does not permit the required action"
            )
        if request.get("purpose") != expected_purpose:
            raise ValueError(
                "Authorization request does not match the required purpose"
            )

        scopes = {
            str(value)
            for value in request.get("scopes") or []
            if str(value)
        }
        if not set(expected_scopes).issubset(scopes):
            raise ValueError(
                "Authorization request lacks the work-acceptance scope"
            )

        evidence_ids = {
            str(value)
            for value in request.get("evidence_ids") or []
            if str(value)
        }
        missing_evidence = set(required_evidence_ids) - evidence_ids
        if missing_evidence:
            raise ValueError(
                "Authorization request lacks transition evidence: "
                + ", ".join(sorted(missing_evidence))
            )

        return receipt
