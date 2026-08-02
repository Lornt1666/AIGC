"""Local read-only executive dashboard for Ω Mission OS."""

from __future__ import annotations

from html import escape
from typing import Any, Mapping


def build_dashboard_payload(snapshot: Mapping[str, Any], revenue: Mapping[str, Any]) -> dict[str, Any]:
    summary = dict(snapshot.get("summary") or {})
    financials = dict(revenue.get("financials") or {})
    return {
        "mission": {
            "title": snapshot.get("mission", {}).get("title"),
            "state": snapshot.get("mission", {}).get("state"),
            "progress_percent": summary.get("mission_progress_percent", 0),
            "next_action": snapshot.get("highest_impact_next_action"),
        },
        "revenue": financials,
        "operations": {
            "approvals_waiting": len(snapshot.get("approvals_waiting") or []),
            "blockers": len(snapshot.get("blockers") or []),
            "quests": len(snapshot.get("quests") or []),
            "registered_phases": len(snapshot.get("phase_registry") or []),
            "sources_available": summary.get("sources_available", 0),
            "sources_missing": summary.get("sources_missing", 0),
            "sources_invalid": summary.get("sources_invalid", 0),
        },
        "funnel": dict(revenue.get("funnel") or {}),
        "warnings": list(snapshot.get("warnings") or []),
        "mode": "READ_ONLY",
        "external_action_performed": False,
        "canonical_state_mutated": False,
    }


def render_dashboard_html(payload: Mapping[str, Any]) -> str:
    mission = payload.get("mission", {})
    revenue = payload.get("revenue", {})
    operations = payload.get("operations", {})
    funnel = payload.get("funnel", {})

    def card(label: str, value: Any) -> str:
        return f'<article class="card"><span>{escape(label)}</span><strong>{escape(str(value))}</strong></article>'

    cards = "".join([
        card("Mission progress", f"{mission.get('progress_percent', 0)}%"),
        card("Verified collected", f"CAD {revenue.get('verified_collected', 0):,.2f}"),
        card("Estimated pipeline", f"CAD {revenue.get('estimated_pipeline', 0):,.2f}"),
        card("Approvals waiting", operations.get("approvals_waiting", 0)),
        card("Blockers", operations.get("blockers", 0)),
        card("Quests", operations.get("quests", 0)),
    ])
    funnel_rows = "".join(
        f"<tr><th>{escape(key.replace('_', ' ').title())}</th><td>{escape(str(value))}</td></tr>"
        for key, value in funnel.items()
    )
    warnings = "".join(f"<li>{escape(str(item))}</li>" for item in payload.get("warnings", [])) or "<li>None reported.</li>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ω Mission OS Executive Dashboard</title>
<style>body{{font-family:system-ui;margin:0;background:#08111f;color:#eef6ff}}main{{max-width:1200px;margin:auto;padding:24px}}.boundary{{padding:12px;border:1px solid #b88a3b;background:#2d2414;border-radius:8px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:18px 0}}.card{{padding:16px;background:#102238;border:1px solid #34516d;border-radius:10px}}.card span{{display:block;color:#b9ccdd}}.card strong{{display:block;font-size:1.5rem;margin-top:8px}}section{{background:#0d1b2d;padding:16px;border-radius:10px;margin:14px 0}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:8px;border-bottom:1px solid #29445f}}code{{color:#7de3d8}}</style></head>
<body><main><h1>Ω Mission OS Executive Dashboard</h1><p class="boundary"><strong>Read-only projection:</strong> this dashboard cannot approve, contact, submit, spend, invoice, collect payment, execute connectors, transition Quests, or mutate canonical state.</p>
<h2>{escape(str(mission.get('title') or 'Mission'))}</h2><p>State: <code>{escape(str(mission.get('state')))}</code></p><div class="grid">{cards}</div>
<section><h2>Highest-impact next action</h2><p>{escape(str(mission.get('next_action') or 'No action identified.'))}</p></section>
<section><h2>Revenue funnel</h2><table>{funnel_rows}</table><p>{escape(str(revenue.get('verification_rule') or ''))}</p></section>
<section><h2>Warnings</h2><ul>{warnings}</ul></section></main></body></html>"""
