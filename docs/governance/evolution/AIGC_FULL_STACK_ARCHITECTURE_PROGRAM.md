# AIGC Full-Stack Architecture Program

Status: procured for staged execution under BOOTSTRAP_OPERATOR_ASSURANCE.

## Objective

Evolve AIGC from a localhost-only governed authorization/API prototype into a persistent, restart-safe, auditable operator platform with explicit job-state governance, connector isolation, production identity boundaries, staging evidence, and deployment controls.

## Ordered trains

1. Local operator API stabilization and exact-head validation.
2. Transactional persistence and append-only audit.
3. Evidence-driven readiness engine.
4. Governed job state machine and Run/Accept controls.
5. Proposal/execution separation and connector policy gateway.
6. Production identity adapter and durable sessions.
7. Reproducible staging, backup/restore, observability, and rollback.
8. Limited deployment authorization only after all blockers are evidenced closed.

## Architectural rule

`HTTP route -> application service -> domain kernel -> repository interface -> infrastructure adapter`

Routes must not contain SQL, connector credentials, production identity logic, or direct external side effects.

## Required bounded interfaces

- PrincipalRepository
- MembershipRepository
- SessionRepository
- PolicyRepository
- ApprovalRepository
- RevocationRepository
- AuthorizationReceiptRepository
- JobRepository
- ArtifactRepository
- AuditEventRepository
- ReadinessEvidenceRepository
- ConnectorRegistry
- SecretProvider
- TelemetrySink

## Governance boundaries

- production_identity_access remains blocking;
- external actions remain disabled by default;
- local bootstrap binds only to 127.0.0.1;
- all consequential actions require proposal, policy decision, approval obligation, operator acceptance, connector execution, and normalized receipt;
- no worker may transition directly from research to external delivery;
- every readiness transition must be revision-bound and evidence-backed;
- staging precedes production;
- rollback and recovery evidence are mandatory before deployment authorization.

## Train acceptance matrix

### Train A — Local API

- exact-head CI green;
- classified/redacted errors;
- deterministic response contracts;
- concurrency, expiry, replay, malformed payload, OpenAPI, startup/shutdown tests;
- expected-head squash merge;
- exact-main verification;
- Seagate localhost installation only after main verification.

### Train B — Persistence

- SQLite WAL mode with foreign keys;
- migrations and integrity checks;
- transactions and idempotency keys;
- optimistic revision columns;
- immutable audit events;
- soft revocation and retention states;
- backup and restore procedure;
- repository interfaces keep SQL out of routes/domain kernel.

### Train C — Orchestration

Job states:

`DISCOVERED -> QUALIFIED -> PROPOSED -> APPROVAL_REQUIRED -> ACCEPTED -> RESEARCHING -> PLANNING -> EXECUTING_LOCALLY -> REVIEW_REQUIRED -> ACCEPTED_FOR_DELIVERY -> DELIVERED -> CLOSED`

Each transition records actor, authorization decision, exact revision, input digest, reason, evidence, timestamp, resulting state, and rollback/compensation path.

### Train D — Connector Gateway

`Worker -> ActionProposal -> ConnectorPolicyGateway -> ApprovalGate -> ConnectorAdapter -> ExternalService -> NormalizedReceipt`

Every connector requires least-privilege scopes, allowlists, dry-run, idempotency, timeout, redaction, approval class, receipt, rate limit, and revocation switch. Official APIs only.

### Train E — Production Identity

`IdentityProviderAdapter -> AuthenticatedSubject -> PrincipalResolver -> MembershipResolver -> SessionIssuer -> AuthorizationKernel`

Authentication establishes subject identity; it never grants tenant/project/job/connector authority by itself.

### Train F — Staging

- clean tagged install;
- migration test;
- health/readiness probes;
- restart recovery;
- persistent receipts;
- concurrency;
- backup/restore;
- log rotation;
- sandboxed secret retrieval;
- rollback drill;
- dependency/security scans;
- external connectors disabled or sandboxed;
- no production data.

## CI target gates

- contracts
- unit-tests
- integration-tests
- mutation-tests
- security-scan
- secret-scan
- dependency-scan
- api-schema-check
- migration-test
- build-package
- staging-smoke
- readiness-evaluation
- evidence-upload

Every evidence artifact must include exact head SHA, artifact digest, tool versions, result flags, and external_action_performed.

## Deployment decision

AIGC is not authorized for public or production deployment until identity, persistence, recovery, monitoring, secrets, staging, connector governance, accessibility, and readiness evidence meet the governed threshold. The near-term milestone is a persistent, restart-safe local operator platform with a governed job state machine.
