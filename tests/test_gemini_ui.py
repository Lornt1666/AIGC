from __future__ import annotations

from html.parser import HTMLParser

from fastapi.testclient import TestClient

from src.webapp.gemini_app import create_app
from src.webapp.gemini_ui import (
    render_surface_script,
    render_surface_styles,
    render_surface_ui,
)


class MarkupAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.label_targets: list[str] = []
        self.inline_scripts = 0
        self.style_tags = 0
        self.inline_style_attributes = 0
        self.landmarks: set[str] = set()
        self.buttons_without_type: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = dict(attrs)
        element_id = values.get("id")
        if element_id:
            self.ids.append(element_id)
        if tag == "label" and values.get("for"):
            self.label_targets.append(values["for"] or "")
        if tag == "script" and not values.get("src"):
            self.inline_scripts += 1
        if tag == "style":
            self.style_tags += 1
        if "style" in values:
            self.inline_style_attributes += 1
        if tag in {"header", "main", "aside", "nav", "form"}:
            self.landmarks.add(tag)
        if tag == "button" and not values.get("type"):
            self.buttons_without_type.append(element_id or "anonymous")


def _audit(surface: str) -> MarkupAudit:
    audit = MarkupAudit()
    audit.feed(render_surface_ui(surface))
    return audit


def test_operator_markup_has_accessible_contract_and_unique_ids() -> None:
    audit = _audit("operator")

    assert len(audit.ids) == len(set(audit.ids))
    assert set(audit.label_targets).issubset(set(audit.ids))
    assert {"header", "main", "aside", "form"}.issubset(audit.landmarks)
    assert audit.inline_scripts == 0
    assert audit.style_tags == 0
    assert audit.inline_style_attributes == 0
    assert audit.buttons_without_type == []

    html = render_surface_ui("operator")
    for expected in (
        'href="/assets/aigc.css"',
        'src="/assets/surface.js"',
        'id="connection-form"',
        'id="intake-form"',
        'id="review-panel"',
        'id="decision-form"',
        'id="evidence-panel"',
        'id="stop-form"',
        'role="alert"',
        'role="status"',
    ):
        assert expected in html
    assert "External actions locked" in html
    assert "internal use only" in html


def test_operator_script_is_complete_and_does_not_persist_credentials() -> None:
    script = render_surface_script("operator")

    for expected in (
        "/api/gemini/status",
        "/api/gemini/workflows",
        "/decision",
        "/api/gemini/runtime/emergency-stop",
        "Idempotency-Key",
        "createIdempotencyKey",
        "renderWorkflow",
        "renderDecision",
        "Do not automatically retry",
        'byId("operator-token").value = ""',
    ):
        assert expected in script

    for forbidden in (
        "localStorage",
        "sessionStorage",
        "document.cookie",
        "document.write",
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "eval(",
        "/api/judge/",
    ):
        assert forbidden not in script


def test_judge_surface_remains_provider_free_and_read_only() -> None:
    audit = _audit("judge")
    assert len(audit.ids) == len(set(audit.ids))
    assert set(audit.label_targets).issubset(set(audit.ids))
    assert audit.inline_scripts == 0
    assert audit.style_tags == 0
    assert audit.inline_style_attributes == 0
    assert audit.buttons_without_type == []

    script = render_surface_script("judge")
    assert "/api/judge/receipts/" in script
    assert 'byId("judge-token").value = ""' in script
    assert "/api/gemini/" not in script
    assert "method: \"POST\"" not in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "innerHTML" not in script


def test_styles_cover_focus_reflow_and_reduced_motion() -> None:
    styles = render_surface_styles()

    assert ":focus-visible" in styles
    assert "min-width: 320px" in styles
    assert "@media (max-width: 760px)" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles
    assert "min-height: 44px" in styles


def test_assets_are_same_origin_and_csp_rejects_inline_code() -> None:
    application = create_app(
        "operator",
        readiness_check=lambda: {
            "ready": True,
            "model_api_call_performed": False,
        },
    )
    client = TestClient(application)

    root = client.get("/")
    stylesheet = client.get("/assets/aigc.css")
    script = client.get("/assets/surface.js")

    assert root.status_code == 200
    assert stylesheet.status_code == 200
    assert script.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert script.headers["content-type"].startswith("text/javascript")
    assert root.headers["cache-control"] == "no-store"
    csp = root.headers["content-security-policy"]
    assert "style-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "'unsafe-inline'" not in csp
    assert "/assets/aigc.css" not in application.openapi()["paths"]
    assert "/assets/surface.js" not in application.openapi()["paths"]
