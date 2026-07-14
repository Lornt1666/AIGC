# Production Environment Decision v1

Status: `ACCEPTED_WITH_DEFERRED_IDENTIFIERS`  
Source issue: `#85`  
Accountable operator: Justice Gray Maciocha, also known as Satoshi and Lornt  
External action performed: **No**

## Purpose

This contract records the accepted production architecture so later security, persistence, identity, connector, and deployment workstreams consume one consistent decision source.

It is not an infrastructure deployment manifest and contains no credentials, phone number, billing-account identifier, domain ownership record, or secret value.

Canonical files:

```text
schemas/production_environment_decision.schema.json
config/production_environment_decision.json
src/core/production_environment_decision.py
```

## Accepted baseline

### Cloud and residency

- Google Cloud;
- isolated staging and production projects;
- Toronto, `northamerica-northeast2`, as primary region;
- Montréal, `northamerica-northeast1`, as recovery region;
- Canadian data-residency target where supported.

The globally unique project IDs and billing account remain unresolved. No project or billing change is authorized.

### Runtime and network

- Cloud Run;
- non-root immutable container;
- external HTTPS load balancer;
- managed TLS;
- default-deny production ingress;
- isolated workload identities and environment boundaries.

The production domain and DNS authority remain unresolved. No DNS or certificate change is authorized.

### Persistence

- Cloud SQL for PostgreSQL;
- private connectivity required;
- RPO: 15 minutes;
- RTO: 4 hours;
- accepted backup baseline with detailed schedule still pending.

No Cloud SQL instance, database, service account, network, backup, or migration is created by this contract.

### Identity

- Google Cloud Identity Platform;
- Google sign-in;
- one accountable tenant initially;
- project isolation;
- public self-registration disabled;
- PIBC-v1 remains the provider-to-domain trust boundary.

No identity provider, OAuth client, user account, redirect URI, token, or credential is configured by this contract.

### Secrets

- Google Secret Manager;
- workload identity required;
- Canada-constrained replication target;
- repository secret values prohibited.

Only future resource references may enter source control. Secret contents remain outside repositories, prompts, logs, receipts, and API responses.

### Connectors

Enabled production connectors:

```text
none
```

Candidate connectors:

```text
GitHub
Google Drive
Gmail
```

Candidate status is not approval. Every connector requires issue #89 evidence and separate activation authority.

### Retention

- application/security logs: 30 days online;
- identity and authorization receipts: at least 90 days;
- review packets: project lifecycle plus an archival policy still to be finalized;
- deployment, rollback, restore, and incident receipts: at least 365 days.

Deletion, export, legal hold, and detailed archive schedules remain part of the security/privacy workstream.

### Budget and operations

- monthly ceiling: CAD $200;
- alerts: 50%, 80%, and 100%;
- incident owner: Justice Gray Maciocha;
- technical escalation contact supplied out-of-band;
- no direct phone number is committed;
- production changes require exact-release-candidate approval.

## Authority matrix

| Action | Current authority |
|---|---:|
| Contract-first implementation | Authorized |
| Infrastructure definitions and tests | Authorized |
| Isolated staging preparation | Authorized |
| Billing changes | Not authorized |
| Google Cloud resource creation | Not authorized |
| Secret access | Not authorized |
| DNS or TLS changes | Not authorized |
| Connector activation | Not authorized |
| Production deployment | Not authorized |

## Unresolved identifiers

The following remain explicit blockers before any resource-creation proposal:

1. globally unique staging project ID;
2. globally unique production project ID;
3. billing account selection;
4. production domain;
5. DNS authority;
6. detailed backup schedule;
7. data-classification register;
8. secure escalation-channel reference.

A later decision amendment must be schema-valid, reviewed, and digest-bound. It must not silently overwrite this accepted record.

## Evaluation

Run:

```bash
python src/core/production_environment_decision.py
```

Expected current result:

```text
accepted_baseline: true
contract_implementation_ready: true
isolated_staging_preparation_ready: true
resource_creation_ready: false
production_deployment_ready: false
default_deny_connectors: true
```

## Next implementation order

1. issue #86: production security and privacy contracts and controls;
2. issue #87: PostgreSQL portability, migrations, backup, and restore design;
3. issue #88: Identity Platform adapter and tenant/session contracts;
4. issue #89: connector and Secret Manager framework with zero enabled connectors;
5. issue #90: reproducible staging infrastructure and operations;
6. issue #91: exact-candidate release judgment and gated deployment.

No readiness-ledger capability is promoted by this decision record alone.
