# AIGC XPRIZE Judge Access Guide

Status: `GUIDE READY — REPOSITORY INVITES / RUNTIME ACCESS NOT YET VERIFIED`

## Scope

This guide is for Build with Gemini XPRIZE testing/judging access. It must not contain reusable credentials, cloud-console privilege, billing authority, repository write authority or secret values.

## Private repository

Repository:

```text
Lornt1666/AIGC
```

The live XPRIZE requirements identify these testing/judging identities for private repository access:

```text
testing@devpost.com
judging@hacker.fund
```

Required access model:

```text
minimum repository read access
no admin/maintain/write authority
no billing authority
no Actions secret access
no deployment-environment secret access
no cloud IAM authority
revocable after the judging requirement ends
```

Current state:

```text
invite/share evidence = UNVERIFIED
working repository access = UNVERIFIED
Devpost shared-repo confirmation = DO NOT CHECK YET
```

Do not guess GitHub usernames from the required email addresses. Use an authenticated GitHub surface that supports the exact Devpost-required sharing mechanism and retain a sanitized invite/acceptance receipt.

## Recommended repository inspection path

Once access is confirmed, judges should be able to inspect:

```text
1. PR #181 — Nexus V1 integration/release train
2. exact-head CI receipt for the final submission candidate
3. docs/architecture/ — authority/evidence/runtime design
4. docs/release/ — release and external-runtime evidence
5. src/core/nexus/ — governed orchestration/runtime logic
6. src/infrastructure/providers/ — provider adapters
7. tests/ — adversarial/governance/runtime coverage
8. Devpost/XPRIZE evidence documents under docs/devpost/
```

The final package must point to the **current admitted** PR/SHA, not historical PR #170 text retained on the currently stale public Devpost page.

## Judge-safe runtime

A working test surface is a separate gate from repository access.

Intended runtime properties after G6/G7:

```text
private/no-public-traffic staging candidate
immutable image digest
Canadian Montréal region for customer-content resources
judge identity with least privilege
no production/billing permissions
no Secret Manager value read unless explicitly required by runtime identity, never by judge directly
no arbitrary external execution
bounded demonstration data
read-only evidence/assessment surface where possible
```

Current state:

```text
G6 immutable staging = NOT EXECUTED
G7 live Gemini proof = NOT EXECUTED
judge runtime URL = NOT AVAILABLE
judge runtime authorization = NOT ISSUED
```

Do not insert a placeholder URL or fabricated login into this guide.

## Evidence package

Judge-facing evidence should include redacted copies of:

```text
final exact-head CI receipt
release SHA/tree
immutable image digest / Cloud revision
GCP region/resource receipt
live Gemini execution receipt
latency / usage / cost evidence
human governance / verifier receipt
real pilot receipt if completed
P&L and source index
claim/evidence matrix
pre-existing-resource disclosure
known limitations
```

## Secret/privacy exclusions

Never provide judges through repository/package/video with:

```text
API keys
OAuth client secrets
access or refresh tokens
raw Authorization headers
private keys
passwords
raw database DSNs
session signing material
payment card data
unredacted customer PII not required for judging
internal participant data outside consent scope
```

Provider and cloud identifiers should be minimized in public/video artifacts when they do not help verification.

## Access verification receipt

Before marking G3 complete, persist:

```text
repository = Lornt1666/AIGC
required identity
permission level
invite/share timestamp
acceptance/working state
verification timestamp/method
runtime surface if applicable
revocation available = true
secret exposure finding = 0
```

## Revocation

After the required judging window or earlier if the rules permit, remove temporary judge/test access according to the competition requirement and retain the revocation receipt.

Revocation must not delete or falsify historical evidence that access was available during the required period.

## Completion boundary

```text
guide exists = true
repository judge access verified = false
runtime judge access verified = false
Devpost shared-repo confirmation supported = false
```

This guide is evidence preparation only and performs no external access mutation.
