# AIGC Québec Google Cloud Foundation

## Hosting Decision

AIGC staging is designed for Google Cloud in Montréal, Québec (`northamerica-northeast1`). Google is a global hyperscale provider, not a Québec-owned company. The architecture uses managed regional services rather than one large virtual machine or an owner-operated server.

## Verified service availability — reviewed 2026-08-06

| Capability | Montréal status | Boundary |
|---|---|---|
| Cloud Run | Verified | Regional resource; customer data associated with the resource is stored in the selected region. |
| Cloud SQL PostgreSQL | Verified | Instance and primary data are stored in the selected region; regional HA synchronously spans zones. |
| Cloud Storage | Verified | Regional Montréal bucket available; regional endpoints can constrain object data at rest and in transit, excluding some resource metadata. |
| Artifact Registry | Verified | Regional Montréal repositories available. |
| Regional Secret Manager | Verified | Montréal regional secrets supported. |
| Cloud KMS | Verified | Montréal regional key rings and software keys supported; Cloud HSM is not available there. |
| Cloud Logging | Verified | Regional Montréal log buckets supported. |
| Cloud Build | Verified | Regional Montréal builds and endpoints supported. |
| Gemini 2.5 Pro / Flash | Verified endpoint availability | Montréal endpoint is listed. Exact model, capability, and ML-processing commitment must be rechecked at authorization. |

## Important model-processing boundary

Google's current documentation states that locational endpoints provide a country-jurisdiction processing commitment, and lists Canada at `northamerica-northeast1` for supported models. It also separately warns that an endpoint listing alone is not proof of residency; the per-model data-residency table and selected capability must be reviewed. AIGC therefore keeps `live_model_call_authorized=false` until that exact review and a one-use permit are complete.

## Device-theft resilience

The owner laptop and phone are access devices only. The runtime, database, evidence, secrets, encryption keys, and deployment artifacts are cloud resources. No service-account key file or raw cloud secret may be stored locally. Lost-device response is session revocation, credential rotation, and audit review—not restoration from a stolen local disk.

## Recovery

- Primary: Montréal only.
- Toronto disaster recovery: disabled until separate approval.
- Proposed RPO: 15 minutes.
- Proposed RTO: 4 hours.
- These targets remain unverified until a restore exercise produces receipts.

## Sources

- https://docs.cloud.google.com/run/docs/locations
- https://docs.cloud.google.com/sql/docs/postgres/locations
- https://docs.cloud.google.com/storage/docs/bucket-locations
- https://docs.cloud.google.com/storage/docs/regional-endpoints
- https://docs.cloud.google.com/artifact-registry/docs/repositories/repo-locations
- https://docs.cloud.google.com/secret-manager/docs/locations
- https://docs.cloud.google.com/kms/docs/locations
- https://docs.cloud.google.com/logging/docs/region-support
- https://docs.cloud.google.com/build/docs/locations
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/data-residency

---

## Threat Model

### Assets

- source and exact-SHA CI evidence;
- container images and build provenance;
- runtime-control database;
- private runtime evidence;
- sanitized judge receipts;
- regional Secret Manager versions;
- KMS keys;
- service identities;
- budget and deployment authorizations.

### Primary threats and required controls

| Threat | Control |
|---|---|
| Stolen owner device | No local runtime data or service-account keys; passkey/MFA; session revocation; full-disk encryption. |
| GitHub account compromise | Passkey/MFA, branch protection, exact-SHA receipts, no automatic merge, immutable build inputs. |
| Google account compromise | Separate identities, least privilege, short-lived credentials, audit alerts, emergency revocation. |
| Raw secret disclosure | Regional Secret Manager exact versions, no raw secret in Git, prompts, logs, state or receipts. |
| Public service exposure | No unauthenticated Cloud Run IAM, public-access prevention on buckets, no public database endpoint. |
| Cross-region drift | Montréal-only variables, resource-location verification, no Toronto replication by default. |
| Global Gemini routing | Regional endpoint only; global endpoint prohibited; exact per-model processing commitment reviewed before permit. |
| Build supply-chain compromise | Pinned actions/providers, dependency checks, secret scan, vulnerability scan, provenance, immutable digest. |
| Evidence overwrite | Create-only objects, versioning, generation receipts, retention, canonical hashes. |
| Runaway cost | CAD 200 maximum authorization ceiling, budget alerts, app request/token limits, bounded Cloud Run scaling. |
| Single-machine failure | Managed Cloud Run, regional Cloud SQL HA, regional object storage, restore-tested backups. |
| Insider privilege abuse | Separate deployer/build/operator/judge/security identities and resource-scoped roles. |

### Residual risks

- Control-plane metadata and provider subprocessors require contract review.
- A Google Cloud budget is not a guaranteed hard stop.
- Strict Québec residency is not established until actual resource and per-model receipts exist.
- Regional HA does not protect against a complete regional outage; Toronto recovery remains separately governed.

---

## Procurement Packet

### Current state

```text
provider_selected_for_plan=true
provider=Google Cloud
target_region=northamerica-northeast1
quebec_cloud_project_verified=false
billing_account_verified=false
resources_created=false
services_deployed=false
strict_quebec_data_residency_verified=false
codex_cloud_region_verified_canada=false
```

### Required exact identifiers

- Google Cloud billing account ID;
- staging project ID and number;
- resource names generated from the approved prefix;
- pre-existing Monitoring notification channels;
- exact owner/deployer identity members;
- exact numeric Montréal regional Secret Manager version references;
- admitted PR #170 release SHA, tree SHA, CI run and artifact;
- exact monthly pricing estimate from Google Cloud pricing tools;
- resource-manifest SHA-256.

### Capacity tiers

| Tier | Runtime | Database | Model use | Authority |
|---|---|---|---|---|
| Controlled staging | Cloud Run min 0, max 2, bounded concurrency | Regional HA PostgreSQL, 20 GB SSD | One separately permitted synthetic canary | Current target; no public access |
| Bounded pilot | Requires load evidence and revised limits | HA capacity scaled from measurements | Bounded approved traffic | Not authorized |
| Reviewed production | Separate project and security review | HA plus tested recovery | Production quota and incident procedures | Prohibited by this packet |

The accepted maximum monthly ceiling is CAD 200. A live provider quote is still required because regional HA Cloud SQL may consume most or all of that ceiling. Resource creation must remain blocked if the reviewed estimate exceeds the ceiling.

### Exact owner authorization form

```text
AUTHORIZE AIGC QUEBEC STAGING
PROJECT <PROJECT_ID>
REGION NORTHAMERICA-NORTHEAST1
RELEASE <EXACT_GIT_SHA>
RESOURCE-DIGEST <SHA256>
MONTHLY-CEILING-CAD 200
NO-PUBLIC-TRAFFIC
NO-LIVE-MODEL-CALL
EXPIRES <ISO-8601-TIMESTAMP>
```

The validator uses an equivalent single-line byte-exact phrase. This approval authorizes only the exact staging packet. It does not authorize production, public access, a Gemini call, judge publication, Gmail sending, or merge.

### Rollback

1. Keep Cloud Run candidates private and unexposed.
2. Activate the durable emergency stop if runtime authority becomes uncertain.
3. Revoke invoker and service-account bindings.
4. Disable new builds and deployments.
5. Preserve evidence and audit logs.
6. Export only reviewed, encrypted recovery data.
7. Destroy staging only through a separately reviewed plan after retention and legal-hold checks.

---

## Data Location Register

| Data class | Planned service | Planned location | Status |
|---|---|---|---|
| Container images | Artifact Registry | Montréal | Planned |
| Operator runtime | Cloud Run | Montréal | Planned |
| Judge runtime | Cloud Run | Montréal | Planned |
| Runtime-control database | Cloud SQL PostgreSQL | Montréal, regional HA | Planned |
| Private execution evidence | Cloud Storage regional bucket | Montréal | Planned |
| Sanitized judge receipts | Cloud Storage regional bucket | Montréal | Planned |
| Deployment receipts | Cloud Storage regional bucket | Montréal | Planned |
| Application secrets | Regional Secret Manager | Montréal | Planned |
| Encryption keys | Cloud KMS regional key ring | Montréal | Planned |
| Application logs | Cloud Logging regional bucket | Montréal | Planned |
| Build execution | Cloud Build regional endpoint | Montréal | Planned |
| Gemini inference | Vertex regional endpoint | Canada commitment requires exact per-model review | Blocked pending permit |
| Codex/ChatGPT processing | OpenAI services | Region not established as Canadian | Sanitized non-personal repository data only |
| Disaster-recovery copy | None | None | Toronto copy not authorized |

No row becomes **Created**, **Deployed**, or **Validated** without provider receipts.

---

## Incident Response

### Immediate containment

1. Activate the durable AIGC emergency stop.
2. Disable new builds and deployments.
3. Revoke affected human sessions and short-lived credentials.
4. Remove compromised invoker and IAM bindings.
5. Preserve regional logs, evidence generations and exact Git identifiers.
6. Do not delete or overwrite suspected evidence.
7. Classify whether any data or processing left the approved jurisdiction.

### Lost owner device

- revoke GitHub and Google sessions;
- remove the device from trusted-device lists;
- rotate affected passkeys or recovery credentials;
- verify no service-account key existed locally;
- review GitHub, IAM, Secret Manager and Cloud Audit Logs;
- retain incident evidence.

### Secret exposure

- disable the exact compromised secret version;
- issue a new regional version;
- update the authorization manifest;
- redeploy only after exact-head and authorization review;
- do not erase the evidence trail.

### Recovery

The proposed targets are RPO 15 minutes and RTO 4 hours. They are not claims until a controlled restore test records database, evidence, IAM, application readiness and integrity receipts.

---

## Recovery Plan

### Default recovery posture

- Primary region: Montréal (`northamerica-northeast1`).
- Cloud SQL: regional HA across zones.
- Evidence: versioned regional buckets with retention.
- Toronto disaster recovery: disabled.
- Non-Canadian failover: prohibited.

### Proposed objectives

```text
RPO=15 minutes
RTO=4 hours
```

### Required restore exercise

1. Select a reviewed Cloud SQL backup retained in Montréal.
2. Restore to an isolated staging instance in Montréal.
3. Validate schema and runtime-control invariants.
4. Resolve generation-pinned evidence without broad public access.
5. Deploy the admitted image digest privately.
6. Run non-generative readiness checks.
7. Verify emergency stop, rate limits, secrets and IAM.
8. Record timestamps, resources, hashes and final disposition.
9. Destroy the recovery exercise only after evidence review.

The exercise must not invoke Gemini without a separate one-use permit.
