# AIGC Evolution and Procurement Cycle — Dual-Revision Evidence Gate v2

Status: **bounded implementation on a separate operator-controlled branch**  
Scope: **AIGC only**  
Base revision at branch creation: `293de53489fe7212fad272c01c698c0ffe2da610`  
Branch: `codex/ci-dual-revision-evidence-gate-v2-current-main`  
Operator approval record — Justice Gray Maciocha approved updating the repository with the inspected findings and bounded replacement implementation.  
Merge approval state — **not granted by this record**  
Deployment performed: **false**  
Credentials used: **false**  
External action performed by AIGC runtime: **false**

## 1. Evolution diagnosis

The exact-revision inspection established that current `main` still used GitHub's default pull-request checkout and named readiness artifacts with `github.sha`. On pull-request workflows this bound assurance artifacts to a synthetic merge revision rather than the immutable reviewed head.

PR #53 implemented a correct immutable-head verifier and passed CI run 671 at head `9c7fecd057cf33f79e202e46a3e6bb83d7fa7e48`. Its selected SHA, checked-out SHA, revision receipt, readiness source revision and artifact name agreed. However, PR #53 originated from `main@532c62150becdc1b0fa606ddeaeb70bc40197574` and later diverged from current `main`, which added the local operator API and transactional SQLite storage.

The evidence defect therefore has two dimensions:

1. **immutable provenance** — prove the reviewed PR head itself; and
2. **current-base integration** — prove the reviewed head still passes when combined with the target branch.

One revision cannot truthfully stand for both dimensions.

## 2. Contender arena

| Rank | Strategy | Strength | Weakness | Decision |
|---:|---|---|---|---|
| 1 | Dual-revision evidence lanes | Separates reviewed-source truth from integration truth | Adds one CI job | Implemented in this PR |
| 2 | Rebase PR #53 unchanged | Preserves its verifier | Carries stale documentation and obscures lineage | Rejected |
| 3 | Merge PR #53 then repair docs | Fastest apparent path | Introduces known stale claims to `main` | Rejected |
| 4 | Synthetic merge evidence only | Proves target-branch compatibility | Does not prove the immutable reviewed source | Rejected |
| 5 | Immutable head evidence only | Proves the exact reviewed code | Does not prove current-base compatibility | Insufficient alone |
| 6 | Manual SHA comparison in PR text | Easy | Non-enforceable and drift-prone | Rejected |

## 3. Auto-design output

The evidence ontology is refined into two classes:

- `immutable_checked_out_revision`;
- `pull_request_merge_candidate`.

The taxonomy adds:

- `selected_revision`;
- `actual_revision`;
- `base_revision`;
- `head_revision`;
- `expected_merge_revision`;
- `base_is_ancestor`;
- `head_is_ancestor`;
- `evidence_lane`;
- `revision_role`.

The design prohibits using a merge-candidate artifact as immutable-head evidence or using immutable-head readiness as proof of target-branch integration.

## 4. Auto-engineer output

The implementation adds:

- strict versioned JSON contracts for both evidence receipts;
- an immutable-revision verifier and CLI;
- a merge-candidate verifier and CLI;
- Git ancestry verification through `git merge-base --is-ancestor`;
- a readiness entrypoint that binds process-local `GITHUB_SHA` only after immutable checkout verification;
- positive, negative, mismatch, authority-boundary, environment-restoration and workflow-wiring tests;
- separate artifact paths and names.

## 5. Auto-architect output

The CI architecture becomes:

```text
GitHub pull-request event
├── immutable-head-assurance
│   ├── select immutable head
│   ├── exact checkout
│   ├── revision receipt
│   ├── contracts / Constitution / secret scan / tests
│   └── immutable-bound readiness artifact
└── merge-candidate-integration
    ├── select event base, immutable head and GitHub merge candidate
    ├── exact merge-candidate checkout
    ├── equality and ancestry receipt
    └── contracts / Constitution / secret scan / tests
```

Both jobs are evidence producers only. Neither has approval, merge, deployment, identity or connector authority.

## 6. Cognitive and analytical review

The central tradeoff is additional CI cost versus trustworthy assurance. A duplicated validation/test pass increases runtime, but removes a material ambiguity: source provenance and integration fitness are different propositions. The separation reduces false confidence, stale-base merges and incorrect readiness attribution.

Assumptions are bounded to GitHub pull-request event fields and Git ancestry available through a full checkout. Any missing or malformed revision fails closed.

## 7. 2026 societal logic integration

The workflow preserves least privilege with repository `contents: read` and disables persisted checkout credentials. No personal information, production identity, credential or external connector is introduced. The artifacts are technical evidence and remain subject to repository access controls and retention settings.

Accessible operator review remains required. CI output must use explicit revision labels rather than relying on color, status icons or unstated GitHub semantics.

## 8. Final synthesis

AIGC now treats the reviewed head as the **blade** and the merge candidate as the **anvil**—a metaphor mapped to concrete controls:

- blade: immutable head equality, receipt and readiness binding;
- anvil: current-base ancestry and integration tests;
- operator hand: final review and merge authority.

No metaphor grants execution authority.

## 9. Single highest-impact implementation step

Implement the dual-revision CI evidence gate from current `main`. This is the smallest step that makes later evidence for PRs #63, #64 and #65 trustworthy without advancing their capability claims.

## 10. Procurement success packet

### Objective

Prove immutable reviewed-source identity and current-target integration separately and mechanically.

### Scope

Workflow, receipt contracts, verifier modules, CLIs, tests, procedure and assurance-index reconciliation.

### Non-scope

No merge, deployment, readiness promotion, production identity, API behavior change, database migration, credential use, connector invocation or external action.

### Prerequisites and evidence

- current main: `293de53489fe7212fad272c01c698c0ffe2da610`;
- PR #53 run 671 evidence retained as reference;
- current workflow confirmed to use default checkout and `github.sha` artifact naming;
- PRs #63–#65 confirmed to have synthetic-merge artifact names;
- Issue #66 confirmed open and blocking.

### Affected ontology domains

Assurance, provenance, CI, readiness, review authority and integration-train governance.

### Affected taxonomy classes

Evidence kind, revision role, review requirement, failure criticality, rollback class and integration train.

### Governing methodologies

Contract-first engineering, fail-closed verification, least privilege, immutable evidence binding, separation of duties, bounded PR delivery and post-merge verification.

### Architecture impact

One CI job becomes two evidence lanes. Runtime product behavior remains unchanged.

### Required contracts

- `ci_revision_evidence_receipt.schema.json` v2;
- `ci_merge_candidate_evidence_receipt.schema.json` v2.

### Required modules and wiring

- immutable verifier core and CLI;
- merge-candidate verifier core and CLI;
- revision-bound readiness CLI;
- two-job GitHub Actions workflow;
- separate artifact roots.

### Persistence

GitHub Actions artifacts only. No application database persistence is added.

### Security, privacy, identity and authorization

- `contents: read`;
- `persist-credentials: false`;
- no secret values;
- no identity-provider integration;
- operator review remains mandatory;
- CI cannot approve or merge.

### Observability and audit

Each lane emits a machine-readable receipt. Artifact names expose the relevant immutable or merge-candidate revision without conflating them.

### Tests and CI gates

- matching and mismatching revision tests;
- malformed SHA tests;
- missing ancestry tests;
- authority-boundary tests;
- receipt contract tests;
- readiness environment-restoration test;
- workflow-wiring test;
- contract validation;
- AEC-001 validation;
- secret scan;
- procurement smoke stages;
- full tests in both lanes.

### Rollback and migration

Rollback is branch abandonment or one squash revert. There is no data migration.

### Ownership

Justice Gray Maciocha is the accountable operator. Automated verification remains advisory evidence.

### Acceptance criteria

- immutable selected, checked-out, receipt, readiness and artifact revisions agree;
- merge expected and actual revisions agree;
- base and head ancestry are true;
- both jobs pass on the final immutable head;
- permissions remain read-only;
- operator reviews the final head;
- merge is separately authorized;
- exact-main post-merge verification succeeds.

### Readiness impact

Immediate structural score impact: `0.0`. Assurance integrity improves, but no production capability is promoted.

### Branch and PR plan

- branch: `codex/ci-dual-revision-evidence-gate-v2-current-main`;
- base: `main@293de53489fe7212fad272c01c698c0ffe2da610`;
- draft PR title: `fix(ci): separate exact-head evidence from merge-candidate validation`;
- expected-head protection required for any later merge.

## 11. Workflow procurement procedure

```text
intake
→ evidence verification
→ scope lock
→ contract-first design
→ implementation plan
→ security/privacy wiring
→ tests
→ dual-lane CI
→ operator review
→ merge decision
→ post-merge verification
→ readiness-ledger update
```

## 12. Engine evolution v+1

The next bounded engine improvement is a `CapabilityEvidenceSnapshot v1` that consumes both receipt types and prevents readiness or procurement consumers from accepting evidence whose revision role is ambiguous.

## 13. Next-run directive

The next cycle shall inspect only this replacement train:

1. final immutable branch head;
2. immutable selected and checked-out SHA;
3. immutable receipt and readiness source revision;
4. immutable artifact name;
5. merge event base, head, expected candidate and checked-out SHA;
6. base/head ancestry flags;
7. both job results and permissions;
8. PR #53 supersession disposition;
9. continued blocking state of PRs #63–#65;
10. continued operator-decision state of Issue #66.

No downstream merge-readiness claim may advance until both evidence lanes pass on the final immutable head.
