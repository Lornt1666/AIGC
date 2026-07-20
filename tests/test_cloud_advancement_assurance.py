from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from typing import Any, Mapping

import pytest

import src.core.cloud_advancement_assurance as assurance_module
from src.core.cloud_advancement_assurance import (
    CloudAdvancementAssuranceStore,
    evaluate_quantitative_metric,
    load_assurance_config,
    nearest_rank,
    validate_assurance_config,
    validate_verification_receipt,
    validate_verification_receipt_payload,
)
from src.core.cloud_advancement_loop import (
    CloudAdvancementError,
    action_semantic_fingerprint,
    canonical_digest,
    canonical_json,
    load_program,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
SOURCE_BYTES = b'{"evidence":"bounded-test-fixture"}\n'
SOURCE_DIGEST = hashlib.sha256(SOURCE_BYTES).hexdigest()


def clone(value: object) -> Any:
    return json.loads(json.dumps(value))


@pytest.fixture(scope="module")
def program() -> dict[str, Any]:
    return load_program(PROJECT_ROOT)


@pytest.fixture(scope="module")
def assurance() -> dict[str, Any]:
    return load_assurance_config(PROJECT_ROOT)


def make_store(
    tmp_path: Path,
    program: Mapping[str, Any],
    assurance: Mapping[str, Any],
    *,
    clock=None,
) -> CloudAdvancementAssuranceStore:
    source = tmp_path / "evidence" / "source.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(SOURCE_BYTES)
    program_path = tmp_path / "config" / "cloud_advancement_loop.json"
    program_path.parent.mkdir(parents=True, exist_ok=True)
    program_path.write_text(
        json.dumps(program, indent=2) + "\n",
        encoding="utf-8",
    )
    receipt_path = (
        tmp_path
        / "reports"
        / "artifacts"
        / "cloud_advancement"
        / "initial_execution_receipt.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        PROJECT_ROOT
        / "reports"
        / "artifacts"
        / "cloud_advancement"
        / "initial_execution_receipt.json",
        receipt_path,
    )
    execution_schema = (
        tmp_path
        / "schemas"
        / "cloud_advancement_execution_receipt.schema.json"
    )
    execution_schema.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        PROJECT_ROOT
        / "schemas"
        / "cloud_advancement_execution_receipt.schema.json",
        execution_schema,
    )
    kwargs = {"clock": clock} if clock else {}
    return CloudAdvancementAssuranceStore(
        tmp_path,
        program,
        assurance,
        **kwargs,
    )


def blocker_fact(value: str = "open_zero_step_ci") -> dict[str, Any]:
    return {
        "fact_type": "blocker",
        "subject_ref": "github.issue.124",
        "value": value,
        "reason_codes": ["hosted_ci_zero_steps"],
        "tags": ["ci", "cloud"],
    }


def remember(
    store: CloudAdvancementAssuranceStore,
    *,
    key: str = "cloud.current-blocker",
    value: Mapping[str, Any] | None = None,
    idempotency_key: str = "memory-operation-0001",
    confidence: str = "1",
    salience: str = "1",
    ttl_hours: int = 24,
    now: datetime = T0,
) -> dict[str, Any]:
    return store.remember(
        key=key,
        value=dict(value or blocker_fact()),
        scope="program",
        actor="pytest",
        source_refs=["evidence/source.json"],
        source_sha256=[SOURCE_DIGEST],
        idempotency_key=idempotency_key,
        derivation_type="direct_observation",
        confidence=confidence,
        salience=salience,
        ttl_hours=ttl_hours,
        now=now,
    )


def measure(
    store: CloudAdvancementAssuranceStore,
    *,
    metric_id: str = "cloud.action_catalog_count",
    idempotency_key: str = "metric-operation-0001",
    now: datetime = T0,
) -> dict[str, Any]:
    return store.record_metric(
        metric_id=metric_id,
        idempotency_key=idempotency_key,
        actor="pytest",
        now=now,
    )


def measure_required(
    store: CloudAdvancementAssuranceStore,
    *,
    now: datetime = T0,
) -> list[dict[str, Any]]:
    return [
        measure(store, now=now),
        measure(
            store,
            metric_id="cloud.completed_unique_action_count",
            idempotency_key="metric-operation-0002",
            now=now,
        ),
    ]


def prepare_verification_root(
    tmp_path: Path,
    assurance: Mapping[str, Any],
) -> Path:
    for relative in assurance["verification"]["required_artifacts"]:
        source = PROJECT_ROOT / str(relative)
        target = tmp_path / str(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return tmp_path


def test_assurance_policy_is_strict_and_preserves_program_digest(
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    validate_assurance_config(assurance)
    assert canonical_digest(program) == (
        "8a2adf6bb6bd995a92f914b6d76c41946c8ae86bd7555749"
        "b13a1f5b5e5ee07c"
    )
    assert assurance["working_memory"]["max_active_entries"] == 32
    assert assurance["performance"]["sample_count"] == 100
    assert assurance["verification"]["trusted_loop_receipt_sha256"] == (
        hashlib.sha256(
            (
                PROJECT_ROOT
                / "reports"
                / "artifacts"
                / "cloud_advancement"
                / "initial_execution_receipt.json"
            ).read_bytes()
        ).hexdigest()
    )
    assert assurance["governance"]["external_action_performed"] is False
    weak_confidence = clone(assurance)
    weak_confidence["quantitative_accuracy"]["metric_definitions"][0][
        "confidence"
    ] = "0.5"
    with pytest.raises(CloudAdvancementError, match="below.*minimum"):
        validate_assurance_config(weak_confidence)
    variable_sampling = clone(assurance)
    variable_sampling["performance"]["sample_count"] = 50
    with pytest.raises(CloudAdvancementError, match="100 measured"):
        validate_assurance_config(variable_sampling)
    impossible_exact_sampling = clone(assurance)
    impossible_exact_sampling["quantitative_accuracy"][
        "minimum_sample_size"
    ] = 2
    with pytest.raises(CloudAdvancementError, match="sample size 1"):
        validate_assurance_config(impossible_exact_sampling)


def test_decimal_math_and_tolerance_boundaries_are_exact(
    assurance: dict[str, Any],
) -> None:
    exact = evaluate_quantitative_metric(
        assurance,
        metric_id="test.decimal_exactness",
        actual="0.3",
        expected="0.3",
        unit="ratio_0_1",
        absolute_tolerance="0",
        relative_tolerance="0",
        sample_size=1,
        confidence="1",
        source_refs=["evidence/decimal.json"],
        source_sha256=[SOURCE_DIGEST],
        measurement_mode="exact",
        observed_at=T0,
    )
    boundary = evaluate_quantitative_metric(
        assurance,
        metric_id="test.tolerance_boundary",
        actual="105",
        expected="100",
        unit="millisecond",
        absolute_tolerance="0",
        relative_tolerance="0.05",
        sample_size=1,
        confidence="1",
        source_refs=["evidence/boundary.json"],
        source_sha256=[SOURCE_DIGEST],
        measurement_mode="exact",
        observed_at=T0,
    )
    outside = evaluate_quantitative_metric(
        assurance,
        metric_id="test.tolerance_outside",
        actual="105.000000001",
        expected="100",
        unit="millisecond",
        absolute_tolerance="0",
        relative_tolerance="0.05",
        sample_size=1,
        confidence="1",
        source_refs=["evidence/outside.json"],
        source_sha256=[SOURCE_DIGEST],
        measurement_mode="exact",
        observed_at=T0,
    )

    assert exact["absolute_error"] == "0"
    assert exact["accuracy_score"] == "1"
    assert boundary["passed"] is True
    assert outside["passed"] is False


@pytest.mark.parametrize("invalid", [0.1, "1e-3", "NaN", "Infinity", "+1"])
def test_non_plain_decimal_inputs_fail_closed(
    assurance: dict[str, Any],
    invalid: Any,
) -> None:
    with pytest.raises(CloudAdvancementError, match="decimal"):
        evaluate_quantitative_metric(
            assurance,
            metric_id="test.invalid_number",
            actual=invalid,
            expected="1",
            unit="count",
            absolute_tolerance="0",
            relative_tolerance="0",
            sample_size=1,
            confidence="1",
            source_refs=["evidence/invalid.json"],
            source_sha256=[SOURCE_DIGEST],
            measurement_mode="exact",
            observed_at=T0,
        )


def test_unit_sample_confidence_and_source_digest_rules(
    assurance: dict[str, Any],
) -> None:
    base = {
        "assurance": assurance,
        "metric_id": "test.contract",
        "actual": "1",
        "expected": "1",
        "unit": "count",
        "absolute_tolerance": "0",
        "relative_tolerance": "0",
        "sample_size": 1,
        "confidence": "1",
        "source_refs": ["evidence/test.json"],
        "source_sha256": [SOURCE_DIGEST],
        "measurement_mode": "exact",
        "observed_at": T0,
    }
    for override, message in [
        ({"unit": "widgets"}, "unit"),
        ({"sample_size": 2}, "sample size"),
        ({"confidence": "0.94"}, "confidence"),
        ({"source_sha256": []}, "paired source"),
    ]:
        with pytest.raises(CloudAdvancementError, match=message):
            evaluate_quantitative_metric(**{**base, **override})


@pytest.mark.parametrize(
    ("unit", "actual", "expected"),
    [
        ("ratio_0_1", "2", "2"),
        ("percent_0_100", "150", "150"),
        ("action", "-1", "-1"),
        ("count", "1.5", "1.5"),
    ],
)
def test_unit_domains_reject_impossible_values(
    assurance: dict[str, Any],
    unit: str,
    actual: str,
    expected: str,
) -> None:
    with pytest.raises(CloudAdvancementError, match="Metric|metrics|unit"):
        evaluate_quantitative_metric(
            assurance,
            metric_id="test.unit_domain",
            actual=actual,
            expected=expected,
            unit=unit,
            absolute_tolerance="0",
            relative_tolerance="0",
            sample_size=1,
            confidence="1",
            source_refs=["evidence/unit.json"],
            source_sha256=[SOURCE_DIGEST],
            measurement_mode="exact",
            observed_at=T0,
        )


def test_decimal_precision_contract_rejects_unrepresentable_inputs(
    assurance: dict[str, Any],
) -> None:
    with pytest.raises(CloudAdvancementError, match="significant-digit"):
        evaluate_quantitative_metric(
            assurance,
            metric_id="test.too_many_digits",
            actual="9" * 25,
            expected="9" * 25,
            unit="count",
            absolute_tolerance="0",
            relative_tolerance="0",
            sample_size=1,
            confidence="1",
            source_refs=["evidence/precision.json"],
            source_sha256=[SOURCE_DIGEST],
            measurement_mode="exact",
            observed_at=T0,
        )


def test_memory_is_idempotent_superseded_and_never_revives(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    first = remember(store, ttl_hours=1)
    replay = remember(store, ttl_hours=1, now=T0 + timedelta(minutes=1))
    replacement = remember(
        store,
        value=blocker_fact("awaiting_hosted_runner_recovery"),
        idempotency_key="memory-operation-0002",
        ttl_hours=1,
        now=T0 + timedelta(minutes=30),
    )

    assert replay["event_id"] == first["event_id"]
    assert replay["idempotent_replay"] is True
    assert replacement["supersedes_event_id"] == first["event_id"]
    active = store.recall(
        scope="program",
        now=T0 + timedelta(minutes=75),
    )
    expired = store.recall(
        scope="program",
        now=T0 + timedelta(minutes=90),
    )
    assert [item["value"]["value"] for item in active] == [
        "awaiting_hosted_runner_recovery"
    ]
    assert expired == []
    assert store.memory_summary(T0 + timedelta(minutes=90))[
        "expired_entry_count"
    ] == 1


@pytest.mark.parametrize("ttl_hours", [True, "1", 1.9])
def test_memory_ttl_requires_an_exact_integer(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
    ttl_hours: object,
) -> None:
    store = make_store(tmp_path, program, assurance)
    with pytest.raises(CloudAdvancementError, match="TTL must be an integer"):
        store.remember(
            key="cloud.current-blocker",
            value=blocker_fact(),
            scope="program",
            actor="pytest",
            source_refs=["evidence/source.json"],
            source_sha256=[SOURCE_DIGEST],
            idempotency_key="memory-invalid-ttl-0001",
            derivation_type="direct_observation",
            ttl_hours=ttl_hours,  # type: ignore[arg-type]
            now=T0,
        )
    assert store.memory_summary(T0)["memory_event_count"] == 0


def test_historical_recall_does_not_leak_a_future_replacement(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    remember(store, ttl_hours=2)
    remember(
        store,
        value=blocker_fact("replacement_state"),
        idempotency_key="memory-operation-0002",
        ttl_hours=1,
        now=T0 + timedelta(minutes=30),
    )

    before_replacement = store.recall(
        scope="program",
        now=T0 + timedelta(minutes=15),
    )
    after_replacement = store.recall(
        scope="program",
        now=T0 + timedelta(minutes=45),
    )

    assert before_replacement[0]["value"]["value"] == "open_zero_step_ci"
    assert after_replacement[0]["value"]["value"] == "replacement_state"


def test_recall_order_is_deterministic_and_confidence_bounded(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    remember(
        store,
        key="cloud.secondary-state",
        value={
            "fact_type": "state",
            "subject_ref": "cloud.secondary",
            "value": "pending",
            "reason_codes": [],
            "tags": ["cloud"],
        },
        idempotency_key="memory-secondary-0001",
        salience="0.5",
    )
    remember(
        store,
        idempotency_key="memory-primary-0001",
        salience="1",
    )
    remember(
        store,
        key="cloud.low-confidence",
        value={
            "fact_type": "state",
            "subject_ref": "cloud.low-confidence",
            "value": "unconfirmed",
            "reason_codes": [],
            "tags": ["cloud"],
        },
        idempotency_key="memory-lowconfidence-0001",
        confidence="0.49",
        salience="1",
    )

    recalled = store.recall(scope="program", query="cloud", now=T0)
    assert [item["key"] for item in recalled] == [
        "cloud.current-blocker",
        "cloud.secondary-state",
    ]


@pytest.mark.parametrize(
    "value",
    [
        {
            "fact_type": "blocker",
            "subject_ref": "github.issue.124",
            "value": {"nested": "object"},
            "reason_codes": [],
            "tags": [],
        },
        {
            "fact_type": "blocker",
            "subject_ref": "github.issue.124",
            "value": "this contains arbitrary prose",
            "reason_codes": [],
            "tags": [],
        },
        {
            "fact_type": "reference",
            "subject_ref": "person.contact",
            "value": "person@example.com",
            "reason_codes": [],
            "tags": [],
        },
        {
            "fact_type": "measurement",
            "subject_ref": "cloud.account-number",
            "value": 123456789,
            "reason_codes": [],
            "tags": [],
        },
        {
            "fact_type": "measurement",
            "subject_ref": "cloud.otp",
            "value": 123456,
            "reason_codes": [],
            "tags": [],
        },
        {
            "fact_type": "reference",
            "subject_ref": "cloud.client-secret",
            "value": "active",
            "reason_codes": [],
            "tags": [],
        },
        {
            "fact_type": "reference",
            "subject_ref": "cloud.reference",
            "value": "q7v3m9x2k4p8r6t1w5y0",
            "reason_codes": [],
            "tags": [],
        },
        {
            "fact_type": "reference",
            "subject_ref": "cloud.reference",
            "value": "john.smith",
            "reason_codes": [],
            "tags": [],
        },
    ],
)
def test_memory_rejects_nested_prose_and_personal_data_without_a_row(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
    value: Mapping[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    with pytest.raises(CloudAdvancementError):
        remember(store, value=value)
    assert store.memory_summary(T0)["memory_event_count"] == 0


def test_provenance_digest_is_resolved_on_write_and_reverification(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    with pytest.raises(CloudAdvancementError, match="does not match"):
        store.remember(
            key="cloud.current-blocker",
            value=blocker_fact(),
            scope="program",
            actor="pytest",
            source_refs=["evidence/source.json"],
            source_sha256=["b" * 64],
            idempotency_key="memory-bad-source-0001",
            derivation_type="direct_observation",
            now=T0,
        )
    assert store.memory_summary(T0)["memory_event_count"] == 0

    remember(store)
    (tmp_path / "evidence" / "source.json").write_bytes(
        b'{"evidence":"changed"}\n'
    )
    replay = remember(store, now=T0 + timedelta(minutes=1))
    assert replay["idempotent_replay"] is True
    summary = store.memory_summary(T0)
    assert summary["source_drift_count"] == 1
    assert summary["sources_current"] is False
    with pytest.raises(CloudAdvancementError, match="provenance has drifted"):
        store.recall(scope="program", now=T0)


def test_current_receipt_validation_detects_later_source_drift(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    anchor_path = Path(assurance["verification"]["anchor_receipt"])
    store.write_verification_receipt(
        store.verify(now=T0 + timedelta(minutes=1)),
        anchor_path,
    )
    (root / "evidence" / "source.json").write_bytes(
        b'{"evidence":"changed"}\n'
    )

    with pytest.raises(CloudAdvancementError, match="working-memory summary"):
        validate_verification_receipt(
            root,
            anchor_path,
            assurance=assurance,
            program=program,
            state_path=store.state_path,
        )
    historical = validate_verification_receipt(
        root,
        anchor_path,
        assurance=assurance,
        program=program,
        state_path=store.state_path,
        historical=True,
    )
    assert historical["assurance_passed"] is True


def test_actor_identity_and_recall_scope_fail_closed(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    with pytest.raises(CloudAdvancementError, match="actor"):
        store.remember(
            key="cloud.current-blocker",
            value=blocker_fact(),
            scope="program",
            actor="person@example.com",
            source_refs=["evidence/source.json"],
            source_sha256=[SOURCE_DIGEST],
            idempotency_key="memory-private-actor-0001",
            derivation_type="direct_observation",
            now=T0,
        )
    with pytest.raises(CloudAdvancementError, match="explicit valid scope"):
        store.recall(scope="", now=T0)
    assert store.memory_summary(T0)["memory_event_count"] == 0


def test_capacity_rejects_without_partial_write(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    bounded = clone(assurance)
    bounded["working_memory"]["max_active_entries"] = 1
    store = make_store(tmp_path, program, bounded)
    remember(store)
    with pytest.raises(CloudAdvancementError, match="capacity"):
        remember(
            store,
            key="cloud.second-fact",
            value={
                "fact_type": "state",
                "subject_ref": "cloud.second",
                "value": "pending",
                "reason_codes": [],
                "tags": [],
            },
            idempotency_key="memory-operation-0002",
        )
    assert store.memory_summary(T0)["memory_event_count"] == 1


def test_backdated_write_is_rejected_without_partial_history(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    remember(store, now=T0 + timedelta(minutes=10))

    with pytest.raises(CloudAdvancementError, match="history head time"):
        remember(
            store,
            key="cloud.second-state",
            value={
                "fact_type": "state",
                "subject_ref": "cloud.second",
                "value": "pending",
                "reason_codes": [],
                "tags": [],
            },
            idempotency_key="memory-backdated-0002",
            now=T0,
        )

    assert store.memory_summary(T0 + timedelta(minutes=10))[
        "memory_event_count"
    ] == 1


def test_append_only_triggers_and_hash_chain_detect_tampering(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    remember(store)
    with sqlite3.connect(store.state_path) as connection:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute(
                "UPDATE cloud_assurance_events SET actor = 'changed'"
            )
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            connection.execute("DELETE FROM cloud_assurance_events")

        connection.execute("DROP TRIGGER assurance_events_no_update")
        connection.execute(
            """
            UPDATE cloud_assurance_events
            SET payload_json = '{"tampered":true}'
            WHERE sequence = 1
            """
        )
        connection.commit()
    with pytest.raises(CloudAdvancementError, match="hash is invalid"):
        store.memory_summary(T0)


def test_verification_detects_same_name_noop_trigger_without_repair(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    with sqlite3.connect(store.state_path) as connection:
        connection.execute("DROP TRIGGER assurance_events_no_update")
        connection.execute(
            """
            CREATE TRIGGER assurance_events_no_update
            BEFORE UPDATE ON cloud_assurance_events
            BEGIN
                SELECT 1;
            END
            """
        )
        connection.commit()

    receipt = store.verify(now=T0 + timedelta(minutes=1))
    assert receipt["assurance_passed"] is False
    assert receipt["checks"]["append_only_controls_valid"] is False
    with sqlite3.connect(store.state_path) as connection:
        trigger_sql = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'trigger'
              AND name = 'assurance_events_no_update'
            """
        ).fetchone()[0]
    assert "SELECT 1" in trigger_sql

    receipt["checks"]["append_only_controls_valid"] = True
    receipt["assurance_passed"] = all(receipt["checks"].values())
    digest_basis = dict(receipt)
    digest_basis.pop("receipt_digest")
    receipt["receipt_digest"] = canonical_digest(digest_basis)
    tampered_path = (
        root
        / "reports"
        / "artifacts"
        / "cloud_advancement"
        / "redigested-trigger-receipt.json"
    )
    tampered_path.parent.mkdir(parents=True, exist_ok=True)
    tampered_path.write_text(
        json.dumps(receipt, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(CloudAdvancementError, match="structural check"):
        validate_verification_receipt(
            root,
            tampered_path.relative_to(root),
        )


def test_write_rejects_same_name_noop_append_only_trigger(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    remember(store)
    with sqlite3.connect(store.state_path) as connection:
        connection.execute("DROP TRIGGER assurance_events_no_update")
        connection.execute(
            """
            CREATE TRIGGER assurance_events_no_update
            BEFORE UPDATE ON cloud_assurance_events
            BEGIN
                SELECT 1;
            END
            """
        )
        connection.commit()

    with pytest.raises(CloudAdvancementError, match="not functional"):
        remember(
            store,
            key="cloud.second-state",
            value={
                "fact_type": "state",
                "subject_ref": "cloud.second",
                "value": "pending",
                "reason_codes": [],
                "tags": [],
            },
            idempotency_key="memory-noop-trigger-0002",
            now=T0 + timedelta(minutes=1),
        )
    assert store.memory_summary(T0 + timedelta(minutes=1))[
        "memory_event_count"
    ] == 1


def test_concurrent_idempotent_remember_has_one_event(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(remember, store) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]

    assert results[0]["event_id"] == results[1]["event_id"]
    assert sorted(item["idempotent_replay"] for item in results) == [
        False,
        True,
    ]
    assert store.memory_summary(T0)["memory_event_count"] == 1


def test_idempotency_ignores_ambient_repository_state(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"value": ("a" * 40, "clean")}
    monkeypatch.setattr(
        assurance_module,
        "repository_revision_state",
        lambda _root: state["value"],
    )
    store = make_store(tmp_path, program, assurance)

    first = remember(store)
    state["value"] = ("b" * 40, "dirty")
    replay = remember(store, now=T0 + timedelta(minutes=1))

    assert replay["event_id"] == first["event_id"]
    assert replay["idempotent_replay"] is True


def test_only_defined_metrics_count_and_every_required_metric_is_needed(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    first = measure(store)
    partial = store.metric_summary()
    second = measure(
        store,
        metric_id="cloud.completed_unique_action_count",
        idempotency_key="metric-operation-0002",
    )
    summary = store.metric_summary()

    assert first["actual"] == "12"
    assert first["expected"] == "12"
    assert first["definition_digest"]
    assert partial["minimum_satisfied"] is False
    assert partial["missing_required_metric_ids"] == [
        "cloud.completed_unique_action_count"
    ]
    assert second["actual"] == "1"
    assert summary["required_metric_count"] == 2
    assert summary["missing_required_metric_ids"] == []
    assert summary["current_failed_count"] == 0
    assert summary["all_current_metrics_passed"] is True
    with pytest.raises(CloudAdvancementError, match="not defined"):
        measure(
            store,
            metric_id="cloud.caller_defined_target",
            idempotency_key="metric-unknown-0001",
        )


def test_completed_action_metric_is_derived_from_executed_actions(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    bounded = clone(assurance)
    original_path = (
        PROJECT_ROOT
        / "reports"
        / "artifacts"
        / "cloud_advancement"
        / "initial_execution_receipt.json"
    )
    receipt = json.loads(original_path.read_text(encoding="utf-8"))
    receipt["executed_actions"][0]["state"] = "blocked"
    digest_basis = dict(receipt)
    digest_basis.pop("receipt_digest")
    receipt["receipt_digest"] = canonical_digest(digest_basis)
    rendered = (json.dumps(receipt, indent=2) + "\n").encode("utf-8")
    bounded["verification"]["trusted_loop_receipt_sha256"] = hashlib.sha256(
        rendered
    ).hexdigest()

    store = make_store(tmp_path, program, bounded)
    receipt_path = (
        tmp_path
        / "reports"
        / "artifacts"
        / "cloud_advancement"
        / "initial_execution_receipt.json"
    )
    receipt_path.write_bytes(rendered)

    result = measure(
        store,
        metric_id="cloud.completed_unique_action_count",
        idempotency_key="metric-completion-derived-0001",
    )

    assert receipt["summary"]["completed_unique_actions"] == 1
    assert result["actual"] == "0"
    assert result["passed"] is False


def test_trusted_loop_receipt_rejects_self_redigested_fabrication(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    receipt_path = (
        tmp_path
        / "reports"
        / "artifacts"
        / "cloud_advancement"
        / "initial_execution_receipt.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["executed_actions"][0]["state"] = "blocked"
    digest_basis = dict(receipt)
    digest_basis.pop("receipt_digest")
    receipt["receipt_digest"] = canonical_digest(digest_basis)
    receipt_path.write_text(
        json.dumps(receipt, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CloudAdvancementError, match="pinned SHA-256"):
        measure(
            store,
            metric_id="cloud.completed_unique_action_count",
            idempotency_key="metric-pinned-receipt-0001",
        )
    assert store.metric_summary()["metric_event_count"] == 0


def test_completed_metric_rejects_actions_outside_bound_program(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    bounded = clone(assurance)
    original_path = (
        PROJECT_ROOT
        / "reports"
        / "artifacts"
        / "cloud_advancement"
        / "initial_execution_receipt.json"
    )
    receipt = json.loads(original_path.read_text(encoding="utf-8"))
    receipt["executed_actions"][0]["action_id"] = "CLD-999"
    digest_basis = dict(receipt)
    digest_basis.pop("receipt_digest")
    receipt["receipt_digest"] = canonical_digest(digest_basis)
    rendered = (json.dumps(receipt, indent=2) + "\n").encode("utf-8")
    bounded["verification"]["trusted_loop_receipt_sha256"] = hashlib.sha256(
        rendered
    ).hexdigest()
    store = make_store(tmp_path, program, bounded)
    receipt_path = (
        tmp_path
        / "reports"
        / "artifacts"
        / "cloud_advancement"
        / "initial_execution_receipt.json"
    )
    receipt_path.write_bytes(rendered)

    with pytest.raises(CloudAdvancementError, match="outside.*bound program"):
        measure(
            store,
            metric_id="cloud.completed_unique_action_count",
            idempotency_key="metric-unknown-action-0001",
        )
    assert store.metric_summary()["metric_event_count"] == 0


def test_idempotency_key_conflict_fails_closed(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    remember(store)
    with pytest.raises(CloudAdvancementError, match="reused"):
        remember(
            store,
            value=blocker_fact("changed_request"),
        )
    assert store.memory_summary(T0)["memory_event_count"] == 1


def test_nearest_rank_is_exact_and_rejects_invalid_samples() -> None:
    samples = list(range(1, 101))
    assert nearest_rank(samples, percentile=Decimal("0.50")) == 50
    assert nearest_rank(samples, percentile=Decimal("0.95")) == 95
    assert nearest_rank(samples, percentile=Decimal("0.99")) == 99
    with pytest.raises(CloudAdvancementError, match="positive"):
        nearest_rank([0, 1], Decimal("0.5"))


def test_performance_statistics_recompute_from_controlled_raw_samples(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    durations = [1, 2, 3, 4, 5, 6, 7]
    ticks = iter(
        value
        for index, duration in enumerate(durations)
        for value in (index * 100, index * 100 + duration)
    )
    store = make_store(
        tmp_path,
        program,
        assurance,
        clock=lambda: next(ticks),
    )

    stats = store._measure_operation(
        lambda: None,
        warmup_count=2,
        sample_count=5,
        budget_ms="0.000020",
    )

    assert stats["warmup_ns"] == [1, 2]
    assert stats["samples_ns"] == [3, 4, 5, 6, 7]
    assert stats["minimum_ns"] == 3
    assert stats["mean_ns"] == 5
    assert stats["p50_ns"] == 5
    assert stats["p95_ns"] == 7
    assert stats["p99_ns"] == 7
    assert stats["maximum_ns"] == 7
    assert stats["passed"] is True


def test_rigorous_verification_receipt_and_anchor_pass(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    before_event_count = store.metric_summary()["metric_event_count"]
    before_database_bytes = store._database_bytes()
    receipt = store.verify(now=T0 + timedelta(minutes=1))

    assert receipt["assurance_passed"] is True
    assert receipt["execution_authorized"] is False
    assert store.metric_summary()["metric_event_count"] == before_event_count
    assert store._database_bytes() == before_database_bytes
    assert receipt["database_integrity"]["declared_foreign_key_count"] >= 1
    assert receipt["performance"]["sample_count"] == 100
    for operation in receipt["performance"]["operations"].values():
        assert len(operation["warmup_ns"]) == 10
        assert len(operation["samples_ns"]) == 100
        assert operation["minimum_ns"] <= operation["p50_ns"]
        assert operation["p50_ns"] <= operation["p95_ns"]
        assert operation["p95_ns"] <= operation["p99_ns"]
        assert operation["p99_ns"] <= operation["maximum_ns"]

    anchor_path = Path(
        assurance["verification"]["anchor_receipt"]
    )
    _, finalized = store.write_verification_receipt(
        receipt,
        anchor_path,
    )
    validated = validate_verification_receipt(root, anchor_path)
    anchored = store.verify(now=T0 + timedelta(minutes=2))
    assert validated["receipt_digest"] == finalized["receipt_digest"]
    assert finalized["assurance_history"]["trusted_checkpoint_count"] == 0
    assert store.metric_summary()["metric_event_count"] == before_event_count
    assert (
        anchored["assurance_history"]["anchor_observation"]
        == "verified"
    )
    assert anchored["assurance_history"]["trusted_checkpoint_count"] == 1


def test_checkpoint_output_must_be_independently_discoverable(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    receipt = store.verify(now=T0 + timedelta(minutes=1))

    for target in (
        Path(".aigc/checkpoint.json"),
        Path(
            ".aigc/cloud_advancement/checkpoints/nested/checkpoint.json"
        ),
        Path(
            "reports/artifacts/cloud_advancement/"
            "unconfigured-checkpoint.json"
        ),
    ):
        with pytest.raises(CloudAdvancementError, match="configured baseline"):
            store.write_verification_receipt(receipt, target)


def test_concurrent_checkpoint_publication_never_overwrites(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    receipt = store.verify(now=T0 + timedelta(minutes=1))
    target = Path(
        ".aigc/cloud_advancement/checkpoints/concurrent.json"
    )
    barrier = Barrier(2)
    real_link = assurance_module.os.link

    def synchronized_link(source: Path, destination: Path) -> None:
        barrier.wait(timeout=10)
        real_link(source, destination)

    monkeypatch.setattr(assurance_module.os, "link", synchronized_link)

    def write_checkpoint() -> str:
        try:
            store.write_verification_receipt(receipt, target)
            return "written"
        except CloudAdvancementError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: write_checkpoint(), range(2)))

    assert outcomes.count("written") == 1
    assert sum("cannot be overwritten" in item for item in outcomes) == 1
    validated = validate_verification_receipt_payload(
        json.loads((root / target).read_text(encoding="utf-8")),
        root,
    )
    assert validated["receipt_digest"] == receipt["receipt_digest"]


def test_checkpoint_anchor_digest_binds_the_exact_history_tuple(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    baseline_path = Path(assurance["verification"]["anchor_receipt"])
    store.write_verification_receipt(
        store.verify(now=T0 + timedelta(minutes=1)),
        baseline_path,
    )
    remember(
        store,
        key="cloud.after-baseline",
        value={
            "fact_type": "state",
            "subject_ref": "cloud.after-baseline",
            "value": "recorded",
            "reason_codes": [],
            "tags": [],
        },
        idempotency_key="memory-anchor-tuple-0001",
        now=T0 + timedelta(minutes=2),
    )
    forged = store.verify(now=T0 + timedelta(minutes=3))
    forged["assurance_history"]["anchor_event_count"] = 0
    forged["assurance_history"]["anchor_history_head_sha256"] = "0" * 64
    digest_basis = dict(forged)
    digest_basis.pop("receipt_digest")
    forged["receipt_digest"] = canonical_digest(digest_basis)
    forged_path = (
        root
        / ".aigc"
        / "cloud_advancement"
        / "checkpoints"
        / "forged-anchor-tuple.json"
    )
    forged_path.parent.mkdir(parents=True, exist_ok=True)
    forged_path.write_text(
        json.dumps(forged, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CloudAdvancementError, match="anchor tuple"):
        validate_verification_receipt(
            root,
            forged_path.relative_to(root),
            assurance=assurance,
            program=program,
            state_path=store.state_path,
        )


def test_anchor_detects_valid_prefix_truncation(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    remember(
        store,
        key="cloud.second-state",
        value={
            "fact_type": "state",
            "subject_ref": "cloud.second",
            "value": "pending",
            "reason_codes": [],
            "tags": [],
        },
        idempotency_key="memory-second-0001",
        now=T0 + timedelta(minutes=1),
    )
    anchor_path = Path(
        assurance["verification"]["anchor_receipt"]
    )
    store.write_verification_receipt(
        store.verify(now=T0 + timedelta(minutes=2)),
        anchor_path,
    )

    with sqlite3.connect(store.state_path) as connection:
        connection.execute("DROP TRIGGER assurance_events_no_delete")
        connection.execute(
            "DELETE FROM cloud_assurance_events WHERE sequence >= 4"
        )
        connection.execute(
            """
            CREATE TRIGGER assurance_events_no_delete
            BEFORE DELETE ON cloud_assurance_events
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'cloud assurance history is append-only'
                );
            END
            """
        )
        connection.commit()
    with pytest.raises(
        CloudAdvancementError,
        match="shorter|missing assurance history",
    ):
        store.verify(now=T0 + timedelta(minutes=3))


def test_retained_newer_checkpoint_prevents_rollback_to_baseline(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    anchor_path = Path(assurance["verification"]["anchor_receipt"])
    store.write_verification_receipt(
        store.verify(now=T0 + timedelta(minutes=1)),
        anchor_path,
    )
    remember(
        store,
        key="cloud.after-baseline",
        value={
            "fact_type": "state",
            "subject_ref": "cloud.after-baseline",
            "value": "recorded",
            "reason_codes": [],
            "tags": [],
        },
        idempotency_key="memory-after-baseline-0001",
        now=T0 + timedelta(minutes=2),
    )
    later_path = Path(
        ".aigc/cloud_advancement/checkpoints/checkpoint-b.json"
    )
    store.write_verification_receipt(
        store.verify(now=T0 + timedelta(minutes=3)),
        later_path,
    )

    with sqlite3.connect(store.state_path) as connection:
        connection.execute("DROP TRIGGER assurance_events_no_delete")
        connection.execute(
            "DELETE FROM cloud_assurance_events WHERE sequence >= 4"
        )
        connection.execute(
            """
            CREATE TRIGGER assurance_events_no_delete
            BEFORE DELETE ON cloud_assurance_events
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'cloud assurance history is append-only'
                );
            END
            """
        )
        connection.commit()

    assert (root / anchor_path).exists()
    assert (root / later_path).exists()
    with pytest.raises(
        CloudAdvancementError,
        match="missing assurance history|shorter|database-byte",
    ):
        store.verify(now=T0 + timedelta(minutes=4))


def test_receipt_digest_tamper_is_rejected(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    receipt = store.verify(now=T0 + timedelta(minutes=1))
    receipt["source_revision"] = "b" * 40
    with pytest.raises(CloudAdvancementError, match="digest"):
        validate_verification_receipt_payload(
            receipt,
            root,
        )


def test_receipt_recomputes_performance_even_with_a_new_outer_digest(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    receipt = store.verify(now=T0 + timedelta(minutes=1))
    stats = receipt["performance"]["operations"]["memory_recall"]
    stats["p95_ns"] += 1
    basis = dict(receipt)
    basis.pop("receipt_digest")
    receipt["receipt_digest"] = canonical_digest(basis)

    with pytest.raises(CloudAdvancementError, match="p95_ns"):
        validate_verification_receipt_payload(receipt, root)


def test_local_receipt_validation_rejects_a_redigested_budget_change(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    receipt = store.verify(now=T0 + timedelta(minutes=1))
    operation = receipt["performance"]["operations"]["memory_recall"]
    operation["budget_p95_ns"] += 1
    operation["passed"] = operation["p95_ns"] <= operation["budget_p95_ns"]
    receipt["performance"]["all_budgets_passed"] = all(
        item["passed"]
        for item in receipt["performance"]["operations"].values()
    )
    receipt["checks"]["performance_budgets_valid"] = receipt[
        "performance"
    ]["all_budgets_passed"]
    receipt["assurance_passed"] = all(receipt["checks"].values())
    basis = dict(receipt)
    basis.pop("receipt_digest")
    receipt["receipt_digest"] = canonical_digest(basis)
    path = (
        root
        / "reports"
        / "artifacts"
        / "cloud_advancement"
        / "redigested-budget-receipt.json"
    )
    path.write_text(
        json.dumps(receipt, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CloudAdvancementError, match="budget is not current"):
        validate_verification_receipt(
            root,
            path.relative_to(root),
        )


def test_attestable_verification_rejects_an_injected_clock(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    counter = iter(range(1, 100000))
    store = make_store(
        root,
        program,
        assurance,
        clock=lambda: next(counter),
    )
    remember(store)
    measure_required(store)
    with pytest.raises(CloudAdvancementError, match="perf_counter_ns"):
        store.verify(now=T0 + timedelta(minutes=1))


def test_current_metric_failure_causes_verification_failure(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    root = prepare_verification_root(tmp_path, assurance)
    failing_assurance = clone(assurance)
    failing_assurance["quantitative_accuracy"]["metric_definitions"][0][
        "expected"
    ] = "13"
    (root / "config" / "cloud_advancement_assurance.json").write_text(
        json.dumps(failing_assurance, indent=2) + "\n",
        encoding="utf-8",
    )
    store = make_store(root, program, failing_assurance)
    remember(store)
    measure_required(store)
    receipt = store.verify(now=T0 + timedelta(minutes=1))
    assert receipt["assurance_passed"] is False
    assert receipt["checks"]["quantitative_accuracy_valid"] is False
    assert receipt["quantitative_accuracy"]["current_failed_count"] == 1


def test_memory_database_contains_no_action_authority_table(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    result = remember(store)
    with sqlite3.connect(store.state_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "cloud_action_events" not in tables
    assert result["external_action_performed"] is False
    assert assurance["governance"]["automation_can_self_approve"] is False


def test_run_memory_requires_existing_run_ancestry(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    with pytest.raises(CloudAdvancementError, match="existing action run"):
        store.remember(
            key="cloud.run-state",
            value={
                "fact_type": "state",
                "subject_ref": "cloud.run",
                "value": "pending",
                "reason_codes": [],
                "tags": [],
            },
            scope="run",
            action_id="CLD-001",
            run_id="CLOUD-RUN-CLD-001-AAAAAAAAAAAA",
            actor="pytest",
            source_refs=["evidence/run.json"],
            source_sha256=[SOURCE_DIGEST],
            idempotency_key="memory-run-0001",
            derivation_type="direct_observation",
            now=T0,
        )


def test_run_memory_rejects_a_forged_matching_ledger_row(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
) -> None:
    store = make_store(tmp_path, program, assurance)
    loop_state = (
        tmp_path
        / ".aigc"
        / "cloud_advancement"
        / "cloud_advancement.sqlite"
    )
    loop_state.parent.mkdir(parents=True, exist_ok=True)
    run_id = "CLOUD-RUN-CLD-001-AAAAAAAAAAAA"
    occurred_at = T0.isoformat().replace("+00:00", "Z")
    action = next(
        item for item in program["actions"] if item["action_id"] == "CLD-001"
    )
    evidence_json = canonical_json(
        {"action_fingerprint": action_semantic_fingerprint(action)}
    )
    event_basis = {
        "event_id": "CLOUD-EVENT-FORGED",
        "run_id": run_id,
        "action_id": "CLD-001",
        "event_type": "claimed",
        "occurred_at": occurred_at,
        "attempt": 1,
        "actor": "pytest",
        "source_revision": "unbound",
        "source_state": "unbound",
        "necessity_reason": "",
        "blocker_key": "",
        "blocker_fingerprint": "",
        "retry_not_before": "",
        "evidence_json": evidence_json,
        "program_digest": canonical_digest(program),
        "previous_event_hash": "0" * 64,
        "external_action_performed": 0,
    }
    event_hash = canonical_digest(event_basis)
    with sqlite3.connect(loop_state) as connection:
        connection.execute(
            """
            CREATE TABLE cloud_action_events (
                sequence INTEGER,
                event_id TEXT,
                run_id TEXT,
                action_id TEXT,
                event_type TEXT,
                occurred_at TEXT,
                attempt INTEGER,
                actor TEXT,
                source_revision TEXT,
                source_state TEXT,
                necessity_reason TEXT,
                blocker_key TEXT,
                blocker_fingerprint TEXT,
                retry_not_before TEXT,
                evidence_json TEXT,
                program_digest TEXT,
                previous_event_hash TEXT,
                event_hash TEXT,
                external_action_performed INTEGER
            )
            """
        )
        connection.execute(
            """
            INSERT INTO cloud_action_events
            VALUES (
                1, ?, ?, 'CLD-001', 'claimed', ?, 1, 'pytest', 'unbound',
                'unbound', '', '', '', '', ?, ?, ?, ?, 0
            )
            """,
            (
                event_basis["event_id"],
                run_id,
                occurred_at,
                evidence_json,
                canonical_digest(program),
                "0" * 64,
                event_hash,
            ),
        )

    with pytest.raises(
        CloudAdvancementError,
        match="trusted execution-receipt anchor",
    ):
        store.remember(
            key="cloud.run-state",
            value={
                "fact_type": "state",
                "subject_ref": "cloud.run",
                "value": "pending",
                "reason_codes": [],
                "tags": [],
            },
            scope="run",
            action_id="CLD-001",
            run_id=run_id,
            actor="pytest",
            source_refs=["evidence/source.json"],
            source_sha256=[SOURCE_DIGEST],
            idempotency_key="memory-run-forged-0001",
            derivation_type="direct_observation",
            now=T0,
        )


def test_cli_exposes_memory_metrics_summary_and_verification() -> None:
    from scripts.cloud_advancement_assurance import (
        _verification_exit_code,
        parse_args,
    )

    recall = parse_args(
        ["recall", "--scope", "program", "--query", "cloud"]
    )
    summary = parse_args(["summary"])
    verify = parse_args(["verify"])
    checkpoint = parse_args(
        [
            "checkpoint",
            "--output",
            ".aigc/cloud_advancement/checkpoints/checkpoint.json",
        ]
    )

    assert recall.command == "recall"
    assert summary.command == "summary"
    assert verify.command == "verify"
    assert checkpoint.command == "checkpoint"
    passing = {
        "assurance_passed": True,
        "checks": {},
    }
    structural_failure = {
        "assurance_passed": False,
        "checks": {
            name: name != "append_only_controls_valid"
            for name in {
                "program_and_assurance_config_valid",
                "sqlite_integrity_valid",
                "foreign_keys_valid",
                "append_only_controls_valid",
                "event_chain_valid",
                "program_binding_valid",
                "assurance_binding_valid",
                "loop_history_valid",
                "required_artifacts_present",
                "secrets_absent",
            }
        },
    }
    assurance_failure = clone(structural_failure)
    assurance_failure["checks"] = {
        name: True for name in structural_failure["checks"]
    }
    assert _verification_exit_code(passing) == 0
    assert _verification_exit_code(structural_failure) == 10
    assert _verification_exit_code(assurance_failure) == 11


def test_cli_verify_does_not_create_missing_state(
    tmp_path: Path,
    assurance: dict[str, Any],
) -> None:
    from scripts.cloud_advancement_assurance import main

    root = prepare_verification_root(tmp_path, assurance)
    state_path = (
        root / ".aigc" / "cloud_advancement" / "cloud_assurance.sqlite"
    )
    result = main(["--root", str(root), "verify"])

    assert result == 10
    assert not state_path.exists()


def test_cli_reports_non_utf8_checkpoint_as_structured_failure(
    tmp_path: Path,
    program: dict[str, Any],
    assurance: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts.cloud_advancement_assurance import main

    root = prepare_verification_root(tmp_path, assurance)
    store = make_store(root, program, assurance)
    remember(store)
    measure_required(store)
    checkpoint = (
        root
        / ".aigc"
        / "cloud_advancement"
        / "checkpoints"
        / "invalid.json"
    )
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_bytes(b"\xff\xfe\x00")

    assert main(["--root", str(root), "verify"]) == 10
    captured = capsys.readouterr()
    assert '"status": "verification_error"' in captured.err
    assert "Traceback" not in captured.err


def test_cli_reports_invalid_schema_as_structured_failure(
    tmp_path: Path,
    assurance: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts.cloud_advancement_assurance import main

    root = prepare_verification_root(tmp_path, assurance)
    schema_path = root / "schemas" / "cloud_advancement_assurance.schema.json"
    schema_path.write_text(
        '{"type":"not-a-real-json-schema-type"}\n',
        encoding="utf-8",
    )

    assert main(["--root", str(root), "verify"]) == 10
    captured = capsys.readouterr()
    assert '"status": "verification_error"' in captured.err
    assert "Traceback" not in captured.err
