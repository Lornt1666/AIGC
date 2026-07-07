# AIGC Orchestration Approval Boundary

## Principle

Orchestration may coordinate work. It may not approve work.

## Approval Boundary

The following states are not equivalent:

- a workflow completed;
- a review packet exists;
- a template is valid;
- a dry-run passed;
- a human approval exists;
- a live action permit exists.

Only an explicit approval or permit record can move a future action toward live execution.

## Self-Approval Rule

Self-approval is disabled. The `action_permit_approval_queue` workflow emits `human_approval.required`, not `human_approval.granted`.
