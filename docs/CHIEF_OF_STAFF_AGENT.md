# AIGC Chief of Staff Agent

**Status:** Implemented as a deterministic, bounded local coordinator; specialist integrations remain evidence-gated.  
**Policy:** `aigc-chief-of-staff-v1`  
**Release authority:** Existing canonical Release Assurance only.

## Purpose

The Chief of Staff converts an AIGC project brief into an ordered work queue, invokes ARCHON-GENESIS to compile the architecture proposal, checks a small set of coordinator invariants, and records explicit work orders for the specialist teams. It prevents agent work from being treated as complete unless the corresponding work actually ran and produced evidence.

## Run

From the repository root:

```bash
python src/aigc_chief_of_staff.py \
  --input config/archon_genesis_aigc_brief.json \
  --output-dir ./artifacts/chief_of_staff_aigc

python -m unittest discover -s tests -p 'test_chief_of_staff.py' -v
```

Outputs are `chief_of_staff_runbook.json` and `chief_of_staff_report.md`.

## Canonical order

1. **Chief of Staff intake and scope lock** — validate the brief and define boundaries.
2. **ARCHON-GENESIS** — compile the deterministic architecture and proposed agent contracts.
3. **Independent contract gate** — check output integrity and governance invariants.
4. **AER** — assess architecture, engineering, reliability, observability, SLOs, and rollback.
5. **Red Team** — propose/assess synthetic threat cases only; no active attacks are run by this coordinator.
6. **Blue Team** — assess timestamped telemetry, detections, defensive controls, and recovery evidence.
7. **Green Team** — propose minimal remediations only after findings exist; no direct writes or merges.
8. **Independent verifier** — validate evidence, trusted authentication, exact commit/tree and policy binding.
9. **Authorized human reviewer** — explicitly accept consequential changes.
10. **Canonical Release Assurance** — sole release decision authority; receives evidence but is not replaced or overridden.

AER, Red, and Blue are independent review streams after the contract gate; their results converge before Green remediation. Green remediation is not authorized while findings or input evidence are absent. The runbook represents this dependency order and detects unknown dependencies, duplicate stage IDs, and cycles.

## Initial execution boundary

The current coordinator actually executes only:
- intake/scope validation through ARCHON's strict input contract;
- deterministic ARCHON-GENESIS compilation;
- static contract/authority invariant checks;
- runbook and work-order generation.

It does **not** claim that AER, Red, Blue, Green, the independent verifier, a human reviewer, or Release Assurance have run. Those stages are marked `BLOCKED_INPUTS` until the relevant evidence, integrations, and approvals exist. This is deliberate fail-closed behavior, not a successful assurance result.

## Non-negotiable invariants

- No permission grants, secret handling, arbitrary shell/tool execution, external writes, merges, deployments, or release actions.
- No live Red Team activity from this coordinator.
- No self-review or self-approval; independent reviewer identity must be distinct from the author.
- Content hashes support integrity checks but are not signatures or proof of identity.
- Exact-revision evidence and an independently configured trusted verifier are required before evidence can be considered authenticated.
- Canonical Release Assurance remains the only release decision authority.
- Unknown evidence, failed checks, stale evidence, missing approvals, and unavailable integrations remain blocked.

## CI

`.github/workflows/aigc-ci.yml` runs the Chief of Staff contract tests and compiles the AIGC brief into the CI evidence directory. A pending workflow is not a passing workflow. Confirm the exact tested commit, conclusion, test output, and artifact receipt before treating validation as complete.
