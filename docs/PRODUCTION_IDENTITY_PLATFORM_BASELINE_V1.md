# Production Identity Platform Baseline v1

Status: `IMPLEMENTED_INTERNAL_PENDING_PROVIDER_AND_STAGING_EVIDENCE`  
Parent program: issue `#83`  
Workstream: issue `#88`  
Provider configured: **No**  
Secret accessed: **No**  
User onboarded: **No**  
Production identity activated: **No**  
External action performed: **No**

## Purpose

This baseline implements the provider-neutral production adapter and durable server-session contracts selected by the accepted environment decision:

- Google Cloud Identity Platform;
- Google sign-in only;
- one accountable AIGC tenant initially;
- public self-registration disabled;
- PIBC-v1 remains the only provider-to-domain identity boundary;
- roles, scopes, tenant authority, and project authority come from trusted AIGC persistence, never provider claims or browser input.

The configured Identity Platform project ID is intentionally `null`. The session-pepper reference contains an unresolved project placeholder. Therefore this baseline cannot accept a live provider assertion or open a production session today.

## Canonical artifacts

```text
config/production_identity_platform_baseline.json
schemas/production_identity_platform_baseline.schema.json
schemas/identity_platform_staging_receipt.schema.json
src/infrastructure/identity/google_identity_platform_adapter.py
src/domain/identity/production_sessions.py
src/application/production_sessions.py
src/infrastructure/persistence/sqlite/production_identity.py
src/infrastructure/persistence/sqlite/durable_production_identity.py
src/infrastructure/persistence/sqlite/provider_revocation.py
migrations/sqlite/0004_production_identity_sessions.sql
migrations/postgresql/0004_production_identity_sessions.sql
```

## Identity Platform assertion verification

The adapter accepts one untrusted field:

```text
signed_assertion
```

It rejects unknown assertion fields and never accepts caller-supplied:

- principal IDs;
- memberships;
- tenant or project authority;
- roles or scopes;
- assurance levels;
- verification flags;
- public-key material;
- revocation decisions;
- session identifiers.

For a configured staging provider, verification requires:

1. JWT header algorithm exactly `RS256`;
2. non-empty `kid`;
3. a certificate selected from the allowlisted Google Secure Token certificate endpoint;
4. valid cryptographic signature;
5. audience equal to the exact Identity Platform project ID;
6. issuer equal to `https://securetoken.google.com/<project-id>`;
7. required `sub`, `iat`, `exp`, `auth_time`, `firebase`, verified email, and email claims;
8. current expiry and bounded clock skew;
9. authentication age within the configured maximum;
10. `firebase.sign_in_provider` exactly `google.com`;
11. provider tenant match when a provider tenant is later configured;
12. exactly one active trusted provider-subject mapping;
13. mapped AIGC tenant equal to `tenant-primary`;
14. current provider revocation evidence.

The adapter emits only minimum-necessary normalized evidence:

- provider binding;
- provider subject for internal mapping;
- AIGC principal ID;
- issuer and audience;
- times;
- assurance values;
- evidence IDs;
- digests of minimum-necessary claims and nonce when present.

It does not place raw signed assertions, email addresses, roles, scopes, unrestricted provider claims, or certificates into PIBC receipts.

## Public-key handling

The Google certificate transport:

- requires the hardcoded HTTPS Google APIs host;
- uses no credential;
- applies a bounded network timeout;
- accepts only certificate-shaped values;
- honors a bounded cache lifetime;
- refreshes when the cache expires or a key ID is missing;
- fails closed if the requested key ID remains unavailable.

Offline tests inject generated RSA certificates and never contact Google.

## Subject mapping

The provider subject is not the AIGC principal, and an email address is never used as an authority identifier.

`provider_subject_bindings` maps:

```text
provider binding + provider subject
→ principal
→ membership
→ tenant
→ project
```

The table stores no email address and no provider profile. Mapping updates require optimistic revision control.

## Provider revocation state

`provider_subject_revocation_state` stores only:

- provider binding;
- provider subject;
- disabled status;
- provider valid-after time;
- checked time;
- evidence ID;
- revision.

A verification fails closed when revocation evidence is:

- missing;
- disabled;
- older than the allowed cache age;
- newer than the assertion authentication time.

A future staging synchronizer must obtain this information through an approved server-side administrative path and update it without persisting tokens or user profile data. Provider synchronization and credentials are not included in this baseline.

## Server-owned sessions

After verified provider evidence and trusted subject mapping, the session service may issue a one-time opaque session credential.

Storage contains only:

- HMAC-SHA256 credential digest;
- AIGC principal, membership, tenant, and project bindings;
- AAL;
- issue, last-seen, idle-expiry, and absolute-expiry times;
- lifecycle state and revision;
- minimum-necessary evidence IDs;
- rotation/revocation metadata.

It never stores the raw session credential.

Current cookie policy:

```text
name: aigc_session
Secure: true
HttpOnly: true
SameSite: strict
idle timeout: 30 minutes
absolute timeout: 12 hours
```

The HMAC pepper must later be resolved from Google Secret Manager through an approved workload identity. The current placeholder causes production activation to remain blocked.

### Idle renewal

Successful session authentication:

- validates state, idle expiry, absolute expiry, tenant, and project;
- advances the last-seen time through optimistic revision control;
- renews the idle window;
- never extends beyond absolute expiry.

### Rotation

Rotation requires:

- active current session;
- current verified provider evidence;
- exact provider binding and subject match;
- principal and membership match;
- atomic transition of the old session to `ROTATED`;
- a newly generated credential and digest.

The old credential is rejected immediately after rotation.

### Revocation and logout

Explicit logout/revocation:

- requires an active session and a reason;
- updates the durable state to `REVOKED` using optimistic revision control;
- prevents later authentication with the same credential.

A later provider-revocation synchronizer must also revoke or invalidate all associated AIGC sessions. This operational path remains unimplemented.

## Offline verification

The tests generate their own RSA key and X.509 certificate in memory. No private key is committed.

They verify:

- valid RS256 assertion;
- wrong audience denial;
- wrong issuer/sign-in-provider denial;
- expired assertion denial;
- unconfigured-project denial before public-key resolution;
- mapping and revocation denial;
- public-key caching and unknown-key denial;
- no email, role, scope, or raw assertion in normalized evidence;
- mapping/session persistence across restart;
- HMAC-only session storage;
- idle renewal capped by absolute expiry;
- rotation and old-credential invalidation;
- explicit revocation;
- tenant and project mismatch denial;
- exact provider binding and subject enforcement;
- complete synthetic assertion-to-session pipeline.

Offline proof is evidence maturity `EA2_SEMANTICALLY_TESTED`. It is not staging or production proof.

## Required staging sequence

After issue #85 supplies the approved staging project ID and separate authority is granted:

1. configure Identity Platform in the isolated staging project;
2. enable Google sign-in for an operator-controlled test identity only;
3. disable public self-registration;
4. configure reviewed redirect origins and domains;
5. create a trusted subject mapping for the staging subject;
6. provision the session-pepper secret and grant only the staging workload identity access;
7. configure provider revocation synchronization;
8. verify valid sign-in and exact issuer/audience;
9. verify wrong signature, issuer, audience, expiry, and provider denial;
10. observe public-key rotation behavior;
11. issue, persist, rotate, restart, and revoke server sessions;
12. test provider revocation and outage behavior;
13. prove cross-tenant and cross-project denial;
14. inspect logs, receipts, and persistence for raw token or claim leakage;
15. emit an `identity_platform_staging_receipt`;
16. obtain accountable-operator review.

## Rollback

If provider verification, mapping, session, or revocation behavior fails:

- keep production identity activation disabled;
- disable the staging sign-in configuration if authorized;
- revoke staging sessions;
- revoke staging workload identity access to the session pepper;
- retain redacted evidence and audit receipts;
- continue using local simulation for development only;
- correct through a new reviewed revision.

Rollback does not delete identity or authorization evidence and does not authorize a fallback that accepts unverified browser identity.

## Current blockers

The baseline intentionally reports `production_complete: false` because the following are absent:

```text
Identity Platform project ID
session-pepper Secret Manager project
verified subject-mapping repository in managed persistence
verified production-session repository in managed persistence
real staging Google sign-in
public-key rotation observation
provider revocation observation
session rotation observation
logout observation
restart persistence in staging
cross-tenant negative evidence
cross-project negative evidence
provider outage evidence
redaction review
```

## Readiness truth

This slice supplies internal implementation evidence only. It does not justify promoting `production_identity_access` from `unimplemented` or removing it from the production blocking gaps.

A later evidence-only readiness PR is permitted only after issue #88 exit criteria and a passing exact-revision staging receipt exist.
