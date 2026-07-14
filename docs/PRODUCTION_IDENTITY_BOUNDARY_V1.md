# Production Identity Boundary Contract v1

Status: **implementation candidate in a separate draft PR**  
Contract ID: `AIGC-PIBC-001`  
Runtime authority delivered by this PR: **LOCAL_SIMULATION only**  
Production identity provider configured: **No**  
External action performed: **No**

## Purpose

PIBC-v1 establishes a strict boundary between untrusted identity-provider input and the existing AIGC authorization kernel.

```text
untrusted provider assertion
→ provider adapter verification
→ redacted ProviderVerification
→ repository-owned membership resolution
→ repository-owned session verification
→ assurance / expiry / revocation / tenant / project / revision checks
→ strict normalized IdentityContext
→ existing authorization kernel
→ immutable redacted IdentityEvidenceReceipt
```

This implementation does not authenticate a live user, configure OIDC, provision credentials, deploy a hosted service, activate a connector, accept a contract, send a message, pay, deliver, or perform another external action.

## Constitutional invariant

> Procurement grants direction. Implementation supplies substance. Verification supplies proof. The operator grants authority.

The presence of these files is implementation evidence, not production proof. The production-readiness ledger is intentionally not advanced by this PR. A later evidence cycle must assess executable tests and exact-revision CI before changing capability maturity.

## Trust boundaries

### Untrusted input

The provider adapter receives only an untrusted assertion mapping.

The local adapter permits these selector fields:

- `assertion_id`
- `principal_id`
- `issuer`
- `audience`

It rejects or fails closed on caller-provided:

- roles or scopes;
- tenant, project, membership, or session authority;
- assurance values;
- verification flags;
- provider claims;
- nonce values;
- access, refresh, or ID tokens;
- credentials or client secrets.

### Provider verification

`ProviderVerification` contains only normalized evidence and digests. It never contains the raw assertion or unrestricted provider claims.

The included `LocalDevelopmentIdentityAdapter` reads the repository-owned synthetic fixture and is structurally fixed to:

- provider class `LOCAL_DEVELOPMENT`;
- evidence maturity `EA1_SCHEMA_VALID`;
- runtime authority `LOCAL_SIMULATION`;
- fixture assurance `IAL0/AAL0/FAL0`.

It cannot advertise production identity.

### Normalized identity context

A permit context contains:

- principal and provider binding;
- active membership;
- tenant and project binding;
- roles and scopes resolved from the membership fixture;
- active session;
- effective IAL, AAL, FAL, and evidence maturity;
- exact repository revision;
- minimum-necessary evidence identifiers;
- expiry;
- `external_action_performed: false`.

Every object is immutable at the Python contract boundary. Collection values use tuples rather than mutable lists.

## Production-mode behavior

Production mode fails closed when any of the following applies:

- local-development provider;
- provider class is not allowlisted;
- issuer or audience is not configured and allowlisted;
- evidence is unverified;
- runtime authority is not `PRODUCTION_VERIFIED`;
- IAL, AAL, FAL, or evidence maturity is below policy;
- revision is not an exact 40-character lowercase Git SHA;
- membership is missing, inactive, revoked, expired, cross-principal, cross-tenant, or lacks the project;
- session is missing, inactive, revoked, expired, too old, or mismatched;
- assertion replay changes the requested intent.

The shipped configuration intentionally contains no production issuer or audience. Therefore no production identity can pass until a separate provider-integration PR supplies reviewed configuration and executable verification.

## Schemas

- `schemas/identity_boundary.schema.json`
- `schemas/identity_evidence_receipt.schema.json`

Both use JSON Schema Draft 2020-12 and prohibit unknown properties.

Raw tokens, assertions, credentials, provider claims, and nonce values are absent from both contracts.

## Persistence

Migration:

```text
migrations/sqlite/0002_identity_boundary_v1.sql
```

Table:

```text
identity_evidence_receipts
```

Properties:

- append-only triggers prevent update and deletion;
- receipt IDs are deterministic;
- request and replay digests are persisted;
- principal, membership, session, tenant, and project identifiers are indexed where operationally useful;
- only the redacted receipt JSON is stored;
- raw secret and assertion material is prohibited.

Rollback retains the additive table and receipts. Runtime wiring can be reverted without deleting evidence.

## Internal preflight API

Run locally:

```bash
uvicorn src.api.identity_boundary_app:app --host 127.0.0.1 --port 8091
```

Endpoint:

```text
POST /api/v1/identity/context/verify
```

Example local request:

```json
{
  "provider_type": "LOCAL_DEVELOPMENT",
  "assertion": {
    "assertion_id": "assertion-a",
    "principal_id": "principal-a",
    "issuer": "local-simulation",
    "audience": "aigc-local-operator"
  },
  "membership_id": "membership-a",
  "session_id": "session-a",
  "tenant_id": "tenant-a",
  "project_id": "project-a",
  "exact_revision": "LOCAL_UNVERIFIED",
  "production_mode": false
}
```

Receipt lookup:

```text
GET /api/v1/identity/receipts/{receipt_id}
```

The API is an internal local preflight surface. It is not a hosted login service.

## Denial evidence

Denials return enumerated reason codes rather than private provider details or exception traces.

Representative codes include:

- `LOCAL_PROVIDER_PROHIBITED`
- `UNVERIFIED_EVIDENCE`
- `INSUFFICIENT_IAL`
- `INSUFFICIENT_AAL`
- `INSUFFICIENT_FAL`
- `MEMBERSHIP_REVOKED`
- `PROJECT_MEMBERSHIP_MISSING`
- `SESSION_EXPIRED`
- `SESSION_PRINCIPAL_MISMATCH`
- `REVISION_UNBOUND`
- `REPLAY_CONFLICT`
- `ROLE_SOURCE_UNTRUSTED`

Every decision records:

- operator review required;
- state changed false;
- external action performed false.

## Tests

The implementation includes:

- strict schema acceptance and rejection;
- unknown and raw-sensitive property rejection;
- local permit behavior;
- local-provider production denial;
- exact-revision production denial;
- role injection denial;
- tenant/project/session binding behavior;
- deterministic replay and replay conflict;
- local-adapter authority limits;
- append-only receipt persistence;
- restart persistence;
- raw-secret absence;
- dedicated API permit, denial, and restart behavior;
- additive migration-ledger regression.

Run:

```bash
python -m pytest
python src/aigc.py validate
python src/security/redaction_scanner.py --paths src config docs schemas tests migrations
```

## Future provider contract

A future OIDC or workload-identity adapter must:

1. verify signature, issuer, audience, expiry, nonce or equivalent replay evidence, and revocation through provider-supported mechanisms;
2. return only `ProviderVerification`;
3. never place raw tokens or unrestricted claims in domain models, logs, persistence, or API responses;
4. map external subjects to existing AIGC principals without constructing authority from request input;
5. advertise `PRODUCTION_VERIFIED` only with reviewed configuration and executable evidence;
6. remain separate from membership, tenant, project, role, scope, and authorization policy resolution.

## Operator gates still required

This PR may advance to `IMPLEMENTED_IN_PR` only after:

- all tests pass;
- contract validation passes;
- secret and redaction scans pass;
- migration tests pass on empty and existing databases;
- exact commit CI evidence is available;
- the accountable operator reviews the diff.

Merge, live provider integration, credentials, deployment, and production authorization require separate explicit decisions.
