"""Fail-closed Connector Activation Framework for Ω Mission OS Increment 12.

This module governs connector registration and activation metadata only. It does
not execute provider actions, unlock production, send Gmail, or mutate GitHub.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import hmac
from typing import Mapping, Sequence

from .connector_kernel import AppendOnlyEvidenceLedger, digest


class Environment(str, Enum):
    TEST = "TEST"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


class LifecycleState(str, Enum):
    REGISTERED = "REGISTERED"
    CONFIGURED = "CONFIGURED"
    DEPENDENCIES_VERIFIED = "DEPENDENCIES_VERIFIED"
    READY_FOR_ACTIVATION = "READY_FOR_ACTIVATION"
    ACTIVATED_TEST = "ACTIVATED_TEST"
    ACTIVATED_STAGING = "ACTIVATED_STAGING"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


_ALLOWED_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.REGISTERED: frozenset({LifecycleState.CONFIGURED, LifecycleState.RETIRED}),
    LifecycleState.CONFIGURED: frozenset({LifecycleState.DEPENDENCIES_VERIFIED, LifecycleState.SUSPENDED}),
    LifecycleState.DEPENDENCIES_VERIFIED: frozenset({LifecycleState.READY_FOR_ACTIVATION, LifecycleState.SUSPENDED}),
    LifecycleState.READY_FOR_ACTIVATION: frozenset({LifecycleState.ACTIVATED_TEST, LifecycleState.ACTIVATED_STAGING, LifecycleState.SUSPENDED}),
    LifecycleState.ACTIVATED_TEST: frozenset({LifecycleState.SUSPENDED}),
    LifecycleState.ACTIVATED_STAGING: frozenset({LifecycleState.SUSPENDED}),
    LifecycleState.SUSPENDED: frozenset({LifecycleState.CONFIGURED, LifecycleState.RETIRED}),
    LifecycleState.RETIRED: frozenset(),
}


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


@dataclass(frozen=True)
class CapabilityManifest:
    schema_version: str
    connector_id: str
    connector_version: str
    readable_capabilities: frozenset[str]
    writable_capabilities: frozenset[str]
    supported_environments: frozenset[Environment]
    requires_approval: bool
    emergency_stop_required: bool
    production_activation_authorized: bool = False
    external_send_authorized: bool = False
    github_mutation_authorized: bool = False
    manifest_sha256: str = ""

    @classmethod
    def compile(
        cls,
        *,
        connector_id: str,
        connector_version: str,
        readable_capabilities: Sequence[str],
        writable_capabilities: Sequence[str] = (),
        supported_environments: Sequence[Environment] = (Environment.TEST,),
        requires_approval: bool = True,
        emergency_stop_required: bool = True,
    ) -> "CapabilityManifest":
        if not connector_id or not connector_version:
            raise ValueError("connector identifier and version are required")
        if requires_approval is not True:
            raise PermissionError("connector approval is mandatory")
        if emergency_stop_required is not True:
            raise PermissionError("connector emergency stop is mandatory")
        readable = frozenset(readable_capabilities)
        writable = frozenset(writable_capabilities)
        environments = frozenset(supported_environments)
        if writable:
            raise PermissionError("Increment 12 introduces no writable connector capabilities")
        if Environment.PRODUCTION in environments:
            raise PermissionError("Increment 12 prohibits production connector activation")
        if not environments or not environments.issubset({Environment.TEST, Environment.STAGING}):
            raise PermissionError("unsupported activation environment")
        body = {
            "schema_version": "1.0.0",
            "connector_id": connector_id,
            "connector_version": connector_version,
            "readable_capabilities": sorted(readable),
            "writable_capabilities": [],
            "supported_environments": sorted(item.value for item in environments),
            "requires_approval": True,
            "emergency_stop_required": True,
            "production_activation_authorized": False,
            "external_send_authorized": False,
            "github_mutation_authorized": False,
        }
        return cls(
            schema_version="1.0.0",
            connector_id=connector_id,
            connector_version=connector_version,
            readable_capabilities=readable,
            writable_capabilities=writable,
            supported_environments=environments,
            requires_approval=True,
            emergency_stop_required=True,
            manifest_sha256=digest(body),
        )

    def verify(self) -> None:
        body = {
            "schema_version": self.schema_version,
            "connector_id": self.connector_id,
            "connector_version": self.connector_version,
            "readable_capabilities": sorted(self.readable_capabilities),
            "writable_capabilities": sorted(self.writable_capabilities),
            "supported_environments": sorted(item.value for item in self.supported_environments),
            "requires_approval": self.requires_approval,
            "emergency_stop_required": self.emergency_stop_required,
            "production_activation_authorized": self.production_activation_authorized,
            "external_send_authorized": self.external_send_authorized,
            "github_mutation_authorized": self.github_mutation_authorized,
        }
        if not hmac.compare_digest(self.manifest_sha256, digest(body)):
            raise PermissionError("capability manifest integrity failed")
        if self.requires_approval is not True:
            raise PermissionError("connector approval is mandatory")
        if self.emergency_stop_required is not True:
            raise PermissionError("connector emergency stop is mandatory")
        if self.writable_capabilities or self.production_activation_authorized or self.external_send_authorized or self.github_mutation_authorized:
            raise PermissionError("Increment 12 authority boundary violated")
        if Environment.PRODUCTION in self.supported_environments:
            raise PermissionError("production environment is prohibited")


@dataclass(frozen=True)
class DependencyReceipt:
    dependency_id: str
    required: bool
    satisfied: bool
    evidence_sha256: str
    receipt_sha256: str

    @classmethod
    def compile(
        cls,
        *,
        dependency_id: str,
        required: bool,
        satisfied: bool,
        evidence_sha256: str,
    ) -> "DependencyReceipt":
        body = {
            "dependency_id": dependency_id,
            "required": required,
            "satisfied": satisfied,
            "evidence_sha256": evidence_sha256,
        }
        receipt = cls(
            dependency_id=dependency_id,
            required=required,
            satisfied=satisfied,
            evidence_sha256=evidence_sha256,
            receipt_sha256=digest(body),
        )
        receipt.verify()
        return receipt

    def verify(self) -> None:
        if not self.dependency_id or not _is_sha256(self.evidence_sha256):
            raise PermissionError("dependency receipt is incomplete")
        body = {
            "dependency_id": self.dependency_id,
            "required": self.required,
            "satisfied": self.satisfied,
            "evidence_sha256": self.evidence_sha256,
        }
        if not hmac.compare_digest(self.receipt_sha256, digest(body)):
            raise PermissionError("dependency receipt integrity failed")
        if self.required and not self.satisfied:
            raise PermissionError(f"required dependency is unsatisfied: {self.dependency_id}")


def dependency_set_digest(dependencies: Sequence[DependencyReceipt]) -> str:
    if not dependencies:
        raise PermissionError("non-empty dependency receipts are required")
    identifiers: set[str] = set()
    ordered: list[dict[str, object]] = []
    for dependency in dependencies:
        dependency.verify()
        if dependency.dependency_id in identifiers:
            raise PermissionError("duplicate dependency receipt")
        identifiers.add(dependency.dependency_id)
        ordered.append({
            "dependency_id": dependency.dependency_id,
            "required": dependency.required,
            "satisfied": dependency.satisfied,
            "evidence_sha256": dependency.evidence_sha256,
            "receipt_sha256": dependency.receipt_sha256,
        })
    return digest({"dependencies": sorted(ordered, key=lambda item: str(item["dependency_id"]))})


@dataclass(frozen=True)
class ActivationRecord:
    schema_version: str
    activation_id: str
    connector_id: str
    connector_version: str
    environment: Environment
    requested_capabilities: frozenset[str]
    manifest_sha256: str
    approval_digest: str
    policy_digest: str
    dependency_digest: str
    lifecycle_state: LifecycleState
    actor_id: str
    created_at: str
    production_activation_authorized: bool
    external_send_authorized: bool
    github_mutation_authorized: bool
    activation_sha256: str

    @classmethod
    def compile(
        cls,
        *,
        activation_id: str,
        manifest: CapabilityManifest,
        environment: Environment,
        requested_capabilities: Sequence[str],
        approval_digest: str,
        policy_digest: str,
        dependencies: Sequence[DependencyReceipt],
        actor_id: str,
    ) -> "ActivationRecord":
        manifest.verify()
        if environment is Environment.PRODUCTION or environment not in manifest.supported_environments:
            raise PermissionError("activation environment is not authorized")
        requested = frozenset(requested_capabilities)
        if not requested or not requested.issubset(manifest.readable_capabilities):
            raise PermissionError("requested capability is outside the read-only manifest")
        if any(not _is_sha256(value) for value in (approval_digest, policy_digest)):
            raise PermissionError("bounded approval and policy digests are required")
        dependency_digest = dependency_set_digest(dependencies)
        created_at = datetime.now(timezone.utc).isoformat()
        body = {
            "schema_version": "1.0.0",
            "activation_id": activation_id,
            "connector_id": manifest.connector_id,
            "connector_version": manifest.connector_version,
            "environment": environment.value,
            "requested_capabilities": sorted(requested),
            "manifest_sha256": manifest.manifest_sha256,
            "approval_digest": approval_digest,
            "policy_digest": policy_digest,
            "dependency_digest": dependency_digest,
            "lifecycle_state": LifecycleState.READY_FOR_ACTIVATION.value,
            "actor_id": actor_id,
            "created_at": created_at,
            "production_activation_authorized": False,
            "external_send_authorized": False,
            "github_mutation_authorized": False,
        }
        if not activation_id or not actor_id:
            raise ValueError("activation and actor identifiers are required")
        return cls(
            schema_version="1.0.0",
            activation_id=activation_id,
            connector_id=manifest.connector_id,
            connector_version=manifest.connector_version,
            environment=environment,
            requested_capabilities=requested,
            manifest_sha256=manifest.manifest_sha256,
            approval_digest=approval_digest,
            policy_digest=policy_digest,
            dependency_digest=dependency_digest,
            lifecycle_state=LifecycleState.READY_FOR_ACTIVATION,
            actor_id=actor_id,
            created_at=created_at,
            production_activation_authorized=False,
            external_send_authorized=False,
            github_mutation_authorized=False,
            activation_sha256=digest(body),
        )

    def verify(self, manifest: CapabilityManifest) -> None:
        manifest.verify()
        body = {
            "schema_version": self.schema_version,
            "activation_id": self.activation_id,
            "connector_id": self.connector_id,
            "connector_version": self.connector_version,
            "environment": self.environment.value,
            "requested_capabilities": sorted(self.requested_capabilities),
            "manifest_sha256": self.manifest_sha256,
            "approval_digest": self.approval_digest,
            "policy_digest": self.policy_digest,
            "dependency_digest": self.dependency_digest,
            "lifecycle_state": self.lifecycle_state.value,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
            "production_activation_authorized": self.production_activation_authorized,
            "external_send_authorized": self.external_send_authorized,
            "github_mutation_authorized": self.github_mutation_authorized,
        }
        if not hmac.compare_digest(self.activation_sha256, digest(body)):
            raise PermissionError("activation record integrity failed")
        if self.manifest_sha256 != manifest.manifest_sha256 or self.connector_id != manifest.connector_id:
            raise PermissionError("activation record is not bound to the registered manifest")
        if not _is_sha256(self.dependency_digest):
            raise PermissionError("activation dependency digest is invalid")
        if self.environment is Environment.PRODUCTION:
            raise PermissionError("production activation is prohibited")
        if self.production_activation_authorized or self.external_send_authorized or self.github_mutation_authorized:
            raise PermissionError("activation record expands authority")


class ConnectorRegistry:
    def __init__(self) -> None:
        self._manifests: dict[str, CapabilityManifest] = {}

    def register(self, manifest: CapabilityManifest) -> None:
        manifest.verify()
        current = self._manifests.get(manifest.connector_id)
        if current is not None and current.manifest_sha256 != manifest.manifest_sha256:
            raise PermissionError("connector registration is immutable")
        self._manifests[manifest.connector_id] = manifest

    def get(self, connector_id: str) -> CapabilityManifest:
        try:
            return self._manifests[connector_id]
        except KeyError as exc:
            raise PermissionError("connector is not registered") from exc

    def snapshot(self) -> Mapping[str, str]:
        return {key: value.manifest_sha256 for key, value in sorted(self._manifests.items())}


class ConnectorActivationFramework:
    def __init__(self, *, registry: ConnectorRegistry, ledger: AppendOnlyEvidenceLedger) -> None:
        self.registry = registry
        self.ledger = ledger
        self._states: dict[str, LifecycleState] = {}
        self._dependency_digests: dict[str, str] = {}

    def transition(
        self,
        connector_id: str,
        target: LifecycleState,
        *,
        dependencies: Sequence[DependencyReceipt] | None = None,
    ) -> LifecycleState:
        manifest = self.registry.get(connector_id)
        manifest.verify()
        current = self._states.get(connector_id, LifecycleState.REGISTERED)
        if target not in _ALLOWED_TRANSITIONS[current]:
            raise PermissionError(f"invalid lifecycle transition: {current.value} -> {target.value}")

        dependency_digest_value: str | None = None
        if target is LifecycleState.DEPENDENCIES_VERIFIED:
            dependency_digest_value = dependency_set_digest(tuple(dependencies or ()))
        elif dependencies is not None:
            raise PermissionError("dependency receipts are accepted only for dependency verification")

        if target is LifecycleState.READY_FOR_ACTIVATION and connector_id not in self._dependency_digests:
            raise PermissionError("connector dependencies have not been evidence-verified")

        self._states[connector_id] = target
        if dependency_digest_value is not None:
            self._dependency_digests[connector_id] = dependency_digest_value
        if target in {LifecycleState.CONFIGURED, LifecycleState.SUSPENDED, LifecycleState.RETIRED}:
            self._dependency_digests.pop(connector_id, None)

        event = {
            "event_type": "connector_lifecycle_transition",
            "connector_id": connector_id,
            "manifest_sha256": manifest.manifest_sha256,
            "from_state": current.value,
            "to_state": target.value,
            "production_activation_authorized": False,
            "external_send_authorized": False,
            "github_mutation_authorized": False,
        }
        if dependency_digest_value is not None:
            event["dependency_digest"] = dependency_digest_value
        self.ledger.append(event)
        return target

    def activate(self, record: ActivationRecord) -> ActivationRecord:
        manifest = self.registry.get(record.connector_id)
        record.verify(manifest)
        if self._states.get(record.connector_id) is not LifecycleState.READY_FOR_ACTIVATION:
            raise PermissionError("connector is not ready for activation")
        verified_dependency_digest = self._dependency_digests.get(record.connector_id)
        if verified_dependency_digest is None:
            raise PermissionError("connector dependencies have not been evidence-verified")
        if not hmac.compare_digest(record.dependency_digest, verified_dependency_digest):
            raise PermissionError("activation dependency digest does not match verified lifecycle evidence")
        target = LifecycleState.ACTIVATED_TEST if record.environment is Environment.TEST else LifecycleState.ACTIVATED_STAGING
        if target not in _ALLOWED_TRANSITIONS[LifecycleState.READY_FOR_ACTIVATION]:
            raise PermissionError("activation transition is unavailable")
        activated_body = {
            **{key: value for key, value in record.__dict__.items() if key != "activation_sha256"},
            "lifecycle_state": target,
        }
        serializable = {
            **activated_body,
            "environment": record.environment.value,
            "requested_capabilities": sorted(record.requested_capabilities),
            "lifecycle_state": target.value,
        }
        activated = replace(record, lifecycle_state=target, activation_sha256=digest(serializable))
        activated.verify(manifest)
        self._states[record.connector_id] = target
        self.ledger.append({
            "event_type": "connector_activation",
            "activation_id": activated.activation_id,
            "activation_sha256": activated.activation_sha256,
            "connector_id": activated.connector_id,
            "environment": activated.environment.value,
            "manifest_sha256": activated.manifest_sha256,
            "dependency_digest": activated.dependency_digest,
            "production_activation_authorized": False,
            "external_send_authorized": False,
            "github_mutation_authorized": False,
        })
        return activated
