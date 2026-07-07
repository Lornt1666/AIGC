# AIGC Workflow Dependency Matrix

| Workflow | Trigger | Emits | External Action |
|---|---|---|---|
| `intake_to_work_order` | manual or placeholder webhook | `work_order.created` | blocked |
| `action_permit_approval_queue` | `work_order.created` | `action_permit.requested`, `human_approval.required` | blocked |
| `regression_guard_check` | manual or schedule placeholder | `regression_guard.passed` | blocked |
| `evidence_pack_refresh` | evidence or baseline fixture | `evidence_pack.updated` | blocked |
| `actor_execution_dry_run` | approved local permit fixture | `actor_task.queued`, `actor_task.started`, `actor_task.completed` | blocked |
| `delivery_draft` | `qa.verification.passed` | `delivery_packet.ready` | blocked |

## Dependency Rule

No workflow output is approval by itself. Approval state must come from a separate human approval or future live action permit record.
