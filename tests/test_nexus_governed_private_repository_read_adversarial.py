from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest

from src.core.epistemic.tool_broker import EpistemicToolBroker
from src.core.nexus.repository_gateway import RepositoryGatewayPolicy
from src.core.nexus.repository_read_executor import (
    GovernedRepositoryReadError,
    GovernedRepositoryReadExecutor,
    repository_request_digest,
)
from src.domain.epistemic.tooling import AgentToolPolicy, ToolCapability
from src.domain.nexus.contextualization import RepositoryReadObservation, RepositoryReadRequest
from src.domain.nexus.contracts import ExecutionPermit, GovernanceDecision
from src.infrastructure.github.repository_read_port import (
    DeterministicCredentialResolver,
    DeterministicGitHubReadProvider,
    UnavailableCredentialResolver,
)
from src.mission_os.connector_adapters import GovernedGitHubKernelAdapter


NOW = datetime(2026, 8, 8, 3, 30, tzinfo=timezone.utc)
REPO = "Lornt1666/AIGC"
REVISION = "1607a53e4df4aadf11d5e904adcdac6017a834f6"
PRINCIPAL = "principal:nexus-repository-reader"
AGENT_ID = "AGT-REPOSITORY-READER"
CHANGE_SET_HASH = "b" * 64
PARENT_STATE_HASH = "a" * 64


class MemoryLedger:
    def __init__(self) -> None:
        self.claims = {}

    def claim(self, key, digest):
        existing = self.claims.get(key)
        if existing is None:
            self.claims[key] = digest
            return "claimed"
        return "duplicate" if existing == digest else "conflict"


def policy(*, maximum_response_bytes=4096, operations=("READ_FILE",)):
    return RepositoryGatewayPolicy(
        allowed_repositories=(REPO,),
        allowed_operations=operations,
        allowed_path_prefixes=("README.md", "src/", "docs/"),
        maximum_response_bytes=maximum_response_bytes,
        allowed_sensitivities=("INTERNAL",),
        external_reads_enabled=True,
    )


def request(*, repository=REPO, revision=REVISION, path="README.md", operation="READ_FILE"):
    return RepositoryReadRequest(
        repository=repository,
        exact_revision=revision,
        operation=operation,
        path_or_query=path,
        sensitivity="INTERNAL",
    )


def observation(content="truth", *, revision=REVISION, path="README.md", raw_hash=None):
    return RepositoryReadObservation(
        repository=REPO,
        observed_revision=revision,
        operation="READ_FILE",
        path_or_query=path,
        retrieved_at=NOW,
        raw_content=content,
        raw_content_sha256=raw_hash or sha256(content.encode()).hexdigest(),
        source_type="DETERMINISTIC_GITHUB_FIXTURE",
        sensitivity="INTERNAL",
    )


def make_broker(*, emergency_stop=False, capability=True):
    capabilities = (
        ToolCapability(
            tool_name=GovernedRepositoryReadExecutor.TOOL_NAME,
            scopes=("read",),
            side_effecting=False,
        ),
    ) if capability else ()
    return EpistemicToolBroker(
        (
            AgentToolPolicy(
                agent_id=AGENT_ID,
                capabilities=capabilities,
                maximum_requests_per_run=10,
                maximum_cost_units_per_run=0,
            ),
        ),
        ledger=MemoryLedger(),
        emergency_stop=emergency_stop,
    )


def make_authority(value, gateway_policy, *, permit_updates=None, decision_updates=None):
    digest = repository_request_digest(value, principal=PRINCIPAL, policy=gateway_policy)
    decision = GovernanceDecision(
        decision_id="GOV-PRIVATE-READ02",
        decision="approved",
        authority_source="HUMAN",
        authority_actor="human:test-authority",
        artifact_state_hash="c" * 64,
        change_set_hash=CHANGE_SET_HASH,
        verifier_report_hash="d" * 64,
        exact_revision=value.exact_revision,
        expires_at=NOW + timedelta(minutes=10),
    )
    if decision_updates:
        decision = decision.model_copy(update=decision_updates)
    repo_scope = f"github://{value.repository}"
    permit = ExecutionPermit(
        permit_id="PERMIT-PRIVATE-READ02",
        governance_decision_id=decision.decision_id,
        principal=PRINCIPAL,
        capability=GovernedRepositoryReadExecutor.CAPABILITY,
        resource_scope=(
            repo_scope,
            f"{repo_scope}/revision/{value.exact_revision}",
            f"{repo_scope}/path/{value.path_or_query}",
        ),
        exact_revision=value.exact_revision,
        change_set_hash=CHANGE_SET_HASH,
        request_digest=digest,
        expires_at=NOW + timedelta(minutes=5),
        maximum_invocations=2,
    )
    if permit_updates:
        permit = permit.model_copy(update=permit_updates)
    return decision, permit


def make_executor(
    provider,
    *,
    gateway_policy=None,
    tool_broker=None,
    credential_resolver=None,
):
    selected_policy = gateway_policy or policy()
    executor = GovernedRepositoryReadExecutor(
        tool_broker=tool_broker or make_broker(),
        gateway_policy=selected_policy,
        github_adapter=GovernedGitHubKernelAdapter(provider),
        credential_resolver=credential_resolver or DeterministicCredentialResolver(),
        principal=PRINCIPAL,
        agent_id=AGENT_ID,
        run_id="RUN-PRIVATE-READ02",
        change_set_id="CHG-PRIVATE-READ02",
        change_set_hash=CHANGE_SET_HASH,
        parent_state_hash=PARENT_STATE_HASH,
        authoritative_clock=lambda: NOW,
    )
    return executor, selected_policy


def test_missing_authority_is_not_started_and_provider_is_not_called():
    provider = DeterministicGitHubReadProvider((observation(),))
    executor, _ = make_executor(provider)
    with pytest.raises(GovernedRepositoryReadError) as exc_info:
        executor.execute(request(), governance_decision=None, permit=None)
    assert exc_info.value.receipt is not None
    assert exc_info.value.receipt.execution_status == "not_started"
    assert provider.calls == 0


@pytest.mark.parametrize(
    "permit_updates, expected",
    [
        ({"principal": "principal:other"}, "principal mismatch"),
        ({"capability": "SOMETHING_ELSE"}, "capability mismatch"),
        ({"exact_revision": "f" * 40}, "exact revision mismatch"),
        ({"request_digest": "0" * 64}, "request digest mismatch"),
        ({"resource_scope": (f"github://{REPO}",)}, "resource scope mismatch"),
        ({"expires_at": NOW - timedelta(seconds=1)}, "expired"),
    ],
)
def test_invalid_permit_bindings_fail_before_provider(permit_updates, expected):
    provider = DeterministicGitHubReadProvider((observation(),))
    executor, gateway_policy = make_executor(provider)
    decision, permit = make_authority(request(), gateway_policy, permit_updates=permit_updates)
    with pytest.raises((GovernedRepositoryReadError, ValueError), match=expected):
        executor.execute(request(), governance_decision=decision, permit=permit)
    assert provider.calls == 0


def test_nonapproved_or_mismatched_governance_fails_before_provider():
    provider = DeterministicGitHubReadProvider((observation(),))
    executor, gateway_policy = make_executor(provider)
    decision, permit = make_authority(
        request(), gateway_policy, decision_updates={"decision": "denied"}
    )
    with pytest.raises(GovernedRepositoryReadError, match="not approved"):
        executor.execute(request(), governance_decision=decision, permit=permit)
    assert provider.calls == 0


def test_toolbroker_denial_and_emergency_stop_leave_transport_at_zero_calls():
    for selected_broker in (make_broker(capability=False), make_broker(emergency_stop=True)):
        provider = DeterministicGitHubReadProvider((observation(),))
        executor, gateway_policy = make_executor(provider, tool_broker=selected_broker)
        decision, permit = make_authority(request(), gateway_policy)
        with pytest.raises(GovernedRepositoryReadError, match="ToolBroker") as exc_info:
            executor.execute(request(), governance_decision=decision, permit=permit)
        assert exc_info.value.receipt is not None
        assert exc_info.value.receipt.execution_status == "not_started"
        assert provider.calls == 0


def test_unavailable_or_live_credential_resolution_fails_closed_before_adapter():
    provider = DeterministicGitHubReadProvider((observation(),))
    unavailable = UnavailableCredentialResolver()
    executor, gateway_policy = make_executor(provider, credential_resolver=unavailable)
    decision, permit = make_authority(request(), gateway_policy)
    with pytest.raises(GovernedRepositoryReadError) as exc_info:
        executor.execute(request(), governance_decision=decision, permit=permit)
    assert exc_info.value.receipt is not None
    assert exc_info.value.receipt.execution_status == "failed"
    assert provider.calls == 0

    class LiveResolver:
        live_credential_resolution = True
        def resolve(self, **kwargs):
            raise AssertionError("live resolver must never be called")

    provider2 = DeterministicGitHubReadProvider((observation(),))
    executor2, gateway_policy2 = make_executor(provider2, credential_resolver=LiveResolver())
    decision2, permit2 = make_authority(request(), gateway_policy2)
    with pytest.raises(GovernedRepositoryReadError, match="live repository credential"):
        executor2.execute(request(), governance_decision=decision2, permit=permit2)
    assert provider2.calls == 0


def test_floating_revision_is_rejected_before_mock_provider_call():
    floating = request(revision="release/aigc-nexus-v1")
    provider = DeterministicGitHubReadProvider(())
    executor, gateway_policy = make_executor(provider)
    decision, permit = make_authority(floating, gateway_policy)
    with pytest.raises(GovernedRepositoryReadError) as exc_info:
        executor.execute(floating, governance_decision=decision, permit=permit)
    assert exc_info.value.receipt is not None
    assert exc_info.value.receipt.execution_status == "failed"
    assert provider.calls == 0


def test_raw_hash_revision_and_oversize_failures_never_become_context():
    cases = [
        (DeterministicGitHubReadProvider((observation("truth", raw_hash="0" * 64),)), policy()),
        (DeterministicGitHubReadProvider((observation("12345"),)), policy(maximum_response_bytes=4)),
    ]
    for provider, gateway_policy in cases:
        executor, _ = make_executor(provider, gateway_policy=gateway_policy)
        decision, permit = make_authority(request(), gateway_policy)
        with pytest.raises(GovernedRepositoryReadError) as exc_info:
            executor.execute(request(), governance_decision=decision, permit=permit)
        assert exc_info.value.receipt is not None
        assert exc_info.value.receipt.execution_status == "failed"

    class WrongRevisionProvider:
        def __init__(self): self.calls = 0
        def repository_health(self): return {"status": "MOCK"}
        def read_state(self, query):
            self.calls += 1
            value = observation("truth", revision="f" * 40)
            return {
                "repository": value.repository,
                "observed_revision": value.observed_revision,
                "operation": value.operation,
                "path_or_query": value.path_or_query,
                "retrieved_at": value.retrieved_at.isoformat(),
                "raw_content": value.raw_content,
                "raw_content_sha256": value.raw_content_sha256,
                "source_type": value.source_type,
                "sensitivity": value.sensitivity,
            }

    provider = WrongRevisionProvider()
    executor, gateway_policy = make_executor(provider)
    decision, permit = make_authority(request(), gateway_policy)
    with pytest.raises(GovernedRepositoryReadError):
        executor.execute(request(), governance_decision=decision, permit=permit)
    assert provider.calls == 1


def test_credential_like_transport_error_is_redacted_and_raw_chain_is_suppressed():
    secret_value = "fixture" + "-secret-value"
    header_name = "Authori" + "zation"

    class FailingProvider:
        def __init__(self): self.calls = 0
        def repository_health(self): return {"status": "MOCK"}
        def read_state(self, query):
            self.calls += 1
            raise RuntimeError(f"{header_name}: Bearer {secret_value}")

    provider = FailingProvider()
    executor, gateway_policy = make_executor(provider)
    decision, permit = make_authority(request(), gateway_policy)
    with pytest.raises(GovernedRepositoryReadError) as exc_info:
        executor.execute(request(), governance_decision=decision, permit=permit)
    assert secret_value not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert provider.calls == 1


def test_credential_material_is_absent_from_canonical_domain_artifacts():
    secret_value = "gh" + "p_" + "fixturecredentialmaterial1234567890"
    secret_assignment = "to" + "ken=" + secret_value
    provider = DeterministicGitHubReadProvider((observation(f"README {secret_assignment}"),))
    executor, gateway_policy = make_executor(provider)
    decision, permit = make_authority(request(), gateway_policy)
    result = executor.execute(request(), governance_decision=decision, permit=permit)

    artifacts = (
        request().model_dump(mode="json"),
        decision.model_dump(mode="json"),
        permit.model_dump(mode="json"),
        result.receipt.model_dump(mode="json"),
        result.context.model_dump(mode="json"),
    )
    serialized = json.dumps(artifacts, sort_keys=True)
    assert secret_value not in serialized
    assert "[REDACTED_SECRET]" in serialized


def test_existing_github_adapter_still_rejects_mutation_and_exposes_no_write_capability():
    provider = DeterministicGitHubReadProvider((observation(),))
    adapter = GovernedGitHubKernelAdapter(provider)
    with pytest.raises(PermissionError, match="mutation"):
        adapter.execute(
            "READ_REPOSITORY_STATE",
            {"repository": REPO, "mutation": True},
            "0" * 64,
        )
    assert adapter.health()["write_capability_present"] is False
    assert provider.calls == 0
