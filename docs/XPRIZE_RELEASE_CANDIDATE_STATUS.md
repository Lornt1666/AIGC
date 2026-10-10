# AIGC Build with Gemini XPRIZE Release Candidate Status

## Status and precedence

**DRAFT RELEASE CANDIDATE — NOT MERGED — NOT DEPLOYED — NOT SUBMITTED**

This document is the current release-specific truth record for the Build with
Gemini XPRIZE candidate. Its branch, pull-request, CI, Devpost, and authority
statements supersede stale branch or status references retained in documents
imported from PR #145. Those imported documents remain technical design and
procedure sources; they are not evidence that a named external gate completed.

## Repository binding

- Repository: `Lornt1666/AIGC`
- Base branch: `main`
- Exact base commit: `6b5d944c5d29e99bfff6e60577f5ce96a94a54d5`
- Exact base tree: `56d8eb2a34631ac3b2ca03c7b352f23c20dd6d7b`
- Source implementation: PR `#145`
- Exact source head: `fcf943a50806e8fd07c2c60ae3afb2d8978ef958`
- Release branch: `release/xprize-gemini-2026`
- Draft release pull request: `#170`

The exact release commit and tree are the current PR head and the tested tree
recorded by the successful exact-head CI artifact. Do not copy a prior head SHA
from prose after the branch advances.

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
exact-head CI
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
