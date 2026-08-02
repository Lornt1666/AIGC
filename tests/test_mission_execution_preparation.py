import json
from pathlib import Path

from src.mission_os.execution import (
    approve_execution_packet,
    build_execution_preparation_projection,
    compile_execution_packet,
    run_preflight,
)


def _credential() -> str:
    return "".join(("local", "-", "credential"))


def _write_fixture(root: Path) -> tuple[Path, str]:
    (root / "config").mkdir(parents=True)
    (root / "data/phase2_processed").mkdir(parents=True)
    (root / "data/phase3_processed").mkdir(parents=True)
    (root / "config/mission_os_offer_catalog.json").write_text(json.dumps({
        "offers": [{
            "offer_id": "offer-test",
            "name": "Governed Blueprint",
            "status": "INTERNAL_DRAFT_ONLY",
            "deliverables": ["Blueprint"],
            "exclusions": ["Deployment"],
            "acceptance_criteria": ["Reviewed"],
            "fit_taxonomy": ["automation"],
            "tiers": [{"tier_id": "standard", "price": 500, "delivery_business_days": 3, "operator_minutes_estimate": 120}],
            "external_action_authorized": False,
        }],
        "external_action_authorized": False,
    }), encoding="utf-8")
    (root / "data/phase2_processed/aigc_phase2_opportunity_queue.json").write_text("", encoding="utf-8")
    (root / "data/phase3_processed/aigc_phase3_assessment_dossiers.json").write_text(json.dumps([{
        "dossier_id": "d1",
        "opportunity_id": "opp-1",
        "title": "Automation blueprint",
        "employer": "Example Client",
        "source_url": "https://example.invalid/apply",
        "radar_score": 90,
        "discovered_taxonomy": ["automation"],
    }]), encoding="utf-8")

    from src.mission_os.activation import build_activation_projection
    proposal = build_activation_projection(root)["internal_proposal_packets"][0]
    decision_ledger = root / ".runtime" / "operator_decisions.jsonl"
    event_body = {
        "schema_version": "1.0.0",
        "decision": "AUTHORIZE_EXACT_PROPOSAL",
        "decision_status": "AUTHORIZED_NOT_EXECUTED",
        "proposal_id": proposal["proposal_id"],
        "exact_revision": proposal["exact_revision"],
        "operator_id": "ACCOUNTABLE_OPERATOR",
        "rationale": "Approved for preparation only.",
        "requested_changes": [],
        "counterparty": proposal["counterparty"],
        "submission_channel": proposal["submission_channel"],
        "binding_complete": True,
        "decided_at": "2026-08-02T00:00:00Z",
        "external_action_authorized": True,
        "external_action_performed": False,
        "canonical_state_mutated": False,
        "previous_receipt_sha256": None,
    }
    from hashlib import sha256
    payload = json.dumps(event_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    event = dict(event_body)
    event["decision_receipt_sha256"] = sha256(payload.encode("utf-8")).hexdigest()
    decision_ledger.parent.mkdir(parents=True)
    decision_ledger.write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
    return decision_ledger, proposal["proposal_id"]


def test_compile_packet_ends_prepared_not_executed(tmp_path: Path) -> None:
    decisions, proposal_id = _write_fixture(tmp_path)
    packet = compile_execution_packet(
        tmp_path,
        proposal_id,
        decision_ledger_path=decisions,
        packet_ledger_path=tmp_path / ".runtime/packets.jsonl",
    )
    assert packet["packet_status"] == "PREPARED_NOT_EXECUTED"
    assert packet["dry_run"]["external_call_performed"] is False
    assert packet["external_action_performed"] is False
    assert packet["canonical_state_mutated"] is False


def test_second_stage_approval_is_one_time_and_nonexecuting(tmp_path: Path) -> None:
    decisions, proposal_id = _write_fixture(tmp_path)
    packets = tmp_path / ".runtime/packets.jsonl"
    approvals = tmp_path / ".runtime/approvals.jsonl"
    packet = compile_execution_packet(tmp_path, proposal_id, decision_ledger_path=decisions, packet_ledger_path=packets)
    credential = _credential()
    request = {
        "packet_digest_sha256": packet["packet_digest_sha256"],
        "operator_id": "ACCOUNTABLE_OPERATOR",
        "rationale": "Reviewed exact destination and dry-run output.",
    }
    approval = approve_execution_packet(
        tmp_path,
        request,
        operator_credential=credential,
        expected_credential=credential,
        packet_ledger_path=packets,
        approval_ledger_path=approvals,
    )
    assert approval["approval_status"] == "PREPARED_NOT_EXECUTED"
    assert approval["external_action_authorized"] is False
    assert approval["external_action_performed"] is False
    try:
        approve_execution_packet(
            tmp_path,
            request,
            operator_credential=credential,
            expected_credential=credential,
            packet_ledger_path=packets,
            approval_ledger_path=approvals,
        )
        raise AssertionError("replay should fail")
    except ValueError as exc:
        assert "already" in str(exc)


def test_preflight_fails_closed() -> None:
    result = run_preflight({}, {})
    assert result["status"] == "BLOCKED"
    assert result["blockers"]


def test_projection_never_claims_execution(tmp_path: Path) -> None:
    projection = build_execution_preparation_projection(tmp_path)
    assert projection["terminal_state"] == "PREPARED_NOT_EXECUTED"
    assert projection["external_action_authorized"] is False
    assert projection["external_action_performed"] is False
    assert projection["canonical_state_mutated"] is False
