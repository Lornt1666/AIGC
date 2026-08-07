# AIGC Nexus Stage-1 Advanced Measurements V1

Status: `MEASURED_NON_DESTRUCTIVE`
Measured exact head: `3f714959203594b753085af4be03259896a0e64d`
AIGC CI: `#2558` / run ID `31182185660` / `SUCCESS`
Retained artifact ID: `8995258580`
Artifact digest: `sha256:c5990e1ec84042d1be64f45a335f0467daf4ef04dd94e076dcd745ca9ad103cf`

This record extends the Stage-1 repository-intelligence baseline. It grants no archive, deletion, merge, deployment, procurement, or retirement authority.

## 1. Schema semantic/caller analysis

- schemas analyzed: `155`;
- schemas with at least one static path/name caller: `94`;
- schemas without an observed static caller: `61`.

The caller metric searches Python, Markdown, JSON, YAML, TOML and Terraform for exact schema paths or basenames. Absence of a static caller is not proof of non-use because schemas can be discovered dynamically.

High-caller examples:

- `schemas/quest.schema.json`: `11` observed callers;
- `schemas/identity_platform_staging_receipt.schema.json`: `6`;
- `schemas/production_connector_secret_broker.schema.json`: `6`;
- `schemas/production_identity_platform_baseline.schema.json`: `6`;
- `schemas/production_deployment_baseline.schema.json`: `5`;
- `schemas/production_release_gate_receipt.schema.json`: `5`.

The previously measured strongest structural-overlap pair remains:

`schemas/exact_sha_ci_issue_request.schema.json`
vs
`schemas/exact_sha_ci_request.schema.json`

with structural feature Jaccard `1.0`. Both have observed references in the repository. This pair is therefore a **semantic/caller consolidation investigation**, not a deletion candidate.

Required next proof before consolidation:

1. compare accepted instances and semantic intent;
2. map all direct and dynamic callers;
3. prove one schema can express the other's contract without semantic loss;
4. migrate validators/tests;
5. run shadow validation against both schemas;
6. only then calculate replacement/dependency ECS inputs.

## 2. Indirect test-ownership tracing

Direct static ownership baseline: `118 / 246 = 47.97%`.

Advanced transitive static import reachability at exact head:

- source modules: `247`;
- source modules reachable from at least one test through internal imports: `132`;
- transitive static test-reachability ratio: `53.44%`;
- source modules with no transitive static test reachability: `115`.

The source count increased by one from the prior baseline because the advanced analyzer itself became active source.

This closes only part of the direct-ownership gap. It remains a **lower bound**, not code coverage. Runtime routes, configuration-driven loading, subprocess execution, CLI entry points and fixtures can exercise modules without an AST-import path.

Strong transitive ownership examples:

- `src.core.contract_validator`: reachable from `57` test modules;
- `src.infrastructure.persistence.sqlite`: `26`;
- `src.application`: `23`;
- `src.infrastructure.identity`: `21`;
- `src.api.composition`: `17`;
- `src.core.phase_registry`: `17`;
- `src.core.production_readiness_ledger`: `13`.

No module is classified removable because it lacks static test reachability.

## 3. Canonical-responsibility mapping

The advanced analyzer creates **heuristic search buckets**, explicitly not authority or duplication counts.

Measured candidate surfaces / present Nexus targets:

- state-machine/lifecycle surface: `33` candidates; canonical Nexus targets detected: `src.core.nexus.state_reducer`, `src.domain.nexus.contracts`;
- policy/governance surface: `164` candidates; canonical targets: `src.core.epistemic.tool_broker`, `src.domain.nexus.contracts`;
- evidence surface: `145` candidates; canonical targets: `src.domain.nexus.evidence`, `src.infrastructure.persistence.sqlite.nexus_evidence`;
- agent-registry/handoff surface: `23` candidates; canonical target: `src.core.nexus.specialist_registry`;
- dashboard/UI surface: `175` candidates; canonical targets: `src.dashboard.nexus_app`, `src.webapp.nexus_dashboard`;
- provider-runtime surface: `79` candidates; canonical provider-runtime target: **not yet present**.

Keyword breadth explains the large governance/evidence/UI counts. These counts define investigation surfaces only.

The strongest architectural signal is provider runtime: historical provider/Gemini capability exists, but the advanced measurement finds no canonical Nexus provider-runtime module yet. This supports the existing `ADAPT` disposition for PR #170 rather than retirement.

## 4. Git branch churn/staleness

The exact checkout fetched the complete origin branch ref set.

Measured remote branches: `133`.

Age bands by last branch commit:

- `0–7 days`: `32`;
- `8–30 days`: `96`;
- `31–90 days`: `5`;
- `>90 days`: `0` in the measured ref set.

High-divergence examples against current `origin/main` include:

- `codex/operator-cockpit-run-accept`: `35` ahead / `280` behind;
- `codex/milestone-l-truth-first-procurement-governance`: `6` ahead / `280` behind;
- `phase26-constellation-refactor`: `8` ahead / `273` behind;
- `aigc-constellation-fabric`: `5` ahead / `274` behind;
- `aigc-cognitive-phase-router`: `6` ahead / `271` behind.

This quantitatively confirms branch-topology saturation and historical divergence. It does **not** authorize branch deletion. Divergent branches remain capability repositories until unique behavior/tests/evidence are extracted.

PR metadata is a separately timestamped GitHub observation. Current open PRs span multiple generations and include the Nexus train plus historical EPI, Colosseum, OMNI-FORGE, Evidence Plane, Policy, Gemini, cloud, cockpit, CI and agent-registry trains. PR lifecycle decisions remain separate governed actions.

## 5. Direct dependency usage and reproducibility

Direct requirements measured: `11`.

Static import use observed for `9 / 11` direct distributions.

No direct static import was observed for:

- `httpx`;
- `psycopg`.

This does **not** prove either dependency is unused. HTTPX can be consumed transitively by framework/testing surfaces, and psycopg can be loaded through adapter/import patterns or extras. Both require caller/runtime verification before any dependency removal proposal.

Resolved CI versions at the measured environment:

- Streamlit `1.61.1`;
- FastAPI `0.141.1`;
- Uvicorn `0.52.1`;
- Pydantic `2.13.4`;
- HTTPX `0.28.1`;
- pytest `8.4.2`;
- jsonschema `4.26.0`;
- PyYAML `6.0.3`;
- psycopg `3.3.4`;
- psycopg_pool `3.3.1`;
- PyJWT `2.13.0`.

Reproducibility findings:

- direct dependency count: `11`;
- requirements use version ranges: `true`;
- supported Python dependency lockfile detected by analyzer: `false`;
- classification: `MEASURED_ENVIRONMENT_DRIFT_RISK`.

Therefore the next dependency task is **constraints/lock strategy evaluation**, not blind version upgrades.

### Security advisory review boundary

The automated repository report intentionally records security advisory state as `EXTERNAL_AUTHORITATIVE_AUDIT_REQUIRED`.

The accompanying August 7, 2026 advisory review found current CI versions are newer than known affected ranges for the checked Streamlit, FastAPI, HTTPX and PyJWT advisories. In particular, Streamlit's 2026 SSRF issue was fixed in 1.54.0 and PyJWT's 2026 JWT/JWK issues were fixed in 2.13.0, matching the CI-resolved PyJWT version. This is not a claim that the complete dependency graph is vulnerability-free.

Remaining security work:

1. package-by-package OSV/advisory query using exact resolved versions;
2. transitive dependency inventory;
3. software-bill-of-materials generation;
4. compatibility testing of any remediation;
5. reproducible lock/constraints evidence.

## 6. Partial subsystem ECS inputs

ECS remains:

`ECS = ReplacementCoverage × TestEquivalence × DependencyMigration × EvidenceConfidence`

The analyzer now emits partial inputs only.

Repository-level test-equivalence proxy used for all heuristic responsibility surfaces: `0.5081`, derived from direct and transitive static ownership measurements.

Heuristic replacement-coverage proxy:

- state machine: `0.5`;
- policy/governance: `0.5`;
- evidence: `0.5`;
- agent registry: `0.5`;
- dashboard: `0.5`;
- provider runtime: `0.0` because no canonical Nexus provider-runtime target is currently detected.

For **every subsystem**:

- DependencyMigration: `UNMEASURED`;
- EvidenceConfidence: `UNMEASURED`;
- ECS: `UNCOMPUTED`.

Therefore no retirement band applies yet.

The `0.5` replacement proxy is not a statement that half of a legacy subsystem has been replaced. It means a plausible canonical Nexus target exists while competing/legacy capability surfaces remain broad and require feature-by-feature mapping.

## Stage-1 interpretation

Measured evidence now supports these decisions:

- continue capability fusion analysis;
- prioritize exact-sha schema unification as a shadow-migration study;
- build a canonical Nexus provider-runtime abstraction before attempting Gemini/provider retirement;
- prioritize highly divergent branch capability extraction;
- add indirect/runtime test ownership before declaring modules untested;
- introduce dependency reproducibility/SBOM work before dependency cleanup;
- keep ECS incomplete until dependent migration and evidence confidence are measured.

Measured evidence does **not** support:

- deleting schemas;
- deleting modules;
- deleting or archiving branches;
- closing historical PRs;
- removing HTTPX or psycopg;
- assigning retirement ECS scores;
- enabling provider execution.
