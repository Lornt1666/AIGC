# AIGC Nexus Evolution Ledger

Status: `STAGE_1_DISCOVER_ADVANCED_MEASURED`
Integration train: `release/aigc-nexus-v1`
Governing contract: `AIGC_INTEGRATION_CONTRACT_V1`

## Governing migration law

Nothing is removed because it is old. Nothing survives merely because it exists.

Every legacy capability is evaluated as:

`KEEP | ADAPT | MERGE | MIGRATE | SUPERSEDE | ARCHIVE | REMOVE | DEPRECATE_AND_OBSERVE | UNKNOWN_REQUIRES_EVIDENCE`

Removal requires capability extraction, replacement validation, dependent migration, test-equivalence evidence and an Evolution Confidence Score (ECS) supported by exact evidence.

## Current measured truth

Advanced repository-intelligence evidence is bound to exact head `3f714959203594b753085af4be03259896a0e64d`.

- AIGC CI `#2558`: `SUCCESS`;
- run ID: `31182185660`;
- retained artifact ID: `8995258580`;
- artifact digest: `sha256:c5990e1ec84042d1be64f45a335f0467daf4ef04dd94e076dcd745ca9ad103cf`;
- detailed measured record: `AIGC_NEXUS_STAGE1_ADVANCED_MEASUREMENTS_V1.md`;
- PR #181 remains draft and unmerged.

The earlier corrected static baseline at `8eeb7eae57c41c957bbc66347307057a3ca66c60` remains historical measurement evidence. This ledger does not treat CI success as production proof or external-action authority.

## Measured repository intelligence

### Structural/topology baseline

At the advanced head the repository contains approximately:

- total files: `1010`;
- source files: `247`;
- test files: `138`;
- documentation files: `234`;
- configuration/schema files: `301`;
- infrastructure files: `18`.

The prior corrected import analysis found `469` internal Python import edges, `0` detected multi-module import cycles and no Python syntax errors.

High-coupling migration anchors remain led by `src.core.contract_validator`, `src.domain.identity.production_sessions`, `src.api.app`, `src.domain.nexus.contracts`, `src.domain.quests.candidates` and `src.domain.epistemic.models`. High coupling is migration-risk evidence, not defect evidence.

### Schema callers and overlap

- schemas analyzed: `155`;
- schemas with observed static callers: `94`;
- schemas without an observed static caller: `61`.

The strongest structural-overlap pair remains the exact-SHA CI issue/request schemas with feature-set Jaccard `1.0`. Both have observed repository references. Disposition remains `INVESTIGATE_FOR_SHADOW_CONSOLIDATION`; no schema deletion is authorized.

### Test ownership

Baseline direct ownership: `118 / 246 = 47.97%`.

Advanced transitive static import reachability:

- source modules: `247`;
- source modules reachable from tests: `132`;
- ratio: `53.44%`;
- no transitive static test reachability: `115`.

This is not runtime coverage. No module is designated untested or removable solely from these measurements.

### Canonical-responsibility search surfaces

The analyzer records heuristic candidate surfaces, not duplicate counts:

| Responsibility | Candidate surface | Nexus target present | Current measured disposition |
|---|---:|---|---|
| state machine / lifecycle | 33 | yes | `FUSE/ADAPT`; dependent migration unmeasured |
| policy / governance | 164 | yes | `FUSE/ADAPT`; policy equivalence unmeasured |
| evidence | 145 | yes | `FUSE/ADAPT`; Evidence Plane enrichment pending |
| agent registry / handoff | 23 | yes | `FUSE/ADAPT`; legacy routing behavior to extract |
| dashboard / UI | 175 | yes | `MIGRATE/CONVERGE`; surface mapping pending |
| provider runtime | 79 | **no canonical Nexus target detected** | `BUILD_CANONICAL_TARGET_THEN_ADAPT` |

The provider-runtime gap is the clearest new architectural finding. Historical Gemini/provider controls cannot be retired into a nonexistent Nexus target.

### Branch/PR topology

- remote branches measured: `133`;
- latest-commit age 0–7 days: `32`;
- 8–30 days: `96`;
- 31–90 days: `5`.

Examples of heavy divergence from main include the historical operator-cockpit branch at `35` ahead / `280` behind, the truth-first procurement branch at `6` ahead / `280` behind, and phase26 constellation refactor at `8` ahead / `273` behind.

This confirms repository-history saturation. Branches remain capability repositories until unique behavior, tests and evidence are extracted. No branch deletion or archival is authorized in Stage 1.

### Direct dependency use and reproducibility

Direct requirements: `11`.

Static import use observed: `9 / 11`.

No direct static import observed for `httpx` or `psycopg`; both remain `VERIFY_USAGE`, not `REMOVE`.

Resolved exact CI environment includes Streamlit 1.61.1, FastAPI 0.141.1, Uvicorn 0.52.1, Pydantic 2.13.4, HTTPX 0.28.1, pytest 8.4.2, jsonschema 4.26.0, PyYAML 6.0.3, psycopg 3.3.4, psycopg_pool 3.3.1 and PyJWT 2.13.0.

Measured reproducibility state:

- requirements use version ranges: true;
- recognized Python lockfile detected: false;
- state: `MEASURED_ENVIRONMENT_DRIFT_RISK`.

The external advisory pass confirms several known historical advisories are outside the measured fixed versions, including the Streamlit 2026 issue fixed in 1.54.0 and PyJWT 2026 issues fixed in 2.13.0. This is not a whole-graph security clearance. Transitive SBOM and exact package advisory automation remain required.

## Evidence grades

- `RUNTIME_PROVEN`: externally observed runtime receipt exists.
- `CI_VALIDATED`: exact-head hosted CI executed and passed.
- `TESTED`: bounded/local or historical tests are reported.
- `IMPLEMENTED`: code exists but stronger validation is absent.
- `DOCUMENTED`: design exists without confirmed implementation.
- `UNKNOWN`: insufficient evidence.

## Capability dispositions

| Historical capability | Evidence | Unique value to preserve | Canonical Nexus target | Disposition | Retirement state |
|---|---|---|---|---|---|
| EPI-01 contracts/canonical hashing (#178) | exact-head validated lineage | immutable contracts, canonical serialization, referential integrity | Nexus epistemic/domain contracts | `MERGED_BY_LINEAGE` | no cleanup until final Nexus disposition |
| EPI-02 ToolBroker (#179) | exact-head validated lineage | default deny, idempotency, budget, approval bindings | Nexus capability policy / ToolBroker | `MERGED_BY_LINEAGE` | provenance retained |
| EPI-03 Verifier (#180) | exact-head validated lineage | deterministic read-only verification | Nexus Verifier | `MERGED_BY_LINEAGE` | provenance retained |
| Colosseum orchestration (#177) | exact-head CI #2411 | DoD traceability, TaskDAG, scheduler, independent verifier assignment, resource reservations | Nexus Planning & Scheduling | `ADAPT` | feature map/test migration required |
| OMNI-FORGE (#173) | implementation + adversarial history; admission history mixed | graph validation, bounded repair, budgets, exact bindings | Nexus deterministic planning/validation | `ADAPT` | lifecycle/authority supersession not yet proven |
| Evidence Plane (#169) | focused structural evidence | lineage, freshness, metrics, quality/insufficiency | Nexus Evidence | `ADAPT` | schema/test/caller migration required |
| Policy Enforcement (#166) | focused tests reported | fail-closed rules, emergency constraints, self-approval prevention | Nexus policy/governance | `ADAPT` | equivalence/dependent migration required |
| Gemini release candidate (#170) | substantial implementation | provider isolation, stop, idempotency, rate/token budgets, receipts, canary discipline | **future canonical Nexus Provider Runtime** | `ADAPT_TO_PROVIDER_RUNTIME` | cannot retire before canonical target exists |
| legacy Gemini #145/#152 | historical implementation/tests | canary/secret-reference/diagnostic regressions | provider runtime / CI evidence | `SUPERSEDE_AFTER_EXTRACTION` | regression migration required |
| Québec GCP foundation (#172) | plan-only/static evidence | Canadian region/IAM/budget/data-residency controls | Nexus infrastructure / GCP adapter | `ADAPT_DESIGN/DEFER_RUNTIME` | no cloud mutation from discovery |
| Agent Registry / handoffs (#79) | historical CI + 345 tests | deterministic handoffs, capability map, review evidence, SQLite adapters | Nexus specialist registry/planning | `ADAPT` | routing/test equivalence required |
| PR graph/review saturation (#75) | historical CI | graph drift and review-load analytics | Nexus Repository Intelligence | `ADAPT` | useful analytics to absorb |
| CI pinning/hardening (#74/#123) | historical CI + portions already mainline | immutable action identity, trigger/evidence hardening | Nexus CI fitness | `REUSE_OR_ADAPT` | compare against current workflow |
| legacy cockpit (#122 + historical cockpit branches) | implementation history | operator workflow, audit, stop visibility | canonical Nexus UI | `MIGRATE` | UI surface map/shadow UX needed |
| procurement / Ω Mission OS corpora | extensive docs/modules | domain decisions and architectural rationale | Nexus docs/intelligence archive targets | `DEPRECATE_AND_OBSERVE` | document-by-document extraction required |

## ECS policy and measured partial inputs

`ECS = ReplacementCoverage × TestEquivalence × DependencyMigration × EvidenceConfidence`

Current partial subsystem inputs:

| Subsystem | ReplacementCoverage proxy | TestEquivalence repository proxy | DependencyMigration | EvidenceConfidence | ECS |
|---|---:|---:|---|---|---|
| state machine | 0.5 | 0.5081 | unmeasured | unmeasured | uncomputed |
| policy/governance | 0.5 | 0.5081 | unmeasured | unmeasured | uncomputed |
| evidence | 0.5 | 0.5081 | unmeasured | unmeasured | uncomputed |
| agent registry | 0.5 | 0.5081 | unmeasured | unmeasured | uncomputed |
| dashboard | 0.5 | 0.5081 | unmeasured | unmeasured | uncomputed |
| provider runtime | 0.0 | 0.5081 | unmeasured | unmeasured | uncomputed |

The replacement proxy is heuristic and the test-equivalence value is a repository-level static proxy. Neither is a subsystem completion percentage.

No component currently qualifies for an ECS retirement band because DependencyMigration and EvidenceConfidence are unset.

## Next measured actions

1. Shadow-validate the exact-SHA schema pair against callers and accepted fixtures.
2. Trace the 115 modules without transitive static ownership through runtime/API/configuration/subprocess paths.
3. Build feature-level capability maps inside each responsibility search surface, excluding keyword false positives.
4. Start canonical Nexus Provider Runtime design by extracting generic controls from #170 without live execution.
5. Generate branch-to-capability maps for the most divergent branches before any branch lifecycle action.
6. Generate a transitive dependency SBOM and exact-version advisory report; choose a reproducible constraints/lock strategy.
7. Calculate component-specific DependencyMigration and EvidenceConfidence inputs before any ECS retirement score.

## Hard boundary

Stage 1 remains non-destructive.

No files, schemas, modules, branches or PRs are removed, archived, closed or merged from these measurements. No dependency is removed. No provider execution, deployment, production activation or external action is authorized.
