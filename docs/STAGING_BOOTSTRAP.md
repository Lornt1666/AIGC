# AIGC Staging Preparation Runbook

## Purpose

`scripts/bootstrap-staging.sh` prepares and evaluates a mock-only staging target against an exact repository revision.

It does **not** bootstrap live Google Cloud resources. It does not perform a provider read, Terraform apply, Workload Identity Federation configuration, Secret Manager access, Identity Platform configuration, DNS mutation, deployment, or any other external action.

## Prerequisites

- Run from a clean Git working tree.
- Use Python with the repository dependencies installed.
- Run after the provider-discovery automation kit from PR #112 is available in the branch.
- Use Bash directly because GitHub's contents API does not preserve executable mode for newly created files.

## Command

```bash
bash scripts/bootstrap-staging.sh
```

## Generated artifacts

The command writes revision-bound preparation artifacts beneath:

```text
artifacts/staging_bootstrap/<EXACT_GIT_SHA>/
```

Expected files include:

```text
provider_discovery/target_specification_submission.json
provider_discovery/command_plan.json
provider_discovery/discovery_simulation_report.json
provider_discovery/provenance_envelope.json
staging_procurement_evaluation.json
preparation_summary.json
```

The provider-discovery output is `SIMULATION_ONLY` and is permanently inadmissible as live provider evidence.

## Current stopping point

The preparation runner stops before provider discovery authority. Its next gate is:

```text
PROVIDER_DISCOVERY_AUTHORIZATION
```

A later live staging runner must be resumable and process no more than one separately authorized phase per invocation:

```text
TARGET_SPECIFICATION
-> DISCOVERY_READY_FOR_REVIEW
-> DISCOVERY_EVIDENCE_ACCEPTED
-> STATE_BACKEND_PLAN_READY
-> STATE_BACKEND_BOOTSTRAPPED
-> IDENTITY_BOOTSTRAP_PLAN_READY
-> READY_FOR_OPERATOR_REVIEW
```

Authorization is never accepted as evidence that the corresponding provider action occurred.

## Future command surface

The intended unified interface is:

```powershell
python .\src\aigc.py staging-bootstrap --resume --stop-at-next-gate
```

That command must validate exact revisions, pack digests, receipt lifetimes, single-use phase consumption, plan evidence, apply authority, post-apply evidence, and operator review before advancing state.
