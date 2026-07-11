# AIGC Assurance Implementation Checklist

## Purpose

This checklist decomposes the intended AIGC assurance architecture into bounded, sequential, reviewable work packages. Completion of a checklist item requires repository evidence; checked boxes in planning documents alone do not prove implementation.

## Gate 0 — PR #29 readiness-ledger prerequisite

Select one truthful path:

- [ ] Path A — obtain a distinct human reviewer.
- [ ] Path B — use the Solo-Operator Alternative Assurance bootstrap defined by the Review Authority Policy.

### Path A

- [ ] identify a distinct eligible reviewer;
- [ ] complete confidentiality and conflict screening;
- [ ] grant minimum, time-bounded access;
- [ ] request review against the exact head;
- [ ] receive a reasoned decision;
- [ ] resolve blocking findings and renew review after head changes.

### Path B

- [ ] record that independent human review was not performed;
- [ ] generate the strongest available AI advisory review and Review Packet;
- [ ] verify exact-head CI and negative tests;
- [ ] confirm no unresolved blocking findings;
- [ ] record operator risk acceptance and bootstrap rationale;
- [ ] confirm PR #29 introduces no deployment, credentials, external actions, or production mutation;
- [ ] define rollback and mandatory post-merge verification;
- [ ] merge using expected-head protection only after explicit operator command.

### Shared completion

- [ ] verify the selected path against the exact head SHA;
- [ ] verify successful required checks;
- [ ] verify zero unresolved mandatory review threads;
- [ ] merge through operator control;
- [ ] verify CI and readiness receipt on the resulting `main` revision.

## Gate 1 — AEC-001 constitutional kernel

- [ ] Canonical Constitution Markdown.
- [ ] Machine-readable article registry.
- [ ] Registry JSON Schema.
- [ ] Traceability-manifest schema.
- [ ] Constitution Gate validator.
- [ ] Amendment and waiver rules.
- [ ] Positive and negative tests.
- [ ] Revision-bound governance receipt.
- [ ] Review path selected according to risk class.
- [ ] Operator ratification.

## Gate 2 — EIAP shared assurance contracts

- [ ] `ActorReference`.
- [ ] `ArtifactReference`.
- [ ] `EvidenceReference`.
- [ ] `Decision`.
- [ ] `ApprovalReference`.
- [ ] `GateReceipt`.
- [ ] `TraceabilityManifest`.
- [ ] Finding and observation schemas.
- [ ] Compatibility and semantic validation tests.
- [ ] Architectural decision record preventing duplicate primitives.

## Gate 3 — Assurance Sensorium v1

- [ ] Sensor registry schema.
- [ ] Observation schema.
- [ ] Sensor-health schema.
- [ ] Finding-synthesis schema.
- [ ] Deterministic registry and runner interfaces.
- [ ] Exact-revision-binding sensor.
- [ ] Missing-traceability sensor.
- [ ] Unsupported-maturity-claim sensor.
- [ ] Secret-like-payload guard.
- [ ] Stale-evidence/reference sensor.
- [ ] Explicit suppression and waiver handling.
- [ ] Markdown and JSON report.
- [ ] Fail-closed negative tests.

## Gate 4 — Permanent Review Packet Generator v1

- [ ] PR source collector.
- [ ] Base/head and CI binding.
- [ ] Architecture, contract, and schema diff classifiers.
- [ ] Security, privacy, accessibility, identity, readiness, and operations sections.
- [ ] Rollback and unresolved-assumption extraction.
- [ ] Review-time estimator with confidence basis.
- [ ] Reviewer decision sheet.
- [ ] Markdown and JSON rendering.
- [ ] Packet receipt and staleness detection.
- [ ] Negative tests for omitted or stale evidence.

## Gate 5 — PR Review Evidence Agent v1

- [ ] Consume review packet, Sensorium findings, CI, reviews, and threads.
- [ ] Produce `recommend_approve`, `recommend_changes`, or `insufficient_evidence`.
- [ ] Separate automated verification, AI advisory review, external assurance, operator ratification, and human review.
- [ ] Invalidate recommendation on head change.
- [ ] Produce plain-language and technical evidence views.
- [ ] Test false human-identity and false independence claims.
- [ ] Test unresolved blocking findings.

## Gate 6 — Engineering Review Council

- [ ] Approve council charter.
- [ ] Prepare candidate overview and role descriptions.
- [ ] Prepare confidentiality and acceptable-use statement.
- [ ] Prepare conflict-of-interest declaration.
- [ ] Define least-privilege access and revocation procedure.
- [ ] Recruit one human reviewer or procure one external assurance source for bounded advisory analysis.
- [ ] Expand to three accepted reviewers or providers.
- [ ] Expand to five seats as risk and workload justify.
- [ ] Record reviewer/provider type, domains, assignments, reviewed head, decision, expiry, and lessons.

## Gate 6A — External assurance provider due diligence

- [ ] disclose whether the service is human-led, AI-assisted, or automated;
- [ ] verify the legal entity and responsible contact;
- [ ] inspect privacy, retention, training-use, deletion, and subprocessor terms;
- [ ] inspect security controls and incident-notification terms;
- [ ] establish written confidentiality and permitted-use restrictions;
- [ ] define ownership of inputs, outputs, findings, and derivative material;
- [ ] define responsibility, remedies, limits, governing law, termination, and deletion obligations;
- [ ] establish time-limited access and a minimal disclosure package;
- [ ] preserve a disclosure manifest and revocation evidence;
- [ ] obtain legal review for material engagements.

## Gate 7 — Identity, Scope and Authorization Kernel v1

- [ ] Strict identity, role, session, resource, policy, decision, and receipt schemas.
- [ ] Deny-by-default decision core.
- [ ] Tenant/project isolation.
- [ ] Session expiry and revocation.
- [ ] Resource-sensitivity taxonomy.
- [ ] Observer-authority adapter.
- [ ] Security & Privacy Wiring Gate adapter.
- [ ] SQLite repository and migrations.
- [ ] Atomic approval consumption and revocation.
- [ ] CLI simulation and negative tests.
- [ ] No live IdP, credentials, or production accounts in v1.

## Gate 8 — Sovereign Documentation Rendering Agent v1

- [ ] Document-intake contract.
- [ ] Evidence/source registry.
- [ ] Claim graph and truth policy.
- [ ] Audience and jurisdiction classification.
- [ ] Plain-language Markdown renderer.
- [ ] Technical evidence renderer.
- [ ] Secret, privacy, certification, and accessibility checks.
- [ ] Document receipt and staleness detection.
- [ ] Cross-document terminology and contradiction checks.
- [ ] No external publishing in v1.

## Gate 9 — UPEP-001 initial implementation

- [ ] Engineering Intent schema.
- [ ] Requirement schema.
- [ ] Procedural Verification schema.
- [ ] Authorization Path schema.
- [ ] Lifecycle Receipt schema.
- [ ] Deterministic phase-transition validator.
- [ ] CLI simulation.
- [ ] Plain-language and JSON outputs.
- [ ] Tests for skipped phases, stale approvals, missing evidence, missing rollback, and unauthorized acquisition.

## Gate 10 — Review Knowledge Graph

- [ ] SQLite schema for issues, PRs, artifacts, findings, evidence, decisions, outcomes, and lessons.
- [ ] Provenance and supersession history.
- [ ] Recurrence and duplicate-finding links.
- [ ] Repository interfaces supporting later database replacement.
- [ ] Privacy-minimized reviewer and decision records.
- [ ] Post-merge lesson capture.

## Gate 11 — Production continuation

- [ ] Managed identity-provider adapter with MFA/passkey support.
- [ ] PostgreSQL-compatible persistence and hardened tenant isolation.
- [ ] Staging environment with synthetic data.
- [ ] Approved read-only official connector.
- [ ] Accessible public/operator portal.
- [ ] Monitoring, alerting, telemetry, and service objectives.
- [ ] Backup/restore proof and disaster-recovery exercise.
- [ ] SBOM and provenance attestations.
- [ ] Accessible HTML, DOCX, and PDF renderers.
- [ ] Controlled deployment, rollback, and post-deployment verification.
- [ ] Mandatory independent human review for release-critical work.

## Mandatory completion evidence for every gate

- [ ] Separate branch and reviewed PR.
- [ ] Explicit scope and exclusions.
- [ ] Contracts/schemas before or with implementation.
- [ ] Positive and negative tests.
- [ ] CI success bound to exact head.
- [ ] Security, privacy, accessibility, and governance review as applicable.
- [ ] Review packet.
- [ ] Review path selected according to the applicable risk class.
- [ ] Operator-controlled merge.
- [ ] Main-branch verification.
- [ ] Readiness-ledger update.
- [ ] Rollback evidence.
- [ ] No unsupported production, compliance, certification, human-identity, or independence claim.

## Definition of completion

The designated end state is reached only when the constitutional, assurance, review, identity, documentation, procurement, knowledge, staging, monitoring, recovery, and deployment layers are implemented, integrated, independently reviewed where required, operationally evidenced, and understandable to non-technical users. Planning documents and generated artifacts are necessary evidence inputs, not substitutes for working capability.
