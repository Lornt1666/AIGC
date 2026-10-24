#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT_DIR"
TIMEOUT_SECONDS=60
POLL_SECONDS=2
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }
info() { printf '[INFO] %s\n' "$*"; }
pass() { printf '[PASS] %s\n' "$*"; }

command -v docker >/dev/null 2>&1 || fail 'docker is required.'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose plugin is required.'
[ -f .env ] || cp .env.example .env
if grep -q 'replace-this-local-password' .env || grep -q 'replace-this-local-operator-token' .env; then
  command -v openssl >/dev/null 2>&1 || fail 'openssl is required to generate local development secrets.'
  if grep -q 'replace-this-local-password' .env; then value="$(openssl rand -hex 32)"; sed "s/replace-this-local-password/$value/" .env > .env.tmp; mv .env.tmp .env; fi
  if grep -q 'replace-this-local-operator-token' .env; then value="$(openssl rand -hex 32)"; sed "s/replace-this-local-operator-token/$value/" .env > .env.tmp; mv .env.tmp .env; fi
fi
chmod 600 .env
info 'Building and starting isolated containers.'
docker compose --env-file .env up --build -d

deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))
while :; do
  states="$(docker compose --env-file .env ps --format json 2>/dev/null || true)"
  if printf '%s' "$states" | grep -q '"Service":"api"' && printf '%s' "$states" | grep '"Service":"api"' | grep -q '"Health":"healthy"' && printf '%s' "$states" | grep -q '"Service":"postgres"' && printf '%s' "$states" | grep '"Service":"postgres"' | grep -q '"Health":"healthy"'; then break; fi
  if [ "$(date +%s)" -ge "$deadline" ]; then docker compose --env-file .env ps; docker compose --env-file .env logs --tail=100 api postgres; fail "Container readiness timed out after ${TIMEOUT_SECONDS}s."; fi
  sleep "$POLL_SECONDS"
done
pass 'API and PostgreSQL health probes are green.'

# DDL migrations are idempotent and are applied in lexical order.
for migration in migrations/command_center_postgresql/*.sql; do
  [ -f "$migration" ] || continue
  info "Applying $migration"
  docker compose --env-file .env exec -T postgres sh -ec 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$migration"
done
# Record bootstrap provenance without seeding fake business records.
docker compose --env-file .env exec -T postgres sh -ec 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
CREATE TABLE IF NOT EXISTS aigc_bootstrap_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO aigc_bootstrap_metadata(key, value) VALUES ('schema_bootstrap', 'containerized-local-v1')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now();
SQL
pass 'Migrations and idempotent bootstrap metadata seed completed.'

set -a
. ./.env
set +a
BASE_URL="http://127.0.0.1:${AIGC_PORT:-8000}"
python3 - "$BASE_URL" "$AIGC_COMMAND_CENTER_TOKEN" <<'PY'
import json, sys, time, urllib.request
base, token = sys.argv[1:3]
def request(path, method='GET', body=None, key=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
    if key: headers['Idempotency-Key'] = key
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as response: return json.load(response)
health = request('/readyz')
assert health.get('ok') is True, health
created = request('/api/run', 'POST', {}, 'bootstrap-' + str(time.time_ns()))
assert created.get('run_id') and created.get('status_url'), created
run_id = created['run_id']
deadline = time.monotonic() + 45
last = None
while time.monotonic() < deadline:
    last = request('/api/run/' + run_id)
    if last.get('status') in {'completed', 'failed', 'timed_out', 'unknown'}: break
    time.sleep(1)
assert last is not None and last.get('run_id') == run_id, last
assert last.get('status') == 'completed', {'run_failed_or_unverified': last}
readback = request('/api/run/' + run_id)
assert readback.get('run_id') == run_id and readback.get('status') == last.get('status'), (last, readback)
print(json.dumps({'ready': health, 'run_id': run_id, 'terminal_status': last['status'], 'readback_consistent': True}))
PY
pass 'Synthetic authenticated API transaction and durable status read-back passed.'
printf '\nAIGC container bootstrap: PASS\nAPI: %s\nHealth: %s/health\nReadiness: %s/readyz\n' "$BASE_URL" "$BASE_URL" "$BASE_URL"
printf 'Disposition: local development only; production readiness is not asserted.\n'
