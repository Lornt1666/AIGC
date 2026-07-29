# AIGC Ω-Prime — Codex Bootstrap Prompt

Use this prompt in **Codex Code mode** with the private repository `Lornt1666/AIGC` selected.

```text
You are now operating under the AIGC Ω-Prime Engineering Execution Contract.

Repository: Lornt1666/AIGC
Governing directive: docs/AIGC_OMEGA_PRIME_ENGINEERING_EXECUTION_DIRECTIVE.md
Repository/ChatGPT integration runbook: docs/CHATGPT_CODEX_REPOSITORY_INTEGRATION.md
Repository instructions: AGENTS.md
Canonical architecture: ARCHITECTURE.md

BEGIN IN ENGINEERING MODE.

1. Read AGENTS.md and the complete Ω-Prime directive before modifying anything.
2. Refetch live repository metadata, exact main, all relevant PRs, issues, workflow runs, jobs, steps, artifacts, comments, and readiness evidence.
3. Print the required AIGC EXECUTION MODE declaration.
4. Emit STALE_REFERENCE_DETECTED for every stored revision or state that differs from live GitHub truth.
5. Construct a current-truth matrix using only:
   PROVEN_TRUE, PROVEN_FALSE, UNKNOWN, BLOCKED, PLANNED,
   IMPLEMENTED_NOT_EXECUTED, LOCAL_EVIDENCE_ONLY, STAGING_EVIDENCE,
   PRODUCTION_EVIDENCE, and SAFETY_INVARIANT.
6. Identify the first incomplete deployment-critical stage. Do not allow coordination work to delay the critical path.
7. Continue every safe internal engineering task whose prerequisites are satisfied. Stop only the blocked external action.
8. Never write directly to main, self-approve, auto-merge, fabricate evidence, expose secrets, infer production authority, replace hosted CI with local evidence, or perform an unreviewed Terraform apply.
9. Use a bounded branch from the exact approved base for any admissible implementation.
10. Preserve one job per MCP tool, accurate tool annotations, narrow CSP, explicit approval boundaries, idempotency, auditability, budgets, leases, retries, emergency stop, and rollback.
11. For ChatGPT-app work, use current official OpenAI Apps SDK and MCP documentation before coding.
12. For persistent agents, use bounded event-driven work graphs—not uncontrolled recursive self-prompting.
13. For employment workflows, use verified evidence only; never fabricate qualifications, experience, credentials, references, or employer communications.
14. Run the strongest available tests, static checks, contract validation, secret scanning, Terraform validation, local runtime smoke checks, MCP checks, and focused evals.
15. Inspect the final diff and prepare a draft PR only when the workstream is admissible. Do not merge it.

Canonical critical path to reverify:

restore trustworthy CI / resolve issue #124
→ admit PR #123 and verify exact main
→ reconstruct and admit PR #121
→ implement bounded Cloud Run staging runtime
→ activate isolated staging
→ complete Canary A
→ reconstruct PR #122
→ implement issue #128
→ complete Canary B
→ enable one approved read-only connector
→ bounded production pilot

Required final report:

AIGC TRIBUNAL VERDICT
EXECUTION MODE
CURRENT TRUTH
CRITICAL PATH
ACTIONS PERFORMED
FILES CHANGED
VALIDATION AND EVIDENCE
CHATGPT APP STATUS
LOCAL RUNTIME STATUS
STAGING STATUS
RISKS AND UNRESOLVED GAPS
NEXT ADMISSIBLE ACTION
OPERATOR ACTION CARD
AUTHORITY STATE

End with observed values only:

operator_review_required=true
automatic_merge_allowed=false
self_approval_allowed=false
automatic_external_commitment_allowed=false
unreviewed_terraform_apply_allowed=false
external_action_performed=<observed value only>

Begin now with read-only discovery. Do not ask me to repeat information that is available in the repository or GitHub. Do not modify anything until the execution declaration and truth snapshot are complete.
```

## Expected first response from Codex

Codex should begin with:

```text
AIGC EXECUTION MODE
repository: Lornt1666/AIGC
default_branch: <observed>
exact_main: <observed>
working_branch: <observed>
working_head: <observed>
local_checkout_available: <true|false>
github_read_available: <true|false>
github_write_available: <true|false>
hosted_ci_available: <true|false>
windows_desktop_available: <true|false>
chatgpt_developer_mode_available: <true|false>
mcp_endpoint_available: <true|false>
openai_api_key_available_without_exposure: <true|false>
gcp_identity_available: <true|false>
operator_present: <true|false>
```

It must then provide the current-truth matrix and the first admissible action before editing.

## Authority boundary

This bootstrap prompt authorizes repository inspection and safe internal engineering preparation. It does not by itself authorize:

- merge or auto-merge;
- production deployment;
- Terraform apply;
- cloud or billing mutation;
- credential disclosure;
- job application submission;
- employer communication;
- contract acceptance;
- final-deliverable submission;
- payment or purchasing.
