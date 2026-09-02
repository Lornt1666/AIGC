from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.phase6_controlled_execution import ExecutionMode, resolve_execution_mode


ROOT = Path(__file__).resolve().parents[1]


def test_phase6_manual_handoff_lock_rejects_other_execution_modes() -> None:
    config = json.loads(
        (ROOT / "config" / "phase6_controlled_execution.json").read_text(encoding="utf-8")
    )

    assert resolve_execution_mode(config) == ExecutionMode.MANUAL_HANDOFF.value
    for mode in (
        ExecutionMode.DRY_RUN.value,
        ExecutionMode.APPROVED_API.value,
        ExecutionMode.APPROVED_PLATFORM_UI.value,
    ):
        with pytest.raises(ValueError, match="locked to manual_handoff"):
            resolve_execution_mode(config, execution_mode_override=mode)


def test_expired_phase5_packets_are_archived_and_removed_from_active_queue() -> None:
    active_path = (
        ROOT
        / "data"
        / "phase5_authorizations"
        / "aigc_phase5_authorization_packets.json"
    )
    archive_path = (
        ROOT
        / "data"
        / "phase5_authorizations"
        / "archive"
        / "aigc_phase5_authorization_packets_2026-09-02_expired.json"
    )
    manifest_path = (
        ROOT
        / "data"
        / "phase5_authorizations"
        / "archive"
        / "aigc_phase5_expired_packet_archive_2026-09-02.json"
    )

    assert json.loads(active_path.read_text(encoding="utf-8")) == []
    archived_packets = json.loads(archive_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert len(archived_packets) == 25
    assert manifest["packet_count"] == len(archived_packets)
    assert manifest["status"] == "archived_expired_do_not_accept_or_handoff"
    now = datetime.now(timezone.utc)
    assert all(
        datetime.fromisoformat(packet["expires_at"]).astimezone(timezone.utc) < now
        for packet in archived_packets
    )


def test_next_cycle_directive_stays_read_only_and_single_scope() -> None:
    directive = json.loads(
        (ROOT / "data" / "phase8_evolution" / "next_cycle_strategy.json").read_text(
            encoding="utf-8"
        )
    )

    controls = directive["manual_handoff_directive"]
    proposal = directive["scoped_internal_improvement_proposal"]

    assert controls["phase4_input_review_mode"] == "read_only"
    assert controls["phase5_input_review_mode"] == "read_only_archived_expired_packets"
    assert controls["packet_regeneration_allowed"] is False
    assert controls["maximum_scoped_internal_improvement_proposals"] == 1
    assert controls["phase6_execution_mode"] == "manual_handoff"
    assert controls["production_locked"] is True
    assert controls["external_contact_allowed"] is False
    assert controls["native_workflow_run_requires_explicit_operator_authorization"] is True
    assert controls["fresh_exact_unexpired_acceptance_required_for_phase6"] is True
    assert proposal["status"] == "proposed_internal_only"
    assert proposal["apply_authorized"] is False


def test_native_workflow_requires_explicit_manual_authorization() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "aigc_constellation_trigger.yml"
    ).read_text(encoding="utf-8")

    assert "issue_comment:" not in workflow
    assert "operator_authorization:" in workflow
    assert "AUTHORIZE AIGC NATIVE WORKFLOW RUN" in workflow
    assert (
        "github.event.inputs.operator_authorization == "
        "'AUTHORIZE AIGC NATIVE WORKFLOW RUN'"
    ) in workflow
