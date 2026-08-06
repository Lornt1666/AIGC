from dataclasses import replace
from pathlib import Path

import pytest

from src.mission_os.connector_activation import (
    ActivationRecord,
    CapabilityManifest,
    ConnectorActivationFramework,
    ConnectorRegistry,
    DependencyReceipt,
    Environment,
    LifecycleState,
)
from src.mission_os.connector_kernel import AppendOnlyEvidenceLedger, digest


SHA = "a" * 64


def manifest(*, environments=(Environment.TEST, Environment.STAGING),
             requires_approval=True, emergency_stop_required=True) -> CapabilityManifest:
    return CapabilityManifest.compile(
        connector_id="github",
        connector_version="1.0.0",
        readable_capabilities=("commit.read", "workflow.read"),
        supported_environments=environments,
        requires_approval=requires_approval,
        emergency_stop_required=emergency_stop_required,
    )


def dependencies(*, satisfied=True, evidence="b" * 64):
    return (
        DependencyReceipt.compile(
            dependency_id="kernel.policy",
            required=True,
            satisfied=satisfied,
            evidence_sha256=evidence,
        ),
    )


def ready_framework(tmp_path: Path, *, verified_dependencies=None):
    registry = ConnectorRegistry()
    value = manifest()
    registry.register(value)
    framework = ConnectorActivationFramework(
        registry=registry,
        ledger=AppendOnlyEvidenceLedger(tmp_path / "activation-evidence.jsonl"),
    )
    receipts = verified_dependencies or dependencies()
    framework.transition("github", LifecycleState.CONFIGURED)
    framework.transition(
        "github",
        LifecycleState.DEPENDENCIES_VERIFIED,
        dependencies=receipts,
    )
    framework.transition("github", LifecycleState.READY_FOR_ACTIVATION)
    return framework, value, receipts


def record(value: CapabilityManifest, environment=Environment.TEST, *, receipts=None):
    return ActivationRecord.compile(
        activation_id="ACTIVATION-0001",
        manifest=value,
        environment=environment,
        requested_capabilities=("commit.read",),
        approval_digest=SHA,
        policy_digest="c" * 64,
        dependencies=receipts or dependencies(),
        actor_id="authority-1",
    )


def forge_record(value: ActivationRecord, **changes) -> ActivationRecord:
    fields = {**value.__dict__, **changes}
    body = {
        "schema_version": fields["schema_version"],
        "activation_id": fields["activation_id"],
        "connector_id": fields["connector_id"],
        "connector_version": fields["connector_version"],
        "environment": fields["environment"].value,
        "requested_capabilities": sorted(fields["requested_capabilities"]),
        "manifest_sha256": fields["manifest_sha256"],
        "approval_digest": fields["approval_digest"],
        "policy_digest": fields["policy_digest"],
        "dependency_digest": fields["dependency_digest"],
        "lifecycle_state": fields["lifecycle_state"].value,
        "actor_id": fields["actor_id"],
        "created_at": fields["created_at"],
        "production_activation_authorized": fields["production_activation_authorized"],
        "external_send_authorized": fields["external_send_authorized"],
        "github_mutation_authorized": fields["github_mutation_authorized"],
    }
    fields["activation_sha256"] = digest(body)
    return ActivationRecord(**fields)


def test_test_activation_is_evidenced_and_integrity_bound(tmp_path: Path) -> None:
    framework, value, receipts = ready_framework(tmp_path)
    activated = framework.activate(record(value, receipts=receipts))
    assert activated.lifecycle_state is LifecycleState.ACTIVATED_TEST
    activated.verify(value)
    events = framework.ledger.verify()
    assert events[-1]["event_type"] == "connector_activation"
    assert events[-1]["activation_sha256"] == activated.activation_sha256
    assert events[-1]["dependency_digest"] == activated.dependency_digest
    assert events[-1]["production_activation_authorized"] is False


def test_staging_activation_is_separate_from_test(tmp_path: Path) -> None:
    framework, value, receipts = ready_framework(tmp_path)
    activated = framework.activate(record(value, Environment.STAGING, receipts=receipts))
    assert activated.environment is Environment.STAGING
    assert activated.lifecycle_state is LifecycleState.ACTIVATED_STAGING


def test_production_is_structurally_prohibited() -> None:
    with pytest.raises(PermissionError, match="production"):
        manifest(environments=(Environment.PRODUCTION,))


def test_writable_capability_manifest_is_prohibited() -> None:
    with pytest.raises(PermissionError, match="writable"):
        CapabilityManifest.compile(
            connector_id="gmail",
            connector_version="1.0.0",
            readable_capabilities=("draft.inspect",),
            writable_capabilities=("message.send",),
        )


def test_disabled_approval_is_structurally_prohibited() -> None:
    with pytest.raises(PermissionError, match="approval"):
        manifest(requires_approval=False)


def test_disabled_emergency_stop_is_structurally_prohibited() -> None:
    with pytest.raises(PermissionError, match="emergency stop"):
        manifest(emergency_stop_required=False)


def test_manifest_verification_rejects_disabled_governance_flags() -> None:
    value = manifest()
    disabled_approval = replace(value, requires_approval=False)
    with pytest.raises(PermissionError, match="integrity|approval"):
        disabled_approval.verify()
    disabled_stop = replace(value, emergency_stop_required=False)
    with pytest.raises(PermissionError, match="integrity|emergency stop"):
        disabled_stop.verify()


def test_github_mutation_and_gmail_send_cannot_be_requested() -> None:
    value = manifest()
    with pytest.raises(PermissionError, match="outside"):
        ActivationRecord.compile(
            activation_id="ACTIVATION-0002",
            manifest=value,
            environment=Environment.TEST,
            requested_capabilities=("issue.write",),
            approval_digest=SHA,
            policy_digest="c" * 64,
            dependencies=dependencies(),
            actor_id="authority-1",
        )


def test_unsatisfied_required_dependency_fails_closed() -> None:
    with pytest.raises(PermissionError, match="unsatisfied"):
        dependencies(satisfied=False)


def test_empty_dependency_set_fails_record_compilation() -> None:
    value = manifest()
    with pytest.raises(PermissionError, match="non-empty"):
        ActivationRecord.compile(
            activation_id="ACTIVATION-EMPTY",
            manifest=value,
            environment=Environment.TEST,
            requested_capabilities=("commit.read",),
            approval_digest=SHA,
            policy_digest="c" * 64,
            dependencies=(),
            actor_id="authority-1",
        )


def test_tampered_dependency_evidence_fails_integrity() -> None:
    receipt = dependencies()[0]
    tampered = replace(receipt, evidence_sha256="d" * 64)
    with pytest.raises(PermissionError, match="integrity"):
        tampered.verify()


def test_unregistered_transition_emits_no_evidence(tmp_path: Path) -> None:
    ledger = AppendOnlyEvidenceLedger(tmp_path / "evidence.jsonl")
    framework = ConnectorActivationFramework(registry=ConnectorRegistry(), ledger=ledger)
    with pytest.raises(PermissionError, match="not registered"):
        framework.transition("unknown", LifecycleState.CONFIGURED)
    assert ledger.verify() == []


def test_dependency_transition_requires_non_empty_verified_receipts(tmp_path: Path) -> None:
    registry = ConnectorRegistry()
    registry.register(manifest())
    ledger = AppendOnlyEvidenceLedger(tmp_path / "evidence.jsonl")
    framework = ConnectorActivationFramework(registry=registry, ledger=ledger)
    framework.transition("github", LifecycleState.CONFIGURED)
    with pytest.raises(PermissionError, match="non-empty"):
        framework.transition("github", LifecycleState.DEPENDENCIES_VERIFIED, dependencies=())
    events = ledger.verify()
    assert events[-1]["to_state"] == LifecycleState.CONFIGURED.value


def test_activation_requires_exact_lifecycle_sequence(tmp_path: Path) -> None:
    registry = ConnectorRegistry()
    value = manifest()
    registry.register(value)
    framework = ConnectorActivationFramework(
        registry=registry,
        ledger=AppendOnlyEvidenceLedger(tmp_path / "evidence.jsonl"),
    )
    with pytest.raises(PermissionError, match="not ready"):
        framework.activate(record(value))
    with pytest.raises(PermissionError, match="invalid lifecycle"):
        framework.transition("github", LifecycleState.READY_FOR_ACTIVATION)


def test_dependency_digest_mismatch_blocks_activation(tmp_path: Path) -> None:
    verified = dependencies(evidence="b" * 64)
    framework, value, _ = ready_framework(tmp_path, verified_dependencies=verified)
    different = dependencies(evidence="d" * 64)
    mismatched_record = record(value, receipts=different)
    with pytest.raises(PermissionError, match="does not match"):
        framework.activate(mismatched_record)
    assert framework.ledger.verify()[-1]["to_state"] == LifecycleState.READY_FOR_ACTIVATION.value


def test_successful_activation_is_bound_to_dependency_transition_evidence(tmp_path: Path) -> None:
    receipts = dependencies()
    framework, value, _ = ready_framework(tmp_path, verified_dependencies=receipts)
    compiled = record(value, receipts=receipts)
    activated = framework.activate(compiled)
    events = framework.ledger.verify()
    dependency_event = next(
        event for event in events
        if event["event_type"] == "connector_lifecycle_transition"
        and event["to_state"] == LifecycleState.DEPENDENCIES_VERIFIED.value
    )
    assert dependency_event["dependency_digest"] == activated.dependency_digest
    assert events[-1]["dependency_digest"] == activated.dependency_digest


def test_forged_record_version_mismatch_is_rejected() -> None:
    value = manifest()
    forged = forge_record(record(value), connector_version="9.9.9")
    with pytest.raises(PermissionError, match="version"):
        forged.verify(value)


def test_forged_record_unsupported_environment_is_rejected() -> None:
    value = manifest(environments=(Environment.TEST,))
    forged = forge_record(record(value), environment=Environment.STAGING)
    with pytest.raises(PermissionError, match="environment"):
        forged.verify(value)


def test_forged_record_undeclared_capability_is_rejected() -> None:
    value = manifest()
    forged = forge_record(record(value), requested_capabilities=frozenset({"issue.write"}))
    with pytest.raises(PermissionError, match="capability"):
        forged.verify(value)


def test_forged_record_empty_capability_set_is_rejected() -> None:
    value = manifest()
    forged = forge_record(record(value), requested_capabilities=frozenset())
    with pytest.raises(PermissionError, match="capability"):
        forged.verify(value)


@pytest.mark.parametrize("field", ["approval_digest", "policy_digest"])
def test_forged_record_malformed_authority_digest_is_rejected(field: str) -> None:
    value = manifest()
    forged = forge_record(record(value), **{field: "not-a-sha256"})
    with pytest.raises(PermissionError, match="approval and policy"):
        forged.verify(value)


def test_forged_record_invalid_lifecycle_state_is_rejected() -> None:
    value = manifest()
    forged = forge_record(record(value), lifecycle_state=LifecycleState.SUSPENDED)
    with pytest.raises(PermissionError, match="lifecycle"):
        forged.verify(value)


def test_registry_is_immutable() -> None:
    registry = ConnectorRegistry()
    registry.register(manifest())
    changed = CapabilityManifest.compile(
        connector_id="github",
        connector_version="2.0.0",
        readable_capabilities=("commit.read",),
    )
    with pytest.raises(PermissionError, match="immutable"):
        registry.register(changed)


def test_tampered_manifest_and_activation_fail_integrity() -> None:
    value = manifest()
    tampered = replace(value, connector_version="9.9.9")
    with pytest.raises(PermissionError, match="integrity"):
        tampered.verify()
    compiled = record(value)
    altered = replace(compiled, actor_id="other")
    with pytest.raises(PermissionError, match="integrity"):
        altered.verify(value)


def test_existing_kernel_authority_flags_remain_false() -> None:
    value = manifest()
    compiled = record(value)
    assert value.production_activation_authorized is False
    assert value.external_send_authorized is False
    assert value.github_mutation_authorized is False
    assert compiled.production_activation_authorized is False
    assert compiled.external_send_authorized is False
    assert compiled.github_mutation_authorized is False
