# Production Security and Privacy Baseline v1

Status: `IMPLEMENTED_INTERNAL_PENDING_OPERATIONAL_EVIDENCE`  
Parent program: issue `#83`  
Workstream: issue `#86`  
External action performed: **No**

## Purpose

This baseline converts the accepted production environment decision into enforceable internal HTTP, privacy, redaction, classification, and threat-model controls.

It does not claim that edge TLS, Cloud Armor, distributed rate limiting, Identity Platform, Secret Manager, Cloud SQL, staging deployment, an incident exercise, a vulnerability scan, or independent review has occurred.

## Canonical artifacts

```text
config/production_security_privacy_baseline.json
config/production_threat_model.json
config/production_privacy_impact_register.json
schemas/production_security_privacy_baseline.schema.json
schemas/production_threat_model.schema.json
schemas/production_privacy_impact_register.schema.json
src/security/production_http_security.py
src/api/security_hardened_app.py
```

## Hardened application entrypoint

Run locally or in an isolated test environment:

```bash
uvicorn src.api.security_hardened_app:app --host 127.0.0.1 --port 8092
```

This entrypoint wraps the existing AIGC API with:

- host allowlisting;
- cross-origin default deny;
- one-megabyte request-size limit;
- fixed-window local rate limiting;
- cookie-authenticated CSRF validation;
- request identifiers;
- no-store controls for identity, audit, Quest, and review evidence paths;
- content-type, frame, referrer, permissions, CSP, cross-origin, and HSTS headers;
- server-header removal where present.

The local limiter is defence in depth only. Production still requires observed edge rate limiting and abuse controls.

## Current Content Security Policy limitation

The existing Quest Board contains inline script and style content. The current policy therefore permits `'unsafe-inline'` for scripts and styles while retaining default-deny directives, `frame-ancestors 'none'`, `base-uri 'none'`, and `form-action 'self'`.

Before public onboarding, the UI should move scripts and styles into separately hashed or nonce-bound resources. This remains an explicit hardening item rather than an unsupported completion claim.

## Privacy controls

The baseline prohibits:

- request-body logging;
- query-value logging;
- raw token persistence;
- raw provider-claim persistence;
- raw secret values in source, logs, or receipts;
- public self-registration;
- default external sharing.

Structured security logging must use `redact_security_event()` and an allowlist of safe header names. Authorization, cookie, token, password, secret, private-key, provider-claim, assertion, and nonce fields are redacted recursively.

## Provisional data classification

| Class | Encryption | Application logging | External sharing default |
|---|---:|---:|---:|
| Public | Optional by content | Allowed after approval | Deny |
| Internal | Required | Minimum-necessary only | Deny |
| Confidential | Required | Deny raw content | Deny |
| Restricted | Required | Deny | Deny |

This register remains `PROVISIONAL_PENDING_OPERATOR_REVIEW` until the detailed data-classification decision in issue #85 is finalized.

## Threat-model coverage

The threat model explicitly records:

- forged or replayed identity assertions;
- caller-supplied role and scope injection;
- cross-tenant/project access;
- evidence tampering;
- audit repudiation;
- secret disclosure;
- request abuse and denial of service;
- CSRF session abuse;
- supply-chain compromise;
- privacy overcollection and overretention.

Every trust boundary is default deny. Defensive tests are authorized; third-party and production testing are not.

## Privacy-impact status

The privacy register blocks public onboarding and records:

- minimum-necessary purposes;
- data subjects and categories;
- purpose and tenant/project binding;
- accepted retention baselines;
- incomplete access, correction, export, deletion, and legal-hold procedures;
- privacy-counsel and jurisdictional review requirements;
- residual risks that must be resolved before public use.

The register deliberately marks legal-basis selection as `COUNSEL_REVIEW_REQUIRED`; it does not present software output as legal advice or legal approval.

## Operational blockers

The evaluator must continue to report `production_complete: false` until all of the following are evidenced:

```text
staging_tls_observed
edge_rate_limit_observed
sbom_generated
vulnerability_scan_passed
incident_exercise_passed
independent_review_passed
```

Additional provisional blockers:

```text
data_classification_register
deletion_export_policy
secret_rotation_procedure
```

Zero unresolved high or critical findings is mandatory.

## Test coverage

The tests verify:

- full Draft 2020-12 schema validation;
- default-deny host and origin behavior;
- response security headers;
- HSTS on HTTPS requests;
- no-store behavior on sensitive APIs;
- cookie-authenticated CSRF enforcement;
- oversized-request denial;
- rate-limit denial;
- recursive event redaction;
- threat-model uniqueness and default-deny boundaries;
- privacy onboarding, logging, persistence, and legal-review blocks.

## Readiness truth

This slice may support `security_privacy_wiring = implemented_internal` evidence. It does not justify `complete` because staging and independent operational evidence are absent.

A later evidence-only PR may update the readiness ledger only after issue #86 exit criteria are met at one exact revision.

## Authority boundary

Authorized:

- defensive internal implementation;
- local and isolated staging tests;
- schema, middleware, threat-model, privacy, and runbook refinement.

Not authorized:

- secret access;
- Google Cloud resource changes;
- third-party security testing;
- production security testing;
- public onboarding;
- connector activation;
- production deployment;
- external action.
