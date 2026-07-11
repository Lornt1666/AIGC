# AIGC Assurance Implementation Checklist

## Purpose

This checklist decomposes the intended AIGC assurance architecture into bounded, sequential, reviewable work packages. Completion of a checklist item requires repository evidence; checked boxes in planning documents alone do not prove implementation.

## Gate 0 — Current prerequisite

- [ ] Obtain a legitimate independent reviewer for PR #29.
- [ ] Bind the review to head `dc6b38204f3087eda7beb676ad53beecf1d8e1e2` or its verified successor.
- [ ] Resolve requested changes, if any.
- [ ] Re-run CI after every head change.
- [ ] Confirm zero unresolved mandatory review threads.
- [ ] Merge through explicit operator action only after required gates pass.
- [ ] Verify CI and readiness receipt on the resulting `main` revision.

## Gate 1 — AEC-001 constitutional kernel

- [ ] Canonical Constitution Markdown.
- [ ] Machine-readable article registry.
- [ ] Registry JSON Schema.
- [ ] Traceability-manifest schema.
- [ ] Constitution Gate validator.
- [ ] Amendment and waiver rules.
- [ ] Positive and negative tests.
- [ ] Revision-bound governance receipt.
- [ ] Independent review and operator ratification.

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
- [ ] Explicit suppression/waiver handling.
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
- [ ] Separate advisory recommendation from authoritative human decision.
- [ ] Invalidate recommendation on head change.
- [ ] Produce plain-language and technical evidence views.
- [ ] Test author-as-independent-reviewer rejection.
- [ ] Test unresolved blocking findings.

## Gate 6 — Engineering Review Council

- [ ] Approve council charter.
- [ ] Prepare candidate overview and role descriptions.
- [ ] Prepare confidentiality and acceptable-use statement.
- [ ] Prepare conflict-of-interest declaration.
- [ ] Define least-privilege access and revocation procedure.
- [ ] Recruit one reviewer for PR #29.
- [ ] Expand to three accepted reviewers.
- [ ] Expand to five seats as risk and workload justify.
- [ ] Record reviewer domains, assignments, reviewed head, decision, expiry, and lessons.

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

## Mandatory completion evidence for every gate

- [ ] Separate branch and reviewed PR.
- [ ] Explicit scope and exclusions.
- [ ] Contracts/schemas before or with implementation.
- [ ] Positive and negative tests.
- [ ] CI success bound to exact head.
- [ ] Security, privacy, accessibility, and governance review as applicable.
- [ ] Review packet.
- [ ] Required independent review.
- [ ] Operator-controlled merge.
- [ ] Main-branch verification.
- [ ] Readiness-ledger update.
- [ ] Rollback evidence.
- [ ] No unsupported production, compliance, certification, or independence claim.

## Definition of completion

The designated end state is reached only when the constitutional, assurance, review, identity, documentation, procurement, knowledge, staging, monitoring, recovery, and deployment layers are implemented, integrated, independently reviewed where required, operationally evidenced, and understandable to non-technical users. Planning documents and generated artifacts are necessary evidence inputs, not substitutes for working capability.
