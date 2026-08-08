# AIGC Evolution and Procurement Cycle — Platform Snapshot Request Packet v1

## Identity

- project: AIGC only
- parent program: Issue #55
- implementation train: PR #75
- graph: `AIGC-PR-DEPENDENCY-GRAPH-001`
- request: `AIGC-PR-PLATFORM-SNAPSHOT-REQUEST-001`
- scope: governance and evidence planes only
- readiness-score impact: `0.0`
- external action performed by AIGC runtime: `false`

## Diagnosed gap

The PR dependency graph and drift evaluator can compare a normalized GitHub snapshot with committed governance truth. Before this procurement, however, no contract specified exactly which read-only fields a future snapshot refresh must acquire, which source is permitted, how fresh the observation must be, which decision gate is mandatory, or how narrowly self-referential exclusions may be used.

Without an acquisition contract, a syntactically valid snapshot could still be incomplete for AIGC governance purposes.

## Objective

Add a strict request packet and deterministic completeness receipt so every future PR-platform snapshot can be evaluated against the same minimum evidence requirements before it is used for graph-drift conclusions.

## Implemented

- strict Draft 2020-12 request schema;
- repository-native request packet;
- required current open-PR field set;
- required Issue #66 decision-gate field set;
- two-hour maximum snapshot age;
- fail-closed missing-field policy;
- block-on-unknown-change policy;
- one narrowly typed self-referential exclusion maximum;
- strict receipt schema;
- request, graph and snapshot digest binding;
- repository, graph, source and current-main checks;
- required-decision-gate checks;
- graph/platform coverage checks;
- deterministic receipt identity;
- CLI and positive/negative tests.

## Governing pipeline

```text
snapshot request contract
→ read-only platform snapshot
→ graph and snapshot validation
→ freshness and completeness evaluation
→ deterministic request receipt
→ drift evaluation
→ operator review
```

## Fail-closed findings

- request repository differs from graph or snapshot;
- graph identity differs;
- unapproved snapshot source;
- graph and snapshot current-main revisions differ;
- evaluation precedes observation;
- snapshot exceeds the two-hour age limit;
- required PR or decision-gate fields are missing;
- a pull request is outside the requested open-state set;
- Issue #66 is absent;
- exclusion count or reason exceeds policy;
- a graph change is absent from the snapshot;
- an undeclared platform change is present.

## Non-scope

- no automatic GitHub query execution by AIGC runtime;
- no automatic snapshot or graph mutation;
- no PR or issue edit;
- no branch rebase;
- no review submission;
- no merge or automatic merge;
- no production identity, credentials, connectors or deployment;
- no runtime application, API, UI or database change;
- no readiness promotion.

## Security and privacy boundary

The request permits only normalized, read-only repository metadata. It does not authorize collection of production personal information, secrets, credentials, private message content, business connector data, or consequential external action. The Security & Privacy Wiring Gate remains unchanged.

## Tests

The bounded test set requires:

1. the current snapshot satisfies the request at a fixed in-window evaluation time;
2. receipt identity remains stable while only the evaluation time changes inside the freshness window;
3. an over-age snapshot fails closed;
4. a missing required decision gate fails closed;
5. exclusion cardinality above the approved maximum fails closed;
6. the receipt validates and persists without alteration;
7. the full repository suite remains green.

## Rollback

Before merge, abandon PR #75 or revert the bounded request-packet commits on its branch. After any separately authorized merge, use one bounded revert and rerun exact-main CI. No data rollback is required.

## Acceptance criteria

- request and receipt schemas validate;
- all required fields are explicit;
- the allowed source is read-only;
- the current snapshot produces `COMPLETE` inside the approved age window;
- stale, incomplete or over-excluded snapshots produce `INCOMPLETE`;
- receipt identity is deterministic for materially equivalent evidence;
- no authority or permission boundary expands;
- CI passes;
- PR remains draft and operator-controlled;
- merge remains a separate expected-head-protected decision.

## Next-run boundary

Inspect only the final PR #75 head, CI, snapshot-request receipt behavior, graph/snapshot drift, PR #74 disposition, PR #69 downstream requirements and Issue #66 state. Do not begin another runtime subsystem, production identity, connector implementation, deployment or automatic repository mutation.
