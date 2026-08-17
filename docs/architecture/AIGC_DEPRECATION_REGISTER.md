# AIGC Deprecation Register

Status: fail-closed. A deprecation candidate is not a deletion authorization.

## Rules

A path may be deleted only after: canonical replacement exists; useful content migrated; runtime/test/workflow/deployment references are zero; no security/release/historical evidence requires it; post-removal validation passes.

## Current candidates

### Legacy competing product vocabulary

Status: CANONICAL_REFACTOR, not deletion.

Mission, Quest, cockpit, OMNARCHON/HLX² and older agent-orchestration vocabulary may describe useful implemented controls. New product-domain code should use Employer, Opportunity, Engagement, WorkOrder, Task, AgentCell, Swarm, Deliverable, Verification and WorkLedger where semantically appropriate. Legacy terms are removed only after migration and compatibility analysis.

### Older Gemini release trains

PR #145 and PR #152 overlap materially with the reconstituted PR #170 release candidate. Status: HISTORICAL_EVIDENCE_KEEP / MERGE_DUPLICATE pending exact blob, dependency and release-evidence comparison. No deletion authorized.

### Older cloud/staging trains

PR #121, #125, #129 and #142 overlap with later Québec foundation and completion-loop work. Status: MERGE_DUPLICATE / HISTORICAL_EVIDENCE_KEEP pending exact reference and evidence analysis. No deletion authorized.

### Generated artifacts

Build outputs, caches, temporary logs and generated evidence that are reproducible and not required by repository policy should not be committed. Existing instances require exact-path inventory before removal.

## Canonical correction

The phrase "least-cost admissible route" is deprecated as a Compute Exchange governing objective. Replace it with "best-fit admissible execution portfolio for the employer's outcome." Cost remains an important dimension and constraint but cannot dominate quality, security, confidentiality, privacy, jurisdiction, licensing, reliability, verification or employer preference.