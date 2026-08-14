from __future__ import annotations

import argparse
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from src.domain.nexus.contracts import EffectClass
from src.domain.nexus.wealth import WealthAction
from src.regenexcalibur.doctrine_models import CoordinatorWorkflow, Modality
from src.integrations.aigc_plugin_bridge import (
    aigc_get_status,
    aigc_render_control_center,
)
from src.operations.employer_sandbox import run_employer_sandbox as run_canonical_employer_sandbox
from src.integrations.mcp.tools import (
    DryRunGoal,
    SandboxScenario,
    assess_aigc_action,
    plan_aigc_alpha_request,
    plan_aigc_llm_lifecycle,
    plan_aigc_regenexcalibur_workflow,
    procure_deep_research_plan,
    plan_aigc_wealth_work,
    run_aigc_dry_run,
    run_aigc_regenexcalibur_diagnostics,
    seed_aigc_regenexcalibur_universe,
)


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def build_mcp_server(*, host: str = "127.0.0.1", port: int = 8000) -> FastMCP:
    server = FastMCP(
        "aigc-nexus",
        instructions=(
            "All tools are local read/simulate operations. They never grant authority, "
            "use credentials, contact employers, submit applications, send messages, or "
            "mutate external systems. BLOCKED_PERMISSION is a truthful terminal result."
        ),
        host=host,
        port=port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )

    @server.tool(
        name="aigc_get_status",
        title="Get AIGC status",
        description="Use this when the user wants the current local AIGC, connector, and occupation-pack status.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def status_tool() -> dict[str, object]:
        return aigc_get_status()

    @server.tool(
        name="aigc_render_control_center",
        title="Render AIGC control center",
        description="Use this to obtain a structured, widget-independent AIGC control-center projection.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def control_center_tool() -> dict[str, object]:
        return aigc_render_control_center()

    @server.tool(
        name="assess_aigc_action",
        title="Assess an AIGC action",
        description="Use this before planning an action to classify consequence and determine whether separate authority is required; this never grants authority.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def assessment_tool(
        intent_id: str,
        effect_class: EffectClass,
        public_read_only: bool = False,
        internal_sandbox_only: bool = False,
        accesses_private_data: bool = False,
        credentials_required: bool = False,
        persistent_internal_mutation: bool = False,
        external_mutation: bool = False,
        communication: bool = False,
        financial_spend_cad: str = "0.00",
        legal_commitment: bool = False,
        security_sensitive: bool = False,
        production_change: bool = False,
        physical_effect: bool = False,
        destructive: bool = False,
        irreversible: bool = False,
        outcome_indeterminate: bool = False,
    ) -> dict[str, object]:
        return assess_aigc_action(
            intent_id=intent_id,
            effect_class=effect_class,
            public_read_only=public_read_only,
            internal_sandbox_only=internal_sandbox_only,
            accesses_private_data=accesses_private_data,
            credentials_required=credentials_required,
            persistent_internal_mutation=persistent_internal_mutation,
            external_mutation=external_mutation,
            communication=communication,
            financial_spend_cad=financial_spend_cad,
            legal_commitment=legal_commitment,
            security_sensitive=security_sensitive,
            production_change=production_change,
            physical_effect=physical_effect,
            destructive=destructive,
            irreversible=irreversible,
            outcome_indeterminate=outcome_indeterminate,
        )

    @server.tool(
        name="run_aigc_dry_run",
        title="Run an AIGC dry run",
        description="Use this when the user wants to preview a governed work-search, application, communication, or daily-work workflow without external action.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def dry_run_tool(goal: DryRunGoal) -> dict[str, object]:
        return run_aigc_dry_run(goal=goal)

    @server.tool(
        name="procure_deep_research_plan",
        title="Procure a Deep Research plan",
        description=(
            "Use this to create a deterministic, source-governed research plan. "
            "It does not retrieve sources, spend money, call a model, or publish."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def deep_research_tool(
        request_id: str,
        question: str,
        intended_decision: str,
        jurisdictions: list[str] | None = None,
        maximum_sources: int = 20,
        maximum_spend_cad: str = "0.00",
    ) -> dict[str, object]:
        return procure_deep_research_plan(
            request_id=request_id,
            question=question,
            intended_decision=intended_decision,
            jurisdictions=jurisdictions,
            maximum_sources=maximum_sources,
            maximum_spend_cad=maximum_spend_cad,
        )

    @server.tool(
        name="aigc_plan_wealth_work",
        title="Plan governed wealth-producing work",
        description=(
            "Use this to coordinate opportunity research, local deliverable production, "
            "applications, sales, revenue tracking, invoices, or transactions. It prepares "
            "a deterministic approval packet and never submits, sends, records, spends, "
            "transfers, trades, signs, or promises a financial outcome."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def wealth_work_tool(
        request_id: str,
        action: WealthAction,
        objective: str,
        target_ref: str | None = None,
        financial_amount_cad: str = "0.00",
        evidence_refs: list[str] | None = None,
    ) -> dict[str, object]:
        return plan_aigc_wealth_work(
            request_id=request_id,
            action=action,
            objective=objective,
            target_ref=target_ref,
            financial_amount_cad=financial_amount_cad,
            evidence_refs=evidence_refs,
        )

    @server.tool(
        name="aigc_seed_regenexcalibur_universe",
        title="Seed the RegenExcalibur universe",
        description=(
            "Use this to validate the canonical 1JGM Genesis seed and create a "
            "deterministic, bounded, zero-egress universe-plan receipt."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def regenexcalibur_seed_tool(
        requested_evolution_depth: int = 1,
    ) -> dict[str, object]:
        return seed_aigc_regenexcalibur_universe(
            requested_evolution_depth=requested_evolution_depth
        )

    @server.tool(
        name="aigc_plan_regenexcalibur_workflow",
        title="Plan a RegenExcalibur employer workflow",
        description=(
            "Use this to prepare an affix-tagged job application, employer-practice "
            "articulation, work-delivery, or invoice workflow. It never authenticates, "
            "submits, signs, sends, charges, or accepts caller-supplied authority."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def doctrine_workflow_tool(
        request_id: str,
        workflow: CoordinatorWorkflow,
        objective: str,
        target_ref: str | None = None,
        artifact_refs: list[str] | None = None,
        consent_artifact_ref: str | None = None,
        credential_ref: str | None = None,
        requested_modalities: list[Modality] | None = None,
    ) -> dict[str, object]:
        return plan_aigc_regenexcalibur_workflow(
            request_id=request_id,
            workflow=workflow,
            objective=objective,
            target_ref=target_ref,
            artifact_refs=artifact_refs,
            consent_artifact_ref=consent_artifact_ref,
            credential_ref=credential_ref,
            requested_modalities=requested_modalities,
        )

    @server.tool(
        name="aigc_run_regenexcalibur_diagnostics",
        title="Run RegenExcalibur blocked-action diagnostics",
        description=(
            "Use this to run six deterministic isolated blocked-action fixtures and "
            "produce an audit-bound acceptance report. No credentials, network, provider, "
            "database, employer, billing, or external system is accessed."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def doctrine_diagnostics_tool() -> dict[str, object]:
        return run_aigc_regenexcalibur_diagnostics()

    @server.tool(
        name="aigc_compose_alpha_plan",
        title="Compose a governed Alpha Plan",
        description=(
            "Use this to turn an objective and optional proposed function calls into a "
            "deterministic hierarchical action graph. It validates and simulates the "
            "plan, returns the exact call sequence, and blocks consequential nodes. "
            "It never executes a function, persists memory, applies a policy update, "
            "uses a credential, or accepts caller-supplied authority."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def alpha_plan_tool(
        request_id: str,
        objective: str,
        domain_profile: Literal[
            "GENERAL", "MULTIMODAL_ECOSYSTEM", "PROCUREMENT_ACCELERATION"
        ] = "GENERAL",
        context_refs: list[str] | None = None,
        operations: list[dict[str, object]] | None = None,
        execution_requested: bool = False,
    ) -> dict[str, object]:
        return plan_aigc_alpha_request(
            request_id=request_id,
            objective=objective,
            domain_profile=domain_profile,
            context_refs=context_refs,
            operations=operations,
            execution_requested=execution_requested,
        )

    @server.tool(
        name="aigc_plan_llm_lifecycle",
        title="Plan the governed AIGC LLM lifecycle",
        description=(
            "Use this to validate and coordinate the canonical data, tokenizer, model, "
            "training, evaluation, and serving lifecycle. It performs no training, "
            "provider call, spend, deployment, or production activation."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def llm_lifecycle_tool() -> dict[str, object]:
        return plan_aigc_llm_lifecycle()

    @server.tool(
        name="aigc_run_employer_sandbox",
        title="Run an employer sandbox scenario",
        description="Use this when the user wants to test one declared occupation capability against a deterministic zero-egress scenario.",
        annotations=READ_ONLY,
        structured_output=True,
    )
    def employer_sandbox_tool(
        mode: Literal["sandbox"] = "sandbox",
        pack_id: str = "OCC-DATA_ANALYSIS_REPORTING",
        capability_id: str = "CAP-DATA_QUALITY",
        scenario: SandboxScenario = "NORMAL_TASK",
    ) -> dict[str, object]:
        return run_canonical_employer_sandbox(
            mode=mode,
            pack_id=pack_id,
            capability_id=capability_id,
            scenario=scenario,
        )

    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the governed AIGC Nexus MCP facade")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_mcp_server(host=args.host, port=args.port).run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
