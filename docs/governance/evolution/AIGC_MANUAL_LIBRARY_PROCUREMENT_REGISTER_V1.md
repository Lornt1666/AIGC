# AIGC Manual Library Procurement Register v1

Status: **Draft / evidence-bound / operator-controlled**  
Register ID: `AIGC-MANUAL-LIBRARY-PROCUREMENT-REGISTER-001`  
Repository: `Lornt1666/AIGC`  
Base revision: `293de53489fe7212fad272c01c698c0ffe2da610`  
External action performed: `false`

## Verified package intake

| Artifact | Provided | SHA-256 matched | Repository placement |
|---|---:|---:|---|
| Documentation source index | Yes | Yes | `docs/manuals/source/` |
| Research synthesis | Yes | Yes | `docs/manuals/research/` |
| Master Bookforge Prompt | Yes | Yes | `docs/manuals/prompts/` |
| Integration manifest | Yes | Yes | `governance/manuals/source/` |
| DOCX compiled codex | Yes | Yes | Verified external artifact; bytes not committed |
| PDF compiled codex | Yes | Yes | Verified external artifact; bytes not committed |
| Book Markdown sources | No | Not verifiable | Blocked |
| Figure PNG sources | No | Not verifiable | Blocked |
| Package README | No | Not verifiable | Blocked |

## Capability decomposition

1. `MANUAL_PACKAGE_PROVENANCE` - verified checksums and source snapshot.
2. `MANUAL_NAVIGATION_INDEX` - repo-native index with truth boundary.
3. `MANUAL_RESEARCH_SOURCE` - advisory research.
4. `MANUAL_REGENERATION_DIRECTIVE` - advisory prompt.
5. `COMPILED_CODEX_SNAPSHOT` - DOCX/PDF release artifacts.
6. `SOURCE_COMPLETE_BOOK_LIBRARY` - blocked because Book and figure sources were not provided.
7. `MANUAL_DRIFT_ASSURANCE` - proposed registry/tests; exact-head assurance depends on PR #53 or equivalent.
8. `CONSTITUTION_DOCUMENT_RECONCILIATION` - separate blocking governance train.

## Procurement register

| Procurement ID | Capability | Status | Blocker / exit evidence |
|---|---|---|---|
| `AIGC-MANUAL-PACKAGE-PROVENANCE-V1` | Hash-verified intake | Implemented on draft branch | CI and operator review |
| `AIGC-MANUAL-NAVIGATION-V1` | Repository-native index | Implemented on draft branch | Link tests and review |
| `AIGC-MANUAL-REGISTRY-V1` | Machine registry and schema | Implemented on draft branch | Schema/tests/CI |
| `AIGC-COMPILED-CODEX-SNAPSHOT-2026-07-11` | DOCX/PDF snapshot | `VERIFIED_NOT_COMMITTED` | Operator-approved release-asset or binary publication path |
| `AIGC-SOURCE-COMPLETE-BOOK-LIBRARY-V1` | Eleven books and figures | `BLOCKED` | Original files matching declared hashes |
| `AIGC-MANUAL-DRIFT-GATE-V1` | Revision/link/state drift assurance | `PLANNED` | Exact-head CI and canonical source completeness |
| `AEC-001-HUMAN-MACHINE-RECONCILIATION` | Constitution status alignment | `BLOCKED` | Dedicated constitutional process and operator ratification |

## Prioritized backlog

| Priority | Action | State |
|---:|---|---|
| P0 | Operator review of manual-library PR exact head | Pending |
| P0 | Resolve exact-head CI through PR #53 or equivalent | Blocking merge assurance |
| P0 | Reconcile AEC-001 human/machine status in a separate PR | Blocking documentation authority |
| P1 | Obtain original eleven Book Markdown files | Missing |
| P1 | Obtain original eleven figure PNGs and package README | Missing |
| P1 | Add link, metadata, and revision-drift validation | Partially implemented |
| P2 | Generate role/state contextual help from canonical registries | Planned |
| P3 | Publish a versioned manual release after source-complete review | Planned |

## Readiness impact

Immediate numeric impact: `0`.

This procurement improves documentation provenance and operator orientation. It does not implement production identity, connectors, payments, public deployment, or autonomous external work.

## Governance

- separate documentation branch;
- draft reviewed PR;
- no direct-main write;
- no self-approval;
- no merge;
- no credentials;
- no deployment;
- no external action;
- compiled artifacts remain non-authoritative;
- rollback preserved.
