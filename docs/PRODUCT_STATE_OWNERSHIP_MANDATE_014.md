# AIGC product state ownership and integration boundary

Status: architecture contract for Mandate 014; this document does not claim that the kernel is integrated or that release readiness has been established.

## Source-of-truth snapshot

Baseline inspected: `main` at `5ff907ebd9a4d477100e38032db2b916b1aba9ab`, 2026-10-23.

The following boundaries are evidenced in the repository:

| Concern | Current component | Current role | Required product contract |
|---|---|---|---|
| Command-center run/review state | `src/webapp/command_center_store.py` | PostgreSQL-backed store, with a process-local development/test implementation | Remain authoritative for the existing command-center workflows until a reviewed task-state migration explicitly changes ownership |
| General phase/artifact records | `src/core/state_store.py` | SQLite artifact tables and runtime event ledger | Do not silently treat these records as the authoritative task lifecycle for the governed Redis kernel |
| Governed task contract | `src/core/contracts.py` on PR #339 | Versioned Pydantic message contracts | Schema validity is not authorization; permit and approval references must be independently verified at actuation |
| Queue delivery | `src/core/orchestrator.py` on PR #339 | Redis Streams coordinator; at-least-once delivery | Delivery state is not durable business/task state; handlers and actuation boundaries must be idempotent |
| Current web execution | `src/webapp/app.py` | Authenticated `/api/run` starts the predefined `BUSINESS_CYCLE` through subprocesses | Do not describe this as the Redis kernel's end-to-end task path |
| Artifact/evidence closure | Not yet demonstrated end-to-end across the above components | Existing stores and evidence mechanisms are separate | A task must bind owner, task ID, attempt, terminal state, artifact digest, and evidence record |

## Required ownership rule before integration

1. The application persistence layer must own the authoritative task lifecycle and terminal status.
2. Redis Streams may deliver work at least once; it must not become the sole source of truth for task status or authorization.
3. Approval and permit records must be durably verified immediately before a protected operation. IDs in a message are references, not proof of authorization.
4. Artifact bytes or immutable artifact storage must be bound to an owner, task, attempt, content digest, and evidence record. A digest must be recomputed from retrieved bytes before reporting verified integrity.
5. A terminal state must not be reported until result persistence and required evidence persistence have succeeded. If the outcome is ambiguous, report an explicit unknown/reconciliation state rather than success.
6. Cross-store disagreement must be reconciled from durable task records and immutable event/evidence data; it must not be resolved by assuming the queue's state is authoritative.

## Integration sequence

1. Add a durable task record and schema/migration strategy to the selected authoritative store.
2. Define the task lifecycle state machine, owner boundary, idempotency binding, attempt identity, and legal terminal transitions.
3. Add a narrow coordinator adapter that validates `TaskContract`, persists the task before enqueue, and correlates queue/result messages to the durable record.
4. Register only a harmless synthetic worker first; do not enable external tools or side effects.
5. Persist the result and artifact metadata, independently recompute the artifact digest, and close the evidence record before returning terminal success.
6. Add isolated PostgreSQL/Redis integration tests for duplicate delivery, enqueue/result persistence failures, worker crash, timeout, cancellation race, restart recovery, and audit failure.
7. Route a real API test through the above path without mocking the coordinator or worker boundary.

## Explicitly unresolved

- PR #339 is a draft and the kernel code is not called by the current web application path.
- PR #340 deadline enforcement is not evidence of end-to-end cancellation or durable task recovery.
- No production database migration, external action, deployment, or release approval is authorized by this document.
- Cloudflare preview root cause remains unknown until the actual build log is available.
