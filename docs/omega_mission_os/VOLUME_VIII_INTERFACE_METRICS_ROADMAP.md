# Volume VIII — Product Interface, Executive Dashboard, Metrics, and Delivery Roadmap

## Operator interface

The interface must answer five questions immediately:

1. What is true now?
2. What changed?
3. What is blocked or risky?
4. What requires human approval?
5. What single action has the highest justified impact?

## Dashboard domains

- mission progress and confidence;
- revenue pipeline, contracted, invoiced, and collected cash;
- active Quests and lifecycle state;
- phase health and artifact freshness;
- engineering and CI status;
- security, compliance, and incident posture;
- infrastructure readiness and operational evidence;
- approvals waiting and expiry;
- time, cost, model usage, and automation coverage.

Metrics must expose provenance and never merge projections with verified outcomes.

## Approval experience

Each approval card includes exact action, target, revision, scope, risk, cost ceiling, expiry, evidence, alternatives, rollback, and the effect of approval. Approval phrases and receipts remain compatible with existing AIGC governance.

## Delivery increments

### Increment 1 — Specification admission
Admit Volumes I–VIII, index them, and establish traceability to current repository components.

### Increment 2 — Mission contracts
Add JSON schemas for missions, objectives, tasks, dependencies, approvals, KPI snapshots, and evidence references.

### Increment 3 — Read-only Mission Director
Compose existing phase, Quest, finance, compliance, quality, CI, and readiness state into one mission snapshot. No writes or external actions.

### Increment 4 — Executive dashboard
Expose mission snapshots, blockers, approvals, and evidence through CLI/API and local UI.

### Increment 5 — Revenue mission adapter
Coordinate existing opportunity, assessment, proposal, finance, compliance, fidelity, quality, and customer-satisfaction artifacts for bounded revenue missions.

### Increment 6 — Governed action bridge
Prepare connector actions and route them through exact approvals, Phase 6 execution modes, idempotency, limits, and receipts.

### Increment 7 — Staging proof
Deploy an immutable staging candidate, run controlled canaries, capture evidence, test rollback and recovery, and validate judge-safe read-only access.

### Increment 8 — Production decision
Calculate production readiness exclusively from canonical evidence and accountable release approval.

## Completion definition

Ω Mission OS v1.0 is complete only when the specification, contracts, runtime composition, dashboard, revenue adapter, governed action bridge, tests, staging operational evidence, recovery evidence, and operator documentation all satisfy their acceptance criteria. Repository structure alone is not completion.