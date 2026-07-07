from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.operator_cockpit import (  # noqa: E402
    DEFAULT_AUTHORIZATIONS_PATH,
    SAFETY_BOUNDARY,
    AuthorizationReview,
    build_accept_command,
    build_deny_command,
    build_enterprise_run_commands,
    build_revise_command,
    load_authorization_packets,
    load_work_order_governance_records,
    render_review_markdown,
    reviews_to_dicts,
    run_command,
    summarize_authorizations,
)


def main() -> int:
    try:
        import streamlit as st  # type: ignore
    except ImportError:
        print("Streamlit is not installed. Run: python -m pip install -r requirements.txt")
        return 1

    st.set_page_config(page_title="AIGC Operator Cockpit", layout="wide")
    st.title("AIGC Operator Cockpit")
    st.caption("Run governed work cycles. Review scoped contents. Accept only what you can see.")

    root = PROJECT_ROOT
    st.sidebar.header("Control Plane")
    st.sidebar.write(f"Project root: `{root}`")
    st.sidebar.warning(
        "No external action is performed by this cockpit. Accept only records scoped approval for Phase 6 eligibility."
    )

    tab_run, tab_review, tab_audit = st.tabs(["Run", "Review & Accept", "Audit / Transparency"])

    with tab_run:
        render_run_tab(st, root)

    with tab_review:
        render_review_tab(st, root)

    with tab_audit:
        render_audit_tab(st, root)

    return 0


def render_run_tab(st, root: Path) -> None:
    st.header("Run Governed Enterprise Cycle")
    st.write(
        "The run button executes the internal readiness chain: preflight, connector governance, secret-vault fake test, "
        "radar, assessment, drafting, approval-packet generation, finance, compliance, fidelity, satisfaction, quality, "
        "work-order governance, productization readiness, observability, and schema validation."
    )

    commands = build_enterprise_run_commands(root)
    with st.expander("Exact run sequence", expanded=False):
        for index, governed in enumerate(commands, start=1):
            st.markdown(f"**{index}. {governed.label}** — `{governed.safety_class}`")
            st.code(" ".join(governed.command), language="powershell")

    stop_on_failure = st.checkbox("Stop immediately if any governance step fails", value=True)
    if st.button("Run governed cycle", type="primary", use_container_width=True):
        progress = st.progress(0)
        results = []
        for index, governed in enumerate(commands, start=1):
            st.subheader(f"{index}. {governed.label}")
            st.caption(f"Safety class: {governed.safety_class}")
            result = run_command(governed.command, root=root, label=governed.label)
            results.append(result)
            progress.progress(index / len(commands))
            if result.ok:
                st.success(f"Completed: {governed.label}")
            else:
                st.error(f"Failed: {governed.label} exited with {result.returncode}")
            with st.expander("Command output", expanded=not result.ok):
                st.code((result.stdout or "").strip()[-8000:] or "(no stdout)", language="text")
                if result.stderr:
                    st.code(result.stderr.strip()[-8000:], language="text")
            if stop_on_failure and not result.ok:
                st.warning("Run stopped by governance setting.")
                break

        payload = [
            {
                "label": result.label,
                "command": result.command,
                "returncode": result.returncode,
                "ok": result.ok,
                "stdout_tail": result.stdout[-2000:],
                "stderr_tail": result.stderr[-2000:],
            }
            for result in results
        ]
        st.download_button(
            "Download run receipt",
            json.dumps(payload, indent=2),
            file_name="aigc_operator_cockpit_run_receipt.json",
            mime="application/json",
        )


def render_review_tab(st, root: Path) -> None:
    st.header("Human Reviewable Contents")
    packets = load_authorization_packets(root)
    work_orders = load_work_order_governance_records(root)
    reviews = summarize_authorizations(packets, work_orders)

    pending_reviews = [
        review for review in reviews
        if review.decision == "pending" and not review.expired and not review.external_action_performed
    ]
    expired_reviews = [review for review in reviews if review.expired and review.decision == "pending"]
    approved_reviews = [review for review in reviews if review.decision == "approved_for_phase_6"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Packets", len(reviews))
    col2.metric("Pending Review", len(pending_reviews))
    col3.metric("Expired Pending", len(expired_reviews))
    col4.metric("Approved", len(approved_reviews))

    if reviews:
        st.dataframe(
            [
                {
                    "action_id": review.action_id,
                    "decision": review.decision,
                    "expired": review.expired,
                    "recipient": review.recipient,
                    "platform": review.platform,
                    "risk": review.risk_class,
                    "quality_state": review.quality_state,
                }
                for review in reviews
            ],
            use_container_width=True,
        )
    else:
        st.info("No authorization packets found. Use Run first to generate reviewable packets.")
        return

    selectable = pending_reviews or [review for review in reviews if review.decision == "pending"] or reviews
    selected_action_id = st.selectbox(
        "Select one action for review",
        [review.action_id for review in selectable],
        format_func=lambda action_id: format_action_label(action_id, selectable),
    )
    selected = next(review for review in selectable if review.action_id == selected_action_id)

    st.markdown(render_review_markdown(selected))
    with st.expander("Full structured review JSON", expanded=False):
        st.json(reviews_to_dicts([selected])[0])

    st.subheader("Decision")
    if selected.expired:
        st.error("This packet is expired. Regenerate Phase 5 packets before acceptance.")
    if selected.external_action_performed:
        st.error("This packet reports external_action_performed=true and cannot be accepted from the cockpit.")
    if selected.decision != "pending":
        st.info(f"This packet is already `{selected.decision}`.")

    st.code(selected.required_phrase or "(accept phrase missing)", language="text")
    reviewed = st.checkbox(
        "I reviewed the exact action, artifact hash, risk state, expiry, blocked actions, and no-external-action boundary.",
        value=False,
    )

    accept_disabled = (
        not reviewed
        or selected.expired
        or selected.external_action_performed
        or selected.decision != "pending"
        or not selected.required_phrase
    )
    deny_disabled = selected.decision != "pending" or not selected.denial_phrase
    revise_disabled = selected.decision != "pending"

    col_accept, col_deny = st.columns(2)
    with col_accept:
        if st.button("Accept selected action", type="primary", disabled=accept_disabled, use_container_width=True):
            result = run_command(
                build_accept_command(root, selected, DEFAULT_AUTHORIZATIONS_PATH),
                root=root,
                label=f"Accept {selected.action_id}",
            )
            render_decision_result(st, result)
            st.info("Refresh the review table to see the updated packet state.")
    with col_deny:
        if st.button("Deny selected action", disabled=deny_disabled, use_container_width=True):
            result = run_command(
                build_deny_command(root, selected, DEFAULT_AUTHORIZATIONS_PATH),
                root=root,
                label=f"Deny {selected.action_id}",
            )
            render_decision_result(st, result)
            st.info("Refresh the review table to see the updated packet state.")

    revision = st.text_area(
        "Revision instructions",
        placeholder="Example: strengthen technical proof, reduce claims, clarify pricing, or resolve compliance blocker.",
    )
    if st.button("Request revision", disabled=revise_disabled or not revision.strip(), use_container_width=True):
        result = run_command(
            build_revise_command(root, selected, revision, DEFAULT_AUTHORIZATIONS_PATH),
            root=root,
            label=f"Revise {selected.action_id}",
        )
        render_decision_result(st, result)
        st.info("Refresh the review table to see the updated packet state.")


def render_audit_tab(st, root: Path) -> None:
    st.header("Audit / Transparency")
    st.subheader("Safety Boundary")
    for item in SAFETY_BOUNDARY:
        st.markdown(f"- {item}")

    st.subheader("Primary Artifacts")
    artifacts = [
        "data/phase5_authorizations/aigc_phase5_authorization_packets.json",
        "data/phase6_execution/aigc_phase6_execution_receipts.json",
        "data/phase12_observability/system_snapshot.json",
        "data/phase23_work_orders/aigc_phase23_work_order_governance_records.json",
        "reports/phase14_runtime_preflight.md",
        "reports/milestone_k_work_order_governor_report.md",
    ]
    for relative_path in artifacts:
        path = root / relative_path
        exists = path.exists()
        st.markdown(f"- `{'present' if exists else 'missing'}` — `{relative_path}`")
        if exists and path.suffix in {".json", ".md"}:
            with st.expander(f"Preview {relative_path}", expanded=False):
                try:
                    st.code(path.read_text(encoding="utf-8")[:8000], language="json" if path.suffix == ".json" else "markdown")
                except UnicodeDecodeError:
                    st.write("Preview unavailable for binary file.")

    st.subheader("Emergency Controls")
    col_stop, col_clear = st.columns(2)
    with col_stop:
        if st.button("Enable emergency stop", use_container_width=True):
            result = run_command(
                [sys.executable, str(root / "src" / "aigc.py"), "--root", str(root), "emergency-stop"],
                root=root,
                label="Emergency stop",
            )
            render_decision_result(st, result)
    with col_clear:
        if st.button("Clear emergency stop", use_container_width=True):
            result = run_command(
                [sys.executable, str(root / "src" / "aigc.py"), "--root", str(root), "clear-emergency-stop"],
                root=root,
                label="Clear emergency stop",
            )
            render_decision_result(st, result)


def render_decision_result(st, result) -> None:
    if result.ok:
        st.success(f"{result.label} completed.")
    else:
        st.error(f"{result.label} failed with code {result.returncode}.")
    if result.stdout:
        st.code(result.stdout.strip()[-4000:], language="text")
    if result.stderr:
        st.code(result.stderr.strip()[-4000:], language="text")


def format_action_label(action_id: str, reviews: list[AuthorizationReview]) -> str:
    review = next(item for item in reviews if item.action_id == action_id)
    status = "expired" if review.expired else review.decision
    return f"{action_id} — {review.recipient} — {status}"


if __name__ == "__main__":
    raise SystemExit(main())
