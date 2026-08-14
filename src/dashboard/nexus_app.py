from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.epistemic.verifier import DeterministicEpistemicVerifier  # noqa: E402
from src.core.nexus.orchestrator import DryRunGovernanceOrchestrator, DryRunRound  # noqa: E402
from src.core.nexus.specialist_registry import select_specialists  # noqa: E402
from src.domain.epistemic.models import ArtifactState  # noqa: E402
from src.domain.epistemic.verification import UtilityWeights  # noqa: E402
from src.domain.nexus.contracts import WorkOrder  # noqa: E402
from src.webapp.nexus_dashboard import build_nexus_dashboard_snapshot  # noqa: E402


_EXACT_REVISION = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
DEFAULT_WEIGHTS = UtilityWeights(
    fidelity=0.30,
    evidence=0.25,
    completeness=0.20,
    redundancy=0.10,
    unsupported=0.15,
)


def build_demo_run(work_order: WorkOrder, exact_revision: str):
    if not _EXACT_REVISION.fullmatch(exact_revision):
        raise ValueError("Nexus demo requires an exact 40- or 64-character hexadecimal revision")
    verifier = DeterministicEpistemicVerifier(weights=DEFAULT_WEIGHTS, utility_threshold=0.0)
    orchestrator = DryRunGovernanceOrchestrator(verifier, exact_revision=exact_revision)
    initial = ArtifactState(stage="ingest", revision=1)
    round_one = DryRunRound(
        1,
        ArtifactState(stage="architect", revision=2),
        ArtifactState(stage="critic", revision=3),
        ArtifactState(stage="synthesizer", revision=4),
    )
    return orchestrator.execute(work_order, initial, (round_one,))


def main() -> int:
    try:
        import streamlit as st  # type: ignore
    except ImportError:
        print("Streamlit is not installed. Run: python -m pip install -r requirements.txt")
        return 1

    st.set_page_config(page_title="AIGC Nexus V1", layout="wide")
    st.title("AIGC Nexus V1")
    st.caption(
        "Integrated brain, governance visibility, artifact state, and evidence — live/runtime capabilities remain governed and default-deny."
    )

    st.sidebar.header("System Boundary")
    st.sidebar.success("Frozen contract: AIGC_INTEGRATION_CONTRACT_V1")
    st.sidebar.warning("ToolBroker: GOVERNED / DEFAULT DENY")
    st.sidebar.warning("External execution: GOVERNED / DEFAULT DENY")
    st.sidebar.warning("Production activation: DISABLED")

    release_revision = os.environ.get("AIGC_RELEASE_REVISION", "").strip().lower()
    if not _EXACT_REVISION.fullmatch(release_revision):
        release_revision = ""

    with st.sidebar.form("nexus_work_order"):
        objective = st.text_area("Work Order", value="Integrate and validate AIGC Nexus V1")
        tags = st.text_input("Domain tags", value="software,security,dashboard")
        exact_revision = st.text_input(
            "Exact revision",
            value=release_revision,
            placeholder="40- or 64-character hexadecimal commit SHA",
        )
        submitted = st.form_submit_button("Run deterministic dry-run")

    work_order = WorkOrder(
        work_order_id="WO-NEXUSUI01",
        objective=objective.strip() or "Integrate AIGC Nexus V1",
        domain_tags=tuple(item.strip() for item in tags.split(",") if item.strip()),
    )
    specialists = select_specialists(work_order)

    result = None
    if submitted:
        normalized_revision = exact_revision.strip().lower()
        if not _EXACT_REVISION.fullmatch(normalized_revision):
            st.sidebar.error("Enter an exact 40- or 64-character hexadecimal revision; branch names are not evidence revisions.")
        else:
            result = build_demo_run(work_order, normalized_revision)

    findings = ()
    governance_state = "LOCKED"
    if result is not None:
        findings = tuple(
            finding.model_dump(mode="json")
            for report in result.reports
            for finding in report.findings
        )
        governance_state = result.terminal_state.upper()

    snapshot = build_nexus_dashboard_snapshot(
        work_order=work_order,
        verifier_findings=findings,
        governance_state=governance_state,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Governance", snapshot["system"]["governance"])
    col2.metric("Verifier", snapshot["system"]["verifier"])
    col3.metric("ToolBroker", snapshot["system"]["toolbroker"])
    col4.metric("External execution", snapshot["system"]["external_execution"])

    tab_graph, tab_artifacts, tab_verifier, tab_governance, tab_connectors, tab_memory, tab_evidence = st.tabs(
        ["Run Graph", "Artifact Canvas", "Verifier", "Governance", "Connections", "Memory", "Evidence"]
    )

    with tab_graph:
        st.subheader("Cognitive topology")
        st.code(" -> ".join(snapshot["run_graph"]), language="text")
        st.subheader("Available governed runtime surfaces")
        st.json(snapshot["available_runtime_surfaces"])
        st.subheader("Selected specialists")
        if specialists:
            st.dataframe([{
                "specialist": item.specialist_id,
                "domain": item.domain,
                "capabilities": ", ".join(item.capabilities),
                "external_action_allowed": item.external_action_allowed,
            } for item in specialists], use_container_width=True)
        else:
            st.info("No specialist matched the current domain tags.")
        if result is not None:
            st.success(f"Dry-run terminal state: {result.terminal_state}")
            st.code(result.run_id, language="text")

    with tab_artifacts:
        st.subheader("Artifact State / ChangeSet / Diff")
        st.info("Write-through is disabled. This canvas is inspection-only in the current release train.")
        st.json(snapshot["artifact_canvas"])
        if result is not None:
            st.write("Final canonical state")
            st.json(result.final_state.model_dump(mode="json"))

    with tab_verifier:
        st.subheader("Verifier findings")
        if snapshot["verifier_findings"]:
            st.dataframe(snapshot["verifier_findings"], use_container_width=True)
        else:
            st.success("No verifier findings in the current projection.")

    with tab_governance:
        st.subheader("Governance console")
        st.metric("Current state", snapshot["governance_state"])
        st.write("Available operator intents: " + ", ".join(snapshot["approval_actions"]))
        st.warning("These controls are presentation-only. They do not mint GovernanceDecisions or ExecutionPermits.")
        if result is not None:
            st.json([decision.model_dump(mode="json") for decision in result.decisions])

    with tab_connectors:
        st.subheader("Employment and AI connections")
        st.warning(
            "A connector status is capability evidence, not execution authority. "
            "Gmail, Indeed, generic websites, and portable AI ports remain blocked or handoff-only."
        )
        st.dataframe(snapshot["connectors"]["records"], use_container_width=True)
        st.metric(
            "Enabled live mutation capabilities",
            snapshot["connectors"]["enabled_live_mutation_capabilities"],
        )

    with tab_memory:
        st.subheader("Memory / strategic context")
        st.info("Persistent memory adapters are available but are not auto-connected to this deterministic demo. Memory cannot grant authority.")
        st.json({
            "work_order": work_order.work_order_id,
            "objective": work_order.objective,
            "domain_tags": work_order.domain_tags,
            "persistent_memory_adapter": snapshot["system"]["memory_adapter"],
            "auto_connected": False,
            "grants_authority": False,
        })

    with tab_evidence:
        st.subheader("Evidence / receipts")
        st.info("This demo run is deterministic and provider-free. Live provider evidence is admitted only through governed runtime receipts.")
        if result is not None:
            payload = {
                "run_id": result.run_id,
                "terminal_state": result.terminal_state,
                "external_action_performed": result.external_action_performed,
                "reports": [report.model_dump(mode="json") for report in result.reports],
                "decisions": [decision.model_dump(mode="json") for decision in result.decisions],
            }
            st.json(payload)
            st.download_button(
                "Download dry-run evidence",
                json.dumps(payload, indent=2),
                file_name="aigc_nexus_dry_run_evidence.json",
                mime="application/json",
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
