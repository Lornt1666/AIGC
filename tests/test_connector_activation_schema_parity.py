from __future__ import annotations

from dataclasses import replace
from enum import Enum
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

from src.mission_os.connector_activation import (
    ActivationRecord,
    CapabilityManifest,
    DependencyReceipt,
    Environment,
    LifecycleState,
)
from src.mission_os.connector_kernel import digest


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "connector_activation_record.schema.json"
)
VALID_STATES = (
    LifecycleState.READY_FOR_ACTIVATION,
    LifecycleState.ACTIVATED_TEST,
    LifecycleState.ACTIVATED_STAGING,
)
INVALID_STATES = (
    LifecycleState.SUSPENDED,
    LifecycleState.RETIRED,
    LifecycleState.REGISTERED,
    LifecycleState.CONFIGURED,
    LifecycleState.DEPENDENCIES_VERIFIED,
)


class UnknownLifecycleState(str, Enum):
    UNKNOWN = "UNKNOWN"


def manifest() -> CapabilityManifest:
    return CapabilityManifest.compile(
        connector_id="github",
        connector_version="1.0.0",
        readable_capabilities=("commit.read",),
        supported_environments=(Environment.TEST, Environment.STAGING),
    )


def dependency_receipts() -> tuple[DependencyReceipt, ...]:
    return (
        DependencyReceipt.compile(
            dependency_id="kernel.policy",
            required=True,
            satisfied=True,
            evidence_sha256="b" * 64,
        ),
    )


def base_record(value: CapabilityManifest) -> ActivationRecord:
    return ActivationRecord.compile(
        activation_id="ACTIVATION-PARITY-0001",
        manifest=value,
        environment=Environment.TEST,
        requested_capabilities=("commit.read",),
        approval_digest="a" * 64,
        policy_digest="c" * 64,
        dependencies=dependency_receipts(),
        actor_id="authority-1",
    )


def redigest(record: ActivationRecord, lifecycle_state: object) -> ActivationRecord:
    state_value = lifecycle_state.value
    body = {
        "schema_version": record.schema_version,
        "activation_id": record.activation_id,
        "connector_id": record.connector_id,
        "connector_version": record.connector_version,
        "environment": record.environment.value,
        "requested_capabilities": sorted(record.requested_capabilities),
        "manifest_sha256": record.manifest_sha256,
        "approval_digest": record.approval_digest,
        "policy_digest": record.policy_digest,
        "dependency_digest": record.dependency_digest,
        "lifecycle_state": state_value,
        "actor_id": record.actor_id,
        "created_at": record.created_at,
        "production_activation_authorized": record.production_activation_authorized,
        "external_send_authorized": record.external_send_authorized,
        "github_mutation_authorized": record.github_mutation_authorized,
    }
    return replace(
        record,
        lifecycle_state=lifecycle_state,
        activation_sha256=digest(body),
    )


def payload(record: ActivationRecord) -> dict[str, object]:
    return {
        "schema_version": record.schema_version,
        "activation_id": record.activation_id,
        "connector_id": record.connector_id,
        "connector_version": record.connector_version,
        "environment": record.environment.value,
        "requested_capabilities": sorted(record.requested_capabilities),
        "manifest_sha256": record.manifest_sha256,
        "approval_digest": record.approval_digest,
        "policy_digest": record.policy_digest,
        "dependency_digest": record.dependency_digest,
        "lifecycle_state": record.lifecycle_state.value,
        "actor_id": record.actor_id,
        "created_at": record.created_at,
        "production_activation_authorized": record.production_activation_authorized,
        "external_send_authorized": record.external_send_authorized,
        "github_mutation_authorized": record.github_mutation_authorized,
        "activation_sha256": record.activation_sha256,
    }


def schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("state", VALID_STATES)
def test_schema_and_runtime_accept_exact_activation_states(state: LifecycleState) -> None:
    value = manifest()
    candidate = redigest(base_record(value), state)
    validate(instance=payload(candidate), schema=schema())
    candidate.verify(value)


@pytest.mark.parametrize("state", INVALID_STATES)
def test_schema_and_runtime_reject_non_activation_lifecycle_states(
    state: LifecycleState,
) -> None:
    value = manifest()
    candidate = redigest(base_record(value), state)
    with pytest.raises(ValidationError):
        validate(instance=payload(candidate), schema=schema())
    with pytest.raises(PermissionError, match="lifecycle"):
        candidate.verify(value)


def test_schema_and_runtime_reject_unknown_lifecycle_state() -> None:
    value = manifest()
    candidate = redigest(base_record(value), UnknownLifecycleState.UNKNOWN)
    with pytest.raises(ValidationError):
        validate(instance=payload(candidate), schema=schema())
    with pytest.raises(PermissionError, match="lifecycle"):
        candidate.verify(value)


def test_schema_lifecycle_enum_exactly_matches_runtime_contract() -> None:
    lifecycle_enum = set(schema()["properties"]["lifecycle_state"]["enum"])
    assert lifecycle_enum == {state.value for state in VALID_STATES}
