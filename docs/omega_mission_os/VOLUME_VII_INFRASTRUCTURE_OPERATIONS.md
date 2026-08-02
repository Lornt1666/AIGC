# Volume VII — Infrastructure, Deployment, Operations, and Recovery

## Scope

Coordinate the existing Infrastructure Plane without granting Mission OS direct infrastructure authority.

## Environment model

Separate local development, synthetic test, read-only replay, isolated staging, judge/read-only demonstration, and production environments. Credentials, identities, data, networks, services, and evidence stores remain environment-scoped.

## Deployment sequence

`PLAN -> VALIDATE -> AUTHORIZE_PLAN -> BUILD -> DIGEST -> AUTHORIZE_APPLY -> DEPLOY_NO_TRAFFIC -> VERIFY -> CONTROLLED_CANARY -> EVIDENCE -> TRAFFIC_DECISION -> MONITOR`

Every apply or deployment is bound to exact source revision, immutable image digest, infrastructure plan digest, identity, region, time window, and rollback target.

## Operations

Define service-level objectives, readiness and liveness checks, observability, budget alerts, quotas, backup, restore, disaster recovery, model/provider emergency stop, and dependency degradation behavior.

Toronto remains the primary target geography and Montréal the recovery target unless a later governed architecture decision changes the baseline.

## Recovery

Recovery plans identify recovery time and recovery point objectives, backup provenance, restoration steps, authority, communications, and evidence requirements. A recovery claim requires a completed drill or real recovery receipt.

## Acceptance criteria

Implementation requires inert-plan validation, immutable artifact receipts, no-traffic candidate deployment, one-run canary permits, readiness evidence, rollback testing, backup/restore drills, and proof that production cannot be promoted by documentation or projected readiness alone.