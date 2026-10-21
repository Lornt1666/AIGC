# MVP++ Documentation Architect Agent

**Policy:** `aigc-mvp-plus-plus-documentation-v1`  
**Status:** Deterministic local generator implemented; generated content is always draft.  
**Release authority:** Existing canonical Release Assurance only.

## Purpose

The Documentation Architect turns a structured project brief into a tailored, linked, content-addressed documentation pack. It creates core governance and delivery documents, then selects additional documents from explicit project signals (API/integrations, data/privacy, AI/agents, infrastructure, security, UX, finance/procurement, and compliance).

The generator is deterministic and offline. It does not make model calls, use the network, execute shell commands, mutate the repository, provision services, or approve its own output.

## Quick start

From the repository root:

```bash
python src/aigc_documentation_architect.py \
  --input config/archon_genesis_aigc_brief.json \
  --output-dir ./artifacts/documentation_architect_aigc

python -m unittest discover -s tests -p 'test_documentation_architect.py' -v
```

Optional evidence inventory:

```bash
python src/aigc_documentation_architect.py \
  --input config/archon_genesis_aigc_brief.json \
  --evidence-inventory ./artifacts/evidence-inventory.json \
  --output-dir ./artifacts/documentation_architect_aigc
```

Evidence inventory entries are source claims only. This tool does not authenticate, validate, or promote them into proof.

## Core pack

1. Executive Charter and Scope
2. Requirements and Acceptance Criteria
3. System Architecture and Architecture Decision Records
4. Risk Register and Threat Model
5. Engineering Plan and Test Strategy
6. Operations, Recovery, and Incident Runbook
7. Evidence Plan and Release Assurance
8. Decision, Assumption, and Open-Question Register
9. Pack index and JSON manifest

Optional specialist documents are selected by keyword signals in the brief. High/critical risk automatically adds security and compliance applicability documents. Selection is a deterministic heuristic, not a substitute for expert review; owners must confirm that the selected pack is complete for the actual system.

## Output contract

- `README.md`: navigable index with per-document SHA-256 digests.
- `documentation_manifest.json`: schema/policy version, source digest, document inventory, document hashes, draft status, and authority limits.
- One Markdown document per selected type.
- Every document states **GENERATED DRAFT — NOT APPROVED**, includes the source digest, and identifies missing facts as unknown/TBD.
- Manifest records `release_decision: BLOCK`, `approvals_inferred: false`, and no repository/external-action authority.

## Design rules

- Never invent project facts, approval, test results, owners, SLOs, certifications, compliance, deployment status, or production readiness.
- Distinguish verified facts, user-provided claims, assumptions, decisions, and open questions.
- Hashes prove byte consistency only; they do not authenticate a source or signer.
- Risk and compliance documents describe a review plan, not a legal conclusion.
- Generated docs are written only to the caller-specified output directory; CI writes to runner-temporary staging.
- Human owners and independent reviewers must tailor and accept the pack before it becomes authoritative.

## Acceptance criteria

- Deterministic output for identical inputs.
- Optional document selection follows the same input signals every time.
- Source digest changes when the brief/evidence inventory changes.
- Every manifest document exists and its digest matches.
- Empty/invalid briefs fail closed.
- No network, shell, repository-write, approval, merge, deployment, or release capability.
- CI tests and generation step pass on the exact source revision before implementation is considered validated.

## Limitations / next hardening

- Current selection is keyword-based; it can over-select or miss specialist documents.
- Output content is a governed starting template, not a project-specific, independently researched design.
- Production use should add a versioned document-schema registry, explicit required-document policy per risk/domain, source-level traceability, link/reference validation, stale-document detection, and an independent review/approval workflow.
