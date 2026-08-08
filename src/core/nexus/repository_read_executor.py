from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.epistemic.tool_broker import EpistemicToolBroker
from src.core.nexus.repository_gateway import (
    NexusRepositoryGateway,
    RepositoryGatewayPolicy,
    repository_gateway_policy_hash,
)
from src.domain.epistemic.tooling import ToolDecisionReceipt, ToolInvocationRequest
from src.domain.nexus.contextualization import RepositoryContext, RepositoryReadRequest
from src.domain.nexus.contracts import (
    ExecutionPermit,
    ExecutionReceipt,
    GovernanceDecision,
    OperationReceipt,
)
from src.infrastructure.github.repository_read_port import (
    GitHubRepositoryReadPort,
    RepositoryCredentialResolver,
)
from src.mission_os.connector_adapters import GovernedGitHubKernelAdapter


@dataclass(frozen=True)
class RepositoryReadExecution:
    context: RepositoryContext
    receipt: ExecutionReceipt
    tool_decision: ToolDecisionReceipt
    request_digest: str


class GovernedRepositoryReadError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        receipt: ExecutionReceipt | None = None,
        tool_decision: ToolDecisionReceipt | None = None,
    ) -> None:
        super().__init__(message)
        self.receipt = receipt
        self.tool_decision = tool_decision


def repository_request_digest(
    request: RepositoryReadRequest,
    *,
    principal: str,
    policy: RepositoryGatewayPolicy,
) -> str:
    return canonical_sha256(
        {
            "repository": request.repository,
            "exact_revision": request.exact_revision,
            "operation": request.operation,
            "path_or_query": request.path_or_query,
            "sensitivity": request.sensitivity,
            "principal": principal,
            "gateway_policy_hash": repository_gateway_policy_hash(policy),
            "maximum_response_bytes": policy.maximum_response_bytes,
        }
    )


class GovernedRepositoryReadExecutor:
    """Canonical implementation-only execution boundary for private repository reads.

    It reuses GovernanceDecision, ExecutionPermit, EpistemicToolBroker, the admitted
    NexusRepositoryGateway and the legacy read-only GitHub adapter. Live credentials
    and live network transport are explicitly unavailable in this release gate.
    """

    TOOL_NAME = "nexus_repository_read"
    CAPABILITY = "READ_REPOSITORY_STATE"

    def __init__(
        self,
        *,
        tool_broker: EpistemicToolBroker,
        gateway_policy: RepositoryGatewayPolicy,
        github_adapter: GovernedGitHubKernelAdapter,
        credential_resolver: RepositoryCredentialResolver,
        principal: str,
        agent_id: str,
        run_id: str,
        change_set_id: str,
        change_set_hash: str,
        parent_state_hash: str,
        authoritative_clock: Callable[[], datetime],
    ) -> None:
        if not principal.strip():
            raise ValueError("repository read executor principal is required")
        if not agent_id.strip() or not run_id.strip():
            raise ValueError("repository read executor agent_id and run_id are required")
        if not change_set_id.strip():
            raise ValueError("repository read executor change_set_id is required")
        if len(change_set_hash) != 64 or any(ch not in "0123456789abcdef" for ch in change_set_hash):
            raise ValueError("repository read executor change_set_hash must be SHA-256")
        if len(parent_state_hash) != 64 or any(ch not in "0123456789abcdef" for ch in parent_state_hash):
            raise ValueError("repository read executor parent_state_hash must be SHA-256")
        if not gateway_policy.external_reads_enabled:
            raise ValueError("governed external repository executor requires an explicit external-read gateway policy")
        self._tool_broker = tool_broker
        self._policy = gateway_policy
        self._github_adapter = github_adapter
        self._credential_resolver = credential_resolver
        self._principal = principal
        self._agent_id = agent_id
        self._run_id = run_id
        self._change_set_id = change_set_id
        self._change_set_hash = change_set_hash
        self._parent_state_hash = parent_state_hash
        self._clock = authoritative_clock
        self._permit_invocations: dict[str, int] = {}

    def execute(
        self,
        request: RepositoryReadRequest,
        *,
        governance_decision: GovernanceDecision | None,
        permit: ExecutionPermit | None,
    ) -> RepositoryReadExecution:
        authoritative_now = self._clock()
        if authoritative_now.tzinfo is None or authoritative_now.utcoffset() is None:
            raise GovernedRepositoryReadError("authoritative clock must be timezone-aware")
        request_digest = repository_request_digest(
            request,
            principal=self._principal,
            policy=self._policy,
        )

        if governance_decision is None or permit is None:
            receipt = self._receipt(
                request=request,
                permit=permit,
                status="not_started",
                failure_class="EXPLICIT_AUTHORITY_REQUIRED",
            )
            raise GovernedRepositoryReadError(
                "governed repository read requires GovernanceDecision and ExecutionPermit",
                receipt=receipt,
            )

        self._validate_authority(
            request,
            governance_decision=governance_decision,
            permit=permit,
            authoritative_now=authoritative_now,
            request_digest=request_digest,
        )
        invocation_count = self._permit_invocations.get(permit.permit_id, 0)
        if invocation_count >= permit.maximum_invocations:
            receipt = self._receipt(
                request=request,
                permit=permit,
                status="not_started",
                failure_class="PERMIT_INVOCATION_LIMIT_EXCEEDED",
            )
            raise GovernedRepositoryReadError(
                "ExecutionPermit maximum_invocations exceeded",
                receipt=receipt,
            )

        tool_request = self._tool_request(request)
        tool_decision = self._tool_broker.evaluate(tool_request)
        if tool_decision.decision != "POLICY_PERMIT_PENDING_EXECUTION_GATE":
            receipt = self._receipt(
                request=request,
                permit=permit,
                status="not_started",
                failure_class=f"TOOL_BROKER_{tool_decision.decision}",
            )
            raise GovernedRepositoryReadError(
                "ToolBroker did not admit repository read intent",
                receipt=receipt,
                tool_decision=tool_decision,
            )

        self._permit_invocations[permit.permit_id] = invocation_count + 1
        if self._credential_resolver.live_credential_resolution:
            receipt = self._receipt(
                request=request,
                permit=permit,
                status="not_started",
                failure_class="LIVE_CREDENTIAL_RESOLUTION_PROHIBITED",
            )
            raise GovernedRepositoryReadError(
                "live repository credential resolution is prohibited in this release gate",
                receipt=receipt,
                tool_decision=tool_decision,
            )

        try:
            capability = self._credential_resolver.resolve(
                permit=permit,
                repository=request.repository,
                authoritative_now=authoritative_now,
            )
            port = GitHubRepositoryReadPort(
                adapter=self._github_adapter,
                credential_capability=capability,
                authoritative_now=authoritative_now,
                live_external_reads_enabled=False,
            )
            gateway = NexusRepositoryGateway(port=port, policy=self._policy)
            context = gateway.read_context((request,))
        except Exception as exc:
            receipt = self._receipt(
                request=request,
                permit=permit,
                status="failed",
                failure_class=type(exc).__name__,
            )
            raise GovernedRepositoryReadError(
                "deterministic repository read execution failed",
                receipt=receipt,
                tool_decision=tool_decision,
            ) from exc

        receipt = self._receipt(
            request=request,
            permit=permit,
            status="succeeded",
            context=context,
        )
        return RepositoryReadExecution(
            context=context,
            receipt=receipt,
            tool_decision=tool_decision,
            request_digest=request_digest,
        )

    def _validate_authority(
        self,
        request: RepositoryReadRequest,
        *,
        governance_decision: GovernanceDecision,
        permit: ExecutionPermit,
        authoritative_now: datetime,
        request_digest: str,
    ) -> None:
        if governance_decision.decision != "approved":
            raise GovernedRepositoryReadError("GovernanceDecision is not approved")
        if governance_decision.decision_id != permit.governance_decision_id:
            raise GovernedRepositoryReadError("ExecutionPermit governance decision binding mismatch")
        if governance_decision.change_set_hash != self._change_set_hash:
            raise GovernedRepositoryReadError("GovernanceDecision ChangeSet hash mismatch")
        if governance_decision.exact_revision != request.exact_revision:
            raise GovernedRepositoryReadError("GovernanceDecision exact revision mismatch")
        if governance_decision.expires_at is not None:
            if governance_decision.expires_at.tzinfo is None or governance_decision.expires_at.utcoffset() is None:
                raise GovernedRepositoryReadError("GovernanceDecision expiry must be timezone-aware")
            if governance_decision.expires_at <= authoritative_now:
                raise GovernedRepositoryReadError("GovernanceDecision is expired")

        permit.verify_temporal_validity(authoritative_now=authoritative_now)
        if permit.principal != self._principal:
            raise GovernedRepositoryReadError("ExecutionPermit principal mismatch")
        if permit.capability != self.CAPABILITY:
            raise GovernedRepositoryReadError("ExecutionPermit capability mismatch")
        if permit.exact_revision != request.exact_revision:
            raise GovernedRepositoryReadError("ExecutionPermit exact revision mismatch")
        if permit.change_set_hash != self._change_set_hash:
            raise GovernedRepositoryReadError("ExecutionPermit ChangeSet hash mismatch")
        if permit.request_digest != request_digest:
            raise GovernedRepositoryReadError("ExecutionPermit repository request digest mismatch")

        repo_scope = f"github://{request.repository}"
        revision_scope = f"{repo_scope}/revision/{request.exact_revision}"
        path_scope = f"{repo_scope}/path/{request.path_or_query}"
        required_scopes = {repo_scope, revision_scope, path_scope}
        if not required_scopes.issubset(set(permit.resource_scope)):
            raise GovernedRepositoryReadError("ExecutionPermit repository resource scope mismatch")

    def _tool_request(self, request: RepositoryReadRequest) -> ToolInvocationRequest:
        provisional = ToolInvocationRequest(
            request_id="TOOL-" + canonical_sha256(
                {
                    "run_id": self._run_id,
                    "repository": request.repository,
                    "revision": request.exact_revision,
                    "operation": request.operation,
                    "path": request.path_or_query,
                }
            )[:24].upper(),
            run_id=self._run_id,
            agent_id=self._agent_id,
            exact_revision=request.exact_revision,
            tool_name=self.TOOL_NAME,
            scope="read",
            purpose="governed exact-revision private repository read",
            resource_id=f"github://{request.repository}/path/{request.path_or_query}",
            parameters={
                "repository": request.repository,
                "revision": request.exact_revision,
                "operation": request.operation,
                "path": request.path_or_query,
                "sensitivity": request.sensitivity,
                "mutation": False,
            },
            idempotency_key="0" * 64,
            estimated_cost_units=0,
            approval_reference=None,
        )
        digest = self._tool_broker.request_digest(provisional)
        return provisional.model_copy(update={"idempotency_key": digest})

    def _receipt(
        self,
        *,
        request: RepositoryReadRequest,
        permit: ExecutionPermit | None,
        status: str,
        failure_class: str | None = None,
        context: RepositoryContext | None = None,
    ) -> ExecutionReceipt:
        resource_ref = f"github://{request.repository}/revision/{request.exact_revision}/path/{request.path_or_query}"
        operation = OperationReceipt(
            operation_id="REPOSITORY_READ",
            status=status,
            resource_ref=resource_ref,
            before_hash=None,
            after_hash=context.canonical_hash if context is not None else None,
            failure_class=failure_class,
            retryable=False if status in {"failed", "indeterminate"} else None,
            evidence_refs=(context.context_id,) if context is not None else (),
        )
        identity = {
            "permit_id": permit.permit_id if permit is not None else None,
            "change_set_id": self._change_set_id,
            "parent_state_hash": self._parent_state_hash,
            "status": status,
            "resource_ref": resource_ref,
            "failure_class": failure_class,
            "context_id": context.context_id if context is not None else None,
        }
        receipt_id = "EXEC-REPO-" + canonical_sha256(identity)[:24].upper()
        return ExecutionReceipt(
            receipt_id=receipt_id,
            permit_id=permit.permit_id if permit is not None else None,
            change_set_id=self._change_set_id,
            parent_state_hash=self._parent_state_hash,
            execution_status=status,
            operations=(operation,),
            external_action_performed=False,
            reconciliation_required=status == "indeterminate",
        )
