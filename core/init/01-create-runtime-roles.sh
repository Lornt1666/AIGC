#!/bin/sh
set -eu
: "${AIGC_APP_DB_PASSWORD:?AIGC_APP_DB_PASSWORD must be set to a URL-safe generated secret}"
: "${AIGC_RECEIPT_DB_PASSWORD:?AIGC_RECEIPT_DB_PASSWORD must be set to a separate URL-safe generated secret}"
case "$AIGC_APP_DB_PASSWORD" in *[!a-fA-F0-9]*) echo 'AIGC_APP_DB_PASSWORD must be hex-only (openssl rand -hex 32)' >&2; exit 1;; esac
case "$AIGC_RECEIPT_DB_PASSWORD" in *[!a-fA-F0-9]*) echo 'AIGC_RECEIPT_DB_PASSWORD must be hex-only (openssl rand -hex 32)' >&2; exit 1;; esac
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE aigc_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE aigc_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD '$AIGC_APP_DB_PASSWORD';
CREATE ROLE aigc_receipt_verifier LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD '$AIGC_RECEIPT_DB_PASSWORD';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO aigc_owner;
SQL
