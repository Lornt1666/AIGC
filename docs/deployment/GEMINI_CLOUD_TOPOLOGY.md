# AIGC deployment topology decision

**Status:** selected implementation boundary; no cloud provisioning or production authorization implied.

## Decision

Keep the existing AIGC command center on its documented AWS ECS Fargate path. Keep the isolated governed Gemini assessment service on its current Google Cloud path for this release candidate.

The Gemini service is not a generic container that can be moved to AWS without changes. Its production contracts currently bind to Vertex AI, Cloud Run's `K_REVISION`, Cloud SQL/PostgreSQL runtime control, Cloud Storage generation-bound evidence, and numeric-version Secret Manager references. The staging helper and build files are Google Cloud-specific.

## Service boundaries

| Surface | Intended host | State/evidence dependencies | Status |
|---|---|---|---|
| Existing AIGC command center | AWS ECS Fargate behind HTTPS ALB | Must gain durable shared run/review/evidence state; see #282 | Not provisioned; public traffic blocked by #275/#282 |
| Governed Gemini operator surface | Google Cloud Run, Canadian region after approval | Cloud SQL/PostgreSQL control store, Vertex AI, exact-version Secret Manager, GCS evidence | Repository implementation and CI only; no live service verified |
| Sanitized judge evidence surface | Separate private Google Cloud Run service | Read-only sanitized GCS receipt prefix; no provider or operator-secret authority | Repository implementation and CI only; no live service verified |

## Required controls before activation

- Review exact project, Canadian region, service accounts, IAM, secrets, database, buckets, quotas, and owner-approved CAD ceiling.
- Use the permit-bound no-traffic deployment and immutable image digest procedure.
- Run readiness checks and verify separate operator/judge credentials and least privilege.
- Perform only the separately authorized one-call synthetic canary, retain exact GCS generation and provider-usage receipts, then review evidence.
- Keep all public traffic, live provider calls, judge publication, and external business actions disabled until their individual gates pass.
- Do not infer cross-cloud authority: AWS roles do not authorize Google Cloud, and Google Cloud service accounts do not authorize AWS.

## Evidence boundary

The integration candidate's exact-head CI run `38083714333` passed on pre-documentation-refresh commit `42d1950684ab8f147151390bdc96dd7ed001feb0`. A fresh exact-head run is required after this document is added. CI does not establish cloud-account access, resource creation, a live endpoint, a Gemini model call, judge access, or final contest submission.
