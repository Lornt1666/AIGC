# PIBC-v1 Acceptance Criteria

PIBC-v1 is accepted as `IMPLEMENTED_IN_PR` only when all of the following are evidenced at one exact head revision:

1. Both identity schemas pass Draft 2020-12 validation and reject unknown properties.
2. The local adapter cannot claim production authority and rejects caller-supplied authority or secret-bearing fields.
3. Local preflight permits only valid repository-owned membership and session bindings.
4. Production mode rejects local providers, IAL0/AAL0/FAL0, insufficient evidence maturity, empty issuer/audience policy, and unbound revision.
5. Identity receipts are redacted, deterministic, replay-bound, persistent across restart, and protected from update and deletion.
6. Existing authorization, Quest, persistence, API, contract, security, and readiness tests remain green.
7. Contract validation, constitutional validation, procurement smoke tests, and redaction scanning pass.
8. The production-readiness ledger is not promoted by documentation or file presence alone.
9. GitHub Actions completes successfully at the exact branch head.
10. The accountable operator reviews the exact diff and separately decides whether to merge.

Production identity, deployment, and external action remain outside these acceptance criteria.
