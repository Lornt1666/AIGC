# AIGC Operational Product and Opportunity Acquisition Blueprint

**Status:** DESIGN ONLY — NOT PRODUCTION-AUTHORIZED  
**Default disposition:** BLOCK  
**Agents:** RX-69–RX-83

## Functional operating model

1. **Policy preflight (RX-69):** check source permission, API/auth method, terms URL, last review, rate limits, attribution, retention and eligibility. Unknown, stale or contradictory policy blocks the adapter.
2. **Discovery (RX-70/RX-76):** query only permitted sources; normalize listings; preserve canonical links and timestamps; deduplicate deterministically; respect rate limits and attribution.
3. **Evidence-bound fit (RX-71/RX-77/RX-78):** rank opportunities and product signals with transparent reasons, sources, assumptions and confidence. Never fabricate candidate credentials, customer interviews, market data or endorsements.
4. **Draft and human gate (RX-72/RX-73):** prepare application materials and scoped approval packets. Submission or external communication requires explicit approval bound to the job, materials digest, action and expiry. Assessments, legal declarations, identity verification, offer acceptance, contract signing and financial commitments remain human-only.
5. **Private pipeline (RX-74/RX-75):** screen for scams, track status/deadlines and prepare follow-ups. Candidate profiles and applications stay in a private user-controlled store, not the repository.
6. **Product operations (RX-79–RX-83):** translate validated needs into roadmap decisions, go-to-market experiments, customer delivery plans, unit economics, SLOs and incident response.

## Operational metrics

- Eligible source coverage, listing freshness, broken-link rate, duplicate rate and stale-listing rate.
- Fit-score usefulness, false positives/negatives, scam-screen precision and unapproved-action attempts blocked.
- Qualified opportunities saved, user-approved applications, response/interview rates, contracts won and time-to-first-relevant-opportunity.
- API/tool cost per qualified opportunity, model cost per dossier, connector success rate, queue delay, SLO burn and recovery time.

## MVP implementation gates

- Build typed source adapters with policy preflight, timeouts, rate limits, idempotency and circuit breakers.
- Use fixtures and synthetic candidate profiles first; never commit candidate PII.
- Add contract, integration, negative, prompt-injection, rate-limit, stale-policy, duplicate and failure-injection tests.
- Show source URL, attribution and freshness on every listing; do not present inferred fields as verified.
- Add private profile storage, consented access, scoped approval receipts and data export/deletion.
- Keep network adapters and external actions disabled until permissions, privacy, security, tests, rollback and independent review are complete.
- Never bypass CAPTCHA, authentication, platform terms or access controls.

## Source baseline consulted

- Greenhouse: https://docs.greenhouse.io/job-board
- Lever: https://github.com/lever/postings-api
- Adzuna: https://developer.adzuna.com/docs/terms_of_service and https://developer.adzuna.com/docs/search
- Remotive: https://remotive.com/remote-jobs/api
- USAJOBS: https://developer.usajobs.gov/api-reference/job-apis
- Canada Job Bank: https://www.jobbank.gc.ca/termsofuse-seeker.xhtml
- LinkedIn: https://ca.linkedin.com/legal/user-agreement and https://www.linkedin.com/help/linkedin/answer/a1341387/prohibition-of-scraping-software
- Wellfound: https://wellfound.com/terms

Source terms must be rechecked at activation. This document does not certify compliance or authorize any connector.


## Additional runtime controls RX-84–RX-94

The additional agents cover least-privilege auditing, sandbox assurance, connector contract tests, benchmark integrity, budget/quota controls, private memory lifecycle, evidence lineage, SLO/incident triage, human-review UX, rollback readiness and provider-build diagnosis. They are advisors/verifiers, not enforcement primitives. Runtime enforcement must be implemented in independently tested policy middleware, isolation boundaries, authenticated identity/approval services, observability pipelines and deployment controls. No agent may self-grant authority or make an advisory report equivalent to a control.
