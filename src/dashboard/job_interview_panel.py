from __future__ import annotations

import json
from pathlib import Path

from src.core.job_interview_cockpit import (
    BLOCKED_ACTIONS,
    load_job_packets,
    prepare_job_packet,
    record_interview_invitation,
    record_job_decision,
)


def render_jobs_interviews_tab(st, root: Path) -> None:
    st.header("Jobs & Interviews")
    st.write(
        "Prepare truthful application and interview packets, review them, and approve them for manual operator submission. "
        "This workspace never logs in, fills a form, applies, sends a message, schedules an interview, or accepts an offer."
    )
    with st.expander("Blocked automation", expanded=False):
        for action in BLOCKED_ACTIONS:
            st.markdown(f"- `{action}`")

    render_job_packet_form(st, root)
    packets = load_job_packets(root)
    if not packets:
        st.info("No job packets exist yet. Prepare one above or run the read-only work-acquisition workflow.")
        return

    st.subheader("Review Queue")
    st.dataframe(
        [
            {
                "packet_id": item.get("packet_id"),
                "role": item.get("role_title"),
                "organization": item.get("organization"),
                "decision": item.get("decision"),
                "interview": item.get("interview_state"),
                "external_action": item.get("external_action_performed"),
            }
            for item in packets
        ],
        use_container_width=True,
    )

    selected_id = st.selectbox(
        "Select a job packet",
        [str(item.get("packet_id")) for item in packets],
        key="selected_job_packet",
    )
    selected = next(item for item in packets if str(item.get("packet_id")) == selected_id)
    render_selected_packet(st, root, selected)


def render_job_packet_form(st, root: Path) -> None:
    st.subheader("Prepare Application & Interview Packet")
    with st.form("job_packet_form"):
        source_url = st.text_input("Official posting URL")
        role_title = st.text_input("Role title")
        organization = st.text_input("Organization")
        posting_summary = st.text_area(
            "Posting summary / requirements",
            help="Paste or summarize only information you are authorized to use.",
        )
        truthful_qualifications = st.text_area(
            "Your truthful qualifications",
            help="Use only verified skills, education, projects, and experience. Do not invent credentials.",
        )
        application_draft = st.text_area(
            "Application or cover-letter draft (optional)",
            help="Leave blank to generate a conservative template from your verified qualifications.",
        )
        interview_notes = st.text_area(
            "Interview-preparation notes (optional)",
            help="Leave blank to generate a role-specific preparation outline.",
        )
        submitted = st.form_submit_button(
            "Prepare internal job packet",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return
    try:
        packet = prepare_job_packet(
            source_url=source_url,
            role_title=role_title,
            organization=organization,
            posting_summary=posting_summary,
            truthful_qualifications=truthful_qualifications,
            application_draft=application_draft,
            interview_notes=interview_notes,
            root=root,
        )
    except Exception as exc:
        st.error(f"Job packet preparation failed: {exc}")
        return

    st.success("Internal job packet prepared. Nothing was submitted or sent.")
    st.json(packet)


def render_selected_packet(st, root: Path, packet: dict[str, object]) -> None:
    st.markdown(
        f"### {packet.get('role_title', 'Role')} — {packet.get('organization', 'Organization')}"
    )
    source_url = str(packet.get("source_url", ""))
    if source_url:
        st.link_button("Open official posting", source_url, use_container_width=True)

    st.markdown("#### Posting Summary")
    st.write(str(packet.get("posting_summary", "")))
    st.markdown("#### Verified Qualifications")
    st.write(str(packet.get("truthful_qualifications", "")))
    st.markdown("#### Application Draft")
    st.code(str(packet.get("application_draft", "")), language="text")
    st.download_button(
        "Download application draft",
        str(packet.get("application_draft", "")),
        file_name=f"{packet.get('packet_id', 'job')}-application.txt",
        mime="text/plain",
        use_container_width=True,
    )
    st.markdown("#### Interview Preparation")
    st.code(str(packet.get("interview_notes", "")), language="text")

    decision = str(packet.get("decision", "PENDING_REVIEW"))
    st.info(
        f"Decision: `{decision}`. Acceptance means approved for manual operator submission only; it does not apply or send."
    )
    if decision == "PENDING_REVIEW":
        required_phrase = str(packet.get("required_accept_phrase", ""))
        st.code(required_phrase, language="text")
        typed_phrase = st.text_input(
            "Type the exact acceptance phrase",
            key=f"job_accept_phrase_{packet.get('packet_id')}",
        )
        reviewed = st.checkbox(
            "I reviewed the posting, truthful qualifications, draft, source URL, and manual-submission boundary.",
            key=f"job_reviewed_{packet.get('packet_id')}",
        )
        accept_disabled = not reviewed or typed_phrase != required_phrase
        col_accept, col_deny = st.columns(2)
        with col_accept:
            if st.button(
                "Accept for manual submission",
                type="primary",
                disabled=accept_disabled,
                use_container_width=True,
                key=f"job_accept_{packet.get('packet_id')}",
            ):
                try:
                    updated = record_job_decision(
                        str(packet.get("packet_id")),
                        decision="ACCEPT_FOR_MANUAL_SUBMISSION",
                        phrase=typed_phrase,
                        root=root,
                    )
                    st.success("Approved for your manual submission. No external action occurred.")
                    st.json(updated)
                except Exception as exc:
                    st.error(str(exc))
        with col_deny:
            denial_phrase = str(packet.get("denial_phrase", ""))
            if st.button(
                "Deny packet",
                use_container_width=True,
                key=f"job_deny_{packet.get('packet_id')}",
            ):
                try:
                    updated = record_job_decision(
                        str(packet.get("packet_id")),
                        decision="DENY",
                        phrase=denial_phrase,
                        root=root,
                    )
                    st.warning("Job packet denied. No external action occurred.")
                    st.json(updated)
                except Exception as exc:
                    st.error(str(exc))

    st.markdown("#### Interview Invitation")
    invitation_notes = st.text_area(
        "Record invitation details or questions received",
        key=f"interview_notes_{packet.get('packet_id')}",
        help="This records the invitation internally. You still schedule or reply manually on the official channel.",
    )
    if st.button(
        "Record interview invitation internally",
        disabled=not invitation_notes.strip(),
        use_container_width=True,
        key=f"record_interview_{packet.get('packet_id')}",
    ):
        try:
            updated = record_interview_invitation(
                str(packet.get("packet_id")),
                invitation_notes=invitation_notes,
                root=root,
            )
            st.success("Interview invitation recorded internally. No reply or scheduling occurred.")
            st.json(updated)
        except Exception as exc:
            st.error(str(exc))

    st.download_button(
        "Download complete job packet",
        json.dumps(packet, indent=2, ensure_ascii=False),
        file_name=f"{packet.get('packet_id', 'job')}.json",
        mime="application/json",
        use_container_width=True,
    )
