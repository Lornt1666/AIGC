# AIGC Nexus Evolution Ledger

Status: `STAGE_1_DISCOVER_ACTIVE`
Integration train: `release/aigc-nexus-v1`
Governing contract: `AIGC_INTEGRATION_CONTRACT_V1`

## Governing migration law

Nothing is removed because it is old. Nothing survives merely because it exists.

Every legacy capability is evaluated as:

`KEEP | ADAPT | MERGE | MIGRATE | SUPERSEDE | ARCHIVE | REMOVE | DEPRECATE_AND_OBSERVE | UNKNOWN_REQUIRES_EVIDENCE`

Removal requires capability extraction, replacement validation, dependent migration, and evidence sufficient for an Evolution Confidence Score (ECS).

## Current exact truth

- Nexus branch exact head before this ledger increment: `1a5d91df4e5130cea8ddbe0d56f1d71e8891f0f5`.
- Exact-head AIGC CI run `#2512` / run ID `31152581143`: `SUCCESS`.
- Retained exact-head artifact ID: `8983880436`.
- Artifact digest: `sha256:83c45b63bf7ccbc882b437afba5a59ecf60848a17370db1762bd5acd7f0b8953`.
- PR #181 remains draft and unmerged.

This ledger does not treat CI success as production proof or external-action authority.

## Evidence grades

- `RUNTIME_PROVEN`: externally observed runtime receipt exists.
- `CI_VALIDATED`: exact-head hosted CI executed and passed.
- `TESTED`: bounded/local or non-exact-head tests are reported.
- `IMPLEMENTED`: code exists, but stronger validation is absent or not yet reviewed here.
- `DOCUMENTED`: documentation/design exists without confirmed implementation.
- `UNKNOWN`: insufficient evidence in this discovery pass.

## Initial capability dispositions

| Historical capability | Evidence observed | Unique value to preserve | Canonical Nexus target | Initial disposition | Removal state |
|---|---|---|---|---|---|
| EPI-01 contracts/canonical hashing (#178) | exact-head CI previously validated; inherited by Nexus | frozen Pydantic contracts, canonical serialization, referential integrity | Nexus epistemic/domain contracts | `MERGED_BY_LINEAGE` | historical PR may close only after final Nexus release disposition |
| EPI-02 ToolBroker (#179) | exact-head CI previously validated; inherited by Nexus | default-deny policy, idempotency, budget, approval bindings | Nexus Capability Policy / ToolBroker | `MERGED_BY_LINEAGE` | retain provenance until release |
| EPI-03 Verifier (#180) | exact-head CI previously validated; inherited by Nexus | deterministic read-only verification, immutable findings | Nexus Verifier | `MERGED_BY_LINEAGE` | retain provenance until release |
| Colosseum orchestration kernel (#177) | exact-head CI #2411 reported admitted | WorkOrder/DoD traceability, TaskDAG, scheduler, independent verifier assignment, bounded resource reservations | Nexus Planning & Scheduling | `ADAPT` | do not merge whole state/authority model |
| OMNI-FORGE (#173) | implementation/adversarial coverage reported; exact-head admission history mixed | graph validation, bounded repair, budgets, exact authorization/evidence bindings | Nexus Deterministic Planning / Structural Validation | `ADAPT` | competing state machine/authority to be superseded after capability extraction |
| Evidence Plane Slice A (#169) | local/focused validation reported; hosted exact-head admission not established in current review | metric definitions, lineage, freshness, quality and insufficiency semantics | Nexus Evidence & Provenance | `ADAPT` | no removal until evidence contracts are mapped and tests ported |
| Policy Enforcement Layer (#166) | local focused tests reported; hosted admission not established in current review | fail-closed policy rules, emergency constraints, self-approval prevention | Nexus Governance / Capability Policy | `ADAPT` | duplicate promotion authority prohibited |
| Governed Gemini release candidate (#170) | substantial repository implementation; current exact-head admission must be rechecked before reuse | provider isolation, durable stop, idempotency, rate/token budgets, evidence receipts, canary discipline | Nexus Provider Runtime + Gemini Adapter | `ADAPT` | provider-specific governance must not remain global architecture |
| Legacy Gemini PRs #145/#152 | historical tests/evidence; superseded by later reconstitution | canary, secret-reference, diagnostic patterns | Nexus Provider Runtime / CI evidence | `SUPERSEDE` | preserve regression/invariant knowledge, not branch topology |
| Québec GCP foundation (#172) | plan-only design/static evidence; external cloud facts unresolved | Canadian-region/IAM/budget/data-residency controls | Nexus Infrastructure / GCP adapter | `DEPRECATE_AND_OBSERVE` for runtime; `ADAPT` design | no Terraform apply or cloud mutation from discovery |
| Canadian cloud operator skill (#171) | repository skill/validator design | region-aware operator policy and truthfulness | operational documentation / policy reference | `ARCHIVE_OR_ADAPT` | not core runtime dependency |
| Diamond/schema hardening (#174) | bounded schema-validator hardening | full Draft 2020-12 validation/format checking | canonical Nexus contract validation | `ADAPT` | compare against current config loader before any merge |
| Cloud advancement loop (#142) | extensive local/full-suite evidence reported | append-only/idempotency/recovery/checkpoint ideas | Nexus reconciliation / evidence | `ADAPT` | competing action lifecycle to be superseded |
| Quest handoffs / Agent Registry (#79) | CI run 1119 reported success; 345 tests | deterministic internal handoffs, capability map, review evidence, SQLite adapters | Nexus Dynamic Specialist Registry / Handoff planning | `ADAPT` | preserve specialist/routing behavior; discard duplicate conductor authority |
| PR graph / review saturation (#75) | historical CI reported success | repository graph drift and queue-health analytics | Nexus Repository Intelligence | `ADAPT` | valuable for convergence analytics, not runtime governance authority |
| CI action pinning (#74/#123) | historical CI evidence; later mainline may already contain portions | immutable action pins, trigger hardening, dependency review receipts | Nexus CI / supply-chain fitness functions | `REUSE_OR_ADAPT` | verify mainline before importing anything |
| Legacy cockpit / one-click UI (#122 and mainline cockpit) | implemented historically; current Nexus uses Streamlit | operator workflows, audit surfaces, emergency-stop visibility | Canonical Nexus UI | `ADAPT` | avoid permanent duplicate dashboards |
| Historical procurement documents/modules | repository search confirms multiple procurement catalogs/reports/modules | domain research, control-layer decisions, prior gap analyses | Nexus Repository Intelligence / Procurement Ledger | `DEPRECATE_AND_OBSERVE` pending content fusion | do not delete until unique decisions are extracted |
| Ω Mission OS documentation corpus | extensive docs detected | operational doctrine and historical architectural rationale | archived reference + selected Nexus documentation | `DEPRECATE_AND_OBSERVE` | classify document-by-document before archival |

## Dependency discovery — initial facts

Current Nexus requirements include Streamlit, FastAPI, Uvicorn, Pydantic, HTTPX, pytest, jsonschema, PyYAML, psycopg/psycopg_pool, and PyJWT.

Initial August 2026 research indicates:

- Streamlit current PyPI release is 1.60.0; Nexus range `>=1.36,<2` remains compatible but very broad.
- Pydantic current stable PyPI release is 2.13.4; Nexus range `>=2.8,<3` remains compatible but broad.
- pytest current PyPI release is 9.1.1; Nexus range `>=8,<9` intentionally excludes the current major and therefore requires compatibility evaluation rather than blind upgrade.
- jsonschema current PyPI release is 4.26.0; Nexus range `>=4.23,<5` includes it.
- psycopg current PyPI release is 3.3.4; Nexus range `>=3.2,<4` includes it.
- PyJWT current PyPI release is 2.13.0; Nexus range `>=2.9,<3` includes it.
- PyYAML current PyPI release is 6.0.3; Nexus range `>=6.0,<7` includes it.
- HTTPX stable remains 0.28.1 while 1.0 development releases exist; Nexus `>=0.27,<1` remains conservative.

No dependency is classified obsolete solely from version distance. Exact import use, transitive security, compatibility, and test evidence remain required.

## Ecosystem evolution findings — initial facts

- Google documentation updated July 21, 2026 describes ADK as supporting predictable workflow agents and dynamic multi-agent routing, with deployment targets including managed Runtime, Cloud Run, and GKE.
- Google release notes state Vertex AI Extensions are deprecated and scheduled for shutdown after November 26, 2026; any AIGC dependency on Extensions must therefore migrate to Agent Platform rather than be preserved.
- Google release notes show Agent Engine Sessions and Memory Bank as generally available and Toronto (`northamerica-northeast2`) available for Agent Engine; this is relevant to future Canadian memory/runtime adapters but does not justify procurement yet.
- MCP published a 2026-07-28 specification with a stateless core, multi-round-trip requests, authorization hardening, extensions, tasks, and deprecations. Any future MCP adapter must target the current specification rather than historical session assumptions.
- A2A is an open interoperability protocol with a 1.0 maturation track and compatibility tooling. It is a future interoperability candidate, not a mandatory Nexus V1 dependency absent a concrete cross-runtime requirement.

## ECS policy

`ECS = ReplacementCoverage × TestEquivalence × DependencyMigration × EvidenceConfidence`

Initial governance bands:

- `0.90–1.00`: candidate for retirement after final validation.
- `0.75–0.89`: deprecate + shadow + observe.
- `0.50–0.74`: migration incomplete; retain.
- `<0.50`: keep; replacement is not proven.

No substantial legacy subsystem currently receives an ECS retirement score from this initial discovery pass because repository-wide dependency/test-equivalence measurement is incomplete.

## Next discovery actions

1. Build canonical responsibility/import maps for orchestration, evidence, policy, memory, dashboards, provider controls, and persistence.
2. Measure duplicate schemas/domain models/state machines.
3. Port reusable historical tests to architectural fitness functions before retirement decisions.
4. Audit direct dependency imports and generate a lock/constraints strategy recommendation.
5. Identify any Vertex AI Extensions references for mandatory migration.
6. Compare legacy cockpit surfaces with Nexus UI and define a single UI migration map.
7. Produce quantitative ECS inputs per subsystem before proposing archive/remove ChangeSets.
