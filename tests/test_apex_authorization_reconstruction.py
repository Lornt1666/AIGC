from datetime import datetime, timezone

import pytest

from src.apex_completion.authorization_reconstruction import reconstruct_authorization_register


NOW = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)


def packet(action_id="AIGC-ACT-1", **overrides):
    value = {
        "authorization_id": f"AUTH-{action_id}",
        "action_id": action_id,
        "created_at": "2026-08-09T09:00:00+00:00",
        "expires_at": "2026-08-09T11:00:00+00:00",
        "proposed_external_action": "Synthetic bounded action",
        "approval": {
            "approved": False,
            "denied": False,
            "revision_required": False,
        },
        "phase6_status": {
            "authorized_for_phase6": False,
            "external_action_performed": False,
        },
    }
    value.update(overrides)
    return value


def test_pending_packet_has_no_current_authority():
    result = reconstruct_authorization_register([packet()], now=NOW)
    assert result.records[0].state == "CURRENT_PENDING"
    assert result.current_authority_count == 0


def test_only_current_approved_phase6_packet_has_current_authority():
    item = packet()
    item["approval"] = {"approved": True, "denied": False, "revision_required": False}
    item["phase6_status"] = {"authorized_for_phase6": True, "external_action_performed": False}
    result = reconstruct_authorization_register([item], now=NOW)
    assert result.records[0].state == "CURRENT_APPROVED"
    assert result.current_authority_count == 1


def test_expired_approval_is_not_current_authority():
    item = packet(expires_at="2026-08-09T09:30:00+00:00")
    item["approval"] = {"approved": True, "denied": False, "revision_required": False}
    item["phase6_status"] = {"authorized_for_phase6": True, "external_action_performed": False}
    result = reconstruct_authorization_register([item], now=NOW)
    assert result.records[0].state == "EXPIRED_APPROVED"
    assert result.current_authority_count == 0


def test_expired_pending_is_classified_historical_not_current():
    result = reconstruct_authorization_register(
        [packet(expires_at="2026-08-01T00:00:00+00:00")],
        now=NOW,
    )
    assert result.records[0].state == "EXPIRED_PENDING"
    assert result.historical_or_expired_count == 1


def test_execution_flag_is_historical_evidence_not_fresh_authority():
    item = packet()
    item["approval"] = {"approved": True, "denied": False, "revision_required": False}
    item["phase6_status"] = {"authorized_for_phase6": True, "external_action_performed": True}
    result = reconstruct_authorization_register([item], now=NOW)
    assert result.records[0].state == "HISTORICAL_EXECUTED"
    assert result.current_authority_count == 0


def test_phase6_authority_without_approval_is_invalid():
    item = packet()
    item["phase6_status"] = {"authorized_for_phase6": True, "external_action_performed": False}
    result = reconstruct_authorization_register([item], now=NOW)
    assert result.records[0].state == "INVALID"
    assert result.invalid_count == 1


def test_contradictory_approval_state_is_invalid():
    item = packet()
    item["approval"] = {"approved": True, "denied": True, "revision_required": False}
    result = reconstruct_authorization_register([item], now=NOW)
    assert result.records[0].state == "INVALID"


def test_duplicate_action_ids_are_reported():
    result = reconstruct_authorization_register([packet(), packet()], now=NOW)
    assert result.unique_action_ids == 1
    assert result.duplicate_action_ids == ("AIGC-ACT-1",)


def test_invalid_expiry_order_is_invalid():
    result = reconstruct_authorization_register(
        [packet(expires_at="2026-08-09T08:00:00+00:00")],
        now=NOW,
    )
    assert result.records[0].state == "INVALID"


def test_naive_timestamp_is_invalid_not_silently_assumed_utc():
    result = reconstruct_authorization_register(
        [packet(created_at="2026-08-09T09:00:00")],
        now=NOW,
    )
    assert result.records[0].state == "INVALID"
