from __future__ import annotations

from pathlib import Path

from src.core.paycheque_workflow import run_paycheque_workflow


def render_paycheque_workflow_tab(st, root: Path) -> None:
    st.header("Paycheque Pipeline")
    st.write(
        "Prepare earning-oriented opportunities, proposals, milestone actions, and invoice notes. "
        "AIGC only prepares, ranks, drafts, copies, opens, and records internal status. "
        "You manually click any real platform Submit, Apply, Accept, Pay, Purchase, or Deploy button."
    )

    st.warning(
        "No external action is performed. No credentials are used. No platform form is submitted by AIGC."
    )

    config_path = root / "config" / "paycheque_workflow.json"
    st.caption(f"Config: `{config_path}`")

    if st.button("GenerateDailyPipeline", type="primary", use_container_width=True):
        try:
            result = run_paycheque_workflow(root, config_path)
        except Exception as exc:
            st.error(f"Paycheque workflow failed: {exc}")
            return

        pipeline = result["pipeline"]
        st.success("Pipeline prepared. External action remained blocked.")
        col1, col2, col3 = st.columns(3)
        col1.metric("Actions", len(pipeline.get("actions", [])))
        col2.metric("Mode", pipeline.get("mode", "unknown"))
        col3.metric("External action", "No")

        st.subheader("Artifacts")
        st.markdown(f"- Pipeline: `{result['pipeline_path']}`")
        st.markdown(f"- Report: `{result['report_path']}`")
        st.markdown(f"- Audit receipt: `{result['audit_receipt_path']}`")

        st.subheader("Today’s Highest-Impact Actions")
        for index, action in enumerate(pipeline.get("actions", []), start=1):
            with st.expander(f"{index}. {action['title']} — score {action['expected_payoff_score']}", expanded=index == 1):
                st.markdown(f"**Category:** `{action['category']}`")
                st.markdown(f"**Platform:** `{action['platform']}`")
                st.markdown(f"**Boundary:** {action['automation_boundary']}")
                st.markdown("**Prepared draft / note:**")
                st.code(action.get("prepared_text", ""), language="text")
                if action.get("platform_link"):
                    st.markdown(f"[Open platform link manually]({action['platform_link']})")
                st.markdown("**Manual required actions:**")
                for required in action.get("human_required_actions", []):
                    st.markdown(f"- {required}")
                if st.button(f"Mark completed internally: {action['action_id']}", key=f"paycheque_mark_{action['action_id']}"):
                    st.info("Marked complete in this UI session only. No external action was performed.")

    with st.expander("Blocked commit actions", expanded=False):
        blocked = [
            "auto_apply",
            "auto_submit",
            "auto_accept",
            "auto_pay",
            "auto_purchase",
            "auto_deploy",
            "auto_use_credentials",
            "secret_logging",
            "self_approval",
        ]
        for item in blocked:
            st.markdown(f"- `{item}`")
