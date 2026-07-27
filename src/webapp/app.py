from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.operator_cockpit import (  # noqa: E402
    DEFAULT_AUTHORIZATIONS_PATH,
    build_accept_command,
    build_deny_command,
    build_revise_command,
    load_authorization_packets,
    load_work_order_governance_records,
    run_command,
    summarize_authorizations,
)
from src.gemini_workflow.api import create_router, safe_status  # noqa: E402
from src.gemini_workflow.models import OperatorIdentity  # noqa: E402

app = FastAPI(
    title="AIGC Governed Worker Command Center",
    version="0.1.0",
    description="Cloud launch surface for governed AIGC business cycles and human review.",
)

RUNS: Dict[str, Dict[str, Any]] = {}
RUN_LOCK = threading.Lock()
COMMAND_CENTER_TOKEN_ENV = "AIGC_COMMAND_CENTER_TOKEN"
OPERATOR_SUBJECT_KEY_ENV = "AIGC_OPERATOR_SUBJECT_KEY"
SESSION_COOKIE_NAME = "aigc_operator_session"
SESSION_TTL_SECONDS = 3_600


class DecisionRequest(BaseModel):
    phrase: str = ""
    revision_instructions: str = ""


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_label: str = Field(min_length=2, max_length=100)
    token: str = Field(min_length=12, max_length=4_096)

    @field_validator("operator_label")
    @classmethod
    def normalize_operator_label(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("operator_label must contain at least 2 characters")
        return normalized


BUSINESS_CYCLE = [
    ("runtime_preflight", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase14"]),
    ("opportunity_radar", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase2"]),
    ("job_assessment", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase3"]),
    ("proposal_drafting", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase4"]),
    ("review_packet_generation", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase5"]),
    ("finance_review", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase15"]),
    ("compliance_review", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase16"]),
    ("agent_team_design", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase19"]),
    ("fidelity_review", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase20"]),
    ("customer_fit_review", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase21"]),
    ("quality_deep_dive", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase22"]),
    ("work_order_governance", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase23"]),
    ("autonomic_business_pipeline", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase24"]),
    ("observability", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "run", "phase12"]),
    ("contract_validation", [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "validate"]),
]


def require_operator_auth(request: Request) -> OperatorIdentity:
    _require_same_origin_for_mutation(request)
    expected = os.environ.get(COMMAND_CENTER_TOKEN_ENV, "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{COMMAND_CENTER_TOKEN_ENV} is required before command center access is enabled.",
        )
    subject_key = _operator_subject_key(expected)
    if subject_key is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"{OPERATOR_SUBJECT_KEY_ENV} is required before production "
                "operator access is enabled."
            ),
        )
    identity = _operator_identity_from_request(request, expected, subject_key)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail="Operator authentication required.",
        )
    return identity


def _require_same_origin_for_mutation(request: Request) -> None:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin", "").strip()
    if not origin:
        return
    origin_host = urlsplit(origin).netloc.lower()
    request_host = request.headers.get("host", "").strip().lower()
    if not origin_host or origin_host != request_host:
        raise HTTPException(
            status_code=403,
            detail="Cross-origin state-changing request rejected.",
        )


def _operator_identity_from_request(
    request: Request,
    expected_token: str,
    subject_key: str,
) -> OperatorIdentity | None:
    session_identity = _identity_from_session_cookie(
        request.cookies.get(SESSION_COOKIE_NAME, ""),
        expected_token,
    )
    if session_identity is not None:
        return session_identity

    header_token = request.headers.get("x-aigc-command-token", "").strip()
    if header_token and hmac.compare_digest(header_token, expected_token):
        label = (
            request.headers.get("x-aigc-operator-label", "").strip()
            or "unlabeled-api-operator"
        )
        return OperatorIdentity(
            subject_sha256=_subject_hash(label, subject_key),
            auth_method="shared_token_header",
            identity_assurance="shared_credential_holder",
        )

    if os.environ.get("AIGC_ENV", "development").strip().lower() == "production":
        return None

    auth = request.headers.get("authorization", "").strip()
    lower = auth.lower()
    if lower.startswith("bearer "):
        provided = auth[7:].strip()
    elif lower.startswith("basic "):
        try:
            decoded = base64.b64decode(auth[6:].strip()).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
        if ":" in decoded:
            username, provided = decoded.split(":", 1)
        else:
            username, provided = "local-operator", decoded
        if provided and hmac.compare_digest(provided, expected_token):
            return OperatorIdentity(
                subject_sha256=_subject_hash(
                    username or "local-operator",
                    subject_key,
                ),
                auth_method="local_authorization_fallback",
                identity_assurance="shared_credential_holder",
            )
        return None
    else:
        return None
    if provided and hmac.compare_digest(provided, expected_token):
        label = (
            request.headers.get("x-aigc-operator-label", "").strip()
            or "local-bearer-operator"
        )
        return OperatorIdentity(
            subject_sha256=_subject_hash(label, subject_key),
            auth_method="local_authorization_fallback",
            identity_assurance="shared_credential_holder",
        )
    return None


def _operator_subject_key(command_token: str) -> str | None:
    configured = os.environ.get(OPERATOR_SUBJECT_KEY_ENV, "").strip()
    if configured:
        return configured
    if os.environ.get("AIGC_ENV", "development").strip().lower() == "production":
        return None
    return hmac.new(
        command_token.encode("utf-8"),
        b"aigc/local-only/operator-subject-key/v1",
        hashlib.sha256,
    ).hexdigest()


def _subject_hash(label: str, subject_key: str) -> str:
    normalized = label.strip().lower().encode("utf-8")
    return hmac.new(
        subject_key.encode("utf-8"),
        b"aigc/operator-subject/v1\0" + normalized,
        hashlib.sha256,
    ).hexdigest()


def _session_cookie(identity: OperatorIdentity, secret: str) -> str:
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = json.dumps(
        {
            "exp": expires_at,
            "sub": identity.subject_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(
        secret.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded}.{signature}"


def _identity_from_session_cookie(
    value: str,
    secret: str,
) -> OperatorIdentity | None:
    try:
        encoded, supplied_signature = value.split(".", 1)
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
        if int(payload["exp"]) < int(time.time()):
            return None
        subject = str(payload["sub"])
        return OperatorIdentity(
            subject_sha256=subject,
            auth_method="shared_token_session",
            identity_assurance="operator_attestation",
        )
    except (
        binascii.Error,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return None


app.include_router(create_router(require_operator_auth))


@app.get("/api/session")
def session_status(request: Request) -> Dict[str, Any]:
    expected = os.environ.get(COMMAND_CENTER_TOKEN_ENV, "").strip()
    subject_key = _operator_subject_key(expected) if expected else None
    identity = (
        _operator_identity_from_request(request, expected, subject_key)
        if expected and subject_key
        else None
    )
    return {
        "configured": bool(expected and subject_key),
        "authenticated": identity is not None,
        "identity_assurance": (
            identity.identity_assurance if identity is not None else None
        ),
    }


@app.post("/api/session")
def create_session(request: Request, session: SessionRequest) -> JSONResponse:
    _require_same_origin_for_mutation(request)
    expected = os.environ.get(COMMAND_CENTER_TOKEN_ENV, "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{COMMAND_CENTER_TOKEN_ENV} is required before login.",
        )
    subject_key = _operator_subject_key(expected)
    if subject_key is None:
        raise HTTPException(
            status_code=503,
            detail=f"{OPERATOR_SUBJECT_KEY_ENV} is required before login.",
        )
    if not hmac.compare_digest(session.token, expected):
        raise HTTPException(status_code=401, detail="Operator login failed.")
    identity = OperatorIdentity(
        subject_sha256=_subject_hash(session.operator_label, subject_key),
        auth_method="shared_token_session",
        identity_assurance="operator_attestation",
    )
    response = JSONResponse(
        {
            "authenticated": True,
            "identity_assurance": identity.identity_assurance,
        }
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_session_cookie(identity, expected),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=(
            os.environ.get("AIGC_ENV", "development").strip().lower()
            == "production"
        ),
        samesite="strict",
        path="/",
    )
    return response


@app.post("/api/session/logout")
def end_session(request: Request) -> JSONResponse:
    _require_same_origin_for_mutation(request)
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        samesite="strict",
    )
    return response


@app.get("/health")
def health() -> Dict[str, Any]:
    expected = os.environ.get(COMMAND_CENTER_TOKEN_ENV, "").strip()
    return {
        "ok": True,
        "mode": "governed_command_center",
        "auth_required": True,
        "auth_configured": bool(
            expected and _operator_subject_key(expected)
        ),
        "operator_subject_key_configured": bool(
            os.environ.get(OPERATOR_SUBJECT_KEY_ENV, "").strip()
        ),
        "gemini_workflow": safe_status(),
    }


@app.get("/api/pipeline", dependencies=[Depends(require_operator_auth)])
def pipeline() -> Dict[str, Any]:
    return {
        "steps": [
            {"name": name, "command": command}
            for name, command in BUSINESS_CYCLE
        ]
    }


@app.post("/api/run", dependencies=[Depends(require_operator_auth)])
def run_cycle() -> Dict[str, Any]:
    run_id = f"AIGC-RUN-{uuid.uuid4()}"
    with RUN_LOCK:
        RUNS[run_id] = {"status": "queued", "steps": [], "current": "", "complete": False}
    thread = threading.Thread(target=_run_cycle_worker, args=(run_id,), daemon=True)
    thread.start()
    return {"run_id": run_id, "status_url": f"/api/run/{run_id}"}


@app.get("/api/run/{run_id}", dependencies=[Depends(require_operator_auth)])
def run_status(run_id: str) -> Dict[str, Any]:
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail="Run not found")
    return RUNS[run_id]


@app.get("/api/reviews", dependencies=[Depends(require_operator_auth)])
def reviews() -> Dict[str, Any]:
    packets = load_authorization_packets(PROJECT_ROOT)
    work_orders = load_work_order_governance_records(PROJECT_ROOT)
    review_items = summarize_authorizations(packets, work_orders)
    return {"reviews": [asdict(item) for item in review_items]}


@app.post("/api/reviews/{action_id}/accept", dependencies=[Depends(require_operator_auth)])
def accept_review(action_id: str, request: DecisionRequest) -> Dict[str, Any]:
    review = _find_review(action_id)
    if review.expired:
        raise HTTPException(status_code=409, detail="Review packet is expired")
    if review.external_action_performed:
        raise HTTPException(status_code=409, detail="Packet already records outward completion")
    if review.decision != "pending":
        raise HTTPException(status_code=409, detail="Packet is not pending")
    result = run_command(
        build_accept_command(PROJECT_ROOT, review, request.phrase, DEFAULT_AUTHORIZATIONS_PATH),
        root=PROJECT_ROOT,
        label=f"accept:{action_id}",
    )
    return _command_payload(result)


@app.post("/api/reviews/{action_id}/deny", dependencies=[Depends(require_operator_auth)])
def deny_review(action_id: str, request: DecisionRequest) -> Dict[str, Any]:
    review = _find_review(action_id)
    result = run_command(
        build_deny_command(PROJECT_ROOT, review, DEFAULT_AUTHORIZATIONS_PATH),
        root=PROJECT_ROOT,
        label=f"deny:{action_id}",
    )
    return _command_payload(result)


@app.post("/api/reviews/{action_id}/revise", dependencies=[Depends(require_operator_auth)])
def revise_review(action_id: str, request: DecisionRequest) -> Dict[str, Any]:
    if not request.revision_instructions.strip():
        raise HTTPException(status_code=400, detail="revision_instructions is required")
    review = _find_review(action_id)
    result = run_command(
        build_revise_command(PROJECT_ROOT, review, request.revision_instructions, DEFAULT_AUTHORIZATIONS_PATH),
        root=PROJECT_ROOT,
        label=f"revise:{action_id}",
    )
    return _command_payload(result)


@app.post("/api/emergency-stop", dependencies=[Depends(require_operator_auth)])
def emergency_stop() -> Dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "emergency-stop"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {"ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}


@app.get("/", response_class=HTMLResponse)
def ui() -> str:
    return render_ui()


def _run_cycle_worker(run_id: str) -> None:
    with RUN_LOCK:
        RUNS[run_id]["status"] = "running"
    for name, command in BUSINESS_CYCLE:
        with RUN_LOCK:
            RUNS[run_id]["current"] = name
        result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, check=False)
        step_payload = {
            "name": name,
            "command": command,
            "returncode": result.returncode,
            "ok": result.returncode == 0,
            "stdout_tail": result.stdout[-6000:],
            "stderr_tail": result.stderr[-6000:],
        }
        with RUN_LOCK:
            RUNS[run_id]["steps"].append(step_payload)
        if result.returncode != 0:
            with RUN_LOCK:
                RUNS[run_id]["status"] = "failed"
                RUNS[run_id]["complete"] = True
            return
    with RUN_LOCK:
        RUNS[run_id]["status"] = "completed"
        RUNS[run_id]["complete"] = True
        RUNS[run_id]["current"] = ""


def _find_review(action_id: str):
    packets = load_authorization_packets(PROJECT_ROOT)
    work_orders = load_work_order_governance_records(PROJECT_ROOT)
    for item in summarize_authorizations(packets, work_orders):
        if item.action_id == action_id:
            return item
    raise HTTPException(status_code=404, detail="Review packet not found")


def _command_payload(result) -> Dict[str, Any]:
    return {
        "ok": result.ok,
        "label": result.label,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def render_ui() -> str:
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AIGC Governed Worker Command Center</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0b1020; color: #eef2ff; }}
    button {{ font-size: 1rem; padding: 1rem 1.25rem; border-radius: 0.75rem; border: 0; cursor: pointer; }}
    .primary {{ background: #8b5cf6; color: white; font-weight: 700; }}
    .danger {{ background: #ef4444; color: white; }}
    code, pre {{ background: #111827; color: #d1d5db; padding: 1rem; border-radius: 0.75rem; display: block; overflow: auto; }}
    .card {{ border: 1px solid #334155; border-radius: 1rem; padding: 1rem; margin: 1rem 0; background: #111827; }}
    input, textarea {{ width: 100%; padding: 0.75rem; border-radius: 0.5rem; border: 1px solid #475569; background: #020617; color: #e5e7eb; }}
  </style>
</head>
<body>
  <h1>AIGC Governed Worker Command Center</h1>
  <p>One cloud-launchable command surface for governed business cycles, review packets, and audit-first operations.</p>
  <p>Cloud Run IAM authenticates access to the private service. A separate short-lived operator session protects application controls without reusing the Cloud Run <code>Authorization</code> header.</p>
  <div class="card" id="session-card">
    <h2>Operator Session</h2>
    <label>Operator label</label>
    <input id="operator-label" maxlength="100" autocomplete="username" placeholder="Accountable operator label" />
    <label>Command-center token</label>
    <input id="operator-token" type="password" maxlength="4096" autocomplete="current-password" placeholder="Loaded from your approved password manager" />
    <button class="primary" onclick="loginOperator()">START OPERATOR SESSION</button>
    <p id="session-status">Checking session…</p>
  </div>
  <div id="app-shell" style="display:none">
  <button onclick="logoutOperator()">End Operator Session</button>
  <div class="card">
    <h2>Large Action Button</h2>
    <button class="primary" onclick="runCycle()">RUN FULL GOVERNED BUSINESS CYCLE</button>
    <p id="run-status"></p>
    <pre id="run-output"></pre>
  </div>
  <div class="card">
    <h2>Human Review Packets</h2>
    <button onclick="loadReviews()">Refresh Reviews</button>
    <div id="reviews"></div>
  </div>
  <div class="card">
    <h2>Governed Gemini Opportunity Assessment</h2>
    <p>A live assessment calls the configured Vertex AI model, then creates an internal draft and a create-only evidence record. It never performs an external business action.</p>
    <label>Opportunity title</label>
    <input id="gemini-title" maxlength="200" placeholder="Permissioned opportunity" />
    <label>HTTPS source URL</label>
    <input id="gemini-source" placeholder="https://example.com/opportunity" />
    <label>Description</label>
    <textarea id="gemini-description" maxlength="12000" placeholder="Describe the opportunity without credentials or unnecessary personal information."></textarea>
    <label>Constraints (one per line)</label>
    <textarea id="gemini-constraints" placeholder="No external business action&#10;Human review required"></textarea>
    <label><input id="gemini-permitted" type="checkbox" /> AI assistance is permitted for this intake</label>
    <label><input id="gemini-disclosure" type="checkbox" checked /> AI-use disclosure is required</label>
    <button class="primary" onclick="runGeminiAssessment()">RUN GOVERNED GEMINI ASSESSMENT</button>
    <p id="gemini-status"></p>
    <pre id="gemini-output"></pre>
    <div id="gemini-decision-panel" style="display:none">
      <label>Operator attestation reason</label>
      <textarea id="gemini-decision-reason" placeholder="Document the accountable operator reason."></textarea>
      <label>Revision instructions (required only for revise)</label>
      <textarea id="gemini-revision" placeholder="State the exact required revision."></textarea>
      <button id="gemini-approve" onclick="decideGemini('approve')">Approve Internal Use</button>
      <button onclick="decideGemini('deny')">Deny</button>
      <button onclick="decideGemini('revise')">Request Revision</button>
    </div>
  </div>
  <div class="card">
    <h2>Emergency Control</h2>
    <button class="danger" onclick="stopNow()">Enable Emergency Stop</button>
    <pre id="stop-output"></pre>
  </div>
  </div>
<script>
let currentGeminiRunId = '';
async function initializeSession() {{
  const response = await fetch('/api/session');
  const data = await response.json();
  const authenticated = Boolean(data.authenticated);
  document.getElementById('session-card').style.display =
    authenticated ? 'none' : 'block';
  document.getElementById('app-shell').style.display =
    authenticated ? 'block' : 'none';
  document.getElementById('session-status').textContent =
    !data.configured
      ? 'Operator login is disabled until AIGC_COMMAND_CENTER_TOKEN is configured.'
      : authenticated
        ? 'Operator session active.'
        : 'Enter the approved operator label and command-center token.';
  if (authenticated) {{
    await Promise.all([loadReviews(), loadGeminiStatus()]);
  }}
}}
async function loginOperator() {{
  const response = await fetch('/api/session', {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{
      operator_label: document.getElementById('operator-label').value,
      token: document.getElementById('operator-token').value
    }})
  }});
  const data = await response.json();
  document.getElementById('operator-token').value = '';
  if (!response.ok) {{
    document.getElementById('session-status').textContent =
      data.detail || 'Operator login failed.';
    return;
  }}
  await initializeSession();
}}
async function logoutOperator() {{
  await fetch('/api/session/logout', {{method:'POST'}});
  currentGeminiRunId = '';
  await initializeSession();
}}
async function runCycle() {{
  const r = await fetch('/api/run', {{method: 'POST'}});
  const data = await r.json();
  document.getElementById('run-status').textContent = 'Run started: ' + data.run_id;
  pollRun(data.run_id);
}}
async function pollRun(id) {{
  const r = await fetch('/api/run/' + encodeURIComponent(id));
  const data = await r.json();
  document.getElementById('run-output').textContent = JSON.stringify(data, null, 2);
  if (!data.complete) setTimeout(() => pollRun(id), 3000);
}}
async function loadReviews() {{
  const r = await fetch('/api/reviews');
  const data = await r.json();
  const root = document.getElementById('reviews');
  root.replaceChildren();
  data.reviews.forEach(item => {{
    const div = document.createElement('div');
    div.className = 'card';
    appendTextElement(
      div,
      'h3',
      String(item.action_id) + ' — ' + String(item.recipient)
    );
    appendTextElement(
      div,
      'p',
      'Status: ' + String(item.decision)
        + ' | Expired: ' + String(item.expired)
        + ' | Risk: ' + String(item.risk_class)
        + ' / ' + String(item.safety_status)
    );
    appendTextElement(div, 'p', 'Quality: ' + String(item.quality_state));
    appendTextElement(
      div,
      'pre',
      String(item.artifact_preview || '').slice(0, 1600)
    );
    appendTextElement(
      div,
      'p',
      'Type exact acceptance phrase only after review:'
    );
    const phrase = document.createElement('input');
    phrase.id = 'phrase-' + String(item.action_id);
    phrase.placeholder = 'Exact acceptance phrase';
    div.appendChild(phrase);
    const acceptButton = document.createElement('button');
    acceptButton.textContent = 'Accept Selected';
    acceptButton.addEventListener('click', () => acceptItem(item.action_id));
    div.appendChild(acceptButton);
    const denyButton = document.createElement('button');
    denyButton.textContent = 'Deny';
    denyButton.addEventListener('click', () => denyItem(item.action_id));
    div.appendChild(denyButton);
    const revision = document.createElement('textarea');
    revision.id = 'revise-' + String(item.action_id);
    revision.placeholder = 'Revision instructions';
    div.appendChild(revision);
    const reviseButton = document.createElement('button');
    reviseButton.textContent = 'Request Revision';
    reviseButton.addEventListener('click', () => reviseItem(item.action_id));
    div.appendChild(reviseButton);
    root.appendChild(div);
  }});
}}
function appendTextElement(parent, tag, value) {{
  const element = document.createElement(tag);
  element.textContent = value;
  parent.appendChild(element);
  return element;
}}
async function acceptItem(id) {{
  const phrase = document.getElementById('phrase-' + id).value;
  const r = await fetch('/api/reviews/' + encodeURIComponent(id) + '/accept', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{phrase}})}});
  alert(JSON.stringify(await r.json(), null, 2));
  loadReviews();
}}
async function denyItem(id) {{
  const r = await fetch('/api/reviews/' + encodeURIComponent(id) + '/deny', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{}})}});
  alert(JSON.stringify(await r.json(), null, 2));
  loadReviews();
}}
async function reviseItem(id) {{
  const revision_instructions = document.getElementById('revise-' + id).value;
  const r = await fetch('/api/reviews/' + encodeURIComponent(id) + '/revise', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{revision_instructions}})}});
  alert(JSON.stringify(await r.json(), null, 2));
  loadReviews();
}}
async function loadGeminiStatus() {{
  const r = await fetch('/api/gemini/status');
  const data = await r.json();
  document.getElementById('gemini-status').textContent =
    data.configured
      ? 'Configured: ' + data.provider + ' / ' + data.model + ' / ' + data.location
      : 'Gemini workflow is disabled or incomplete. No model call will run.';
}}
async function runGeminiAssessment() {{
  const payload = {{
    title: document.getElementById('gemini-title').value,
    source_url: document.getElementById('gemini-source').value,
    description: document.getElementById('gemini-description').value,
    constraints: document.getElementById('gemini-constraints').value
      .split('\\n').map(value => value.trim()).filter(Boolean),
    ai_assistance_permitted: document.getElementById('gemini-permitted').checked,
    ai_disclosure_required: document.getElementById('gemini-disclosure').checked
  }};
  const r = await fetch('/api/gemini/workflows', {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify(payload)
  }});
  const data = await r.json();
  document.getElementById('gemini-output').textContent = JSON.stringify(data, null, 2);
  if (!r.ok) {{
    currentGeminiRunId = '';
    document.getElementById('gemini-decision-panel').style.display = 'none';
    return;
  }}
  currentGeminiRunId = data.run_id;
  const decisionEligible = [
    'pending_human_review',
    'clarification_required',
    'blocked'
  ].includes(data.status);
  document.getElementById('gemini-decision-panel').style.display =
    decisionEligible ? 'block' : 'none';
  document.getElementById('gemini-approve').disabled =
    data.status !== 'pending_human_review';
}}
async function decideGemini(decision) {{
  if (!currentGeminiRunId) return;
  const payload = {{
    decision,
    reason: document.getElementById('gemini-decision-reason').value,
    revision_instructions: document.getElementById('gemini-revision').value
  }};
  const r = await fetch(
    '/api/gemini/workflows/' + encodeURIComponent(currentGeminiRunId) + '/decision',
    {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify(payload)
    }}
  );
  const data = await r.json();
  document.getElementById('gemini-output').textContent = JSON.stringify(data, null, 2);
  if (r.ok) document.getElementById('gemini-decision-panel').style.display = 'none';
}}
async function stopNow() {{
  const r = await fetch('/api/emergency-stop', {{method:'POST'}});
  document.getElementById('stop-output').textContent = JSON.stringify(await r.json(), null, 2);
}}
initializeSession();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.webapp.app:app",
        host=os.environ.get("AIGC_WEBAPP_HOST", os.environ.get("HOST", "127.0.0.1")),
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )
