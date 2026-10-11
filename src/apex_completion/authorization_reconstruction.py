from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


AUTH_STATES = {
    "CURRENT_PENDING",
    "CURRENT_APPROVED",
    "CURRENT_DENIED",
    "CURRENT_REVISION_REQUIRED",
    "EXPIRED_PENDING",
    "EXPIRED_APPROVED",
    "EXPIRED_DENIED",
    "EXPIRED_REVISION_REQUIRED",
    "HISTORICAL_EXECUTED",
    "INVALID",
}


@dataclass(frozen=True)
class ReconstructedAuthorization:
    authorization_id: str
    action_id: str
    created_at: str
    expires_at: str
    state: str
    current_authority: bool
    approved: bool
    denied: bool
    revision_required: bool
    authorized_for_phase6: bool
    external_action_performed: bool
    proposed_external_action: str
    source_index: int


@dataclass(frozen=True)
class AuthorizationReconstructionReport:
    records: tuple[ReconstructedAuthorization, ...]
    total_records: int
    unique_action_ids: int
    current_authority_count: int
    historical_or_expired_count: int
    invalid_count: int
    duplicate_action_ids: tuple[str, ...]


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def reconstruct_authorization_register(
    records: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> AuthorizationReconstructionReport:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    source = tuple(records)
    seen_actions: set[str] = set()
    duplicates: set[str] = set()
    reconstructed: list[ReconstructedAuthorization] = []

    for index, item in enumerate(source):
        authorization_id = str(item.get("authorization_id") or "").strip()
        action_id = str(item.get("action_id") or "").strip()
        created_at = str(item.get("created_at") or "").strip()
        expires_at = str(item.get("expires_at") or "").strip()
        approval = _mapping(item.get("approval"))
        phase6 = _mapping(item.get("phase6_status"))
        approved = bool(approval.get("approved"))
        denied = bool(approval.get("denied"))
        revision_required = bool(approval.get("revision_required"))
        authorized_for_phase6 = bool(phase6.get("authorized_for_phase6"))
        external_action_performed = bool(phase6.get("external_action_performed"))
        proposed_action = str(item.get("proposed_external_action") or "")

        invalid = False
        expired = False
        try:
            if not authorization_id or not action_id or not created_at or not expires_at:
                invalid = True
            else:
                created = _parse_timestamp(created_at)
                expires = _parse_timestamp(expires_at)
                if expires <= created:
                    invalid = True
                expired = current >= expires
        except (ValueError, TypeError):
            invalid = True

        if action_id:
            if action_id in seen_actions:
                duplicates.add(action_id)
            seen_actions.add(action_id)

        contradictory = sum((approved, denied, revision_required)) > 1
        if contradictory:
            invalid = True
        if authorized_for_phase6 and not approved:
            invalid = True

        if invalid:
            state = "INVALID"
            current_authority = False
        elif external_action_performed:
            state = "HISTORICAL_EXECUTED"
            current_authority = False
        elif expired:
            if approved:
                state = "EXPIRED_APPROVED"
            elif denied:
                state = "EXPIRED_DENIED"
            elif revision_required:
                state = "EXPIRED_REVISION_REQUIRED"
            else:
                state = "EXPIRED_PENDING"
            current_authority = False
        elif approved and authorized_for_phase6:
            state = "CURRENT_APPROVED"
            current_authority = True
        elif denied:
            state = "CURRENT_DENIED"
            current_authority = False
        elif revision_required:
            state = "CURRENT_REVISION_REQUIRED"
            current_authority = False
        else:
            state = "CURRENT_PENDING"
            current_authority = False

        reconstructed.append(
            ReconstructedAuthorization(
                authorization_id=authorization_id,
                action_id=action_id,
                created_at=created_at,
                expires_at=expires_at,
                state=state,
                current_authority=current_authority,
                approved=approved,
                denied=denied,
                revision_required=revision_required,
                authorized_for_phase6=authorized_for_phase6,
                external_action_performed=external_action_performed,
                proposed_external_action=proposed_action,
                source_index=index,
            )
        )

    invalid_count = sum(item.state == "INVALID" for item in reconstructed)
    current_authority_count = sum(item.current_authority for item in reconstructed)
    historical_or_expired_count = sum(
        item.state.startswith("EXPIRED_") or item.state == "HISTORICAL_EXECUTED"
        for item in reconstructed
    )
    return AuthorizationReconstructionReport(
        records=tuple(reconstructed),
        total_records=len(reconstructed),
        unique_action_ids=len(seen_actions),
        current_authority_count=current_authority_count,
        historical_or_expired_count=historical_or_expired_count,
        invalid_count=invalid_count,
        duplicate_action_ids=tuple(sorted(duplicates)),
    )
