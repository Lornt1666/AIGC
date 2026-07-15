from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dashboard.job_interview_panel import render_jobs_interviews_tab  # noqa: E402
from src.dashboard.operator_cockpit_app import (  # noqa: E402
    render_audit_tab,
    render_review_tab,
    render_run_tab,
    render_work_order_tab,
)
from src.dashboard.operator_initialization_panel import (  # noqa: E402
    render_operator_initialization_tab,
)
from src.dashboard.paycheque_workflow_panel import (  # noqa: E402
    render_paycheque_workflow_tab,
)


def main() -> int:
    try:
        import streamlit as st  # type: ignore
    except ImportError:
        print("Streamlit is not installed. Run: python -m pip install -r requirements.txt")
        return 1

    st.set_page_config(page_title="AIGC Operator Cockpit", layout="wide")
    st.title("AIGC Operator Cockpit")
    st.caption(
        "Initialize safely. Prepare work. Review exact contents. Accept only for bounded internal or manual-operator next steps."
    )

    root = PROJECT_ROOT
    st.sidebar.header("Control Plane")
    st.sidebar.write(f"Project root: `{root}`")
    st.sidebar.warning(
        "No external submission, messaging, scheduling, contract acceptance, credential use, Terraform apply, or deployment is automatic."
    )

    (
        tab_initialize,
        tab_run,
        tab_jobs,
        tab_work_order,
        tab_paycheque,
        tab_review,
        tab_audit,
    ) = st.tabs(
        [
            "Initialize",
            "Run",
            "Jobs & Interviews",
            "New Work Order",
            "Paycheque Pipeline",
            "Review & Accept",
            "Audit / Transparency",
        ]
    )

    with tab_initialize:
        render_operator_initialization_tab(st, root)
    with tab_run:
        render_run_tab(st, root)
    with tab_jobs:
        render_jobs_interviews_tab(st, root)
    with tab_work_order:
        render_work_order_tab(st, root)
    with tab_paycheque:
        render_paycheque_workflow_tab(st, root)
    with tab_review:
        render_review_tab(st, root)
    with tab_audit:
        render_audit_tab(st, root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
