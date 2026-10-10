# Devpost Submission Draft

## Evidence boundary

The first section below is ready to paste while only repository evidence is
available. It intentionally does not claim a successful GitHub Actions run,
Google Cloud deployment, live Gemini call, judge publication, merge, or Devpost
submission. Add the receipt-gated paragraph only after every named value has
been verified against the exact release receipt.

## Paste-ready repository-evidence version

### Project title

AIGC — Governed Gemini Opportunity Assessment

### One-line description

RegenExcalibur's evidence-first workflow turns a permissioned opportunity into
a structured Gemini-assisted assessment while preserving deterministic policy,
human review, and a hard boundary against external business action.

### Inspiration

Opportunity assessment often mixes useful AI analysis with risky assumptions,
private data, unclear authority, and pressure to act quickly. AIGC explores a
more accountable pattern: separate analysis from action, bind claims to
evidence, and make deployment and publication explicit human decisions.

### What it does

The repository implements a dedicated Gemini opportunity-assessment path. It
validates and sanitizes an operator-supplied intake, rejects recognized
secret-like material, requests a strict structured assessment, validates the
model's input-evidence pointers, and applies deterministic policy. Every
assessment remains an internal draft until an authenticated operator records
one approve, deny, or revise attestation. Even approval does not authorize an
application, message, purchase, submission, or other external business action.

The production path is designed to fail closed. Its repository implementation
includes a durable emergency-stop epoch, idempotency binding, per-principal and
global rate and reserved-token limits, an isolated operator service, a separate
read-only judge service, non-generative dependency readiness checks, an exact
container file allowlist, exact-version Secret Manager references through the
Omega-X and Ultra-Secrets chain, and create-only Cloud Storage evidence with
object-generation receipts.

### How we built it

The application uses Python, FastAPI, Pydantic, the Google Gen AI SDK for Vertex
AI, PostgreSQL for durable runtime controls, and Cloud Storage for evidence.
The Gemini response contract requires a bounded recommendation, rationale,
risks, assumptions, proposed scope, disclosure text, and pointers to supplied
input fields. Deterministic code then evaluates AI permission, disclosure,
grounding pointers, risk, and human-review requirements.

The repository also contains a default-deny Canadian staging authorization
validator, an allowlisted non-root container build, a plan-first deployment
helper that resolves and deploys an immutable image digest with no traffic, and
a permit-bound canary helper for exactly one synthetic call with no automatic
retry. These helpers do not prove that deployment or a live model call occurred.

### Responsible AI and safety

AIGC treats model output as an assessment of operator-supplied material, not as
verified fact. It records assumptions and evidence pointers, discloses AI use,
requires accountable human review, and never grants the model authority to act
externally. Shared-credential possession is not described as verified human
identity. Readiness checks use only configuration, metadata, storage, and
control-store probes; they do not generate model output.

If final evidence persistence or the durable completion marker fails, the
result is not exposed as a completed execution. A network-unknown canary
outcome is recorded as non-retriable rather than silently spending a second
model call.

### Challenges

The hardest part was making operational claims narrower than implementation
claims. A passing unit test can show how an emergency stop, idempotency rule, or
generation-bound receipt behaves in a controlled test; it cannot show that a
specific cloud environment is configured correctly or that a live Gemini call
occurred. The workflow therefore treats CI, staging authorization, immutable
deployment, live execution, judge publication, and final submission as
separate receipt-gated events.

### Accomplishments

- A strict Gemini assessment schema with deterministic, fail-closed policy.
- Durable stop, idempotency, rate, and reserved-token control contracts.
- Separate operator and provider-free, read-only judge surfaces.
- Generation-bound evidence and content-bound judge-publication contracts.
- A default-deny Canadian staging and one-call proof sequence.
- An explicit distinction between repository evidence and runtime evidence.

### What we learned

Governance is most useful when it changes runtime state transitions. It is not
enough to describe a human gate or an audit trail: the system must prevent a
provider call when control state is unavailable, quarantine evidence that is
not bound to durable completion, and refuse public claims that exceed their
receipts.

### What's next

Restore GitHub-hosted runner admission and obtain a passing receipt for the
exact release SHA; review and authorize the Canadian staging configuration;
deploy the allowlisted image by digest; execute one synthetic, permit-bound
Gemini assessment; publish only a sanitized judge receipt; capture a redacted
walkthrough; and merge and submit only after those receipts pass review.

### Current status disclosure

This submission text describes repository implementation. It does not, by
itself, claim a live Gemini call, production availability, cloud-budget
enforcement, verified human identity, public judge access, PR merge, or Devpost
submission.

## Receipt-gated live-proof paragraph

Do not paste this paragraph until a completed
`aigc.gemini-runtime-receipt.v1` and matching deployment and CI receipts exist.
Replace every angle-bracket field from those receipts; do not infer a value.

> On `<captured_at>`, one authorized synthetic staging assessment invoked
> `<provider>` model `<model>` in `<location>`. The recorded latency was
> `<latency_ms>` ms and provider-reported usage was `<prompt_tokens>` prompt,
> `<candidate_tokens>` candidate, and `<total_tokens>` total tokens. The run is
> bound to Git SHA `<release_revision>`, image digest `<image_digest>`, Cloud
> Run revision `<cloud_run_revision>`, and Cloud Storage object
> `<redacted_object_uri>` generation `<generation>`. The receipt records
> `model_api_call_performed: true` and
> `external_business_action_performed: false`.

Do not publish the raw response identifier, authentication material, private
intake or output, operator identifier, service-account email, candidate URL, or
an unreviewed bucket name.
