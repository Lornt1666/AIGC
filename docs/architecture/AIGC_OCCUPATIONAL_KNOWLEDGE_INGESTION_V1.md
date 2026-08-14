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

OccupationProfileV3
├── classifications
├── title aliases
├── tasks
├── activities
├── contexts
├── skills / knowledge / abilities / work styles
├── technologies
├── credential requirements
├── jurisdiction
├── exclusions / adjacency / progression / mobility
└── AIGC occupational-control references
```

## Stable identity

AIGC internal identifiers are deterministically derived from:

```text
ConceptKind | SourceAuthority | TaxonomyVersion | SourceID
```

This prevents a display label from becoming identity and ensures a new taxonomy version creates a new version-bound internal concept rather than overwriting history.

## Temporal/version policy

A concept already imported for the same `(authority, version, kind, source_id)` is immutable. If the same source/version/source identifier produces a different canonical digest, ingestion fails closed. Legitimate upstream changes must be represented as a new source version and, where appropriate, linked with `DEPRECATED_BY`, `SPLIT_INTO`, `MERGED_FROM`, or other explicit crosswalk relations.

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

`EXACT_MATCH` requires a high-confidence mapping. Semantic similarity alone should normally produce `CLOSE_MATCH` until authoritative or expert evidence supports exact equivalence.

## Title resolution

Titles seed occupation candidates but do not determine them. Candidate scoring may use:

```text
observed title
+ job-description task evidence
+ observed skill evidence
+ industry / work-context evidence (future adapter)
+ jurisdiction (future adapter)
```

Market/employer titles remain aliases or observations unless a reviewed emergent-occupation process establishes a new AIGC extension.

## Emergent occupations

```text
OBSERVED
-> PROVISIONAL
-> EVIDENCE_ACCUMULATING
-> MAPPED_TO_EXISTING
   or AIGC_EXTENSION_ACCEPTED
-> REVIEWED
```

Promotion to an accepted/mapped state requires evidence. An emergent label is never presented as an official ISCO/ESCO/NOC/SOC/O*NET occupation unless that source actually contains it.

## Ingestion pipeline

```text
fetch/download source outside core registry
-> verify source authority/version/digest
-> parse source-specific representation
-> normalize into SourceConcepts
-> retain original identifiers and URIs
-> import append-only concepts
-> construct source-native relations
-> propose crosswalks
-> validate crosswalk confidence/provenance
-> construct OccupationProfileV3 projections
-> expose title-resolution and career-mobility queries
-> emit ingestion receipt
```

Network retrieval is intentionally separated from the core model. The current runtime implements normalization/identity/crosswalk/title-resolution primitives; source-specific download adapters and persistent storage remain follow-on WorkCommissions.

## Authority boundary

Occupational knowledge is descriptive evidence. It cannot itself authorize an action.

```text
occupation match != competency
competency != credential
credential != authority
source classification != permission
market demand != authority
```

Actual work remains governed by `ScopeOfPractice + Jurisdiction + WorkCommission + OutcomeContract + AuthorityEnvelope + WorkAttempt`.
