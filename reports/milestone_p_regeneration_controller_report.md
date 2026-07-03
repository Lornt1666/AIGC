# Milestone P - Fresh Candidate Regeneration Controller

Milestone P instantiates Phase 28 as AIGC's guarded regeneration controller.

Phase 28 creates a truth-preserving bridge from Phase 27 renewal records to fresh internal Phase 4 and Phase 5 candidate payloads. It blocks by default and requires explicit operator-approved freshness review before any regenerated candidate is produced.

## Added

- Schema: `schemas/regeneration_candidate_record.schema.json`
- Configuration: `config/phase28_regeneration_controller.json`
- Prompt doctrine: `prompts/phase28_fresh_candidate_regeneration.md`
- Runtime module: `src/phase28_regeneration_controller.py`
- CLI route: `python .\src\aigc.py run phase28`
- Tests: `tests/test_milestone_p_regeneration_controller.py`

## Safety Boundary

Phase 28 performs no external data fetch, no employer contact, no proposal submission, no approval grant, no Phase 6 authorization, no credential use, no canonical Phase 4 overwrite, no canonical Phase 5 overwrite, and no external action.

## Regeneration Principle

Fresh candidates may be created only from Phase 27 renewal records and only after an exact-phrase freshness review gate is satisfied. The output remains an internal regeneration ledger, not an active application or submission workflow.
