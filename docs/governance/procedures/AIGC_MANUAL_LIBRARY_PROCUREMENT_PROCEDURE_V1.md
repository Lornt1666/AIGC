# AIGC Manual Library Procurement Procedure v1

Status: **Proposed / operator-controlled**  
Procedure ID: `AIGC-MANUAL-LIBRARY-PROCUREMENT-PROCEDURE-001`  
Applies to: `Lornt1666/AIGC` only  
Base revision: `293de53489fe7212fad272c01c698c0ffe2da610`  
External action performed: `false`

## Purpose

This procedure governs ingestion of research, prompts, indexes, compiled manuals, figures, book sources, manifests, and checksums into the AIGC repository without confusing documentation with runtime authority.

## Principles

1. Inspect repository evidence before accepting package claims.
2. Verify every provided artifact against a checksum when one exists.
3. Preserve source snapshots separately from adapted repository indexes.
4. Store canonical text sources under `docs/manuals/`.
5. Store machine inventory under `governance/manuals/`.
6. Store schemas under `governance/schemas/manuals/`.
7. Store compiled DOCX/PDF editions as non-authoritative release artifacts.
8. Never reconstruct absent source files while claiming checksum continuity.
9. Never combine documentation procurement with runtime, identity, connector, payment, or deployment changes.
10. No self-approval, merge, deployment, credentials, external action, or readiness promotion.

## Ordered process

### 1. Intake

Record package identity, source repository, source revision, publication state, provided files, expected files, and requested destination.

### 2. Evidence verification

- compute SHA-256 for every provided file;
- compare against the uploaded manifest;
- validate JSON;
- preflight the PDF;
- render the DOCX;
- inspect rendered pages;
- inspect current repository and open PR state;
- compare human and machine constitutional status.

### 3. Scope lock

Allowed:

- manual source Markdown;
- prompts and research;
- indexes;
- source manifest and checksums;
- registry and schema;
- compiled release artifacts;
- documentation tests;
- procedure and procurement register.

Disallowed:

- runtime behavior;
- database migration;
- API/UI feature wiring;
- identity-provider integration;
- secrets;
- connectors;
- payment;
- deployment;
- direct write to `main`.

### 4. Path normalization

Use:

```text
docs/manuals/AIGC_MANUAL_INDEX.md
docs/manuals/research/
docs/manuals/prompts/
docs/manuals/books/
docs/manuals/figures/
docs/manuals/source/
docs/manuals/releases/<snapshot-date>/
governance/manuals/manual_registry.json
governance/manuals/source/
governance/schemas/manuals/
tests/docs/
```

### 5. Integrity classification

Each artifact is classified as one of:

- `REPOSITORY_NAVIGATION`;
- `ADVISORY_RESEARCH`;
- `ADVISORY_PROMPT`;
- `SNAPSHOT_SOURCE`;
- `NON_AUTHORITATIVE_RELEASE_ARTIFACT`;
- `MISSING_SOURCE_ARTIFACT`.

### 6. Governance reconciliation

If the manual package identifies a conflict between human and machine authority documents, record it as a blocking finding. Do not amend either authority document inside the manual-library PR.

### 7. Tests and validation

Require:

- registry schema validation;
- artifact existence;
- SHA-256 match;
- link/path checks;
- no citation-token leakage;
- no secret-like content;
- compiled-artifact non-authority labels;
- missing-source declarations;
- full repository regression suite.

### 8. CI

Require contract validation, AEC-001 validation, secret scanning, full tests, readiness evaluation without promotion, and exact-head evidence when PR #53 or equivalent is available.

### 9. Operator review

Present the exact head, changed paths, verified hashes, missing-source list, non-claims, rollback, and residual risks.

### 10. Merge decision

Only the accountable operator may authorize an expected-head-protected merge after all mandatory gates pass.

### 11. Post-merge verification

Verify exact `main`, file hashes, registry validity, links, binary openability, and rollback availability.

### 12. Readiness ledger

Documentation integration has immediate numeric readiness impact `0`. It may reduce operational ambiguity but does not prove runtime capability.

## Rollback

Before merge: abandon the branch or close the draft PR.  
After merge: revert the single squash commit. No runtime data or external compensation is required.

## Stop conditions

Stop and request operator action when:

- a provided checksum fails;
- a source file is missing but represented as integrated;
- authority documents conflict;
- exact-head evidence is unavailable for merge acceptance;
- a manual claim exceeds repository evidence;
- runtime or external-action scope enters the PR.
