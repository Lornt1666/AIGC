# AIGC dead-letter ledger deployment and recovery

## Purpose and invariants

The PostgreSQL `aigc_dead_letters` table is the durable disposition ledger. Redis Streams is a projection for operations and consumers, not the sole audit record. A source entry must not be acknowledged until its disposition is committed in PostgreSQL and the deduplicated Redis dead-letter projection is confirmed.

The disposition identity is stable for a source stream and stream entry ID. Redis Lua performs the deduplication marker and `XADD` atomically. A process crash between projection and source acknowledgement can therefore retry the projection without creating another dead-letter entry, provided the Redis keyspace containing the marker survives.

## Deploy on a fresh database

The Compose PostgreSQL initialization mounts `core/migrations/003_dead_letters.sql` as `/docker-entrypoint-initdb.d/04-dead-letters.sql`. This initialization script runs automatically only when PostgreSQL initializes a new data directory.

## Apply to an existing database

Do not assume that adding a file under `docker-entrypoint-initdb.d` migrates an existing volume. Back up PostgreSQL first, then apply the mounted migration explicitly:

```sh
docker compose exec -T postgres pg_dump --username aigc --dbname aigc --format=custom > aigc-before-003-dead-letters.dump
docker compose exec -T postgres psql --set ON_ERROR_STOP=1 --username aigc --dbname aigc --file /docker-entrypoint-initdb.d/04-dead-letters.sql
docker compose exec -T postgres psql --set ON_ERROR_STOP=1 --username aigc --dbname aigc --command "SELECT version FROM aigc_schema_migrations WHERE version = '003_dead_letters';"
docker compose exec -T postgres psql --set ON_ERROR_STOP=1 --username aigc --dbname aigc --command "SELECT to_regclass('public.aigc_dead_letters');"
```

Expected results: one migration marker row and relation `aigc_dead_letters`. If either check fails, stop rollout and inspect the migration error before restarting services.

## Restart and verify

```sh
docker compose up -d --build app worker
docker compose ps
docker compose logs --tail=200 app worker
docker compose exec -T postgres psql --set ON_ERROR_STOP=1 --username aigc --dbname aigc --command "SELECT count(*) AS dispositions, count(*) FILTER (WHERE published_at IS NULL) AS not_projected FROM aigc_dead_letters;"
```

A nonzero `not_projected` count requires investigation. Do not manually delete ledger rows or Redis pending entries to make the count zero.

## Crash-recovery expectations

- Crash before PostgreSQL commit: the Redis source entry remains pending and can be retried.
- Crash after PostgreSQL commit but before Redis projection: retry reuses the stable PostgreSQL disposition identity and publishes the projection.
- Crash after Redis projection but before PostgreSQL projection receipt or source acknowledgement: the Lua marker returns the existing Redis entry ID; retry completes the receipt and acknowledgement.
- PostgreSQL unavailable: fail closed; do not acknowledge the source entry.
- Redis marker/keyspace lost or restored from an inconsistent backup: reconcile the PostgreSQL ledger against the Redis dead-letter stream before resuming consumers. The atomic deduplication guarantee applies only while the marker key survives.
- Dead-lettered entries are for manual review; dead-lettering is not permission to retry the original side effect automatically.

## Production gate

This runbook does not itself establish production readiness. Require passing CI for the exact deployed commit, integration tests against real PostgreSQL and Redis, crash-injection coverage for each boundary above, backup/restore evidence, alerting for pending ledger rows and Redis pending-entry growth, and independent review. Keep release blocked until the repository's designated release authority records acceptance against the exact commit and evidence digest.
