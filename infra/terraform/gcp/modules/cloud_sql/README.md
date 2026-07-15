# AIGC Cloud SQL Staging Module

## Purpose

This module defines an isolated Cloud SQL for PostgreSQL staging foundation with private IP connectivity.

It creates:

- required Google APIs;
- a dedicated VPC network;
- a reserved private-services address range;
- a Service Networking peering connection;
- one Cloud SQL PostgreSQL instance;
- one application database;
- optional least-privilege runtime IAM bindings.

## Security posture

- Public IPv4 is disabled.
- Private services access is required.
- Encrypted transport is required by default.
- Automated backups and point-in-time recovery are enabled.
- Terraform and Google Cloud API deletion protection are enabled by default.
- Auto-grown disk-size drift is ignored so Terraform does not attempt to shrink storage.
- Query Insights does not record client addresses.
- IAM database authentication is enabled by default.
- PostgreSQL 16 is explicitly bound to the Enterprise edition for the shared-core staging tier.
- No `google_sql_user`, password, DSN, credential, or Secret Manager value is created or committed.

## Authority boundary

The root module instantiates this module only when all of the following are true:

```text
local.resource_creation_effective
AND environment == staging
AND cloud_sql_enabled
```

`local.resource_creation_effective` already requires the repository's exact-revision, immutable-artifact, release-gate, deployment-authorization, and resource-creation controls.

This module definition is infrastructure code, not authorization to apply it.

## Staging defaults

The default machine tier is deliberately small and zonal for a bounded staging environment. Review the edition, tier, availability type, disk size, retention, and budget before any authorized plan or apply.

A production or high-availability environment must be evaluated as a separate exact-revision infrastructure decision.
