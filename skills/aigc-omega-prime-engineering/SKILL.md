---
name: aigc-omega-prime-engineering
description: Use this Skill for evidence-bound engineering, diagnosis, implementation, review, release, ChatGPT-app integration, and operational coordination of Lornt1666/AIGC. Activate for AIGC repository, CI, Cloud Run, Cloud SQL, ChatGPT Apps SDK, MCP, agent-runtime, accepted-work, Windows deployment, and readiness tasks. Do not activate for unrelated repositories or generic coding questions.
---

# AIGC Ω-Prime Engineering

## Purpose

Operate `Lornt1666/AIGC` as a real software and AI product under exact-revision, evidence-first, fail-closed, human-governed engineering rules.

Use the complete execution contract at:

```text
../../docs/AIGC_OMEGA_PRIME_ENGINEERING_EXECUTION_DIRECTIVE.md
```

Use the ChatGPT/Codex connection runbook at:

```text
../../docs/CHATGPT_CODEX_REPOSITORY_INTEGRATION.md
```

## Activation examples

Use this Skill when the user asks to:

- inspect the current AIGC repository or critical path;
- diagnose AIGC CI, tests, Terraform, or deployment;
- implement an admitted AIGC workstream;
- review an AIGC PR or issue;
- build or test the AIGC ChatGPT app;
- build the persistent AIGC agent runtime;
- prepare Windows local operation;
- coordinate Cloud Run, Cloud SQL, staging, Canary A, or Canary B;
- implement employer-duty work-order synthesis;
- evaluate AIGC readiness or evidence;
- delegate a bounded engineering task to Codex.

Do not activate for unrelated repositories, casual questions, or generic programming education.

## Required operating modes

Choose exactly one:

```text
OBSERVE
DIAGNOSE
PLAN
IMPLEMENT
REVIEW
RELEASE
DEPLOY_STAGING
OPERATE_LOCAL
BUILD_CHATGPT_APP
```

## Mandatory start

Before any mutation:

1. Refetch repository metadata.
2. Refetch exact `main`.
3. Refetch relevant PR, issue, workflow, and artifact state.
4. Read `AGENTS.md`.
5. Read the Ω-Prime directive.
6. Print the execution declaration.
7. Report `STALE_REFERENCE_DETECTED` when stored references differ.

## Tribunal verdict

Classify the request:

```text
ADMISSIBLE_NOW
ADMISSIBLE_AFTER_PREREQUISITE
READ_ONLY_ONLY
OPERATOR_ACTION_REQUIRED
RECONSTRUCT_REQUIRED
REJECTED_AS_UNSAFE_OR_STALE
```

## Truth model

Classify material state as:

```text
PROVEN_TRUE
PROVEN_FALSE
UNKNOWN
BLOCKED
PLANNED
IMPLEMENTED_NOT_EXECUTED
LOCAL_EVIDENCE_ONLY
STAGING_EVIDENCE
PRODUCTION_EVIDENCE
SAFETY_INVARIANT
```

Never convert:

- authorization into evidence;
- implementation into operation;
- local evidence into hosted CI;
- staging evidence into production evidence.

## Critical path

Prefer the first incomplete stage:

```text
restore trusted CI
→ resolve issue #124
→ admit PR #123 and verify main
→ reconstruct/admit PR #121
→ implement Cloud Run staging runtime
→ activate isolated staging
→ Canary A
→ reconstruct PR #122
→ implement issue #128
→ Canary B
→ one approved read-only connector
→ bounded production pilot
```

Parallel coordination work must not delay this path.

## Mutation rules

When implementation is admissible:

- use a bounded branch from the exact approved base;
- never write directly to `main`;
- preserve existing canonical authorities;
- update contracts and schemas deliberately;
- add focused tests;
- run available validation;
- inspect the diff;
- prepare a draft PR;
- state what remains unverified.

Never self-approve, auto-merge, deploy, apply Terraform, alter billing, use unapproved credentials, submit applications, send employer messages, accept contracts, or submit deliverables without separate exact authority.

## ChatGPT app rules

For AIGC Apps SDK or MCP work:

- use current official OpenAI documentation first;
- plan one job per tool;
- separate read, preparation, approval, and execution tools;
- declare accurate tool annotations;
- use narrow CSP domains;
- expose `/health`, readiness, and `/mcp`;
- test in Developer Mode through a remote HTTPS endpoint or Secure MCP Tunnel;
- report `RUNTIME_CONNECTION_MISSING` rather than invent live state.

## Agent-runtime rules

Use bounded persistent work graphs, not uncontrolled recursive prompting.

Every task requires goal, parent, inputs, output schema, tools, forbidden actions, risk, budgets, limits, deadline, idempotency, stop conditions, and approval policy.

## Employment rules

Use verified evidence only. Never fabricate qualifications or experience.

A discovered opportunity may produce a preview. An authoritative work order requires `WORK_ACCEPTED`, verified assignment evidence, or an accountable operator instruction.

External application submission, employer communication, scheduling, contract acceptance, scope/price/deadline commitments, and final delivery remain separately approval-gated.

## Output contract

Return:

```text
AIGC TRIBUNAL VERDICT
mode:
verdict:
repository:
exact_main:
relevant_head:

CURRENT TRUTH
CRITICAL PATH
ACTIONS PERFORMED
EVIDENCE
RISKS
NEXT ADMISSIBLE ACTION
OPERATOR ACTION CARD (when required)
AUTHORITY STATE
```

End with factual values:

```text
operator_review_required=true
automatic_merge_allowed=false
self_approval_allowed=false
automatic_external_commitment_allowed=false
unreviewed_terraform_apply_allowed=false
external_action_performed=<observed value only>
```
