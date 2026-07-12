# Dual-Revision Evidence Gate v2 — PR Review Checklist

## Immutable-head lane

- [ ] final PR head is a full 40-character SHA;
- [ ] selected SHA equals checked-out `HEAD`;
- [ ] immutable receipt expected and actual revisions equal the final head;
- [ ] immutable receipt reports `verified=true`;
- [ ] readiness `source_revision` equals the final head;
- [ ] readiness artifact name contains the final head;
- [ ] contracts, AEC-001, secret scan, procurement smoke stages and full tests pass.

## Merge-candidate lane

- [ ] event base SHA is recorded;
- [ ] immutable head SHA is recorded;
- [ ] expected merge-candidate SHA equals checked-out `HEAD`;
- [ ] base ancestry is true;
- [ ] head ancestry is true;
- [ ] merge-candidate receipt reports `verified=true`;
- [ ] contracts, AEC-001, secret scan, procurement smoke stages and full tests pass;
- [ ] merge-candidate artifact name contains the immutable head and merge-candidate SHA.

## Authority and safety

- [ ] workflow permissions remain `contents: read`;
- [ ] checkout credentials are not persisted;
- [ ] no production identity, secret, connector, deployment or external action is introduced;
- [ ] operator reviews the final immutable head;
- [ ] a new commit invalidates prior review;
- [ ] merge is separately and explicitly authorized with expected-head protection;
- [ ] rollback remains branch abandonment or one squash revert;
- [ ] post-merge exact-main verification is planned.

## Downstream controls

- [ ] PR #53 remains open until v2 evidence passes;
- [ ] PRs #63, #64 and #65 remain non-merge-ready pending fresh evidence;
- [ ] Issue #66 remains independently blocking until operator semantic decisions are recorded;
- [ ] no readiness score or capability status is promoted in this PR.
