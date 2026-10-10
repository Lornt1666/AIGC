# AIGC Build with Gemini XPRIZE Release Candidate Status

## Status and precedence

**INTEGRATION CANDIDATE — LAST VERIFIED HEAD PASSED EXACT-HEAD CI — NOT MERGED — NOT DEPLOYED — NOT SUBMITTED**

This document is the current release-specific truth record for the Build with
Gemini XPRIZE candidate. Its branch, pull-request, CI, Devpost, and authority
statements supersede stale branch or status references retained in documents
imported from PR #145. Those imported documents remain technical design and
procedure sources; they are not evidence that a named external gate completed.

## Repository binding

- Repository: `Lornt1666/AIGC`
- Base branch: `main`
- Exact current-main base commit: `a96833daaf9b0c7ed7bb39b0f4af9000f2b11b1d`
- Current-main base tree: `64384176a6a885300cd08ff6c6781964d62d6975`
- Source implementation: draft PR `#170`, branch `release/xprize-gemini-2026`
- Source head reviewed: `cc1c77e473b4ef383310782d333a727b59ddf052`
- Reconciled integration candidate: draft PR `#284`, branch `integration/gemini-governed-mainline-2026-10-10`
- Last verified candidate head: `a9cf471590f69b2589872417616b1b049df00a22`
- Exact-head hosted CI run: `38083903246` — passed all 3 jobs, including canonical validation, focused Gemini tests, secret scanning, offline smoke, and locked v0.12/v0.13 revalidation.
- Retained artifacts: `aigc-colosseum-orchestration-exact-head-a9cf471590f69b2589872417616b1b049df00a22`, plus both locked-release validation artifacts.

These receipts prove only the exact head named above. Before merge or admission, compare the current PR head with the successful run's SHA and require all checks and artifacts for that exact SHA. Every later commit needs fresh exact-head CI.

## Bounded release scope

The candidate adds the isolated governed Gemini opportunity-assessment vertical
slice only:

- strict structured intake and assessment contracts;
- deterministic policy and accountable operator review;
- separate operator and provider-free read-only judge surfaces;
- durable emergency stop, idempotency, rate, request, and reserved-token limits;
- exact-version secret-reference brokering;
- non-generative readiness checks;
- generation-bound evidence and orphan-evidence quarantine;
- exact container and Cloud Build context allowlists;
- default-deny staging authorization, digest deployment planning, and a
  permit-bound one-call canary procedure;
- judge-safe receipt preparation and publication controls;
- focused positive and adversarial tests;
- XPRIZE narration, evidence matrix, and completion procedures.

The candidate deliberately does not import PR #145 rewrites to the legacy
`Dockerfile`, `README.md`, `requirements.txt`, Cloud Run deployment script,
legacy web application composition, or legacy webapp tests. Current Ω Mission
OS and connector behavior remain unchanged.

## CI admission contract

The pull-request-triggered `AIGC CI` workflow must:

1. request the exact `github.event.pull_request.head.sha`;
2. check out that full SHA, not the synthetic pull-request merge commit;
3. fail unless requested SHA equals observed `HEAD`;
4. record the tested Git tree and workflow revision;
5. install base and isolated Gemini dependencies and pass `pip check`;
6. pass Python compilation;
7. execute the shared canonical repository validation runner;
8. pass the release-only secret scan;
9. pass the focused Gemini suite with warnings treated as errors;
10. complete the offline smoke with no model call or external action; and
11. retain exact-head artifact evidence.

A queued run, zero-step job, synthetic-merge checkout, missing artifact,
skipped critical test, warning-only critical gate, SHA/tree mismatch, failed,
cancelled, or timed-out run is not an admission receipt.

## Hosting topology decision

- The existing AIGC command-center deployment target remains AWS ECS Fargate behind an HTTPS Application Load Balancer, as documented in `docs/deployment/AWS_ECS_FARGATE.md`.
- This isolated Gemini service remains a separate Google Cloud Run surface because its current provider, runtime, evidence, and secret-broker contracts explicitly depend on Vertex AI, Cloud SQL/PostgreSQL, Cloud Storage, numeric Secret Manager versions, and Cloud Run revision identity.
- This is an intentional multi-cloud design boundary, not a completed integration: no cross-cloud IAM federation, network route, cloud project, database, bucket, secret, or service has been provisioned or verified.
- Do not deploy the Gemini service on AWS using the GCP-specific deployment helper. Do not infer that AWS authorization grants Google Cloud authority.
- AWS command-center public traffic remains blocked by #275 and #282. Gemini staging/live activation remains blocked by its exact-target authorization and runtime-receipt gates.

## Devpost state

- Devpost project ID: `1289277`
- Project: `AIGC — Governed Gemini Opportunity Assessment`
- XPRIZE association: present
- Project page: published by Devpost when required project fields were saved
- XPRIZE submission timestamp: absent
- Final contest submission: not performed

The project page may describe repository implementation. It must not claim a
live Gemini call, cloud deployment, production operation, users, revenue,
customer evidence, judge publication, merge, or final submission until the
corresponding receipts exist.

## Known production blockers retained from design review

Before any production or real-user activation, governed review must resolve or
prove at runtime at least the following:

- server-side atomic consumption of a one-use live-model permit bound to actor,
  tenant, request/model/prompt/schema/policy digests, release revision, expiry,
  emergency-stop epoch, and usage ceiling;
- a least-privilege evidence read/index design that does not require an
  incompatible object-list permission for a create-only runtime writer;
- exact Canadian staging project, region, IAM, service accounts, numeric secret
  versions, evidence buckets, quotas, and an owner-approved CAD ceiling;
- immutable image digest, Cloud Build receipt, and no-traffic Cloud Run
  revisions;
- one permit-bound synthetic Gemini runtime receipt with provider usage,
  latency, release SHA, image digest, revision, and exact GCS URI/generation;
- explicit judge-publication authorization and redaction-reviewed media;
- truthful customer, user, revenue, expense, and P&L evidence.

Repository tests can verify contracts and failure behavior. They cannot alone
prove these external operational facts.

## Authority boundary

```text
production_activation=false
gmail_send_authority=absent
github_runtime_mutation_authority=absent
external_business_action_authority=absent
automatic_merge=false
merge=false
deployment=false
live_gemini_call=false
judge_publication=false
increment_12_1_started=false
devpost_submission=false
```

No successful CI result changes these values. Each later external gate requires
separate, explicit, exact-target authorization and a retained receipt.

## Next governed sequence

```text
verify exact-head CI and retained artifacts for the current PR revision
→ governed code and residual-risk review
→ separately authorized Canadian staging preparation
→ immutable no-traffic deployment
→ one permit-bound synthetic canary
→ evidence review
→ separately authorized bounded pilot
→ truthful business and customer evidence
→ sanitized judge package and three-minute video
→ final claim-to-receipt review
→ explicit Devpost submission approval
```

Do not merge, deploy, activate production, send Gmail, grant GitHub runtime
mutation, begin Increment 12.1, publish judge evidence, or submit to Devpost
merely because the release candidate or CI exists.
