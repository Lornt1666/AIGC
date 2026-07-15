from __future__ import annotations

import json
from pathlib import Path

from src.core.job_interview_cockpit import (
    BLOCKED_ACTIONS,
    load_job_packets,
    load_radar_opportunities,
    prepare_job_packet,
    prepare_job_packet_from_opportunity,
    record_interview_invitation,
    record_job_decision,
)
from src.core.operator_cockpit import build_aigc_command, run_command


def render_jobs_interviews_tab(st, root: Path) -> None:
    st.header("Jobs & Interviews")
    st.write(
        "Refresh AIGC's read-only opportunity radar or enter an official posting manually, prepare truthful application and interview packets, review them, and approve them for manual operator submission. "
        "This workspace never logs in, fills a form, applies, sends a message, schedules an interview, or accepts an offer."
    )
    with st.expander("Blocked automation", expanded=False):
        for action in BLOCKED_ACTIONS:
            st.markdown(f"- `{action}`")

    render_radar_opportunity_section(st, root)
    render_job_packet_form(st, root)
    packets = load_job_packets(root)
    if not packets:
        st.info(
            "No job packets exist yet. Import a radar opportunity or prepare one manually."
        )
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
                "radar_score": dict(item.get("source_metadata") or {}).get(
                    "radar_score"
                ),
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
    selected = next(
        item for item in packets if str(item.get("packet_id")) == selected_id
    )
    render_selected_packet(st, root, selected)


def render_radar_opportunity_section(st, root: Path) -> None:
    st.subheader("Read-Only Opportunity Radar")
    st.caption(
        "Refresh queries only AIGC's approved public/API/RSS sources, writes the Phase 2 queue, and stops before applying, messaging, credential use, or platform action."
    )
    if st.button(
        "Refresh read-only opportunities",
        use_container_width=True,
        key="refresh_phase2_opportunities",
    ):
        result = run_command(build_aigc_command(root, "run", "phase2"), root)
        if result.ok:
            st.success(
                "Opportunity radar refreshed. No application, message, login, or external commitment occurred."
            )
        else:
            st.error(f"Opportunity refresh failed with exit code {result.returncode}.")
        if result.stdout:
            st.code(result.stdout[-4000:], language="text")
        if result.stderr:
            st.code(result.stderr[-4000:], language="text")

    try:
        opportunities = load_radar_opportunities(root)
    except Exception as exc:
        st.error(f"Unable to load the Phase 2 opportunity queue: {exc}")
        return
    if not opportunities:
        st.info(
            "No eligible job opportunities are currently in the Phase 2 queue. Refresh the radar or enter a posting manually below."
        )
        return

    st.dataframe(
        [
            {
                "opportunity_id": item.get("opportunity_id"),
                "title": item.get("title"),
                "employer": item.get("employer") or item.get("client"),
                "source": item.get("source_platform"),
                "score": item.get("radar_score"),
                "decision": item.get("radar_decision"),
                "risks": ", ".join(str(value) for value in item.get("risk_flags") or []),
            }
            for item in opportunities
        ],
        use_container_width=True,
    )
    by_id = {str(item.get("opportunity_id")): item for item in opportunities}
    selected_id = st.selectbox(
        "Select an eligible radar opportunity",
        list(by_id),
        format_func=lambda value: (
            f"{by_id[value].get('title', 'Untitled')} — "
            f"{by_id[value].get('employer') or by_id[value].get('client') or by_id[value].get('source_platform')} "
            f"(score {by_id[value].get('radar_score', 0)})"
        ),
        key="selected_radar_opportunity",
    )
    selected = by_id[selected_id]
    source_url = str(selected.get("source_url") or "")
    if source_url:
        st.link_button(
            "Open selected official posting",
            source_url,
            use_container_width=True,
        )
    with st.expander("Radar evidence and risks", expanded=False):
        st.json(
            {
                "radar_score": selected.get("radar_score"),
                "radar_decision": selected.get("radar_decision"),
                "platform_policy_status": selected.get("platform_policy_status"),
                "risk_flags": selected.get("risk_flags") or [],
                "forbidden_flags": selected.get("forbidden_flags") or [],
                "approval_required_before": selected.get(
                    "approval_required_before"
                )
                or [],
                "external_action_performed": False,
            }
        )

    with st.form("radar_job_packet_form"):
        truthful_qualifications = st.text_area(
            "Your truthful qualifications for this opportunity",
            key="radar_truthful_qualifications",
            help="Use only verified skills, education, projects, and experience.",
        )
        application_draft = st.text_area(
            "Optional application draft override",
            key="radar_application_draft",
        )
        interview_notes = st.text_area(
            "Optional interview-preparation override",
            key="radar_interview_notes",
        )
        prepared = st.form_submit_button(
            "Prepare selected opportunity for review",
            type="primary",
            use_container_width=True,
        )
    if not prepared:
        return
    try:
        packet = prepare_job_packet_from_opportunity(
            selected_id,
            truthful_qualifications=truthful_qualifications,
            application_draft=application_draft,
            interview_notes=interview_notes,
            root=root,
        )
    except Exception as exc:
        st.error(f"Opportunity packet preparation failed: {exc}")
        return
    st.success(
        "Radar opportunity converted into an internal review packet. Nothing was submitted or sent."
    )
    st.json(packet)


def render_job_packet_form(st, root: Path) -> None:
    st.subheader("Manual Posting Entry")
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

    source_metadata = dict(packet.get("source_metadata") or {})
    if source_metadata:
        with st.expander("Source and radar evidence", expanded=False):
            st.json(source_metadata)

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
            "I reviewed the posting, truthful qualifications, draft, source URL, risks, and manual-submission boundary.",
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
                    st.success(
                        "Approved for your manual submission. No external action occurred."
                    )
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
            st.success(
                "Interview invitation recorded internally. No reply or scheduling occurred."
            )
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
