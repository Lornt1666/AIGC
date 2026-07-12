# Dual-Revision Evidence Gate v2 — Branch Manifest

Branch: `codex/ci-dual-revision-evidence-gate-v2-current-main`  
Base: `main@293de53489fe7212fad272c01c698c0ffe2da610`  
Scope: AIGC CI assurance only  
Operator-controlled: yes  
Merge authorized: no  
Deployment authorized: no  
Credentials authorized: no  
External action authorized: no

## Changed evidence surfaces

- `.github/workflows/aigc-ci.yml`
- `schemas/ci_revision_evidence_receipt.schema.json`
- `schemas/ci_merge_candidate_evidence_receipt.schema.json`
- `schemas/operator_implementation_authorization.schema.json`
- `src/core/ci_revision_evidence.py`
- `src/ci_revision_evidence_cli.py`
- `src/production_readiness_revision_bound_cli.py`
- `src/core/ci_merge_candidate_evidence.py`
- `src/ci_merge_candidate_evidence_cli.py`
- `tests/test_ci_revision_evidence.py`
- `tests/test_ci_merge_candidate_evidence.py`
- `tests/test_ci_operator_authorization.py`
- `governance/receipts/ci_dual_revision_evidence_v2_operator_authorization.json`
- `docs/governance/procedures/AIGC_DUAL_REVISION_CI_EVIDENCE_PROCEDURE_V2.md`
- `docs/governance/evolution/AIGC_EVOLUTION_PROCUREMENT_CYCLE_2026_07_11_DUAL_REVISION_EVIDENCE_V2.md`
- `docs/governance/evolution/AIGC_DUAL_REVISION_EVIDENCE_V2_PR_CHECKLIST.md`
- `docs/governance/AIGC_PROCUREMENT_ASSURANCE_INDEX.md`

## Review boundary

This manifest records intended branch scope. It does not claim CI success, operator review of the final head, merge authorization, post-merge verification, readiness promotion, deployment, credential use or external action.
