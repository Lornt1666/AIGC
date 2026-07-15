from __future__ import annotations

import json
from pathlib import Path

from src.core.operator_initialization import (
    INITIALIZATION_BOUNDARY,
    build_initialization_commands,
    run_operator_initialization,
)


def render_operator_initialization_tab(st, root: Path) -> None:
    st.header("Initialize AIGC")
    st.write(
        "One click initializes the local state database, validates contracts, evaluates health and readiness, "
        "prepares the read-only work-acquisition packet, runs the cockpit smoke test, and executes mock-only provider discovery."
    )
    st.warning(
        "Initialize does not install software, use credentials, contact job platforms, submit applications, send messages, "
        "schedule interviews, accept contracts, run Terraform apply, create cloud resources, deploy, or deliver work."
    )

    with st.expander("Initialization safety boundary", expanded=False):
        for item in INITIALIZATION_BOUNDARY:
            st.markdown(f"- {item}")

    with st.expander("Exact internal sequence", expanded=False):
        try:
            commands = build_initialization_commands(root)
        except Exception as exc:
            st.error(f"Unable to resolve initialization sequence: {exc}")
            return
        for index, command in enumerate(commands, start=1):
            st.markdown(f"**{index}. {command.label}** — `{command.safety_class}`")
            st.code(" ".join(command.command), language="powershell")

    stop_on_failure = st.checkbox(
        "Stop initialization immediately when a required step fails",
        value=True,
        key="initialize_stop_on_failure",
    )
    if not st.button(
        "Initialize AIGC safely",
        type="primary",
        use_container_width=True,
        key="initialize_aigc_button",
    ):
        st.info("Initialization has not been run from this session.")
        return

    try:
        receipt = run_operator_initialization(
            root,
            stop_on_failure=stop_on_failure,
        )
    except Exception as exc:
        st.error(f"Initialization blocked: {exc}")
        return

    if receipt.status == "READY_FOR_OPERATOR_REVIEW":
        st.success("AIGC local initialization completed. Review remains required before consequential actions.")
    else:
        st.error("AIGC initialization is blocked. Review the failed step before continuing.")

    st.json(receipt.to_dict())
    st.download_button(
        "Download initialization receipt",
        json.dumps(receipt.to_dict(), indent=2),
        file_name=f"{receipt.receipt_id}.json",
        mime="application/json",
        use_container_width=True,
    )
