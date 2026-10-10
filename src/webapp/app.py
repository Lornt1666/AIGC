from __future__ import annotations

import html
import base64
import hmac
import json
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel


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

app = FastAPI(
    title="AIGC Governed Worker Command Center",
    version="0.1.0",
    description="Cloud launch surface for governed AIGC business cycles and human review.",
)

RUNS: Dict[str, Dict[str, Any]] = {}
RUN_LOCK = threading.Lock()
# This process-local gate prevents thread floods in one worker. Multi-replica and
# restart-safe execution still requires durable shared state and remains a deploy blocker.
MAX_CONCURRENT_RUNS = max(1, int(os.environ.get("AIGC_MAX_CONCURRENT_RUNS", "1")))
RUN_CAPACITY = threading.BoundedSemaphore(MAX_CONCURRENT_RUNS)
STEP_TIMEOUT_SECONDS = max(5, int(os.environ.get("AIGC_STEP_TIMEOUT_SECONDS", "120")))
EMERGENCY_STOP_TIMEOUT_SECONDS = max(5, int(os.environ.get("AIGC_EMERGENCY_STOP_TIMEOUT_SECONDS", "15")))
MAX_OUTPUT_CHARS = 2000
COMMAND_CENTER_TOKEN_ENV = "AIGC_COMMAND_CENTER_TOKEN"

def _safe_output(value: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Bound and redact common secret-shaped output before returning it to a browser."""
    value = value or ""
    import re
    patterns = [
        (r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;]+", r"\1[REDACTED]"),
        (r"""(?i)((?:"?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|secret)"?)\s*[:=]\s*["']?)[^\s,;"']+""", r"\1[REDACTED]"),
        (r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", "[REDACTED_AWS_KEY]"),
    ]
    for pattern, replacement in patterns:
        value = re.sub(pattern, replacement, value)
    if len(value) > limit:
        value = value[-limit:]
    return value


class DecisionRequest(BaseModel):
    phrase: str = ""
    revision_instructions: str = ""


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


def require_operator_auth(request: Request) -> bool:
    expected = os.environ.get(COMMAND_CENTER_TOKEN_ENV, "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"{COMMAND_CENTER_TOKEN_ENV} is required before command center access is enabled.",
        )
    provided = extract_operator_token(request)
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail="Operator authentication required.",
            headers={"WWW-Authenticate": 'Basic realm="AIGC Command Center"'},
        )
    return True


def extract_operator_token(request: Request) -> str:
    header_token = request.headers.get("x-aigc-command-token", "").strip()
    if header_token:
        return header_token
    auth = request.headers.get("authorization", "").strip()
    lower = auth.lower()
    if lower.startswith("bearer "):
        return auth[7:].strip()
    if lower.startswith("basic "):
        try:
            decoded = base64.b64decode(auth[6:].strip()).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return ""
        if ":" in decoded:
            _username, password = decoded.split(":", 1)
            return password
        return decoded
    return ""


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "mode": "governed_command_center",
        "auth_required": True,
        "auth_configured": bool(os.environ.get(COMMAND_CENTER_TOKEN_ENV, "").strip()),
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
    if not RUN_CAPACITY.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="A governed run is already active; retry after it finishes.")
    run_id = f"AIGC-RUN-{uuid.uuid4()}"
    with RUN_LOCK:
        RUNS[run_id] = {"status": "queued", "steps": [], "current": "", "complete": False}
    try:
        thread = threading.Thread(target=_run_cycle_worker, args=(run_id,), daemon=True)
        thread.start()
    except Exception:
        with RUN_LOCK:
            RUNS.pop(run_id, None)
        RUN_CAPACITY.release()
        raise HTTPException(status_code=503, detail="Could not start the governed run.")
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
    _require_pending_review(review)
    result = run_command(
        build_accept_command(PROJECT_ROOT, review, request.phrase, DEFAULT_AUTHORIZATIONS_PATH),
        root=PROJECT_ROOT,
        label=f"accept:{action_id}",
    )
    return _command_payload(result)


@app.post("/api/reviews/{action_id}/deny", dependencies=[Depends(require_operator_auth)])
def deny_review(action_id: str, request: DecisionRequest) -> Dict[str, Any]:
    review = _find_review(action_id)
    _require_pending_review(review)
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
    _require_pending_review(review)
    result = run_command(
        build_revise_command(PROJECT_ROOT, review, request.revision_instructions, DEFAULT_AUTHORIZATIONS_PATH),
        root=PROJECT_ROOT,
        label=f"revise:{action_id}",
    )
    return _command_payload(result)


@app.post("/api/emergency-stop", dependencies=[Depends(require_operator_auth)])
def emergency_stop() -> Dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "aigc.py"), "--root", str(PROJECT_ROOT), "emergency-stop"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=False,
            timeout=EMERGENCY_STOP_TIMEOUT_SECONDS,
        )
        return {"ok": result.returncode == 0, "stdout": _safe_output(result.stdout), "stderr": _safe_output(result.stderr)}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Emergency-stop command timed out; verify the underlying stop state locally.")


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_operator_auth)])
def ui() -> str:
    return render_ui()


def _run_cycle_worker(run_id: str) -> None:
    try:
        with RUN_LOCK:
            RUNS[run_id]["status"] = "running"
        for name, command in BUSINESS_CYCLE:
            with RUN_LOCK:
                RUNS[run_id]["current"] = name
            try:
                result = subprocess.run(
                    command, cwd=PROJECT_ROOT, capture_output=True, text=True,
                    check=False, timeout=STEP_TIMEOUT_SECONDS,
                )
                returncode = result.returncode
                stdout = result.stdout
                stderr = result.stderr
            except subprocess.TimeoutExpired as exc:
                returncode = 124
                stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr = (exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
                stderr += f"\nTimed out after {STEP_TIMEOUT_SECONDS} seconds."
            step_payload = {
                "name": name,
                "command": command,
                "returncode": returncode,
                "ok": returncode == 0,
                "stdout_tail": _safe_output(stdout),
                "stderr_tail": _safe_output(stderr),
            }
            with RUN_LOCK:
                RUNS[run_id]["steps"].append(step_payload)
            if returncode != 0:
                with RUN_LOCK:
                    RUNS[run_id]["status"] = "timed_out" if returncode == 124 else "failed"
                    RUNS[run_id]["complete"] = True
                return
        with RUN_LOCK:
            RUNS[run_id]["status"] = "completed"
            RUNS[run_id]["complete"] = True
            RUNS[run_id]["current"] = ""
    except Exception:
        # Do not leave a permanently "running" record after an unexpected worker error.
        with RUN_LOCK:
            if run_id in RUNS:
                RUNS[run_id]["status"] = "failed"
                RUNS[run_id]["complete"] = True
                RUNS[run_id]["current"] = ""
    finally:
        RUN_CAPACITY.release()


def _require_pending_review(review) -> None:
    if review.expired:
        raise HTTPException(status_code=409, detail="Review packet is expired")
    if review.external_action_performed:
        raise HTTPException(status_code=409, detail="Packet already records outward completion")
    if review.decision != "pending":
        raise HTTPException(status_code=409, detail="Packet is not pending")


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
        "stdout": _safe_output(result.stdout),
        "stderr": _safe_output(result.stderr),
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
  <p>This command center requires operator authentication. Configure <code>AIGC_COMMAND_CENTER_TOKEN</code> outside Git before use.</p>
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
    <h2>Emergency Control</h2>
    <button class="danger" onclick="stopNow()">Enable Emergency Stop</button>
    <pre id="stop-output"></pre>
  </div>
<script>
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
  root.innerHTML = '';
  data.reviews.forEach(item => {{
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `<h3>${{escapeHtml(item.action_id)}} — ${{escapeHtml(item.recipient)}}</h3>
      <p>Status: ${{escapeHtml(item.decision)}} | Expired: ${{item.expired}} | Risk: ${{escapeHtml(item.risk_class)}} / ${{escapeHtml(item.safety_status)}}</p>
      <p>Quality: ${{escapeHtml(item.quality_state)}}</p>
      <pre>${{escapeHtml(item.artifact_preview || '').slice(0, 1600)}}</pre>
      <p>Type exact acceptance phrase only after review:</p>
      <input id="phrase-${{item.action_id}}" placeholder="Exact acceptance phrase" />
      <button onclick="acceptItem('${{item.action_id}}')">Accept Selected</button>
      <button onclick="denyItem('${{item.action_id}}')">Deny</button>
      <textarea id="revise-${{item.action_id}}" placeholder="Revision instructions"></textarea>
      <button onclick="reviseItem('${{item.action_id}}')">Request Revision</button>`;
    root.appendChild(div);
  }});
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
async function stopNow() {{
  const r = await fetch('/api/emergency-stop', {{method:'POST'}});
  document.getElementById('stop-output').textContent = JSON.stringify(await r.json(), null, 2);
}}
function escapeHtml(value) {{
  return String(value).replace(/[&<>'"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}}[c]));
}}
loadReviews();
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
