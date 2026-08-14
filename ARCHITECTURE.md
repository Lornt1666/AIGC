# AIGC Architecture

## Architectural Authority

Justice Gray Maciocha is the accountable human operator and final source of consequential authority.

Omega-X is AIGC's constitutional supervisor and evolution governor. It may evaluate, coordinate, route, record, recommend, and propose bounded changes. It may not independently grant itself authority, bypass approval gates, activate infrastructure, use secrets, perform consequential external actions, alter accepted audit history, or represent generated capability as a legal credential.

## Operational Identity

AIGC is an autonomous career, occupation, and discipline worker. Its persistent identity is occupational rather than software-specific: it discovers opportunities, qualifies work, operates inside admitted disciplines, selects governed methods, executes bounded commissions, verifies outcomes, maintains evidence-backed professional history, and proposes continuing learning.

Auto-design, CHCM, Alpha Plan, coordination engineering, multi-agent execution, and software generation are governed methods available to the worker. They are not AIGC's identity, authority source, credential source, or completion authority.

Normative occupational architecture: [AIGC Occupational Autonomy Architecture v2](docs/architecture/AIGC_OCCUPATIONAL_AUTONOMY_V2.md).

Machine-readable contract: [`schemas/aigc_occupational_control_plane.schema.json`](schemas/aigc_occupational_control_plane.schema.json).

## Authority Precedence

Lower layers may refine work but may never override a higher layer:

```text
CareerConstitution
  > CareerMandate
  > WorkCommission
  > OutcomeContract
  > MethodGenome / TaskGraph
  > Attempt Instructions
  > Model Output
```

## Six-Plane Architecture

AIGC is divided into six planes with explicit ownership boundaries.

### 1. Governance Plane

**Owns:**

- Omega-X constitutional supervision
- Policies, constitutions, contracts, schemas, and validators
- Authorization and approval gates
- Emergency stop and default-deny controls
- Readiness rules and release decisions
- Evolution-patch governance
- Maximum occupational authority ceiling

**Does not own:**

- Transactional Quest state
- Provider execution
- Secret values
- External communications or delivery
- Fabrication of professional credentials or work evidence

### 2. Occupational Control Plane

**Owns:**

- `CareerConstitution`
- `OccupationProfile` and `DisciplineProfile`
- `CareerMandate`
- `WorkCommission` and `OutcomeContract`
- `CompetencyGraph`
- `AuthorityEnvelope`
- Stakeholder and professional-ethics context
- Evidence-backed `WorkPortfolio`
- Opportunity acceptance policy
- Continuing-learning proposals

**May autonomously:**

- Discover and normalize opportunities through admitted read-only channels
- Qualify opportunities against current mandate and competence
- Accept work only when the complete requested effect is inside the current autonomous authority envelope
- Select and evaluate bounded methods
- Execute admitted low-risk internal work
- Verify outcomes through discipline-appropriate evaluators
- Record verified portfolio evidence
- Propose learning and method improvements

**May not autonomously:**

- Invent licenses, credentials, employment status, contractual authority, payment authority, secret access, production authority, or identity claims
- Expand its own authority ceiling
- Weaken evidence or evaluator requirements
- Convert a proposed capability into verified competence without evidence

Target occupational maturity is O4/O5: autonomous career operator / governed multi-discipline professional, while consequential authority remains externally bounded.

### 3. Phase / Method Plane

**Owns:**

- Numbered AIGC phases
- Research, assessment, drafting, compliance, quality, and evolution processes
- Long-running or batch-oriented internal workflows
- Internal reports and proposed artifacts
- Coordination Engineering and Alpha Plan methods
- CHCM and bounded autodesign
- MethodGenome candidate generation and comparison
- Multi-agent planning and bounded specialist work

The Phase / Method Plane answers **how** admitted work should be performed. It cannot decide that AIGC possesses an occupation, credential, authority, or completed outcome merely because a method generated one.

Software-oriented autodesign is generalized to `MethodGenome` so the same governed search/evaluation mechanism can support software/API work, CAD/building design, automation, DevSecOps, technical documentation, research, construction planning, and other admitted disciplines.

### 4. Quest / Work Plane

**Owns:**

- FastAPI operator application
- Candidate and Quest persistence
- Transactional Quest / WorkCommission lifecycle
- Work-acceptance authorization
- Review Evidence Packets
- Accountable human judgment
- Delivery-state and rework decisions

A Quest is the runtime representation of a bounded WorkCommission; it is not the occupational identity itself.

Canonical occupational lifecycle:

```text
OBSERVE
-> DISCOVER_OPPORTUNITY
-> QUALIFY
-> ACCEPT_WITHIN_MANDATE | APPROVAL_REQUIRED
-> CONTRACT
-> DESIGN_METHOD
-> EXECUTE
-> VERIFY
-> DELIVER
-> RECORD_EVIDENCE
-> UPDATE_PORTFOLIO
-> REFLECT
-> PROPOSE_LEARNING
-> READY
```

Cross-cutting interruption states:

```text
BLOCKED
NO_PROGRESS
APPROVAL_REQUIRED
ESCALATED
CANCELLED
FAILED
REWORK_REQUIRED
ROLLED_BACK
```

`DELIVER` does not imply permission to perform a consequential external action. Delivery must remain separately authorized when its effect leaves the approved autonomous envelope.

Legacy Quest lifecycle states remain valid as compatibility states during migration, but they must map to this occupational lifecycle rather than define career identity.

### 5. Infrastructure Plane

**Owns:**

- Isolated Google Cloud staging and production environments
- Workload Identity Federation
- Cloud Run
- Cloud SQL for PostgreSQL
- Google Secret Manager
- Google Cloud Identity Platform
- Networking, managed TLS, monitoring, backup, and recovery
- Terraform planning and separately authorized application

Target geography:

- Toronto primary: `northamerica-northeast2`
- Montréal recovery: `northamerica-northeast1`

The Infrastructure Plane may act only through exact-revision, time-bounded, phase-specific authorization.

### 6. Evidence Plane

**Owns:**

- Structural repository evidence
- Operational staging evidence
- Authorization and execution receipts
- Test and CI evidence
- Artifact digests and provenance
- Deployment and rollback receipts
- Recovery-drill evidence
- Production-readiness reports
- Attempt-bound competency evidence
- Delivery receipts and portfolio provenance
- Current external-state verification when required

The Evidence Plane records truth. It does not grant authority, silently change lifecycle state, manufacture experience, or certify a legal credential without external proof.

## Plane Relationships

```text
Accountable Operator
        |
        v
Governance Plane
        |
        v
Occupational Control Plane
   career / discipline / mandate
        |
        +--------------------------+
        v                          v
Phase / Method Plane         Quest / Work Plane
how work is designed         what work is active
        |                          |
        +------- artifacts --------+
                                   v
                         Infrastructure Plane
                                   |
                                   v
                             Evidence Plane
                                   |
                      verified truth / learning
                                   |
                                   +----> Governance + Occupational Control
```

Omega-X may supervise all planes. Multi-agent execution must preserve one authoritative writer per mutable artifact set and independent verification for high-risk outcomes.

## Work Acceptance Invariant

AIGC may auto-accept work only when:

```text
AUTO_ACCEPT :=
    career_mandate_is_current
    AND discipline_is_admitted
    AND competency_gate_passes
    AND requested_outcome_is_testable
    AND authority_envelope_covers_all_planned_effects
    AND risk_tier_is_within_autonomous_ceiling
    AND financial_and_time_budgets_are_within_limits
    AND no_credential_or_license_claim_is_invented
    AND no_required_human_approval_is_missing
```

Otherwise the work enters `APPROVAL_REQUIRED`, `BLOCKED`, or `DECLINED`.

## Work Completion Invariant

```text
WORK_COMPLETE :=
    career_mandate_is_current
    AND outcome_contract_is_current
    AND required_artifacts_exist
    AND all_hard_gates_pass
    AND evidence_is_attempt_bound
    AND independent_verification_passes
    AND required_delivery_receipt_exists
    AND required_approval_is_valid
    AND external_state_is_current_when_applicable
    AND rollback_or_recovery_requirements_pass_when_applicable
    AND no_unresolved_blocking_finding_exists
```

Model self-report is never sufficient evidence of completion.

## Semantic No-Progress Invariant

Execution must stop rather than loop when a configured no-progress rule fires. Default policy is no more than three plan/execute/review cycles per task and no more than two retries for an identical failure class unless the WorkCommission explicitly authorizes a different bounded budget.

A stopped attempt emits a blocker/evidence receipt and transitions to `NO_PROGRESS`, `BLOCKED`, or `ESCALATED` instead of retry-until-green.

## Architectural Invariants

1. Authorization is not evidence of execution.
2. Structural evidence is not operational proof.
3. No plane may expand its own authority.
4. No consequential external action occurs without authority covering the exact effect.
5. All consequential transitions are exact-revision and evidence bound.
6. Secret values never enter repository files, prompts, logs, memory, or receipts.
7. Production readiness is calculated from canonical evidence, never manually asserted.
8. Occupational identity outranks Quest, Phase, CHCM, autodesign, task, attempt, and model instructions.
9. A generated skill claim is not a verified competency; a verified competency is not a legal credential unless separately proven.
10. Portfolio experience requires attempt-bound delivery evidence.
11. Capability may grow autonomously; authority may not.
12. Auto-design is finite per execution and remains proposal-first until verification/admission.
13. One authoritative writer owns a mutable worktree/artifact set at a time; independent evaluators may read in parallel.
14. High-risk outcomes cannot be independently verified solely by the same execution lineage that authored them.
15. Repeated no-progress cycles terminate rather than consume unbounded time, tools, tokens, or money.
