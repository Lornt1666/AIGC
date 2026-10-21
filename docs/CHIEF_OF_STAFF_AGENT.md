# AIGC Chief of Staff Agent

**Status:** Implemented as a deterministic, bounded local coordinator; specialist integrations remain evidence-gated.  
**Policy:** `aigc-chief-of-staff-v1`  
**Release authority:** Existing canonical Release Assurance only.

## Purpose

The Chief of Staff converts an AIGC project brief into an ordered work queue, invokes ARCHON-GENESIS to compile the architecture proposal, checks coordinator invariants, and can invoke the evidence-driven specialist workflow. It prevents agent work from being treated as complete unless the corresponding evaluator actually ran and produced a version-bound report.

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

## Evidence-driven specialist execution

`src/aigc_evidence_workflow.py` invokes the repository's actual deterministic `AERAgent`, `RedTeamAgent`, `BlueTeamAgent`, and (only when eligible) `GreenTeamAgent` evaluators. Each invocation receives a structured task containing stage/agent IDs, input digest, repository, full commit SHA, tree SHA, policy digest, invocation ID, output contract, allowed actions, and prohibited actions.

The Chief of Staff can delegate to this runner when exact-version envelope and input JSON files are provided:

```bash
python src/aigc_chief_of_staff.py \
  --input config/archon_genesis_aigc_brief.json \
  --output-dir ./artifacts/chief_of_staff_aigc \
  --evidence-envelope ./artifacts/evidence-envelope.json \
  --evidence-inputs ./artifacts/specialist-inputs.json
```

The workflow writes per-agent JSON reports, `workflow_summary.json`, and `evidence.jsonl`. The JSONL ledger verifies sequence continuity and a SHA-256 hash chain, flushes each record, and calls `fsync`. It is locally tamper-evident, not a digital signature or remote immutable store. Preserve the final digest independently and archive the CI artifact under a separately governed retention policy before calling it durable evidence.

### Trusted authentication boundary

`authenticate_report` accepts an external signing callback and a separate verification callback. `make_ed25519_verifier` verifies Ed25519 signatures against a caller-supplied pinned PEM public key and exact signer identity/trust-root ID. The private key must remain in a separately controlled KMS/HSM/signing service; it must not be placed in this repository or local workflow inputs. The CLI intentionally has no private-key-file option and does not claim to provision a production trust root. Without both callbacks, specialist reports remain unauthenticated and downstream Green remediation is blocked. Test-only signers/verifiers in unit tests are synthetic and do not establish production trust.

### Current execution boundary

- Chief of Staff and ARCHON compile the deterministic architecture/runbook.
- The evidence runner executes AER, Red, and Blue evaluators against supplied inputs; missing evidence yields `BLOCK`/`UNKNOWN`, not a fabricated pass.
- Green is invoked only after the upstream reports are authenticated and bound to the exact repository/commit/tree/policy/invocation.
- Independent verification remains `BLOCK` unless required specialist reports are trusted and pass.
- Human acceptance is always `BLOCKED` unless an authorized human explicitly accepts outside this automation.
- Canonical release remains `BLOCK`; the runner does not call or replace the existing canonical Release Assurance authority.

A successful unit test proves the evaluator/runner contract against the tested fixture, not that production signing, CI execution, or release evidence has passed.

## Non-negotiable invariants

- No permission grants, secret handling, arbitrary shell/tool execution, external writes, merges, deployments, or release actions.
- No live Red Team activity from this coordinator.
- No self-review or self-approval; independent reviewer identity must be distinct from the author.
- Content hashes support integrity checks but are not signatures or proof of identity.
- Exact-revision evidence and an independently configured trusted verifier are required before evidence can be considered authenticated.
- Canonical Release Assurance remains the only release decision authority.
- Unknown evidence, failed checks, stale evidence, missing approvals, and unavailable integrations remain blocked.

## CI

`.github/workflows/aigc-ci.yml` runs Chief of Staff and evidence-workflow contract tests, invokes the specialist evaluators against deliberately incomplete offline inputs, and uploads their run evidence with the exact-head CI artifact. The CI workflow does not have a production signing key, so this run is expected to block at trusted handoff and release. A pending or failed workflow is not a passing workflow. Confirm the exact tested commit, conclusion, test output, and artifact receipt before treating validation as complete.

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
