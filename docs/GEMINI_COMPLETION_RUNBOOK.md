# Governed Gemini Completion Runbook

This runbook is the procurement record for completing the governed Gemini
opportunity-assessment workflow under RegenExcalibur's business identity. A
gate is complete only when its named receipt exists. Repository implementation
is not evidence of a live deployment or live Gemini call.

## Current boundary

- Repository: `Lornt1666/AIGC`
- Source branch: `release/xprize-gemini-2026` / PR `#170` (stale, draft, non-mergeable)
- Reconciled candidate: `integration/gemini-governed-mainline-2026-10-10` / PR `#284` (draft)
- Recorded verified candidate head: `a9cf471590f69b2589872417616b1b049df00a22`
- Exact-head CI run `38083903246`: success; all 3 jobs and all critical validation steps passed, with the canonical and both locked-release artifacts retained. Before merge, verify that the current PR head has its own successful run; any later commit requires a new exact-head receipt.
- Production and staging authorization remain default-deny.
- Runtime controls, isolated surfaces, governed secret access, readiness,
  container allowlisting, and generation-bound evidence are repository
  implementations; they are not yet staging-operation receipts.
- No Cloud resource creation, deployment, live Gemini assessment, merge, judge
  publication, or Devpost submission is authorized merely by this runbook.

## Hosting topology decision

The existing AIGC command center targets AWS ECS Fargate behind an HTTPS Application Load Balancer. The isolated Gemini assessment service remains a separate Google Cloud Run surface because its current implementation depends on Vertex AI, Cloud SQL/PostgreSQL, Cloud Storage evidence, exact-version Secret Manager references, and Cloud Run revision identity. This is an intentional multi-cloud boundary, not a claim that either cloud is provisioned or connected. Do not run the GCP deployment helper against AWS resources or infer cross-cloud permissions. AWS public exposure remains blocked by #275 and #282; Gemini staging/live execution remains blocked by its own target-specific authorization and evidence gates.

## Completion sequence

| Gate | Action | Required receipt | Stop condition |
|---|---|---|---|
| CI-1 | Run the current PR head through AIGC CI and inspect all required jobs | Actions URL with allocated steps, complete logs, passing conclusion, head SHA and artifacts | A zero-step job is not a code failure and is not a passing receipt |
| CTRL-1 | Validate emergency stop, idempotency, rate/token limits, surface isolation, SecretBroker, readiness, image allowlist and GCS receipts | Passing unit/integration logs bound to the release SHA | Any failing or skipped critical test |
| GCP-1 | Review exact staging project, Canadian region, IAM, service accounts, exact secret versions, buckets and CAD ceiling | Completed `gemini_staging_authorization.v1` with exact approval phrase and unexpired authorization | Blank identifier, broad IAM, mutable secret alias, missing ceiling or authorization false |
| DEPLOY-1 | Build the allowlisted image and deploy by `sha256` digest with no traffic | Artifact Registry digest, Cloud Build ID, Cloud Run revision and inspected configuration | Mutable tag used for deployment or revision differs from authorized SHA |
| LIVE-1 | Execute exactly one synthetic, permissioned assessment | Completed `gemini-runtime-receipt.v1` with model, latency, usage, SHA, digest, revision and GCS URI/generation | Permit mismatch/expiry, emergency stop, readiness failure or missing usage/evidence |
| JUDGE-1 | Publish one explicitly authorized sanitized receipt and capture walkthrough/screenshots | Content-bound publication receipt plus redacted media manifest | Private intake/output/operator identity appears in judge material |
| PR-1 | Review changed files, receipts and required checks; mark ready; merge | Approved PR, passing required checks and merge commit SHA | Any earlier gate incomplete |
| DEVPOST-1 | Update and submit only receipt-backed claims | Saved Devpost preview, claim-to-receipt matrix and final submission confirmation | Claim is broader than repository/runtime evidence |

## CI recovery procedure

Historical context: earlier Actions runs did create jobs without allocating a runner, leaving zero steps, logs, or artifacts. The recorded run `38083903246` on candidate `a9cf471590f69b2589872417616b1b049df00a22` completed successfully with real validation steps and retained artifacts. Verify the current PR head has a matching passing run before merge; if a later run has zero steps, no logs, or no artifacts, treat it as a runner/account-capacity blocker rather than a code pass.

1. In GitHub, inspect the failed job annotation and repository
   **Settings → Actions → General**.
2. Confirm Actions are enabled for the repository and allowed actions include
   the workflow's pinned actions.
3. Inspect the owning account or organization billing page for Actions minutes,
   spending limit, payment method and plan eligibility.
4. Restore hosted-runner eligibility without increasing spend beyond the
   owner's approved ceiling.
5. Re-run the exact PR-head workflow once.
6. Accept the gate only if `Set up job` and every workflow step ran, logs are
   downloadable, required artifacts exist and the conclusion is `success`.

The workflow now avoids duplicate PR-branch `push` runs; it runs for pull
requests, `main` pushes and explicit manual dispatches.

## Control verification procedure

Run the exact-head test suite without cloud credentials:

```bash
python -m pytest
python scripts/run_gemini_workflow_smoke.py
```

Accept `CTRL-1` only when the complete suite passes and the exact-head hosted CI
artifact contains the logs. At minimum, review the tests for durable controls,
surface isolation, readiness, image allowlisting, GCS receipts, governed
secrets, staging authorization, digest deployment, controlled canary, and judge
receipt storage. The offline smoke must continue to report no model call,
deployment, or external business action.

## Staging authorization procedure

Copy `config/gemini_staging_authorization.example.json` outside the repository
or to an intentionally untracked permit path, then fill every exact identifier.
Do not commit an approved permit.

The reviewer must confirm:

1. The project belongs to the intended Google Cloud billing account.
2. The recorded infrastructure region is Canadian. The current regional
   Gemini endpoint table lists Montréal (`northamerica-northeast1`) and not
   Toronto, so the authorization records Montréal as the Vertex location and
   rechecks the selected model there before deployment.
3. Operator and judge use different service accounts. Judge has no Vertex role,
   no Secret Manager access to operator/runtime-admin credentials and no
   control-store write permission. No primitive or administrative role is
   accepted; Secret Manager and Storage access is reviewed at the exact secret,
   bucket, or prefix scope, and private Cloud Run invoker bindings are recorded.
4. Every Secret Manager reference ends in an exact numeric version. `latest`
   is forbidden.
5. Evidence buckets have public-access prevention and uniform bucket-level
   access. Runtime evidence is create-only for the operator. Judge access is
   limited to the sanitized receipt prefix. Each service receives read access
   only to its exact, non-sensitive readiness sentinel; readiness does not
   require bucket listing.
6. The owner records an authorized monthly CAD ceiling and acknowledges that a
   Cloud Billing budget is an alert, not a hard spending cap. Vertex quotas and
   application limits provide additional guardrails.
7. The exact release SHA and approval phrase match the permit.

## Live-assessment procedure

Use `config/gemini_canary_intake.example.json` without adding personal,
customer, credential, payment, or confidential data. Review the fixture and
hash its canonical JSON before requesting authorization. The one-call permit
must bind that exact fixture hash, model, release SHA, immutable image digest,
and operator Cloud Run revision. The committed fixture's current canonical
SHA-256 is
`f11f7c38730d2c207240d3966a53b1b28ad58e3e07c7028f0faa933127f7e874`;
recompute it from the reviewed file and require equality rather than trusting
this documentation. Any fixture edit invalidates the permit.

Before the call:

- required CI and control tests pass;
- operator `/readyz` is `200` and reports no generative probe;
- emergency stop is inactive at the recorded epoch;
- the idempotency key is unique and retained;
- the permit is unexpired and allows exactly one call.

After the call, capture only:

- provider/model/location;
- latency and provider-reported usage;
- response-ID presence, not the identifier in public material;
- release SHA, image digest and Cloud Run revision;
- run/input/assessment hashes and policy outcome;
- GCS `gs://` URI, exact generation, and record hash;
- truthful model-call and external-action flags.

If final evidence persistence fails, the assessment is unusable and the
idempotency key remains non-retriable. A second model call requires a new,
explicit permit.

## Judge walkthrough and media procedure

Start from `config/gemini_judge_media_manifest.example.json`. Keep its
publication authorization false until the final files and sanitized receipt
have been reviewed.

1. Prepare a sanitized judge-receipt draft from the exact authorization,
   deployment, CI, and live runtime receipts. The default command performs only
   a create-only local draft write and creates no GCS object:

   ```bash
   python scripts/publish_gemini_judge_receipt.py \
     /secure/path/staging-authorization.json \
     /secure/path/deployment-receipt.json \
     /secure/path/ci-receipt.json \
     /secure/path/runtime-receipt.json
   ```

   The public claim excludes the intake, model output, operator identity,
   decision reason, response identifier, authentication material, and private
   URLs. Keep the printed content-bound publication phrase out of public logs.
2. Review the content hash, then authorize publication with the byte-exact,
   content-bound phrase. Publication is blocked unless the staging
   authorization passes the judge gate, the exact draft still matches all four
   receipts, and the explicit mode is used:

   ```bash
   python scripts/publish_gemini_judge_receipt.py \
     /secure/path/staging-authorization.json \
     /secure/path/deployment-receipt.json \
     /secure/path/ci-receipt.json \
     /secure/path/runtime-receipt.json \
     --publish \
     --draft reports/artifacts/gemini_staging/judge-receipt-draft.json \
     --confirmation-phrase '<exact phrase printed by prepare mode>'
   ```

   This command is not authorized merely because it appears here. Until the
   judge authorization and runtime receipts exist, stop after preparation (or
   before it if its evidence gate fails). Record the create-only receipt and
   index URI, generation, and checksum privately after an authorized
   publication.
3. Open only the no-traffic candidate revisions using an authorized reviewer
   identity. Do not expose identity tokens, application-token headers, browser
   developer tools, environment variables, secret references, or account
   consoles in the recording.
4. Record one walkthrough of the already completed synthetic run. Do not issue
   another Gemini request for the recording. Show the synthetic-data and AI-use
   disclosures, non-generative readiness result, policy/human-review boundary,
   and read-only sanitized judge receipt.
5. Capture the operator-result and judge-receipt screenshots listed in the
   manifest. Redact private bucket and candidate names if their disclosure was
   not separately approved.
6. Hash each final media file, complete every redaction-review flag, and bind
   the manifest to the release SHA, image digest, both Cloud Run revisions,
   runtime receipt, and judge receipt.
7. Obtain explicit publication authorization only after viewing the exact
   files. A completed manifest is evidence of review; it does not itself upload
   or publish media.

## Evidence packet register

Keep approved permits and runtime receipts outside the repository unless a
separately reviewed redacted copy is intentionally committed. The completion
packet must contain:

| Artifact | Minimum binding |
|---|---|
| CI receipt | repository, run URL/ID, exact head SHA, executed-step count, conclusion, artifact names |
| Staging authorization | project, Canadian regions, resources, IAM review, exact secret versions, CAD ceiling, authorizer and expiry |
| Deployment receipt | release SHA, Cloud Build ID, immutable digest, operator/judge revisions and candidate URLs, no traffic |
| Live permit | fixture hash, model, release SHA, digest, operator revision, one call, token ceiling and expiry |
| Runtime receipt | model/location, latency/usage, run and content hashes, release/digest/revision, GCS URI/generation and CI receipt |
| Judge publication receipt | sanitized claim hash, publication phrase, GCS receipt/index generations and checksums |
| Media manifest | final file hashes, redaction review, runtime/judge receipt bindings and publication authorization |
| PR/Devpost receipts | approval/checks, merge SHA, reviewed preview and submission confirmation |

## Claim discipline

Allowed repository-backed wording before staging proof:

> The repository implements a governed Gemini opportunity-assessment workflow
> and contains offline tests for human review, fail-closed policy checks and
> default-deny deployment controls.

Wording that requires a completed live receipt:

> A controlled staging assessment invoked the recorded Vertex AI Gemini model
> and produced the attached generation-bound runtime evidence.

Never claim production deployment, continuous availability, guaranteed budget
enforcement, verified human identity, judge publication or Devpost submission
without the corresponding receipt.

The only critical missing external assets are listed in
`docs/GEMINI_REQUIREMENTS_EVIDENCE_MATRIX.md`. Do not expand that list with
optional polish while a completion gate is blocked.
