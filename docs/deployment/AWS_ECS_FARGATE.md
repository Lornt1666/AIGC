# AWS ECS Fargate Development Hosting Runbook

**Status:** planning/runbook only. This document does not provision AWS resources, configure DNS, deploy a container, or authorize production traffic.

## Release gate

Do **not** route public traffic to the AIGC Command Center until the blockers in [issue #275](https://github.com/Lornt1666/AIGC/issues/275) and the durable-state acceptance evidence in [issue #282](https://github.com/Lornt1666/AIGC/issues/282) are complete. The current candidate contains bounded run admission, subprocess timeouts, sanitized/truncated output, consistent pending-review guards, and PostgreSQL-backed state/idempotency/lease recovery. Those code controls do not themselves prove that RDS is provisioned, migrations are applied, TLS/IAM are configured, browser identity is correct, or an end-to-end deployed service works.

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
1. Close the browser identity/session and protected-route acceptance tests in issue #275.
2. Provision private RDS PostgreSQL, apply migration 003 using a separate migration role, and inject `AIGC_COMMAND_CENTER_STATE_DSN` from Secrets Manager with `sslmode=verify-full` and an explicit mounted `sslrootcert`.
3. Verify `/ready` reports durable PostgreSQL schema version 3; production must fail readiness without the DSN, verified TLS, or migration.
4. Exercise idempotent run creation, cross-instance active-run admission, review-decision claims, lease expiry to explicit `unknown`, and restart recovery against the deployed service.
5. Enforce the same expiry, pending-state, authorization, and race-safety rules in the canonical command layer for accept/deny/revise.
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

## Durable state configuration and migration

Production must set `AIGC_ENV=production` and inject `AIGC_COMMAND_CENTER_STATE_DSN` from AWS Secrets Manager. The DSN must use `sslmode=verify-full` and an explicit `sslrootcert` path to the mounted AWS RDS CA bundle. The application fails readiness closed when durable storage is missing or migration 003 is absent. Do not let the application role create schemas; apply `migrations/003_command_center_state.sql` with a separate least-privilege migration identity before deployment. Restrict RDS to private subnets and the ECS task security group; enable encryption, backups/PITR, monitoring, and connection limits. The current pool allows up to eight connections per task, so size RDS and ECS task counts together.

After deployment, send an `Idempotency-Key` header with each `POST /api/run` and review decision request. Reuse the same key only for a retry of the same request. If a lease expires, the run/review is recorded as `unknown`; do not retry it under a new key until an operator reconciles the packet/files and database record. Example read-only audit queries:

```sql
SELECT run_id, status, current_step, created_at, updated_at
  FROM command_center_runs WHERE status = 'unknown' ORDER BY updated_at DESC;
SELECT action_id, decision, state, created_at, updated_at
  FROM command_center_review_decisions WHERE state = 'unknown' ORDER BY updated_at DESC;
```

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
