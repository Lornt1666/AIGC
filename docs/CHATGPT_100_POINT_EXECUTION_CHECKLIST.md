# AIGC Operations — 100-Point Execution Checklist

A checked box requires attributable evidence. Intent, architecture, local-only success, screenshots, or narrative assertions are insufficient.

## 1. Local and contract validation

- [ ] canonical MCP server and widget exist;
- [ ] persistent control plane and worker pass local tests;
- [ ] approval nonce, replay, emergency-stop, and task-graph tests pass;
- [ ] submission package has five positive and three negative tests;
- [ ] file catalogue, exclusions, manifest, and build receipt verify.

## 2. ChatGPT Developer Mode — #132

- [ ] stable HTTPS `/mcp` endpoint;
- [ ] ChatGPT scans intended tools;
- [ ] explicit tool input/output schemas and annotations;
- [ ] widget renders and updates;
- [ ] authenticated operator and tenant isolation;
- [ ] Approval Inbox and single-use approval pass;
- [ ] prompt-injection and disconnected-runtime tests pass;
- [ ] operator accepts the evidence.

Then:

```text
chatgpt_developer_mode_connected=true
chatgpt_end_to_end_acceptance_passed=true
```

## 3. Hosted CI — #124 / PR #123

- [ ] hosted runner executes real steps;
- [ ] checkout, tests, Terraform, MCP/widget, security, and supply-chain gates pass;
- [ ] required exact-revision artifacts exist;
- [ ] GAR/GHR accepted.

Then:

```text
hosted_ci_evidence_present=true
hosted_ci_replacement_allowed=false
```

## 4. Staging and Canary A — PR #121 / #130

- [ ] isolated project, remote state, WIF, and least privilege;
- [ ] Cloud Run, private PostgreSQL, Secret Manager;
- [ ] authentication, tenant isolation, migrations, transactions, pooling;
- [ ] logs, metrics, alerts, budgets, incident path;
- [ ] immutable image, SBOM, provenance, signature, scan;
- [ ] rollback, backup, isolated restore, observed RPO/RTO;
- [ ] Canary A accepted.

Then:

```text
staging_operational_evidence_present=true
```

## 5. Canary B — #128

- [ ] attributable `WORK_ACCEPTED` trigger;
- [ ] employer facts separated from inference;
- [ ] requirements traceability and verified capability claims;
- [ ] deterministic, idempotent governed work graph;
- [ ] budgets, depth, concurrency, stop conditions;
- [ ] amendment reconciliation and escalation;
- [ ] delivery approval;
- [ ] Canary B accepted.

## 6. Connectors and exact external action — #134

- [ ] one approved read-only connector;
- [ ] one operator-controlled sandbox mutation;
- [ ] exact payload, destination, connector version, approval, nonce, and idempotency binding;
- [ ] provider result verified;
- [ ] immutable receipt accepted;
- [ ] replay rejected.

Then:

```text
external_action_receipt_present=true
```

`external_action_performed=true` belongs only to the immutable receipt for the exact action.

## 7. Production dossier — #133

- [ ] all evidence groups present;
- [ ] every artifact revision-, image-, environment-, time-, and digest-bound;
- [ ] evidence is mutually consistent;
- [ ] accountable operator accepts the dossier.

Then:

```text
production_evidence_present=true
```

## 8. Final release disposition — #135

`release_100_permitted=true` only when:

```text
all ten categories=PRODUCTION_ACCEPTED
all evidence truths=true
all safety invariants=false
operator evidence disposition=accepted
```

Never change a safety invariant to true to increase the score.
