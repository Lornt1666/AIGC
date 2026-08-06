# Canadian Execution and Privacy Policy Reference

## Status

ENGINEERING GOVERNANCE BASELINE — NOT LEGAL CERTIFICATION — PRODUCTION DISABLED

This reference translates Canadian and Quebec privacy values into fail-closed AIGC controls. Qualified legal, privacy, security, and cloud review remains necessary for regulated, personal, sensitive, or production workloads.

## Control-plane and execution-plane distinction

The Codex cloud environment is the repository-control plane. Its physical processing location must not be represented as Quebec or Canada without an authoritative service-specific receipt or contract.

The Canadian execution plane is a separately authorized cloud surface whose resources are explicitly bound to Canadian regions. The preferred region is Montréal (`northamerica-northeast1`). Toronto (`northamerica-northeast2`) is a fallback only when the exact service supports it and the owner explicitly approves it. No silent failover outside Canada is permitted.

## Privacy engineering principles

The system must preserve:

- accountability and recorded human authority;
- identified and limited purposes;
- consent or another documented lawful authority where applicable;
- collection, use, disclosure, and retention minimization;
- accurate and correctable records;
- safeguards proportionate to sensitivity and impact;
- openness about AI assistance and system boundaries;
- access, correction, and challenge paths;
- privacy-protective defaults;
- privacy-impact and cross-border assessments when warranted;
- human review before consequential use.

## Data handling boundary

Codex receives only sanitized, non-personal repository material, synthetic fixtures, hashes, and bounded metadata. Personal or sensitive runtime data remains on the approved Canadian execution plane. Public or judge-facing evidence must be separately sanitized and publication-authorized.

## Regional inventory

Before staging execution, record and inspect every relevant resource:

- compute service and revision;
- container registry and immutable digest;
- database and backups;
- object storage and evidence prefix;
- logs, traces, metrics, and alerting sinks;
- Secret Manager references using exact versions;
- key-management location where applicable;
- networking, egress, DNS, and service dependencies;
- disaster-recovery or fallback region;
- provider/model service availability;
- billing account, CAD ceiling, quotas, and alerts.

A regional frontend does not prove that dependent services, backups, logs, or model processing remain in the same jurisdiction.

## Required evidence

A Canadian staging claim requires, at minimum:

1. Exact Git SHA and tree SHA.
2. Exact Canadian region and service availability review.
3. Immutable image digest and no-traffic deployment receipt.
4. Resource and IAM inventory with least-privilege review.
5. Exact-version secret references with no raw values.
6. Storage, logging, backup, and evidence-region review.
7. Privacy-impact and cross-border assessment status.
8. Human approval, expiry, and CAD ceiling.
9. Explicit false production, live-call, send, merge, and external-action states.
10. A canonical contract digest.

## Stop conditions

Stop before external execution when any of the following is true:

- the region is absent, non-Canadian, mutable, or inferred;
- the exact model or service has not been checked in the selected region;
- a dependency may fail over outside Canada;
- personal data would enter the Codex control plane;
- a required assessment or human approval is missing or expired;
- raw secret material is present;
- the repository SHA or tree is not exact;
- logs, backups, evidence, or storage locations are unknown;
- the spending ceiling or quota review is missing;
- production, live-call, send, merge, publication, or business-action authority is implied.
