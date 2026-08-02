import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.mission_os.activation import build_activation_projection
from src.mission_os.api import create_mission_app
from src.mission_os.decisions import read_operator_decisions, record_operator_decision


def _fixture(root: Path, *, bound: bool = True) -> None:
    (root / "config").mkdir(parents=True)
    (root / "data/phase2_processed").mkdir(parents=True)
    (root / "data/phase3_processed").mkdir(parents=True)
    (root / "config/mission_os_offer_catalog.json").write_text(json.dumps({
        "offers": [{
            "offer_id": "offer-test",
            "name": "Test Blueprint",
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
    record = {
        "dossier_id": "d1",
        "opportunity_id": "opp-1",
        "title": "Automation blueprint",
        "employer": "Example" if bound else "Unknown",
        "source_url": "https://example.invalid/apply" if bound else None,
        "radar_score": 90,
        "discovered_taxonomy": ["automation"],
    }
    (root / "data/phase3_processed/aigc_phase3_assessment_dossiers.json").write_text(json.dumps([record]), encoding="utf-8")


def _proposal(root: Path) -> dict:
    return build_activation_projection(root)["internal_proposal_packets"][0]


def _request(proposal: dict, decision: str, **extra) -> dict:
    payload = {
        "decision": decision,
        "proposal_id": proposal["proposal_id"],
        "exact_revision": proposal["exact_revision"],
        "operator_id": "ACCOUNTABLE_OPERATOR",
        "rationale": "Reviewed against scope, evidence, and authority boundaries.",
    }
    payload.update(extra)
    return payload


def _local_credential() -> str:
    return "".join(("test", "-", "credential"))


def test_authorization_records_receipt_but_does_not_execute(tmp_path: Path) -> None:
    _fixture(tmp_path)
    proposal = _proposal(tmp_path)
    ledger = tmp_path / ".runtime" / "decisions.jsonl"
    credential = _local_credential()
    event = record_operator_decision(
        tmp_path,
        _request(proposal, "AUTHORIZE_EXACT_PROPOSAL"),
        operator_credential=credential,
        expected_credential=credential,
        ledger_path=ledger,
    )
    assert event["decision_status"] == "AUTHORIZED_NOT_EXECUTED"
    assert event["external_action_authorized"] is True
    assert event["external_action_performed"] is False
    assert event["canonical_state_mutated"] is False
    assert event["previous_receipt_sha256"] is None
    projection = read_operator_decisions(tmp_path, ledger_path=ledger)
    assert projection["integrity_status"] == "VERIFIED"
    assert len(projection["records"]) == 1


def test_reject_and_revision_request_are_hash_chained(tmp_path: Path) -> None:
    _fixture(tmp_path)
    proposal = _proposal(tmp_path)
    ledger = tmp_path / ".runtime" / "decisions.jsonl"
    credential = _local_credential()
    reject = record_operator_decision(
        tmp_path,
        _request(proposal, "REJECT"),
        operator_credential=credential,
        expected_credential=credential,
        ledger_path=ledger,
    )
    revise = record_operator_decision(
        tmp_path,
        _request(proposal, "REQUEST_REVISION", requested_changes=["Clarify acceptance criteria"]),
        operator_credential=credential,
        expected_credential=credential,
        ledger_path=ledger,
    )
    projection = read_operator_decisions(tmp_path, ledger_path=ledger)
    records = projection["records"]
    assert reject["decision_status"] == "REJECTED"
    assert revise["decision_status"] == "REVISION_REQUESTED"
    assert revise["previous_receipt_sha256"] == reject["decision_receipt_sha256"]
    assert projection["integrity_status"] == "VERIFIED"
    assert len(records) == 2
    assert all(item["external_action_performed"] is False for item in records)


def test_tampered_ledger_fails_closed_and_blocks_append(tmp_path: Path) -> None:
    _fixture(tmp_path)
    proposal = _proposal(tmp_path)
    ledger = tmp_path / ".runtime" / "decisions.jsonl"
    credential = _local_credential()
    record_operator_decision(
        tmp_path,
        _request(proposal, "REJECT"),
        operator_credential=credential,
        expected_credential=credential,
        ledger_path=ledger,
    )
    tampered = json.loads(ledger.read_text(encoding="utf-8"))
    tampered["rationale"] = "Altered after recording."
    ledger.write_text(json.dumps(tampered) + "\n", encoding="utf-8")

    projection = read_operator_decisions(tmp_path, ledger_path=ledger)
    assert projection["integrity_status"] == "INTEGRITY_FAILURE"
    assert projection["invalid_lines"] == 1
    assert projection["records"] == []
    try:
        record_operator_decision(
            tmp_path,
            _request(proposal, "REJECT"),
            operator_credential=credential,
            expected_credential=credential,
            ledger_path=ledger,
        )
        raise AssertionError("append should fail when ledger integrity is broken")
    except ValueError as exc:
        assert "integrity" in str(exc)


def test_stale_revision_and_missing_credential_fail_closed(tmp_path: Path) -> None:
    _fixture(tmp_path)
    proposal = _proposal(tmp_path)
    credential = _local_credential()
    payload = _request(proposal, "AUTHORIZE_EXACT_PROPOSAL")
    payload["exact_revision"] = "0" * 64
    try:
        record_operator_decision(tmp_path, payload, operator_credential=credential, expected_credential=credential)
        raise AssertionError("stale revision should fail")
    except ValueError as exc:
        assert "stale" in str(exc)
    try:
        record_operator_decision(tmp_path, _request(proposal, "REJECT"), operator_credential=None, expected_credential=credential)
        raise AssertionError("missing credential should fail")
    except PermissionError:
        pass


def test_incomplete_binding_cannot_be_authorized(tmp_path: Path) -> None:
    _fixture(tmp_path, bound=False)
    proposal = _proposal(tmp_path)
    credential = _local_credential()
    try:
        record_operator_decision(
            tmp_path,
            _request(proposal, "AUTHORIZE_EXACT_PROPOSAL"),
            operator_credential=credential,
            expected_credential=credential,
        )
        raise AssertionError("incomplete binding should fail")
    except ValueError as exc:
        assert "binding is incomplete" in str(exc)


def test_api_requires_credential_for_reads_and_writes_and_has_no_execution_route(tmp_path: Path) -> None:
    _fixture(tmp_path)
    proposal = _proposal(tmp_path)
    ledger = tmp_path / ".runtime" / "decisions.jsonl"
    credential = _local_credential()
    app = create_mission_app(
        tmp_path,
        tmp_path / "config/missing-mission.json",
        tmp_path / "missing.sqlite3",
        decision_ledger_path=ledger,
        operator_credential=credential,
    )
    client = TestClient(app)
    payload = _request(proposal, "REJECT")
    assert client.get("/api/v1/operator/decisions").status_code == 401
    assert client.post("/api/v1/operator/decisions", json=payload).status_code == 401
    response = client.post("/api/v1/operator/decisions", json=payload, headers={"X-Operator-Token": credential})
    assert response.status_code == 201
    assert response.json()["external_action_performed"] is False
    read_response = client.get("/api/v1/operator/decisions", headers={"X-Operator-Token": credential})
    assert read_response.status_code == 200
    assert read_response.json()["integrity_status"] == "VERIFIED"
    paths = {route.path for route in app.routes}
    assert "/api/v1/operator/execute" not in paths
    assert "/api/v1/revenue/submit" not in paths
