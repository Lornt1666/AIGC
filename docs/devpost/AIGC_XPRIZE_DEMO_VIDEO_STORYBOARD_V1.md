# AIGC XPRIZE Demo Video Storyboard V1

Status: `PRODUCTION PLAN — RECORDING BLOCKED ON G6/G7/PILOT EVIDENCE`

Target duration: **2:40–2:55**. Hard stop: **under 3:00**.

## Production law

Only show a capability as live when the exact demonstrated revision has a retained receipt. If live G6/G7/pilot evidence is not complete, do not substitute mock footage and narrate it as real.

## 0:00–0:15 — Problem / thesis

Visual:
- title: `AIGC — Governed Gemini Opportunity Assessment`;
- one simple flow: `Opportunity → AI Assessment → Human Authority → Evidence → Work`.

Narration target:
- economic opportunities are expensive to assess manually;
- ordinary agent systems can blur model output, permission and execution;
- AIGC aims to increase useful AI-assisted work while preserving accountable authority.

## 0:15–0:35 — Architecture

Visual:

```text
WorkOrder
→ ContextEnvelope
→ ArtifactState / ChangeSet
→ VerifierReport
→ GovernanceDecision
→ ExecutionPermit
→ ToolInvocation
→ ExecutionReceipt
```

Overlay:

```text
Reasoning != Verification != Authority != Execution != Evidence
```

Do not show internal chain-of-thought.

## 0:35–0:55 — Opportunity intake / governed AI role

Visual:
- live/private operator surface if G6 is verified;
- sanitized opportunity input;
- task/assessment record;
- provider/model metadata.

Narration:
- Gemini helps analyze/structure the opportunity;
- the model cannot authorize its own consequential action;
- credentials stay outside prompts/evidence.

## 0:55–1:20 — One-use Gemini proof

**Only record this section after Issue #213 is verified.**

Visual evidence:
- exact release SHA;
- immutable image digest abbreviated on screen;
- one-use permit summary: provider/model, max calls = 1, cost ceiling;
- completed execution receipt;
- latency, token usage and CAD cost;
- response content redacted/minimized if needed.

Narration:
- one task;
- one invocation;
- no automatic retry after uncertain outcome;
- durable runtime controls and audit receipt.

Forbidden substitute:
- unit test output represented as live Gemini.

## 1:20–1:40 — Verification and human decision

Visual:
- Verifier result;
- GovernanceDecision;
- human approval/rejection surface;
- evidence timeline.

Narration:
- AI recommendation is candidate evidence;
- independent verification and human authority govern material transitions;
- execution claims require receipts.

## 1:40–2:00 — Real pilot / user value

**Only record after Issue #214 is complete.**

Visual:
- consented/redacted third-party pilot;
- problem/use case;
- before/after workflow timing or output;
- participant feedback or testimonial only within consent scope.

Narration:
- state exactly what the pilot participant used;
- report actual result/time/cost;
- do not generalize one pilot into broad market traction.

Fallback if no pilot before deadline:
- omit positive customer claim and state that customer proof is not complete. Do not count founder/synthetic use as a user.

## 2:00–2:20 — Revenue-Ω / business model

Visual:
- diagram, not fake payment activity:

```text
Employer / Client
→ agreed success / platform / compute fee
→ invoice lineage
→ settlement receipt
→ P&L
```

Narration:
- current Revenue-Ω software supports deterministic billing/sandbox settlement/evidence-bound finance;
- employment placement model defaults to employer-funded where applicable;
- real payment operations require commercial/provider/tax authorization.

If real arms-length revenue exists by filming time, show only settled evidence-backed amount.

## 2:20–2:40 — Why it is different

Visual:
- four tiles:
  1. governed autonomy;
  2. exact evidence/provenance;
  3. bounded Gemini execution;
  4. economic opportunity/job creation.

Narration:
- autonomy without evidence is hard to trust;
- evidence without authority is not permission;
- AIGC attempts to combine useful AI work with auditable controls.

## 2:40–2:55 — Close / judge path

Visual:
- repository access;
- evidence package;
- exact-head CI receipt;
- deployment/Gemini receipt;
- QR/link only if judge-safe and final.

Narration:
- judges can inspect the private repository/evidence package;
- finish with the strongest evidence-backed current claim, not an aspirational future capability.

## Required pre-record checklist

```text
[ ] G3 judge access path prepared
[ ] G4 current exact-head receipt valid
[ ] G6 immutable staging receipt valid
[ ] G7 live Gemini receipt valid
[ ] pilot evidence status known
[ ] finance claims reconciled
[ ] every screen secret/PII reviewed
[ ] account/project IDs minimized where unnecessary
[ ] no access token / API key / auth header / DSN displayed
[ ] final claim matrix reviewed
[ ] duration < 3:00
[ ] audio intelligible
[ ] video URL works without unintended privilege
```

## Evidence capture bundle

Retain separately from the video:

```text
video file SHA-256
recorded-at timestamp
exact release SHA/tree
image digest
Cloud revision
Gemini receipt ref
pilot receipt ref if shown
claim-matrix revision
redaction-review receipt
published video URL
```

Video upload/publication remains a separate authorized external action.
