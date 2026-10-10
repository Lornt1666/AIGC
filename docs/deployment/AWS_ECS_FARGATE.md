# AWS ECS Fargate Development Hosting Runbook

**Status:** planning/runbook only. This document does not provision AWS resources, configure DNS, deploy a container, or authorize production traffic.

## Release gate

Do **not** route public traffic to the AIGC Command Center until the remaining blockers in [issue #275](https://github.com/Lornt1666/AIGC/issues/275) and canonical packet/evidence persistence in [issue #282](https://github.com/Lornt1666/AIGC/issues/282) are closed with test evidence. Current main includes a PostgreSQL run/review ledger, actor-scoped idempotency, unknown-outcome handling, versioned run reconciliation, subprocess timeouts, bounded output redaction, and consistent review guards. These controls do not make the repository workspace or authorization/evidence files shared and durable, and do not prove browser identity, AWS configuration, or a live deployment.

## Target topology

- GitHub Actions builds and tests a container from an exact source commit.
- GitHub OIDC assumes a narrowly scoped AWS deployment role; no long-lived AWS access key in GitHub secrets.
- Amazon ECR stores an immutable image reference; deploy by image digest, not a mutable tag.
- ECS Fargate runs tasks in private subnets with **no public IP**.
- An internet-facing Application Load Balancer is the only public ingress, with HTTPS enforced and a certificate managed by ACM.
- The task security group accepts application traffic only from the ALB security group.
- Use a real identity/session boundary for browser users. Do not expose a shared operator token to browser JavaScript or rely on a public long-lived bearer token.
- AWS Secrets Manager holds runtime secrets; task role permissions are least-privilege and separate from the task execution role.
- CloudWatch logs have explicit retention, access controls, and redaction. Never log secrets, approval phrases, or unfiltered subprocess output.
- Configure budget/cost alerts before enabling tasks or ALB resources.

## Ordered implementation plan

### Gate 0 — account and ownership
1. Confirm the intended AWS account ID, deployment region, billing owner, domain/DNS owner, and an authorized AWS administrator.
2. Establish a dedicated non-production environment/account where feasible.
3. Confirm the budget threshold and who receives cost alerts.
4. Do not put credentials, session tokens, account secrets, or private keys in this repository or in chat.

### Gate 1 — application blockers
1. Close browser identity/session and protected-route acceptance tests in issue #275.
2. Externalize canonical authorization packets and phase/evidence outputs from task-local `PROJECT_ROOT` to durable shared storage with immutable/versioned references and idempotent writes; keep #282 open until verified.
3. Provision private RDS PostgreSQL, apply `migrations/command_center_postgresql/0001_durable_command_center.sql` with a separate migration identity, and grant the runtime role only required table privileges.
4. Inject `AIGC_COMMAND_CENTER_DATABASE_URL` from Secrets Manager, set `AIGC_COMMAND_CENTER_DB_SSLMODE=verify-full`, and mount the RDS CA bundle at `AIGC_COMMAND_CENTER_DB_SSLROOTCERT`. Production store initialization fails closed without verified TLS and an existing CA-bundle file.
5. Verify `/readyz` reports durable PostgreSQL readiness; test idempotency, two-instance claims, stale-run recovery, and exact-version reconciliation on the deployed service.
6. Replace shared-token-only browser auth with an approved identity/session boundary and test every protected route.
7. Run as non-root, pin dependencies through a reviewed lockfile/hash strategy, scan the image, and test filesystem/runtime restrictions.

### Gate 2 — CI and image provenance
1. Run tests, schema/contract validation, redaction scanning, and dependency/security checks on the exact candidate commit.
2. Build the image once and record source SHA, workflow run, test evidence, image digest, and scanner results.
3. Push to ECR with immutable tags enabled; promote the exact digest rather than rebuilding for another environment.
4. Use OIDC with a narrowly scoped role and restrict deployment to protected branches/environments. Do not grant wildcard administrative permissions.

### Gate 3 — AWS network and identity
1. Create VPC/private subnets and the ALB-facing public subnets; attach appropriate routing and security groups.
2. Create an HTTPS ALB listener using an ACM certificate. Redirect HTTP to HTTPS; do not expose the task port directly.
3. Configure ECS Fargate tasks in private subnets with no public IP. Permit inbound application traffic only from the ALB security group.
4. Separate ECS task execution permissions (image pull/log delivery/secret injection as required) from the application task role.
5. Store only required runtime secrets in Secrets Manager and scope access to the exact secret ARNs.
6. Configure CloudWatch log groups, retention, alarms, health checks, and cost/budget alerts before service launch.

### Gate 4 — controlled deployment and evidence
1. Deploy first to a non-production service with desired count and scaling limits explicitly bounded.
2. Keep business-cycle execution and all external write connectors disabled. A hosting deployment does not authorize business actions.
3. Verify the service health/readiness behavior, HTTPS certificate/redirect, authentication, authorization on every protected route, and absence of direct task ingress.
4. Test restart recovery, durable evidence lineage, duplicate requests, run timeouts, cancellation, output redaction, and emergency-stop behavior.
5. Capture a deployment receipt containing source SHA, image digest, AWS account/region, ECS service/task definition revision, endpoint identity, test results, timestamp, rollback target, and operator approval reference. Never include secret values.
6. Do not enable public traffic or production promotion until all gates have explicit evidence and an authorized human approves the release.

## Durable state configuration and remaining boundary

Production uses `AIGC_COMMAND_CENTER_DATABASE_URL`, `AIGC_COMMAND_CENTER_DB_SSLMODE=verify-full`, and `AIGC_COMMAND_CENTER_DB_SSLROOTCERT` pointing to a mounted AWS RDS CA bundle. The schema is `migrations/command_center_postgresql/0001_durable_command_center.sql`; apply it with a controlled migration role before deploying application tasks. Grant the runtime role only `SELECT` on run/review records and the required `INSERT`/`UPDATE` privileges; do not grant schema creation or `TRUNCATE`. The PostgreSQL pool is capped at five connections per task, so size RDS and ECS task counts together.

The ledger protects run/review decisions, but canonical authorization packets and generated artifacts remain file-based under `PROJECT_ROOT`; they are not shared or durable across replacement ECS tasks. Keep public business-cycle execution disabled until those files and evidence references are externalized, browser identity/session tests pass, and the live service has an approved deployment receipt.

## Rollback criteria

Roll back to the last known-good immutable image digest and service/task-definition revision if authentication or authorization fails, health checks regress, evidence/state is lost, unexpected external actions occur, resource usage exceeds the approved limit, or secret material appears in logs/responses. Preserve incident evidence, stop further promotion, and follow the repository incident-response process.

## Required deployment receipt fields

- Environment: development / staging / production
- Source commit SHA and GitHub Actions run URL
- Image repository and immutable image digest
- AWS account ID and region
- ECS cluster/service and task-definition revision
- ALB/endpoint identity and TLS validation result
- Authentication and protected-route test results
- Persistence/restart and idempotency test results
- Secret/log redaction scan results
- Deployment timestamp and operator approval reference
- Rollback image digest/revision and decision

## Current state

No AWS account connection or authorized provisioning session was available when this runbook was authored. No AWS resources have been created, no image has been pushed, and no live endpoint has been verified.
