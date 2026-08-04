# Ω Mission OS Increment 11.2 — Governed Review Packet

## Review target

Issue-Driven Exact-SHA Dispatch Bridge.

## Required invariants

- Executing workflow is sourced from the default branch.
- Workflow checkout is bound to immutable `github.workflow_sha`.
- Request issue cannot provide executable code or arbitrary commands.
- Request author is authenticated through issue author association and exact actor/author identity.
- Request ID, issue identity, actor identity, timestamps, body digest, target SHA, and broker revision are replay-bound.
- Duplicate request IDs fail closed.
- Post-validation issue edits, relabeling, closure, or author drift fail closed.
- Target is a full SHA, exists, and is reachable from `main`.
- Exact target checkout and tested Git-tree SHA are bound into stage records and receipt evidence.
- The existing shared canonical AIGC CI runner is used without a second implementation.
- Stage evidence is isolated in runner-controlled temporary storage and atomically published.
- Receipt and completion manifests are digest-covered.
- Final uploaded-file inventory rejects missing, modified, or additional files.
- Success comments and closes the issue only after terminal revalidation.
- Failure leaves the issue open and emits only a bounded classification.
- Permissions are exactly `contents: read` and `issues: write`.
- No contents write, actions write, PR write, OIDC, secrets, deployment, Terraform apply, Gmail, production, or provider authority exists.

## Review procedure

1. Confirm exact PR head.
2. Confirm hosted AIGC CI success on that unchanged head.
3. Inspect the complete PR diff and every review thread.
4. Verify the issue schema and form are closed.
5. Verify the workflow is default-branch controlled and all actions are pinned.
6. Verify issue authorization and global replay rejection.
7. Verify exact target reachability and checkout binding.
8. Verify shared canonical runner use and evidence isolation.
9. Recompute execution-binding, stage-record, receipt, completion, and upload-inventory digests in regression tests.
10. Confirm terminal issue mutation is bounded to comments and successful closure.
11. Confirm every prohibited authority remains absent.

## Release decision

Keep the PR draft until exact-head hosted CI passes and the complete governed review finds no blocking concern. Do not merge on partial, stale, mismatched, or inferred evidence.
