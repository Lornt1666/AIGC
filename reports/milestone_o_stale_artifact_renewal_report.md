# Milestone O - Stale Artifact Renewal

Milestone O instantiates Phase 27 as AIGC's stale-artifact renewal and deep-research controller.

It does not delete stale generated artifacts. It converts them into governed renewal records that preserve truth, define research questions, name architecture improvements, and specify regeneration commands before any new approval candidate can be considered.

## Added

- Schema: `schemas/stale_artifact_renewal_record.schema.json`
- Configuration: `config/phase27_stale_artifact_renewal.json`
- Prompt doctrine: `prompts/phase27_stale_artifact_renewal.md`
- Runtime module: `src/phase27_stale_artifact_renewal.py`
- CLI route: `python .\src\aigc.py run phase27`
- Tests: `tests/test_milestone_o_stale_artifact_renewal.py`

## Safety Boundary

Phase 27 performs no deletion, no external data fetch, no employer contact, no credential use, no proposal submission, no approval grant, and no external action.

## Renewal Principle

Stale generated artifacts are preserved as historical derivatives and upgraded into renewal blueprints. They are not active approvals.

## Definition Of Done

- Renewal records are contract-valid.
- Stale source and generated derivative roles remain explicit.
- Deep research is represented as operator-scheduled questions, not hidden browsing.
- Regeneration remains blocked until truth, freshness, quality, approval, and execution gates resolve.
