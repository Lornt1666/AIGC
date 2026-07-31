# AIGC Devpost Submission Evidence Template

> **Truth boundary:** This template is not evidence by itself. A claim becomes verified only when linked to exact repository, CI, deployment, or runtime receipts.

## Project identity

- Project: **AIGC**
- Repository: `Lornt1666/AIGC`
- Repository visibility: `PRIVATE`
- Submission status: `PLANNED | BLOCKED | PARTIAL | VERIFIED`
- Exact merged Git SHA: `<40-character SHA>`
- Pull request: `<number and URL>`
- Release tag: `<tag or NOT DEMONSTRATED>`

## One-sentence project statement

`<Describe only behavior demonstrated by the evidence matrix below.>`

## Problem and approach

`<State the problem, intended users, bounded scope, and why the governed Gemini workflow is appropriate.>`

## Architecture

- Architecture document: `<path>`
- Exact implementation paths/symbols: `<paths and symbols>`
- Trust boundaries: `<operator, provider, evidence store, judge surface>`
- Non-goals and prohibited behavior: `<list>`

## Implemented features

| Claim | Status | Repository evidence | Test evidence | Runtime evidence | Limitation |
|---|---|---|---|---|---|
| Governed Gemini assessment | `VERIFIED/PARTIAL/PLANNED/BLOCKED/NOT DEMONSTRATED` | `<path:symbol@SHA>` | `<test/run>` | `<receipt>` | `<boundary>` |
| Durable emergency stop |  |  |  |  |  |
| Approval-bound execution |  |  |  |  |  |
| Durable idempotency |  |  |  |  |  |
| Rate and budget ceilings |  |  |  |  |  |
| Secret-reference isolation |  |  |  |  |  |
| Read-only judge surface |  |  |  |  |  |
| Immutable evidence binding |  |  |  |  |  |

## Repository and CI evidence

- Exact reviewed SHA: `<SHA>`
- Exact merged SHA: `<SHA or NOT MERGED>`
- GitHub Actions workflow: `<name>`
- Run ID / attempt: `<ID>` / `<attempt>`
- Checked SHA: `<SHA>`
- Required checks conclusion: `<PASS/BLOCKED>`
- Test command: `<command>`
- Test count: `<passed/failed/skipped>`
- Coverage: `<method and value>`
- Artifact names and SHA-256: `<receipts>`

## Security and governance proof

- Emergency-stop receipt: `<path/URI/hash>`
- Approval receipt: `<path/URI/hash>`
- Idempotency replay/concurrency receipt: `<path/URI/hash>`
- Rate-limit and budget receipt: `<path/URI/hash>`
- Filesystem and egress allowlist receipt: `<path/URI/hash>`
- Redaction/secret-scan receipt: `<path/URI/hash>`
- Open Critical findings: `<0 required>`
- Open High findings: `<0 required>`

## Build and deployment evidence

Complete only after actual execution.

- Cloud project: `<approved project>`
- Region: `<approved region>`
- Build ID: `<ID>`
- Source Git SHA: `<SHA>`
- Container image URI: `<URI>`
- Immutable image digest: `sha256:<digest>`
- SBOM SHA-256: `<digest>`
- Provenance/attestation: `<receipt>`
- Cloud Run service: `<service>`
- Cloud Run revision: `<revision>`
- Startup/readiness/liveness proof: `<receipt>`
- Rollback proof: `<receipt>`

## Controlled Gemini assessment

Complete only after one explicitly approved request.

- Approval digest: `<digest>`
- Prompt digest: `<digest>`
- Idempotency digest: `<digest>`
- Provider: `<provider>`
- Returned model version: `<modelVersion>`
- Response/request identifier: `<ID or approved hash>`
- Latency: `<milliseconds>`
- Prompt tokens: `<value>`
- Candidate tokens: `<value>`
- Total tokens: `<value>`
- Cost ceiling and calculated cost: `<CAD>`
- Finish/safety status: `<value>`
- Output digest: `<digest>`
- External business action performed: `false`

## Immutable evidence object

- GCS URI: `gs://<bucket>/<object>`
- Object generation: `<generation>`
- Content type: `<type>`
- Size: `<bytes>`
- SHA-256: `<digest>`
- Independently retrieved by exact generation and rehashed: `<true/false>`

## Evaluation

- Dataset name/version: `<value>`
- Number of cases: `<denominator>`
- Correctness method/results: `<value>`
- Policy-compliance method/results: `<value>`
- Denial/adversarial method/results: `<value>`
- Latency and cost method/results: `<value>`
- Failed cases and remediation: `<value>`

## Judge-safe demonstration

- Judge access: `<read-only, time-bounded, revocable>`
- Demo data: `<synthetic/sanitized>`
- Demo runbook: `<path>`
- Reset/revocation proof: `<receipt>`
- Walkthrough manifest and hash: `<path/hash>`
- Screenshot manifest and hash: `<path/hash>`
- Fallback recorded demonstration: `<path/URL>`

## Reproduction steps

```text
<Exact commands pinned to the merged SHA and immutable image digest.>
```

## Known limitations

- `<State every material limitation.>`
- `<Do not describe local-only evidence as cloud/runtime proof.>`
- `<Do not describe a dry-run as a live Gemini assessment.>`

## Unsupported claims

| Claim | Why unsupported | Evidence needed |
|---|---|---|
| `<claim>` | `<gap>` | `<receipt>` |

## Rollback

```text
<Exact repository and Cloud Run rollback procedure.>
```

## Final review

- [ ] Every claim maps to exact evidence.
- [ ] Every receipt points to the final merged/deployed SHA.
- [ ] No secret or unnecessary personal data appears in text or media.
- [ ] No mutable tag is represented as deployment identity.
- [ ] Limitations and AI assistance are disclosed.
- [ ] Owner explicitly approved the final submission.
