# AIGC Observer Authority Verification

## Purpose

This procedure answers a critical question:

> How do we make sure the people who are being observant actually have authority to observe?

AIGC must not grant observer access because someone claims to be an employer, client, officer, reviewer, or authority.

Observer access requires verified authority, specific scope, operator approval, redaction review, expiry, revocation, and audit receipt.

## Research Basis

This gate follows the same defensive principles used by:

- NIST SP 800-63-4 Digital Identity Guidelines: identity proofing, authentication, federation, authenticators, and management processes;
- NIST SP 800-207 Zero Trust Architecture: no implicit trust, authenticate and authorize before resource access;
- privacy-by-design and minimum-necessary disclosure practices.

## Current Implementation

Files:

```text
config/observer_authority_verification.json
schemas/observer_authority_verification.schema.json
src/core/observer_authority_verification.py
src/observer_authority_verification_cli.py
```

Command:

```powershell
python .\src\observer_authority_verification_cli.py
```

Outputs:

```text
reports/artifacts/observer_authority/<verification_id>/observer_authority_verification.json
reports/artifacts/observer_authority/<verification_id>/observer_authority_verification.md
```

## Required Verification Checks

Before any observer packet can become proceed-capable, AIGC requires:

1. Observer identity proof.
2. Organization or platform linkage.
3. Role authority.
4. Specific project/request scope.
5. Counterparty request linkage.
6. Operator approval.
7. Redaction review.
8. Expiry date/time.
9. Revocation path.
10. Audit receipt.

## Employer / Client Observer

Acceptable evidence may include:

- verified platform conversation or contract;
- company email domain matching the organization;
- signed or platform-recorded statement of work;
- operator-approved counterparty request packet.

Not acceptable:

- unsourced self-claim;
- generic public email with no project linkage;
- request to observe unrelated work;
- request for backend or whole-account access.

## Authorized Evidence Reviewer

Authorized evidence review is not a backdoor.

It requires:

- documented lawful or process-bound request;
- named organization and officer/agent role;
- jurisdiction/process review;
- specific evidence scope and purpose;
- audit receipt;
- minimum-necessary evidence export.

AIGC must not provide unrestricted backend access or bulk account access.

## Decision States

```text
insufficient_authority
blocked_scope_overreach
ready_for_operator_review
ready_for_operator_review_high_risk
```

## Hard Blocks

AIGC blocks:

- whole-account access;
- backend access;
- raw chat-log access by default;
- unrelated project access;
- silent sharing;
- unverified identity;
- unverified role authority;
- expired authority;
- unrevocable access.

## Proper Flow

```text
observer request
→ identity verification
→ organization/platform linkage verification
→ role authority verification
→ counterparty request linkage
→ scope boundary
→ expiry and revocation check
→ redaction review
→ operator approval popup
→ audit receipt
→ selected redacted observer packet only
```

## Core Rule

No one observes AIGC work unless their identity, role, authority, and specific project scope are verified.

No observer receives whole-account access, backend access, unrelated project access, or raw chat-log access by default.
