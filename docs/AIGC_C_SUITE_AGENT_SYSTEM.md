# AIGC C-Suite Agent System — MVP++ Architecture

**Status:** Proposed implementation contract. Agents are decision-support and workflow-control software, not legally appointed corporate officers. **No agent can grant itself authority, approve its own work, or bypass the canonical Release Assurance Agent.**

## Design principles

1. One task envelope and one version-bound evidence envelope across the crew.
2. Proposals are separate from execution. Only the execution controller can invoke side-effecting tools, and it independently validates the CEO's scoped approval, policy, risk decision, expiry, idempotency key, and exact task digest.
3. Risk, legal, security, privacy, finance, and assurance have veto/block powers inside policy. They cannot approve the work they produce.
4. Human-only gates remain for release authorization, real spending, contracts, M&A, employment actions, destructive changes, production credentials, and regulated filings unless a separately approved policy explicitly permits a narrower action.
5. Missing, stale, conflicting, unsigned, wrong-subject, or indeterminate evidence means BLOCK.
6. Do not store secrets in task/evidence records. Use managed identities and secret managers.
7. All agents are deterministic policy wrappers around specialist tools/models; model output is untrusted input and must validate against strict schemas.

## Shared task contract

Every specialist receives:
```json
{
  "schema_version": "1.0",
  "task_id": "uuid",
  "parent_task_id": null,
  "objective": "string",
  "scope": {"allowed_actions": [], "denied_actions": []},
  "source_revision": "full commit SHA or null",
  "input_refs": [{"uri": "opaque reference", "sha256": "64 lowercase hex"}],
  "budget": {"max_usd": 0, "max_steps": 20, "deadline_utc": "RFC3339"},
  "risk_class": "low|medium|high|critical",
  "approval_ref": null,
  "idempotency_key": "stable opaque key"
}
```

Every agent returns:
```json
{
  "schema_version": "1.0",
  "agent_id": "stable identifier",
  "task_id": "uuid",
  "status": "PASS|WARN|BLOCK|ERROR",
  "claims": [{"kind":"FACT|MEASUREMENT|CALCULATION|INFERENCE|HYPOTHESIS|ASSUMPTION","text":"string","source_refs":[]}],
  "findings": [{"severity":"info|low|medium|high|critical","code":"stable-code","message":"string","evidence_refs":[]}],
  "artifacts": [{"uri":"opaque reference","sha256":"64 lowercase hex","media_type":"string"}],
  "recommendation": "string",
  "requires_human": true,
  "created_at_utc": "RFC3339",
  "input_digest_sha256": "64 lowercase hex",
  "agent_build_digest_sha256": "64 lowercase hex",
  "signature_ref": null
}
```
No agent may claim PASS if its required inputs or checks are missing. All outputs require schema validation, provenance binding, size limits, and escaped rendering.

## Roster and mandate

| ID | Executive role | Primary outputs | Gate / authority |
|---|---|---|---|
| CEO | Chief Executive / Action Approval Agent | Prioritized decisions, scoped approval proposals, escalation | Approves only actions permitted by policy; never bypasses mandatory human gates or Release Assurance |
| COS | Chief of Staff | Dependency DAG, ordered queue, deadline and handoff tracking | Schedules; cannot elevate permissions |
| CIO-CAP | Chief Investment & Capital Allocation | Scenario models, hurdle-rate and capital-allocation recommendations | Recommendation only; human approval for actual capital movement |
| CORPDEV | Corporate Development / M&A | Target scorecards, DCF/LBO scenarios, diligence checklist | No contact, offer, trade, or deal execution without human approval |
| SYNERGY | Chief Synergy & Integration | Capability map, overlap analysis, integration roadmap | No destructive migration or staff/vendor changes |
| CRO | Chief Risk Officer | Risk register, stress tests, contagion and FMEA report | Can BLOCK high-risk work; cannot waive policy |
| CPO | Chief Procurement Officer | Supplier scorecards, RFP drafts, spend and concentration analysis | No binding PO, contract, auction bid, or purchase without human authorization |
| CLO | Chief Legal Officer / Corporate Secretary | Issue spotting, obligation matrix, draft resolutions/minutes | Not legal advice; qualified counsel validates; no filings/votes by default |
| OPCO | Operating Partner / Subsidiary Portfolio Chair | KPI variance, operating review, intervention proposals | Recommendations only for personnel and subsidiary control actions |
| CTO | Group Technology & Digital Architect | Reference architecture, ADRs, IAM/API/platform standards | No production infrastructure changes without execution-controller policy and approval |
| CISO | Chief Information Security Officer / Protector | Threat model, security posture, control tests, incident recommendations | Can veto unsafe execution; cannot self-certify |
| TRUST | Trustworthiness & Evidence Assessor | Source quality, evidence freshness, provenance chain, contradiction report | Independent evaluation; never generates the evidence it verifies |
| RED | Red Team | Adversarial test plans, exploitability findings, abuse cases | Synthetic/sandbox scope only unless separately authorized |
| BLUE | Blue Team | Defensive controls, detection and containment recommendations | No unapproved production changes |
| GREEN | Green Team / Reliability & Recovery | Resilience, repair plans, rollback and recovery evidence | Changes require tests and normal authorization |
| AER | Architecture & Engineering Review | Architecture compliance, dependency review, NFR traceability | Review finding only; independent of implementation owner |
| DOC | MVP++ Documentation Architect | Traceable draft documentation packs, document manifest and hashes | Never infers approvals or release readiness |
| QA | Verification & Quality Engineering | Test matrix, exact-head test results, reproducibility report | Uses actual checker outputs; cannot fabricate test results |
| DATA | Data Governance & Analytics | Data lineage, metric quality, privacy/data retention inventory | No unauthorized data export or deletion |
| FIN | Finance & Cost Controller | Budget forecast, per-run spend guard, cost anomaly report | Hard budget stop; no payment execution |
| AUDIT | Internal Audit / Control Assurance | Control mapping, evidence sampling, segregation-of-duties findings | Independent assurance; cannot implement the controls it audits |
| COMMS | Communications & Stakeholder Reporting | Status reports and audience-specific summaries | No external publication or commitments without approval |
| PEOPLE | People & Succession Planning | Role/coverage map, capability gaps, succession scenarios | No employment decisions or personal-data processing without lawful basis and human review |
| SECRETARY | Board Governance & Corporate Secretariat | Decision log, meeting pack, quorum/approval checklist | No fabricated minutes, votes, signatures, or board authority |
| DISPATCH | Execution Controller | Policy-checked tool calls, idempotency, durable action receipts | Only component allowed to execute external side effects; independently rechecks approvals |
| RELEASE | Canonical Release Assurance | One signed decision receipt: PASS/BLOCK | Sole canonical software release decision authority; BLOCK unless every applicable criterion is proven |

## Deterministic order of operations

1. COS validates task schema, scope, budget, deadline, idempotency, and dependencies.
2. CTO/AER determine technical path and required checks; DOC drafts traceability and runbook.
3. Domain specialist proposes the work; claims cite source/evidence references.
4. RED/CISO/CRO run relevant adversarial, security, privacy, safety, and systemic-risk gates. Any critical finding blocks.
5. FIN checks the hard budget. CLO/SECRETARY flag legal and governance approval requirements.
6. QA runs the real checkers and binds outputs to exact source revision, tested tree, tool version, and run ID.
7. TRUST verifies source identity, signatures, subject digest, freshness, workflow identity, and contradictory/missing evidence.
8. AUDIT/AER independently review where required; neither reviews its own implementation.
9. CEO evaluates the proposal against policy and may approve only within its delegated authority. It cannot waive human gates, checker failures, or the canonical release authority.
10. DISPATCH revalidates the complete approval and evidence immediately before each action; records intent, result, idempotency key, and recovery state.
11. RELEASE independently evaluates authenticated evidence and returns PASS or BLOCK. Release still requires explicit authorized human acceptance when policy requires it.
12. COS reconciles all handoffs and issues a factual status report with outstanding blockers.

## State machine

`DRAFT -> VALIDATED -> PROPOSED -> SPECIALIST_REVIEW -> VERIFIED -> APPROVAL_PENDING -> APPROVED_SCOPED -> EXECUTING -> RECONCILING -> COMPLETE`

Any missing or conflicting evidence transitions to `BLOCKED`; runtime exceptions transition to `RECOVERY_REQUIRED`; expired approval transitions to `APPROVAL_PENDING`. No retry may repeat a non-idempotent side effect without reconciling the previous outcome first.

## CEO approval object

```json
{
  "schema_version": "1.0",
  "decision_id": "uuid",
  "task_id": "uuid",
  "task_digest_sha256": "64 lowercase hex",
  "source_revision": "full commit SHA",
  "action_class": "read|write|external_communication|spend|deploy|release|destructive",
  "allowed_action_ids": ["specific action identifiers"],
  "denied_action_ids": [],
  "max_usd": 0,
  "expires_at_utc": "RFC3339",
  "required_check_ids": [],
  "evidence_digests": [],
  "risk_decision": "PASS|BLOCK",
  "human_approval_ref": null,
  "decision": "APPROVE_SCOPED|BLOCK|ESCALATE",
  "rationale": "evidence-backed explanation",
  "signer_identity": "authenticated service identity",
  "signature_ref": null
}
```
Reject wildcards for consequential actions. Bind approvals to exact task digest, revision, action IDs, spend cap, evidence digests, and expiry. Any change invalidates the approval.

## Required production tests

- Strict schema, unknown field, type confusion, oversized payload, and malformed digest rejection.
- Spoofed CEO identity, altered task digest, expired approval, wrong revision, missing checker, conflicting decision, and replay rejection.
- Execution controller rejects an approval for any different action/subject; tool permissions prove least privilege.
- Duplicate delivery and concurrent worker idempotency; interrupted writes and process restart; reconcile unknown outcomes before retry.
- Signature/workflow identity/source revision/subject digest verification using real signed attestations and negative cases.
- Audit log tamper detection, durable evidence retention, access control, and recovery drill.
- Independent reviewer records findings against exact proposed commit; fixes trigger reruns.
- Release authority returns BLOCK until all required evidence is authenticated and every applicable criterion passes.

## Delivery boundary

This file is the role and protocol contract, not proof that all roles have executable implementations. A role is considered operational only after an implementation, strict schemas, least-privilege tool adapter, unit/integration/adversarial tests, authenticated evidence, observability, and independent review exist. Until then it is `SPECIFIED_NOT_OPERATIONAL`.
