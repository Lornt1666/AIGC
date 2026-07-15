# AIGC Architecture

## Architectural Authority

Justice Gray Maciocha is the accountable human operator and final source of consequential authority.

Omega-X is AIGC's constitutional supervisor and evolution governor. It may evaluate, coordinate, route, record, recommend, and propose bounded changes. It may not independently grant itself authority, bypass approval gates, activate infrastructure, use secrets, perform consequential external actions, or alter accepted audit history.

## Five-Plane Architecture

AIGC is divided into five planes with explicit ownership boundaries.

### 1. Governance Plane

**Owns:**

- Omega-X constitutional supervision
- Policies, constitutions, contracts, schemas, and validators
- Authorization and approval gates
- Emergency stop and default-deny controls
- Readiness rules and release decisions
- Evolution-patch governance

**Does not own:**

- Transactional Quest state
- Provider execution
- Secret values
- External communications or delivery

### 2. Phase / Batch Plane

**Owns:**

- Numbered AIGC phases
- Opportunity discovery and normalization
- Research, assessment, drafting, compliance, quality, and evolution processes
- Long-running or batch-oriented internal workflows
- Internal reports and proposed artifacts

**Does not own:**

- Canonical Quest lifecycle transitions
- Production identity
- Infrastructure mutation
- External-execution authority

### 3. Quest / Product Plane

**Owns:**

- FastAPI operator application
- Candidate and Quest persistence
- Transactional Quest lifecycle
- Work-acceptance authorization
- Review Evidence Packets
- Accountable human judgment
- `ACCEPTED_FOR_DELIVERY` and `REWORK_REQUIRED` decisions

Canonical lifecycle:

```text
DISCOVERED
-> QUALIFIED
-> PROPOSED
-> APPROVAL_REQUIRED
-> WORK_ACCEPTED
-> REVIEW_REQUIRED
-> ACCEPTED_FOR_DELIVERY | REWORK_REQUIRED
```

`ACCEPTED_FOR_DELIVERY` does not itself perform delivery.

### 4. Infrastructure Plane

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

### 5. Evidence Plane

**Owns:**

- Structural repository evidence
- Operational staging evidence
- Authorization and execution receipts
- Test and CI evidence
- Artifact digests and provenance
- Deployment and rollback receipts
- Recovery-drill evidence
- Production-readiness reports

The Evidence Plane records truth. It does not grant authority or silently change lifecycle state.

## Plane Relationships

The Phase Plane and Quest Plane are complementary rather than duplicative:

- **Phase / Batch Plane:** research, transformation, assessment, and orchestration
- **Quest / Product Plane:** canonical transactional business state

```text
Accountable Operator
        |
        v
Governance Plane
        | grants bounded authority
        +----------------------+
        v                      v
Phase / Batch Plane      Quest / Product Plane
        |                      |
        +---- artifacts -------+
                               v
                     Infrastructure Plane
                               |
                               v
                         Evidence Plane
                               |
                               +-- returns evidence to Governance
```

Omega-X may supervise both execution planes. Multi-agent Quest execution remains unavailable until QuestConductor is reconstructed on the current identity, authorization, persistence, and review architecture.

## Architectural Invariants

1. Authorization is not evidence of execution.
2. Structural evidence is not operational proof.
3. No plane may expand its own authority.
4. No external action occurs without scoped accountable approval.
5. All consequential transitions are exact-revision and evidence bound.
6. Secret values never enter repository files, prompts, logs, or receipts.
7. Production readiness is calculated from canonical evidence, never manually asserted.
