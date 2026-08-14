from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.epistemic.tool_broker import EpistemicToolBroker
from src.core.nexus.repository_gateway import RepositoryGatewayPolicy
from src.core.nexus.repository_read_executor import (
    GovernedRepositoryReadExecutor,
    repository_request_digest,
)
from src.domain.epistemic.tooling import AgentToolPolicy, ToolCapability
from src.domain.nexus.contextualization import RepositoryReadRequest
from src.domain.nexus.contracts import ExecutionPermit, GovernanceDecision
from src.infrastructure.github.repository_read_port import GitHubActionsReadBoundary
from src.mission_os.connector_adapters import GovernedGitHubKernelAdapter


GATE = "RELEASE_GATE_ONE_LIVE_PRIVATE_GITHUB_READ_CANARY"
TARGET_REPOSITORY = "Lornt1666/AIGC"
TARGET_OPERATION = "READ_FILE"
TARGET_PATH = "docs/architecture/AIGC_NEXUS_GOVERNED_PRIVATE_GITHUB_READ_V1.md"
TARGET_REVISION = "1b0977827791c99de75133ffa6ac29ed97f495c0"
RESOURCE_BASELINE_CI_RUN = 2652
RESOURCE_BASELINE_CI_RUN_ID = 31236985127
RESOURCE_BASELINE_ARTIFACT_ID = 9015753389
RESOURCE_BASELINE_ARTIFACT_DIGEST = "sha256:520ceec38b8ab88c912c7dee0cc48db8d387f882a447c79decedbe5912e14f8a"
IMPLEMENTATION_VERIFIED_HEAD = "24f18a4a30182c318713f8658ff6c9675e4a5719"
IMPLEMENTATION_CI_RUN = 2662
IMPLEMENTATION_CI_RUN_ID = 31238348084
IMPLEMENTATION_ARTIFACT_ID = 9016201297
IMPLEMENTATION_ARTIFACT_DIGEST = "sha256:07063825317c5269b2004a33e4ce920653b7aa01a2dd9d7634a61f64cd43da1f"
PRINCIPAL = "principal:nexus-repository-reader"
AGENT_ID = "AGT-REPOSITORY-READER"


class OneShotLedger:
    def __init__(self) -> None:
        self._claims: dict[str, str] = {}

    def claim(self, idempotency_key: str, request_digest: str):
        existing = self._claims.get(idempotency_key)
        if existing is None:
            self._claims[idempotency_key] = request_digest
            return "claimed"
        return "duplicate" if existing == request_digest else "conflict"


def _authority(now: datetime, request: RepositoryReadRequest, policy: RepositoryGatewayPolicy):
    change_set_hash = canonical_sha256(
        {
            "gate": GATE,
            "repository": TARGET_REPOSITORY,
            "operation": TARGET_OPERATION,
            "path": TARGET_PATH,
            "exact_revision": TARGET_REVISION,
            "maximum_network_requests": 1,
            "maximum_repository_reads": 1,
            "repository_writes": 0,
            "financial_spend_cad": "0.00",
            "implementation_verified_head": IMPLEMENTATION_VERIFIED_HEAD,
            "implementation_ci_run": IMPLEMENTATION_CI_RUN,
        }
    )
    parent_state_hash = canonical_sha256(
        {"repository": TARGET_REPOSITORY, "exact_revision": TARGET_REVISION}
    )
    verifier_report_hash = canonical_sha256(
        {
            "resource_exact_head": TARGET_REVISION,
            "resource_ci_run": RESOURCE_BASELINE_CI_RUN,
            "resource_ci_run_id": RESOURCE_BASELINE_CI_RUN_ID,
            "resource_artifact_id": RESOURCE_BASELINE_ARTIFACT_ID,
            "resource_artifact_digest": RESOURCE_BASELINE_ARTIFACT_DIGEST,
            "implementation_verified_head": IMPLEMENTATION_VERIFIED_HEAD,
            "implementation_ci_run": IMPLEMENTATION_CI_RUN,
            "implementation_ci_run_id": IMPLEMENTATION_CI_RUN_ID,
            "implementation_artifact_id": IMPLEMENTATION_ARTIFACT_ID,
            "implementation_artifact_digest": IMPLEMENTATION_ARTIFACT_DIGEST,
            "conclusion": "success",
        }
    )
    request_digest = repository_request_digest(
        request,
        principal=PRINCIPAL,
        policy=policy,
    )
    decision = GovernanceDecision(
        decision_id="GOV-GITHUB-CANARY01",
        decision="approved",
        authority_source="HUMAN",
        authority_actor="human:repository-owner",
        artifact_state_hash=parent_state_hash,
        change_set_hash=change_set_hash,
        verifier_report_hash=verifier_report_hash,
        exact_revision=TARGET_REVISION,
        conditions=(
            GATE,
            "one network request only",
            "READ_FILE only",
            "zero repository writes",
            "zero financial spend",
            "no automatic retry",
            "pull_request first-run-attempt only",
        ),
        expires_at=now + timedelta(minutes=10),
    )
    repo_scope = f"github://{TARGET_REPOSITORY}"
    permit = ExecutionPermit(
        permit_id="PERMIT-GITHUB-CANARY01",
        governance_decision_id=decision.decision_id,
        principal=PRINCIPAL,
        capability=GovernedRepositoryReadExecutor.CAPABILITY,
        resource_scope=(
            repo_scope,
            f"{repo_scope}/revision/{TARGET_REVISION}",
            f"{repo_scope}/path/{TARGET_PATH}",
        ),
        exact_revision=TARGET_REVISION,
        change_set_hash=change_set_hash,
        request_digest=request_digest,
        expires_at=now + timedelta(minutes=5),
        maximum_invocations=1,
    )
    return decision, permit, change_set_hash, parent_state_hash


def execute_canary(*, output: Path) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    if os.environ.get("GITHUB_EVENT_NAME", "") != "pull_request":
        raise RuntimeError("canary may execute only in a pull_request workflow")
    if os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise RuntimeError("canary may execute only on the first workflow run attempt")
    if os.environ.get("GITHUB_REPOSITORY", "") != TARGET_REPOSITORY:
        raise RuntimeError("canary repository binding mismatch")

    request = RepositoryReadRequest(
        repository=TARGET_REPOSITORY,
        exact_revision=TARGET_REVISION,
        operation=TARGET_OPERATION,
        path_or_query=TARGET_PATH,
        sensitivity="INTERNAL",
    )
    policy = RepositoryGatewayPolicy(
        allowed_repositories=(TARGET_REPOSITORY,),
        allowed_operations=(TARGET_OPERATION,),
        allowed_path_prefixes=(TARGET_PATH,),
        maximum_response_bytes=262144,
        allowed_sensitivities=("INTERNAL",),
        external_reads_enabled=True,
    )
    decision, permit, change_set_hash, parent_state_hash = _authority(now, request, policy)

    broker = EpistemicToolBroker(
        (
            AgentToolPolicy(
                agent_id=AGENT_ID,
                capabilities=(
                    ToolCapability(
                        tool_name=GovernedRepositoryReadExecutor.TOOL_NAME,
                        scopes=("read",),
                        side_effecting=False,
                    ),
                ),
                human_approval_scopes=(),
                maximum_requests_per_run=1,
                maximum_cost_units_per_run=0,
            ),
        ),
        ledger=OneShotLedger(),
        emergency_stop=False,
    )
    boundary = GitHubActionsReadBoundary(maximum_network_requests=1)
    executor = GovernedRepositoryReadExecutor(
        tool_broker=broker,
        gateway_policy=policy,
        github_adapter=GovernedGitHubKernelAdapter(boundary),
        credential_resolver=boundary,
        principal=PRINCIPAL,
        agent_id=AGENT_ID,
        run_id="RUN-GITHUB-CANARY01",
        change_set_id="CHG-GITHUB-CANARY01",
        change_set_hash=change_set_hash,
        parent_state_hash=parent_state_hash,
        authoritative_clock=lambda: now,
        live_external_reads_enabled=True,
        maximum_live_network_requests=1,
    )
    execution = executor.execute(
        request,
        governance_decision=decision,
        permit=permit,
    )
    record = execution.context.records[0]
    if execution.receipt.execution_status != "succeeded":
        raise RuntimeError("canary did not produce a successful ExecutionReceipt")
    if execution.receipt.external_action_performed is not True:
        raise RuntimeError("live canary receipt must record external_action_performed=true")
    if boundary.network_calls != 1 or boundary.real_github_calls != 1:
        raise RuntimeError("live canary must perform exactly one GitHub network request")
    if boundary.repository_writes != 0:
        raise RuntimeError("live canary performed an unexpected repository write")
    if not boundary.canary_consumed:
        raise RuntimeError("live canary authority was not consumed")

    result: dict[str, object] = {
        "schema_version": "aigc.nexus.private-github-read-canary.v1",
        "gate": GATE,
        "repository": TARGET_REPOSITORY,
        "operation": TARGET_OPERATION,
        "path": TARGET_PATH,
        "exact_revision": TARGET_REVISION,
        "resource_baseline_ci_run": RESOURCE_BASELINE_CI_RUN,
        "resource_baseline_ci_run_id": RESOURCE_BASELINE_CI_RUN_ID,
        "resource_baseline_artifact_id": RESOURCE_BASELINE_ARTIFACT_ID,
        "resource_baseline_artifact_digest": RESOURCE_BASELINE_ARTIFACT_DIGEST,
        "implementation_verified_head": IMPLEMENTATION_VERIFIED_HEAD,
        "implementation_ci_run": IMPLEMENTATION_CI_RUN,
        "implementation_ci_run_id": IMPLEMENTATION_CI_RUN_ID,
        "implementation_artifact_id": IMPLEMENTATION_ARTIFACT_ID,
        "implementation_artifact_digest": IMPLEMENTATION_ARTIFACT_DIGEST,
        "request_digest": execution.request_digest,
        "tool_decision": execution.tool_decision.decision,
        "permit_id": permit.permit_id,
        "repository_context_id": execution.context.context_id,
        "repository_context_hash": execution.context.canonical_hash,
        "raw_content_sha256": record.raw_content_sha256,
        "projected_content_sha256": record.projected_content_sha256,
        "redaction_applied": record.redaction_applied,
        "execution_receipt_id": execution.receipt.receipt_id,
        "execution_status": execution.receipt.execution_status,
        "external_action_performed": execution.receipt.external_action_performed,
        "network_requests_attempted": boundary.network_calls,
        "repository_reads_attempted": boundary.real_github_calls,
        "repository_writes": boundary.repository_writes,
        "credentials_used": boundary.credentials_used,
        "canary_consumed": boundary.canary_consumed,
        "remaining_network_requests": 0,
        "live_external_reads_default_after_canary": False,
        "financial_spend_cad": "0.00",
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    serialized = json.dumps(result, sort_keys=True, indent=2) + "\n"
    token = os.environ.get("GITHUB_TOKEN", "")
    if token and token in serialized:
        raise RuntimeError("credential material leaked into canary evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = execute_canary(output=args.output)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
