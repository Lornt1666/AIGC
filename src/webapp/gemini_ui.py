from __future__ import annotations


def render_surface_ui(surface: str) -> str:
    if surface == "judge":
        return _JUDGE_UI
    return _OPERATOR_UI


_BASE_STYLE = """
  :root { color-scheme: dark; font-family: Inter, system-ui, sans-serif; }
  body { margin: 0; background: #07111d; color: #edf6ff; }
  main { max-width: 900px; margin: 0 auto; padding: 3rem 1.25rem; }
  .eyebrow { color: #69d5c5; letter-spacing: .12em; text-transform: uppercase; }
  .card { background: #0e2031; border: 1px solid #24445b; border-radius: 18px;
          padding: 1.25rem; margin: 1rem 0; box-shadow: 0 18px 50px #0005; }
  label { display: block; margin-top: .9rem; color: #bdd1df; }
  input, textarea, button { box-sizing: border-box; width: 100%; padding: .8rem;
          border-radius: 10px; border: 1px solid #426277; margin-top: .35rem; }
  input, textarea { background: #07111d; color: #edf6ff; }
  textarea { min-height: 110px; resize: vertical; }
  button { background: #69d5c5; color: #061018; border: 0; font-weight: 750;
           cursor: pointer; margin-top: 1rem; }
  button.danger { background: #ff7d79; }
  pre { white-space: pre-wrap; overflow-wrap: anywhere; background: #061018;
        padding: 1rem; border-radius: 12px; min-height: 3rem; }
  .muted { color: #9bb1c1; }
"""


_OPERATOR_UI = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RegenExcalibur · Governed Gemini Operator</title>
<style>{_BASE_STYLE}</style></head>
<body><main>
<p class="eyebrow">RegenExcalibur / AIGC</p>
<h1>Governed Gemini Opportunity Assessment</h1>
<p class="muted">Private operator surface. Every model call requires an
idempotency key, durable runtime controls, and bounded usage. Outputs remain
internal unless and until an operator records a separate decision.</p>
<section class="card">
  <h2>Operator authentication</h2>
  <label>Operator label (attestation only)<input id="label" maxlength="100"></label>
  <label>Operator token<input id="token" type="password" autocomplete="current-password"></label>
</section>
<section class="card">
  <h2>Assessment intake</h2>
  <label>Title<input id="title" maxlength="200"></label>
  <label>HTTPS source URL<input id="source" type="url"></label>
  <label>Description<textarea id="description" maxlength="12000"></textarea></label>
  <label>Constraints, one per line<textarea id="constraints"></textarea></label>
  <label><input id="permitted" type="checkbox"> AI assistance is permitted</label>
  <button id="assess">Run governed assessment</button>
  <pre id="result" aria-live="polite"></pre>
</section>
<section class="card">
  <h2>Emergency stop</h2>
  <label>Accountable reason<textarea id="stop-reason"></textarea></label>
  <button class="danger" id="stop">Activate durable Gemini stop</button>
  <pre id="stop-result" aria-live="polite"></pre>
</section>
</main>
<script>
const value = id => document.getElementById(id).value;
const headers = () => ({{
  "Content-Type": "application/json",
  "X-AIGC-Operator-Token": value("token"),
  "X-AIGC-Operator-Label": value("label")
}});
const show = (id, payload) => {{
  document.getElementById(id).textContent = JSON.stringify(payload, null, 2);
}};
document.getElementById("assess").addEventListener("click", async () => {{
  const h = headers();
  h["Idempotency-Key"] = "operator-ui-" + crypto.randomUUID();
  const response = await fetch("/api/gemini/workflows", {{
    method: "POST", headers: h, body: JSON.stringify({{
      title: value("title"), description: value("description"),
      source_url: value("source"),
      constraints: value("constraints").split("\\n").filter(Boolean),
      ai_assistance_permitted: document.getElementById("permitted").checked,
      ai_disclosure_required: true
    }})
  }});
  show("result", {{status: response.status, body: await response.json()}});
}});
document.getElementById("stop").addEventListener("click", async () => {{
  const response = await fetch("/api/gemini/runtime/emergency-stop", {{
    method: "POST", headers: headers(),
    body: JSON.stringify({{reason: value("stop-reason")}})
  }});
  show("stop-result", {{status: response.status, body: await response.json()}});
}});
</script></body></html>"""


_JUDGE_UI = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RegenExcalibur · Judge Evidence</title>
<style>{_BASE_STYLE}</style></head>
<body><main>
<p class="eyebrow">RegenExcalibur / AIGC</p>
<h1>Judge-safe Gemini Evidence</h1>
<p class="muted">Read-only, sanitized evidence receipts. This surface cannot
invoke Gemini, approve work, change controls, or expose private intake content.</p>
<section class="card">
  <label>Judge access token<input id="token" type="password"></label>
  <label>Public receipt ID<input id="receipt"></label>
  <button id="load">Load sanitized receipt</button>
  <pre id="result" aria-live="polite"></pre>
</section>
</main>
<script>
document.getElementById("load").addEventListener("click", async () => {{
  const receipt = document.getElementById("receipt").value;
  const response = await fetch("/api/judge/receipts/" + encodeURIComponent(receipt), {{
    headers: {{"X-AIGC-Judge-Token": document.getElementById("token").value}}
  }});
  document.getElementById("result").textContent =
    JSON.stringify({{status: response.status, body: await response.json()}}, null, 2);
}});
</script></body></html>"""
