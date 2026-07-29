# AIGC Production Evidence Dossier

`production_evidence_present=true` is permitted only after the accountable operator accepts a complete evidence dossier bound to one immutable application revision, one immutable deployed image, and one environment.

## Required evidence groups

1. Stable HTTPS MCP endpoint and ChatGPT connection.
2. Authentication, authorization, tenant isolation, session expiry, and revocation.
3. Private PostgreSQL, migrations, transactions, pooling, retries, rollback, and conflict tests.
4. Secret Manager references, least-privilege identity, and secret-redaction evidence.
5. Immutable image digest, SBOM, provenance, signature verification, and vulnerability scan.
6. Logs, traces, metrics, alerts, latency/error monitoring, cost budgets, and incident response.
7. Exact approval binding, payload digest, destination binding, single-use nonce, idempotency, and replay tests.
8. Emergency stop, connector disablement, and token revocation.
9. Rollback to a prior immutable release.
10. Backup integrity, isolated restore, observed RPO, and observed RTO.
11. Canary A platform journey.
12. Canary B employer-duty autonomy journey.
13. ChatGPT positive, negative, prompt-injection, retry, and repeated-call evaluation.
14. One approved read-only connector proof.
15. One exact-approved external-action receipt.
16. Accountable operator evidence acceptance.

## Required artifact binding

Every evidence artifact must include:

```text
exact_repository_revision
exact_image_digest
environment_and_project
evidence_timestamp
artifact_sha256
accountable_source_or_observer
external_action_status
operator_acceptance_status
```

## Non-evidence

The following are not sufficient on their own:

- repository definitions;
- local command success;
- Codex execution;
- screenshots;
- a healthy endpoint;
- an unreviewed Terraform plan;
- an operator assertion without artifacts;
- local evidence represented as hosted CI.

## Acceptance rule

Only when all evidence groups are present, integrity-verified, mutually consistent, exact-revision bound, and accepted may the canonical state record:

```text
production_evidence_present=true
```

This truth does not authorize a future deployment, Terraform apply, credential use, or external action.
