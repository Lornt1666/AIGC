# AIGC Occupational Knowledge Ingestion Engine V1

## Purpose

Build a federated, source-versioned occupational knowledge graph for AIGC without flattening official taxonomies, job-title aliases, skills, tasks, credentials, or jurisdictional rules into one ambiguous list.

## Source roles

```text
ISCO  -> global classification backbone
ESCO  -> canonical granular occupation + skills graph
NOC   -> Canadian TEER / regulatory / title localization
SOC   -> strict U.S. statistical classification
O*NET -> tasks / activities / context / worker requirements / titles
AIGC  -> competency / evidence / scope / authority / methods / experience
```

No source replaces another. Every imported concept retains source authority, source version, source identifier, source hash, and optional source URI.

## Constitutional best practices

```text
BP-01 classify by work performed, not title alone
BP-02 Job != Occupation != Discipline != Role
BP-03 title aliases never become canonical occupations implicitly
BP-04 source + version + identifier + digest are mandatory provenance
BP-05 crosswalks carry relation, confidence, method and evidence
BP-06 skills/knowledge/tasks/activities remain reusable graph entities
BP-07 competency requires evidence
BP-08 credential != competency
BP-09 credential != authority
BP-10 scope of practice is jurisdiction-sensitive
BP-11 regulatory restrictions override autonomous capability
BP-12 work context modifies risk and evaluator requirements
BP-13 occupational risk != action risk
BP-14 experience requires evidence-backed completed work
BP-15 reputation derives from verified outcomes
BP-16 emergent occupations remain provisional until mapped or reviewed
BP-17 taxonomy upgrades append new versions; historical state is retained
BP-18 deprecated concepts remain historically addressable
BP-19 market titles cannot silently modify canonical ontology
BP-20 labels may change; canonical AIGC IDs remain version-bound
BP-21 taxonomies coexist through explicit mappings
BP-22 method selection depends on task + context + risk
BP-23 economics cannot override authority
BP-24 learning != competence
BP-25 competence != legal permission
```

## Core graph

```text
SourceConcept
├── Occupation
├── Title
├── Skill
├── Knowledge
├── WorkActivity
├── Task
├── WorkContext
├── Ability
├── WorkStyle
├── Technology
└── CredentialRequirement
```

## Stable identity and temporal policy

AIGC identifiers derive from `ConceptKind | SourceAuthority | TaxonomyVersion | SourceID`. Existing `(authority, version, kind, source_id)` concepts are immutable. Legitimate upstream changes require a new taxonomy version and explicit temporal/crosswalk relations rather than destructive overwrite.

## Acquisition and ingestion boundary

```text
NETWORK / FILE ACQUISITION
        ↓
RawSourcePackage
  authority
  version
  dataset_name
  concept_kind
  source_uri
  expected_sha256
        ↓
CHECKSUM + SOURCE VALIDATION
        ↓
SOURCE-SPECIFIC ADAPTER
  IscoAdapter
  EscoAdapter
  NocAdapter
  SocAdapter
  OnetAdapter
        ↓
NormalizedSourceRecord[]
        ↓
DRY-RUN DIFF
  new
  unchanged
  conflicts
        ↓
CONFLICTS? ──yes──> BLOCKED
        │
        no
        ↓
APPEND-ONLY COMMIT
        ↓
IngestionReceipt
```

The runtime does not fetch internet data itself. Acquisition remains a separately authorized capability boundary. Adapters consume bytes only after an expected SHA-256 is supplied and verified.

## Dataset identity

`RawSourcePackage` binds source authority, taxonomy version, dataset name, optional explicit concept kind, URI, payload bytes, and expected SHA-256. This prevents a parser from treating unrelated files from the same taxonomy as interchangeable.

For O*NET and other multi-table sources, non-occupation rows require row-level identity. An occupation code alone is insufficient for tasks, activities, contexts, skills, knowledge, abilities, work styles, technologies, or titles.

```text
occupation identity:
  15-1252.00

task identity:
  15-1252.00:TASK:<task-id-or-deterministic-row-hash>
```

This prevents distinct records from colliding under a shared occupation code.

## Dry-run law

Canonical mutation is forbidden until a dry run reports zero immutable-history conflicts.

```text
INGESTION_COMMIT_ELIGIBLE :=
    source_checksum_valid
    AND adapter_authority_matches
    AND concept_kind_supported
    AND dry_run_completed
    AND immutable_history_conflicts = 0
```

A dry run emits `IngestionReceipt(mode=DRY_RUN)` and performs no persistence.

## Persistence contract

`OccupationalRegistryStore` is the persistence boundary. Implementations must preserve append-only source/version history. `InMemoryRegistryStore` is only a deterministic contract/test implementation; durable database storage requires a later sealed WorkCommission.

A commit re-runs normalization after a clean dry run and persists only concepts absent under the exact source/version/kind/source-ID tuple. The receipt records source hash, normalized count, imported count, diff, mode, result, and notes.

## Source adapter rules

### ISCO

Normalize global hierarchy/unit-group datasets to `OCCUPATION` while retaining classification-level metadata.

### ESCO

Support occupation, title, skill, and knowledge datasets. Explicit package `concept_kind` overrides weak inference so source dataset semantics remain authoritative.

### NOC

Preserve NOC code and TEER metadata. Occupation rows use the NOC code as identity; title and credential-requirement datasets use row-level identities attached to the NOC code.

### SOC

Normalize strict occupation codes/titles without importing O*NET semantics into SOC.

### O*NET

Treat O*NET as a multi-dataset source. Explicit concept kind is preferred. Non-occupation records combine the O*NET-SOC occupation code with source-native row IDs such as Task ID, Element ID, or Title ID, falling back to a deterministic row hash only when no source-native row identifier exists.

## Crosswalk relations

```text
EXACT_MATCH
CLOSE_MATCH
BROADER_THAN
NARROWER_THAN
SPLIT_INTO
MERGED_FROM
DEPRECATED_BY
UNMAPPED
```

Mappings retain relation, confidence, method, evidence references, and review time. Semantic similarity alone never creates exact equivalence.

## Title resolution

Titles seed candidates but do not determine occupations. Resolution combines observed title, job-description task evidence, observed skills, and eventually work context/jurisdiction. Market/employer titles remain aliases or observations unless the emergent-occupation process promotes them with evidence.

## Emergent occupations

```text
OBSERVED
→ PROVISIONAL
→ EVIDENCE_ACCUMULATING
→ MAPPED_TO_EXISTING | AIGC_EXTENSION_ACCEPTED
→ REVIEWED
```

Promoted states require evidence and never masquerade as official taxonomy entries.

## Verification requirements

Tests must cover checksum rejection, source/adapter mismatch, unsupported concept kind, title/occupation separation, stable IDs, same-version overwrite denial, dry-run no-mutation behavior, append-only commit behavior, new-version acceptance, O*NET row uniqueness, crosswalk validation, emergent-state evidence gates, and task/skill-aware title resolution.

## Authority boundary

Occupational knowledge is descriptive evidence, not permission.

```text
occupation match != competency
competency != credential
credential != authority
source classification != permission
market demand != authority
```

Actual work remains governed by `ScopeOfPractice + Jurisdiction + WorkCommission + OutcomeContract + AuthorityEnvelope + WorkAttempt`. Hosted exact-head verification remains required before this layer can be promoted from draft architectural/runtime status.
