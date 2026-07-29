# AIGC ChatGPT Operational Acceptance Standard

## Purpose

This standard defines what `100/100` means for AIGC as a completely functional application inside ChatGPT. It prevents score inflation by separating implementation, local verification, hosted CI, staging evidence, production acceptance, and immutable per-action evidence.

## Three state classes

### Evidence truths that may become true

```text
hosted_ci_evidence_present
staging_operational_evidence_present
production_evidence_present
chatgpt_developer_mode_connected
chatgpt_end_to_end_acceptance_passed
external_action_receipt_present
```

### Per-action fact

`external_action_performed` is false by default and becomes true only inside the immutable receipt for the exact approved action that actually occurred. It is not a reusable permission and does not authorize another action.

### Permanent safety invariant

```text
hosted_ci_replacement_allowed=false
```

Local tests, Codex runs, screenshots, and operator assertions may supplement diagnosis. They can never replace the required hosted CI run.

## Ten-category score

Each category carries ten points:

1. Apps SDK and MCP contract.
2. ChatGPT widget and Approval Inbox.
3. Persistent control plane.
4. Governed agent orchestration.
5. Exact-approved external action.
6. Identity, tenant isolation, and secrets.
7. Hosted CI and supply chain.
8. Hosting, observability, and recovery.
9. Employment and accepted-work execution.
10. ChatGPT acceptance and operations.

Evidence levels:

```text
DEFINED=25%
IMPLEMENTED_LOCAL=50%
VERIFIED_LOCAL=65%
HOSTED_CI_VERIFIED=75%
STAGING_VERIFIED=90%
PRODUCTION_ACCEPTED=100%
```

A numerical score of 100 is still insufficient unless every required evidence truth is true and every safety invariant remains preserved.

## Required operational chain

```text
local contract and tests
→ stable HTTPS MCP endpoint
→ ChatGPT Developer Mode connection
→ widget and tool acceptance tests
→ authenticated operator and tenant isolation
→ hosted CI with exact-revision artifacts
→ isolated staging deployment
→ Canary A platform proof
→ Canary B accepted-work proof
→ first read-only connector
→ one exact-approved external action
→ immutable external-action receipt
→ rollback and backup/restore evidence
→ accountable operator acceptance
```

## 100/100 release rule

`release_100_permitted=true` only when:

1. all ten categories are `PRODUCTION_ACCEPTED`;
2. every evidence truth is true;
3. all safety invariants remain false;
4. accountable operator review remains required and has accepted the evidence.

A high score cannot grant authority or synthesize missing evidence.
