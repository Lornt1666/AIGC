---
name: aigc-canadian-cloud-operator
description: Govern AIGC repository and release operations from Codex cloud without relying on a local laptop, while requiring any external execution or data plane to remain in explicitly approved Canadian regions. Use for exact-SHA CI recovery, Canadian staging planning, regional execution-contract validation, and evidence-bound release preparation. Do not use to authorize production, merge, live model calls, publication, email sending, financial action, or unreviewed external mutation.
---

# AIGC Canadian Cloud Operator

## Purpose

Run the engineering and review procedure from Codex cloud while keeping the user's laptop out of the execution path. Treat Codex as the repository-control plane. Treat separately authorized Canadian infrastructure as the only permitted external execution and data plane.

This skill does **not** claim that the Codex sandbox, model inference, or all OpenAI processing occurs in Canada. Unless an authoritative service receipt proves otherwise, record:

```text
codex_cloud_region_verified_canada=false
```

For strict Canadian residency, send Codex only repository content, synthetic fixtures, hashes, metadata, and sanitized non-personal evidence. Route any approved external workload to the Canadian execution plane defined by the contract.

## Primary regional policy

- Primary region: `northamerica-northeast1` — Montréal, Quebec, Canada.
- Optional fallback: `northamerica-northeast2` — Toronto, Ontario, Canada, only after exact service availability and explicit owner approval.
- Silent failover outside Canada is prohibited.
- A global or multi-region resource is not accepted as Canadian merely because a Canadian endpoint exists.
- Compute, storage, logs, evidence, backups, secrets, and databases must each receive an explicit regional review before staging execution.
- Model availability must be verified for the exact model and service at the time of authorization.

## Canadian governance values

Apply these controls as engineering requirements, not as an unsupported claim of legal certification:

1. Accountability and an identifiable human decision-maker.
2. Defined purpose and bounded authority before collection or execution.
3. Data minimization and least-privilege access.
4. Privacy by design and privacy-protective defaults.
5. Accuracy, traceability, and correction mechanisms.
6. Proportionate safeguards, retention limits, and deletion procedures.
7. Transparency about AI assistance, uncertainty, and system boundaries.
8. Human oversight for consequential decisions.
9. A privacy-impact assessment when the data, transfer, or automated decision warrants it.
10. A documented cross-border assessment because the Codex control-plane region is not established as Canadian.

## Required files

- Contract template: `assets/execution-contract.example.json`
- Policy reference: `references/canadian-execution-policy.md`
- Validator: `scripts/validate_canadian_execution.py`

## Procedure

### 1. Bind the repository state

Record the exact repository, branch, full commit SHA, full tree SHA, base SHA, pull request, and changed-file inventory. Never act on “latest” without resolving it to exact identifiers.

### 2. Classify the task

Choose one:

- `repository_only`: code review, tests, CI repair, documentation, or evidence preparation inside the repository.
- `canadian_staging_plan`: no external execution; prepare an exact regional plan and default-deny authorization packet.
- `canadian_staging_execution`: a separately authorized no-production staging action on the approved Canadian execution plane.

### 3. Minimize Codex inputs

Codex inputs must remain `SANITIZED_NON_PERSONAL`. Never place raw credentials, private keys, authorization headers, cookies, personal records, private customer content, or unredacted runtime output in a prompt, contract, repository file, log, or receipt.

### 4. Prepare the contract

Copy the example contract outside any public evidence location. Fill exact identifiers and reviews. Do not put raw secret values in the contract. Secret references must use exact versions and remain external to this skill package.

### 5. Validate before action

Planning validation:

```bash
python .agents/skills/aigc-canadian-cloud-operator/scripts/validate_canadian_execution.py \
  --contract /secure/path/canadian-execution-contract.json \
  --gate plan
```

Exact-head CI validation:

```bash
python .agents/skills/aigc-canadian-cloud-operator/scripts/validate_canadian_execution.py \
  --contract /secure/path/canadian-execution-contract.json \
  --gate ci
```

No-production staging validation:

```bash
python .agents/skills/aigc-canadian-cloud-operator/scripts/validate_canadian_execution.py \
  --contract /secure/path/canadian-execution-contract.json \
  --gate staging
```

A passing contract validates only the packet. It does not deploy anything.

### 6. Enforce approval separation

Repository analysis and local/cloud-sandbox tests may proceed within their existing authority. Any external staging execution requires an exact, unexpired, human-approved contract. Production, live model calls, traffic migration, publication, sending, merging, financial action, and real-user activation require separate procedures and remain prohibited by this skill.

### 7. Produce a bounded receipt

Return only:

- repository and task identifiers;
- requested branch, SHA, and tree SHA;
- gate and validation conclusion;
- approved Canadian region and region label;
- Codex-region verification state;
- data classification;
- privacy and cross-border review states;
- human-approval state;
- false authority states;
- canonical contract SHA-256;
- remaining blockers.

Never include secret values or credential-bearing command output.

## Hard prohibitions

```text
codex_cloud_region_verified_canada=false unless independently evidenced
silent_non_canadian_failover=false
production_activation_authorized=false
live_model_call_authorized=false
external_business_action_authorized=false
gmail_send_authorized=false
github_runtime_mutation_authorized=false
merge_authorized=false
judge_publication_authorized=false
financial_action_authorized=false
```

Do not weaken existing AIGC exact-SHA, emergency-stop, redaction, secret, approval, evidence-integrity, or human-review controls.
