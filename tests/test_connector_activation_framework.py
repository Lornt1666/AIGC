from pathlib import Path

import pytest

from mission_os.connector_activation import (
    ActivationRecord,
    CapabilityManifest,
    ConnectorActivationFramework,
    ConnectorRegistry,
    DependencyReceipt,
    Environment,
    LifecycleState,
)
from mission_os.connector_kernel import AppendOnlyEvidenceLedger


SHA = "a" * 64


def manifest(*, environments=(Environment.TEST, Environment.STAGING)) -> CapabilityManifest:
    return CapabilityManifest.compile(
        connector_id="github",
        connector_version="1.0.0",
        readable_capabilities=("commit.read", "workflow.read"),
        supported_environments=environments,
    )


def dependencies(*, satisfied=True):
    return (DependencyReceipt("kernel.policy", True, satisfied, "b" * 64),)


def ready_framework(tmp_path: Path):
    registry = ConnectorRegistry()
    value = manifest()
    registry.register(value)
    framework = ConnectorActivationFramework(
        registry=registry,
        ledger=AppendOnlyEvidenceLedger(tmp_path / "activation-evidence.jsonl"),
    )
    framework.transition("github", LifecycleState.CONFIGURED)
    framework.transition("github", LifecycleState.DEPENDENCIES_VERIFIED)
    framework.transition("github", LifecycleState.READY_FOR_ACTIVATION)
    return framework, value


def record(value: CapabilityManifest, environment=Environment.TEST):
    return ActivationRecord.compile(
        activation_id="ACTIVATION-0001",
        manifest=value,
        environment=environment,
        requested_capabilities=("commit.read",),
        approval_digest=SHA,
        policy_digest="c" * 64,
        dependencies=dependencies(),
        actor_id="authority-1",
    )


def test_test_activation_is_evidenced_and_integrity_bound(tmp_path: Path) -> None:
    framework, value = ready_framework(tmp_path)
    activated = framework.activate(record(value))
    assert activated.lifecycle_state is LifecycleState.ACTIVATED_TEST
    activated.verify(value)
    events = framework.ledger.verify()
    assert events[-1]["event_type"] == "connector_activation"
    assert events[-1]["activation_sha256"] == activated.activation_sha256
    assert events[-1]["production_activation_authorized"] is False


def test_staging_activation_is_separate_from_test(tmp_path: Path) -> None:
    framework, value = ready_framework(tmp_path)
    activated = framework.activate(record(value, Environment.STAGING))
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


def test_github_mutation_and_gmail_send_cannot_be_requested() -> None:
    value = manifest()
    with pytest.raises(PermissionError, match="outside"):
        ActivationRecord.compile(
            activation_id="ACTIVATION-0002", manifest=value,
            environment=Environment.TEST,
            requested_capabilities=("issue.write",),
            approval_digest=SHA, policy_digest="c" * 64,
            dependencies=dependencies(), actor_id="authority-1",
        )


def test_unsatisfied_required_dependency_fails_closed() -> None:
    value = manifest()
    with pytest.raises(PermissionError, match="unsatisfied"):
        ActivationRecord.compile(
            activation_id="ACTIVATION-0003", manifest=value,
            environment=Environment.TEST,
            requested_capabilities=("commit.read",),
            approval_digest=SHA, policy_digest="c" * 64,
            dependencies=dependencies(satisfied=False), actor_id="authority-1",
        )


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
    tampered = value.__class__(**{**value.__dict__, "connector_version": "9.9.9"})
    with pytest.raises(PermissionError, match="integrity"):
        tampered.verify()
    compiled = record(value)
    altered = compiled.__class__(**{**compiled.__dict__, "actor_id": "other"})
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
