# Pipeline Serpent

## Genesis stages

1. Universe Seed Validation
2. Ontology Expansion
3. Architecture Synthesis
4. Module Generation
5. Security Gates
6. Observability Mesh Activation
7. Evolution Loop Trigger

Every stage emits `PASS` or `BLOCKED_PERMISSION` plus a named artifact. Runtime exceptions are failed-safe and no downstream external action exists.

## Verification gates

- JSON Schema and Pydantic validation agree.
- Unknown and authority-shaped inputs are rejected.
- Agent roles and stage order are exact.
- Same input produces the same hashes and receipt.
- Recursion beyond the configured limit is blocked.
- MCP annotations remain read-only, idempotent, and closed-world.
- Serialized output contains no raw-secret patterns.
- Full repository tests must pass locally; hosted CI is separately reported.

## Release and recovery

Changes travel through a non-default branch and protected pull request. A failed check blocks landing. Evolution proposals use normal patches and review; no history rewriting, protection bypass, or autonomous merge is permitted. Rollback is a new reviewed revert commit, preserving evidence.
