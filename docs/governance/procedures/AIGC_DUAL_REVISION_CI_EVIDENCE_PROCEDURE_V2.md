# AIGC Dual-Revision CI Evidence Procedure v2

Status: **proposed implementation procedure**  
Scope: **AIGC only**  
Authority boundary: **CI produces evidence; it does not approve, merge, deploy, grant access, or perform external action.**

## 1. Purpose

A pull request has two materially different revisions:

1. the immutable pull-request head reviewed by the operator; and
2. the integration candidate produced by combining that head with the current target branch.

AIGC must prove both without treating them as interchangeable.

## 2. Evidence lanes

### Lane A — immutable-head assurance

The workflow shall:

1. select `github.event.pull_request.head.sha` for pull requests or `github.sha` for pushes;
2. checkout that full revision explicitly;
3. disable persisted checkout credentials;
4. verify the selected revision equals `git rev-parse HEAD`;
5. emit a contract-valid immutable-revision receipt;
6. run contract validation, AEC-001 validation, secret scanning, procurement smoke stages and the full test suite;
7. generate readiness evidence only after immutable-head verification;
8. require readiness `source_revision` to equal the immutable head;
9. name the readiness artifact with the immutable head.

### Lane B — merge-candidate integration

For pull requests only, the workflow shall:

1. record the event base SHA, immutable head SHA and GitHub merge-candidate SHA;
2. checkout the merge-candidate SHA explicitly;
3. disable persisted checkout credentials;
4. verify the checked-out revision equals the expected merge-candidate SHA;
5. prove both the event base and immutable head are ancestors of the checked-out candidate;
6. emit a contract-valid merge-candidate receipt;
7. run contract validation, AEC-001 validation, secret scanning, procurement smoke stages and the full test suite;
8. name the integration artifact separately from immutable-head readiness evidence.

## 3. Required equality and ancestry controls

The immutable lane passes only when:

```text
selected immutable SHA
= checked-out HEAD
= immutable evidence receipt expected revision
= immutable evidence receipt actual revision
= readiness source_revision
= immutable artifact-name revision
```

The integration lane passes only when:

```text
expected merge-candidate SHA = checked-out HEAD
AND event base SHA is an ancestor of checked-out HEAD
AND immutable PR head SHA is an ancestor of checked-out HEAD
```

## 4. Failure behavior

The workflow shall fail closed when any of the following occurs:

- a revision is absent, abbreviated or malformed;
- selected and checked-out immutable revisions differ;
- readiness names a different source revision;
- merge-candidate expected and actual revisions differ;
- base ancestry cannot be proven;
- head ancestry cannot be proven;
- a receipt changes the operator-review or external-action boundary;
- a required test or validation stage fails.

Failure receipts may be uploaded for diagnosis, but a failed receipt never becomes positive assurance.

## 5. Permission boundary

Workflow permissions remain:

```yaml
permissions:
  contents: read
```

Checkout credentials are not persisted. The workflow may read repository content and upload its own run artifacts through GitHub Actions. It may not write repository content, approve, merge, deploy, use production credentials or invoke external connectors.

## 6. Operator review sequence

The binding sequence is:

```text
intake
→ repository evidence verification
→ scope lock
→ contract-first design
→ implementation
→ immutable-head assurance
→ merge-candidate integration
→ operator review of the final immutable head
→ explicit expected-head-protected merge decision
→ post-merge exact-main verification
→ readiness-ledger reconciliation in a separate reviewed change
```

A new commit invalidates prior operator review and requires both evidence lanes to rerun.

## 7. PR #53 transition rule

PR #53 is retained as historical reference until this v2 replacement obtains successful immutable-head and merge-candidate evidence. After that point, PR #53 may be closed unmerged as superseded, with a link to the replacement PR. Its stale-base documentation must not be merged into current `main`.

## 8. Downstream gates

PRs #63, #64 and #65 remain non-merge-ready until the dual-revision gate is available on their review path and their final immutable heads receive fresh evidence.

Issue #66 remains independently blocking for canonical acceptance and rework semantics. CI evidence cannot resolve that accountable operator decision.

## 9. Rollback

Before merge, abandon the branch or close the PR. After merge, use one bounded squash revert. This procedure introduces no database migration, credential, public deployment or external side effect.

## 10. Definition of done

The capability is done only when:

- both receipt schemas validate;
- positive and negative tests pass;
- both CI jobs pass on the final immutable PR head;
- artifact names and receipt fields match their respective revisions;
- permissions remain read-only;
- operator review is recorded;
- merge remains separately authorized;
- post-merge exact-main verification is completed.
