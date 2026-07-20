from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

import src.core.cloud_advancement_loop as cloud_loop
from src.core.cloud_advancement_loop import (
    CloudAdvancementError,
    CloudAdvancementStore,
    action_semantic_fingerprint,
    execute_next,
    load_program,
    observe_github_actions_gate,
    validate_execution_receipt,
    validate_program,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def clone(value: object) -> Any:
    return json.loads(json.dumps(value))


@pytest.fixture(scope="module")
def program() -> dict[str, Any]:
    return load_program(PROJECT_ROOT)


def fake_github_runner(
    *,
    issue_state: str,
    run_conclusion: str,
    steps: list[dict[str, Any]],
    required_head: str,
):
    def run(command: Sequence[str], cwd: Path) -> Mapping[str, Any]:
        assert command[0] == "gh"
        assert cwd.is_absolute()
        if command[1:3] == ["issue", "view"]:
            return {
                "number": 124,
                "state": issue_state,
                "url": "https://github.com/Lornt1666/AIGC/issues/124",
                "updatedAt": "2026-07-20T12:00:00Z",
            }
        if command[1:3] == ["pr", "view"]:
            return {
                "headRefOid": required_head,
                "url": "https://github.com/Lornt1666/AIGC/pull/123",
                "statusCheckRollup": [
                    {
                        "name": "validate",
                        "workflowName": "AIGC CI",
                        "completedAt": "2026-07-20T12:00:00Z",
                        "startedAt": "2026-07-20T11:59:00Z",
                        "detailsUrl": (
                            "https://github.com/Lornt1666/AIGC/"
                            "actions/runs/100/job/200"
                        ),
                    }
                ],
            }
        if command[1:3] == ["run", "view"]:
            return {
                "databaseId": 100,
                "status": "completed",
                "conclusion": run_conclusion,
                "headSha": required_head,
                "workflowName": "AIGC CI",
                "url": (
                    "https://github.com/Lornt1666/AIGC/actions/runs/100"
                ),
                "updatedAt": "2026-07-20T12:00:00Z",
                "jobs": [
                    {
                        "name": "validate",
                        "status": "completed",
                        "conclusion": run_conclusion,
                        "url": (
                            "https://github.com/Lornt1666/AIGC/"
                            "actions/runs/100/job/200"
                        ),
                        "steps": steps,
                    }
                ],
            }
        raise AssertionError(f"Unexpected command: {command}")

    return run


def make_store(
    tmp_path: Path,
    program: Mapping[str, Any],
) -> CloudAdvancementStore:
    return CloudAdvancementStore(tmp_path, program)


def test_program_is_strict_unique_and_dependency_ordered(
    program: dict[str, Any],
) -> None:
    validate_program(program)
    actions = program["actions"]

    assert len(actions) == 12
    assert [item["stage"] for item in actions] == list(range(1, 13))
    assert len(
        {action_semantic_fingerprint(item) for item in actions}
    ) == len(actions)
    assert program["schedule"]["max_actions_per_run"] == 1
    assert (
        program["selection_policy"][
            "completed_action_reselection_allowed"
        ]
        is False
    )
    assert program["safety"]["git_push_allowed_by_loop"] is False
    assert program["safety"]["terraform_apply_allowed"] is False
    assert program["safety"]["provider_resource_mutation_allowed"] is False
    assert actions[-1]["phase5_required"] is True


def test_initial_execution_receipt_is_strict_and_digest_bound() -> None:
    receipt = validate_execution_receipt(
        PROJECT_ROOT,
        Path(
            "reports/artifacts/cloud_advancement/"
            "initial_execution_receipt.json"
        ),
    )

    assert receipt["executed_actions"][0]["state"] == "completed"
    assert receipt["executed_actions"][1]["state"] == "blocked"
    assert receipt["hosted_ci_observation"]["executed_step_count"] == 0
    assert receipt["governance"]["external_action_performed"] is False


def test_program_rejects_semantic_duplicates_cycles_and_weakened_safety(
    program: dict[str, Any],
) -> None:
    duplicate = clone(program)
    copied = clone(duplicate["actions"][10])
    copied["action_id"] = "CLD-013"
    copied["stage"] = 13
    copied["priority"] = 70
    duplicate["actions"].append(copied)
    with pytest.raises(CloudAdvancementError, match="Semantically duplicate"):
        validate_program(duplicate)

    cycle = clone(program)
    cycle["actions"][0]["dependencies"] = ["CLD-002"]
    with pytest.raises(
        CloudAdvancementError,
        match="non-earlier|cycle",
    ):
        validate_program(cycle)

    weakened = clone(program)
    weakened["safety"]["terraform_apply_allowed"] = True
    with pytest.raises(CloudAdvancementError, match="weakened"):
        validate_program(weakened)


def test_first_action_executes_once_and_history_is_append_only(
    tmp_path: Path,
    program: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program)
    result = execute_next(
        tmp_path,
        program,
        store,
        actor="pytest",
        now=T0,
    )

    assert result["status"] == "completed"
    assert result["action_id"] == "CLD-001"
    assert result["external_action_performed"] is False
    assert len(store.events()) == 2
    status = store.status(now=T0)
    assert status["completed_action_ids"] == ["CLD-001"]
    assert status["duplicate_prevention"]["completed_actions_reselected"] is False
    assert (
        status["duplicate_prevention"]["program_bound_hash_chain_valid"]
        is True
    )
    assert len(status["history_head_sha256"]) == 64

    with sqlite3.connect(store.state_path) as connection:
        with pytest.raises(
            sqlite3.DatabaseError,
            match="append-only",
        ):
            connection.execute(
                "UPDATE cloud_action_events SET actor = 'tampered'"
            )
        with pytest.raises(
            sqlite3.DatabaseError,
            match="append-only",
        ):
            connection.execute("DELETE FROM cloud_action_events")


def test_hash_chain_detects_raw_database_tampering(
    tmp_path: Path,
    program: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program)
    execute_next(tmp_path, program, store, actor="pytest", now=T0)

    with sqlite3.connect(store.state_path) as connection:
        connection.execute("DROP TRIGGER cloud_events_no_update")
        connection.execute(
            """
            UPDATE cloud_action_events
            SET evidence_json = '{"tampered":true}'
            WHERE sequence = 1
            """
        )
        connection.commit()

    with pytest.raises(CloudAdvancementError, match="event hash is invalid"):
        store.status(now=T0 + timedelta(minutes=1))


def test_history_is_bound_to_the_exact_program(
    tmp_path: Path,
    program: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program)
    execute_next(tmp_path, program, store, actor="pytest", now=T0)
    changed_program = clone(program)
    changed_program["actions"][0]["title"] = "Changed baseline title"
    changed_store = CloudAdvancementStore(
        tmp_path,
        changed_program,
        state_path=store.state_path,
    )

    with pytest.raises(CloudAdvancementError, match="different program"):
        changed_store.status(now=T0 + timedelta(minutes=1))


def test_hosted_ci_observation_blocks_then_retries_only_after_cooldown(
    tmp_path: Path,
    program: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program)
    execute_next(tmp_path, program, store, actor="pytest", now=T0)
    required_head = program["hosted_ci_gate"]["required_head_sha"]

    blocked = execute_next(
        tmp_path,
        program,
        store,
        actor="pytest",
        command_runner=fake_github_runner(
            issue_state="OPEN",
            run_conclusion="failure",
            steps=[],
            required_head=required_head,
        ),
        now=T0 + timedelta(minutes=1),
    )
    assert blocked["status"] == "blocked"
    assert blocked["action_id"] == "CLD-002"
    assert "issue_closed" in blocked["observation"]["failed_checks"]
    assert "job_has_executed_steps" in blocked["observation"]["failed_checks"]
    assert blocked["observation"]["external_action_performed"] is False

    too_soon = execute_next(
        tmp_path,
        program,
        store,
        actor="pytest",
        command_runner=fake_github_runner(
            issue_state="CLOSED",
            run_conclusion="success",
            steps=[{"name": "checkout", "conclusion": "success"}],
            required_head=required_head,
        ),
        now=T0 + timedelta(hours=23),
    )
    assert too_soon["status"] == "no_eligible_action"

    recovered = execute_next(
        tmp_path,
        program,
        store,
        actor="pytest",
        command_runner=fake_github_runner(
            issue_state="CLOSED",
            run_conclusion="success",
            steps=[{"name": "checkout", "conclusion": "success"}],
            required_head=required_head,
        ),
        now=T0 + timedelta(hours=25),
    )
    assert recovered["status"] == "completed"
    assert recovered["action_id"] == "CLD-002"
    assert recovered["observation"]["gate_passed"] is True
    claims = [
        item
        for item in store.events()
        if item["action_id"] == "CLD-002"
        and item["event_type"] == "claimed"
    ]
    assert [item["attempt"] for item in claims] == [1, 2]
    assert claims[1]["necessity_reason"]


def test_completed_actions_can_never_be_retried(
    tmp_path: Path,
    program: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program)
    execute_next(tmp_path, program, store, actor="pytest", now=T0)

    with pytest.raises(CloudAdvancementError, match="never be retried"):
        store.retry_action(
            "CLD-001",
            actor="pytest",
            necessity_reason=(
                "This should still be rejected because completion is final."
            ),
            now=T0 + timedelta(hours=1),
        )


def test_expired_claim_requires_explicit_recorded_necessity(
    tmp_path: Path,
    program: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program)
    first = store.claim_next(actor="pytest", now=T0)
    assert first["action"]["action_id"] == "CLD-001"

    expired = store.claim_next(
        actor="pytest",
        now=T0 + timedelta(minutes=121),
    )
    assert expired["status"] == "no_eligible_action"
    assert first["run_id"] in expired["expired_claims"]

    with pytest.raises(CloudAdvancementError, match="substantive necessity"):
        store.retry_action(
            "CLD-001",
            actor="pytest",
            necessity_reason="retry",
            now=T0 + timedelta(minutes=122),
        )

    retried = store.retry_action(
        "CLD-001",
        actor="pytest",
        necessity_reason=(
            "The prior claim lease expired before work could complete; "
            "re-establishing the baseline is operationally necessary."
        ),
        now=T0 + timedelta(minutes=122),
    )
    assert retried["attempt"] == 2
    assert retried["selection_reason"] == "explicit_recorded_necessity"
    assert retried["necessity_reason"]


def test_only_one_action_claim_can_be_active(
    tmp_path: Path,
    program: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program)
    first = store.claim_next(actor="pytest", now=T0)
    second = store.claim_next(
        actor="pytest-2",
        now=T0 + timedelta(minutes=1),
    )

    assert first["status"] == "claimed"
    assert second["status"] == "active_claim_exists"
    assert second["active_run"]["run_id"] == first["run_id"]


def test_internal_action_requires_clean_worktree_and_manual_claim(
    tmp_path: Path,
    program: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = make_store(tmp_path, program)
    required_head = program["hosted_ci_gate"]["required_head_sha"]
    execute_next(tmp_path, program, store, actor="pytest", now=T0)
    execute_next(
        tmp_path,
        program,
        store,
        actor="pytest",
        command_runner=fake_github_runner(
            issue_state="CLOSED",
            run_conclusion="success",
            steps=[{"name": "checkout", "conclusion": "success"}],
            required_head=required_head,
        ),
        now=T0 + timedelta(minutes=1),
    )

    blocked_dirty = store.claim_next(
        actor="pytest",
        now=T0 + timedelta(minutes=2),
    )
    assert blocked_dirty["status"] == "no_eligible_action"
    assert any(
        item["action_id"] == "CLD-003"
        and item["reason"] == "clean_worktree_required"
        for item in blocked_dirty["blocked_reasons"]
    )

    monkeypatch.setattr(
        cloud_loop,
        "repository_revision_state",
        lambda root: ("a" * 40, "clean"),
    )
    claimed = store.claim_next(
        actor="pytest",
        now=T0 + timedelta(minutes=3),
    )
    assert claimed["action"]["action_id"] == "CLD-003"
    assert claimed["action"]["execution_class"] == "agent_internal"


def test_secret_fields_and_secret_like_values_are_rejected_from_evidence(
    tmp_path: Path,
    program: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program)
    claimed = store.claim_next(actor="pytest", now=T0)

    with pytest.raises(CloudAdvancementError, match="Sensitive field"):
        store.complete(
            claimed["run_id"],
            actor="pytest",
            evidence={"token": "test_only_value"},
            now=T0 + timedelta(minutes=1),
        )
    with pytest.raises(CloudAdvancementError, match="Secret-like value"):
        store.complete(
            claimed["run_id"],
            actor="pytest",
            evidence={"result": "sk-" + "A" * 24},
            now=T0 + timedelta(minutes=1),
        )


def test_phase5_action_is_never_locally_eligible(
    tmp_path: Path,
    program: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program)
    status = store.status(now=T0)
    deployment = next(
        item
        for item in status["action_results"]
        if item["action_id"] == "CLD-012"
    )

    assert deployment["eligible"] is False
    assert (
        deployment["eligibility_reason"]
        == "phase5_external_action_requires_separate_authority"
    )
    assert status["governance"]["phase5_approval_present"] is False
    assert status["governance"]["external_action_performed"] is False


def test_observer_requires_exact_head_success_and_real_steps(
    tmp_path: Path,
    program: dict[str, Any],
) -> None:
    required_head = program["hosted_ci_gate"]["required_head_sha"]
    observation = observe_github_actions_gate(
        tmp_path,
        program,
        command_runner=fake_github_runner(
            issue_state="CLOSED",
            run_conclusion="success",
            steps=[{"name": "tests", "conclusion": "success"}],
            required_head=required_head,
        ),
    )

    assert observation["gate_passed"] is True
    assert observation["executed_step_count"] == 1
    assert observation["failed_checks"] == []


def test_cli_exposes_status_execution_and_necessity_retry() -> None:
    from scripts.cloud_advancement_loop import parse_args

    status = parse_args(["status", "--markdown"])
    execute = parse_args(["execute-next", "--actor", "scheduled-codex"])
    retry = parse_args(
        [
            "retry-action",
            "--action-id",
            "CLD-003",
            "--actor",
            "operator",
            "--necessity-reason",
            "A changed blocker makes this retry necessary and bounded.",
        ]
    )

    assert status.command == "status"
    assert status.markdown is True
    assert execute.command == "execute-next"
    assert retry.command == "retry-action"
    assert retry.action_id == "CLD-003"
