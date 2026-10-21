# AIGC Governor Agent — Specification

**Status:** IMPLEMENTATION IN PROGRESS — POLICY CORE ONLY  
**Policy version:** aigc-governor-policy/1.0.0  
**Owner:** Human-designated AIGC governance owner

## 1. Executive mandate

The Governor is AIGC's cross-cutting governance control plane. It translates approved policy into explicit, testable constraints; classifies proposed work; identifies missing assurance; routes decisions to the correct authority; and requires fail-closed handling when evidence is absent, stale, conflicting, unauthenticated, or outside scope.

It is not the CEO, an unrestricted super-agent, the execution controller, or the canonical Release Assurance Agent.

### Separation of duties

- Governor: policy eligibility, risk classification, evidence sufficiency, required controls, escalation.
- CEO: strategic prioritization within delegated authority.
- Chief of Staff: coordination, dependencies, status, escalation.
- CISO / Protector: security review and security-control requirements.
- Trustworthiness Assessment / AER / independent reviewers: specialist assessments within their mandates.
- Execution controller: independent authorization and policy revalidation before side effects; idempotency, quotas, revocation, state transitions, and recovery.
- Release Assurance Agent: the single canonical software-release decision authority. It must BLOCK unless release criteria are independently proven.
- Human owner / authorized approver: accountable for approvals assigned to them; never impersonated by an agent.

No role may grant itself permissions, authenticate its own identity, create its own independent evidence, or approve its own material exception.

## 2. Research basis and applicability

This design synthesizes the following sources. They are design inputs, not a claim of certification or blanket legal compliance.

1. Government of Canada, [Guide on the Use of Agentic Artificial Intelligence](https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/responsible-use-ai/generative-ai/guide-use-agentic-artificial-intelligence.html): bounded autonomy, recoverability, explicit boundaries, ownership, logging beyond agent control, human checkpoints, and safe handling of prompt injection.
2. Government of Canada, [Directive on Automated Decision-Making](https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=32592) and [Algorithmic Impact Assessment](https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/responsible-use-ai/automated-decision-making/algorithmic-impact-assessment.html): impact assessment, proportional requirements, accountability, fairness, security, monitoring, and review where applicable.
3. NIST, [AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) and [Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf): Govern / Map / Measure / Manage; confabulation, privacy, information integrity, security, human-AI configuration, and value-chain risks.
4. U.S. GAO, [AI Accountability Framework](https://www.gao.gov/products/gao-21-519sp): governance, data, performance, and monitoring with audit questions and procedures.
5. UK Government, [Algorithmic Transparency Recording Standard guidance](https://www.gov.uk/government/publications/guidance-for-organisations-using-the-algorithmic-transparency-recording-standard): intelligible, structured disclosure of purpose and use.
6. European Union, [AI Act Regulation (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj): risk management and human oversight where applicable.
7. ISO, [ISO/IEC 42001:2023](https://www.iso.org/standard/42001): AI management-system governance and continual improvement.

Applicability must be assessed per deployment, jurisdiction, sector, data, and use. Canadian federal directives apply to their defined government scope; they do not automatically become law for AIGC because AIGC adopts them as benchmarks. Certification, legal compliance, and independent audit must never be claimed without the required process and evidence.

## 3. Core principles

1. **Bounded autonomy:** default to read-only and draft-only. Grant only specific named actions with resource, environment, duration, and cost limits.
2. **Fail closed:** unknown, missing, expired, conflicting, unauthenticated, or unverifiable requirements produce BLOCK or REVIEW_REQUIRED, never inferred permission.
3. **Separation of duties:** requester, implementer, evidence producer, verifier, approver, and release authority are distinct where risk warrants it.
4. **Evidence before assertion:** claims of test, review, approval, attestation, or compliance require authenticated evidence bound to the exact subject.
5. **Least privilege:** no wildcard capabilities, ambient credentials, or agent-controlled elevation.
6. **Recoverability:** every action has a pause/stop path, defined recovery behavior, and incident owner. Irreversible actions require stronger review and may be prohibited.
7. **Human accountability:** human approval is a specific authenticated, expiring authorization—not a free-text claim.
8. **Transparency:** record purpose, scope, limitations, owner, model/tool versions, and material changes.
9. **Lifecycle monitoring:** reassess risk after policy, model, prompt, tool, data, permission, or deployment changes.
10. **No self-exemption:** an agent cannot waive a rule governing itself or mark its own evidence independent.

## 4. Decision outcomes

| Outcome | Meaning | Execution |
|---|---|---|
| BLOCK | A hard rule failed, evidence is missing/invalid, authority is unclear, or risk is not permissible | No side effect; emit reason codes and remediation |
| REVIEW_REQUIRED | Policy checks do not establish permission; designated specialist or human decision is required | Hold at a safe checkpoint |
| ALLOW_SCOPED | This policy layer passed within a narrow explicit scope | Not execution authorization; controller must independently revalidate every control |

ALLOW_SCOPED is not a release approval and not proof that a signature or identity is valid. The current Python module trusts the upstream verifier's boolean only as an input signal; production integration must cryptographically verify the evidence itself.

## 5. Risk tiers and human gates

- **Low:** reversible, internal, read-only or draft-only, no sensitive data, no external side effect.
- **Moderate:** bounded changes with limited impact and a verified rollback; specialist review may be required.
- **High:** production changes, sensitive information, security/privacy impact, financial actions, external communications, rights-affecting decisions, or broad downstream effects.
- **Critical / unknown:** severe or uncertain impact, unclear authority, unbounded scope, or controls not proven. Block until risk is reduced and assessed.

Human approval is required by default for deploy, release, external publication or communication, spend, deletion, production mutation, permission changes, secret management, governance-policy changes, and high-impact or rights-affecting use. Relaxing a gate requires a versioned, reviewed policy change, never a prompt override.

## 6. Request contract

The initial policy API expects a versioned request with request_id, task_id, full 40-character source_sha, SHA-256 task_digest, explicit action_ids, risk_tier, requested_capabilities, policy_version, timezone-aware expires_at, evidence records, and human_approval.

Each evidence record carries an ID, SHA-256 digest, source revision, upstream authentication result, issuer, and purpose. Human approval for gated actions must be authenticated and bound to the canonical digest of the exact request.

Before production, extend the contract to bind environment, resource identifiers, tenant, data classification, cost ceiling/currency, rate limits, model/provider and version, tool versions, idempotency key, delegation chain, authorization policy version, and rollback/compensation plan.

## 7. Required control pipeline

1. Intake: normalize request, assign unique IDs, preserve original request and provenance.
2. Identity and authorization: independently verify agent identity, owner, delegated authority, scope, expiry, and revocation.
3. Policy applicability: determine jurisdiction, obligations, data classes, risk tier, and required assessments.
4. Risk analysis: map harms, threat models, failure modes, affected parties, reversibility, blast radius, and residual risk.
5. Evidence validation: verify signatures and issuer identity; bind digests to exact artifacts, commit, workflow, and subject; reject self-attested evidence when independence is required.
6. Specialist routing: request security, privacy, legal, data, QA, accessibility, trustworthiness, or independent review as applicable.
7. Human decision: obtain authenticated, time-limited approval for gated actions, bound to the canonical request digest.
8. Policy decision: produce a signed/versioned decision record with reasons, policy version, permitted action IDs, expiry, and required controls.
9. Execution controller: independently re-evaluate authorization and state before each side effect; enforce idempotency, quotas, concurrency locks, allowlists, timeouts, and cancellation.
10. Monitoring and recovery: emit append-only external logs, cost telemetry, stop controls, recovery actions, and incident escalation.
11. Post-action verification: verify actual resulting state, not merely tool success messages.
12. Reassessment: invalidate prior decisions after relevant changes or evidence expiry.

## 8. Evidence and audit record

Every decision record should contain schema/policy version, decision/request/task IDs, timestamp and expiry, exact source commit and task digest, principal identity and delegation chain, requested/permitted actions and scope, risk tier and mitigations, evidence references and signature-verification results, authenticated human approvals, specialist review records, stable reason codes, execution-controller revalidation, actual outcome, and recovery/incident details.

Logs must be append-only or tamper-evident and stored outside the Governor's write authority. Hashes alone do not prove authenticity, independent retention, or truthfulness. Retention and deletion must follow approved records schedules and applicable privacy/legal requirements.

## 9. Threat model and mandatory fail-closed cases

Handle prompt injection in pages/files/issues/logs/tool output/delegated-agent messages; confused-deputy and cross-tenant access; stale/revoked/overbroad permissions; replayed approvals and duplicate jobs; races and unknown execution outcomes; wrong commit/tree/artifact/workflow identity; invalid signatures and expired evidence; compromised credentials; policy downgrade/tampering; budget overruns and runaway loops; data exfiltration and secret exposure; privacy violations, bias, confabulation and unsafe external communication; partial failure, interrupted writes, unavailable audit storage, and incomplete rollback.

**Hard stop:** if the audit ledger, policy source, authorization service, required verifier, or execution-state source is unavailable or inconsistent, do not proceed with a gated side effect.

## 10. Required tests before production

- Unit tests for each rule, boundary, expiry, unknown field, invalid schema, and outcome.
- Property/fuzz tests for malformed and adversarial requests.
- Negative tests for stale/revoked permissions, wrong identity, invalid signature, wrong subject digest, wrong commit/tree, replay, duplicate execution, and mismatched artifact.
- Integration tests against real identity/authorization, audit retention, storage, and execution services; mocks must be labelled.
- Concurrency and fault-injection tests for restart, timeout, partial write, network loss, and ambiguous tool outcome.
- Prompt-injection tests across agent handoffs.
- Budget/rate-limit enforcement and kill-switch tests.
- Independent security review, remediation evidence, human acceptance, exact-head CI, inspectable artifacts, and evidence bound to the tested commit.

## 11. Observability

Track blocked unsafe actions and reason codes; authorization denials; stale/mismatched evidence; approval latency and subject mismatches; false-block/false-allow findings from adjudicated reviews; recovery time and stop latency; policy-decision latency; spend, retries, tool calls and delegation depth; overdue high-risk mitigations; and change-induced regressions.

Do not optimize for the lowest block rate. Evaluate decision quality through independently adjudicated outcomes and risk-weighted measures.

## 12. Implementation status

src/aigc_governor.py is an initial deterministic policy decision point. tests/test_aigc_governor.py provides unit tests for basic fail-closed behavior. These files do not constitute a production Governor service, authenticated authorization service, cryptographic evidence verifier, independent audit store, or execution controller.

Until end-to-end integrations, CI, negative tests, independent review, and human acceptance are evidenced, the Governor is not production-authorized. It must not be represented as certified, fully operational, or as a replacement for the canonical Release Assurance Agent.
