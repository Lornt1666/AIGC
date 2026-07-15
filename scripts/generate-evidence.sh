#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

for command_name in git python terraform; do
  command -v "$command_name" >/dev/null 2>&1 \
    || fail "Required command is unavailable: $command_name"
done

REVISION="$(git rev-parse HEAD)"
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] \
  || fail "Evidence generation requires an exact 40-character Git revision"

if [[ -n "$(git status --porcelain)" ]]; then
  fail "Evidence generation requires a clean working tree"
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_ROOT="${1:-reports/artifacts/local_ci_evidence/${REVISION}/${STAMP}}"
OUTPUT_ROOT="$(python - "$OUTPUT_ROOT" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
)"

CURRENT_STAGE="initialization"
mkdir -p \
  "$OUTPUT_ROOT/provider_discovery_simulation" \
  "$OUTPUT_ROOT/terraform_validation" \
  "$OUTPUT_ROOT/test_results" \
  "$OUTPUT_ROOT/production_readiness" \
  "$OUTPUT_ROOT/logs"

write_run_status() {
  local exit_code="$1"
  python - "$OUTPUT_ROOT/run-status.json" "$REVISION" "$CURRENT_STAGE" "$exit_code" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

path = Path(sys.argv[1])
payload = {
    "contract_id": "AIGC-LOCAL-CI-EVIDENCE-RUN-001",
    "source_revision": sys.argv[2],
    "last_stage": sys.argv[3],
    "exit_code": int(sys.argv[4]),
    "result": "COMPLETE" if int(sys.argv[4]) == 0 else "FAILED_CLOSED",
    "hosted_ci_replacement": False,
    "operator_review_required": True,
    "provider_action_performed": False,
    "terraform_apply_performed": False,
    "external_action_performed": False,
    "recorded_at": datetime.now(timezone.utc).isoformat(),
}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

on_exit() {
  local status="$?"
  write_run_status "$status"
  exit "$status"
}
trap on_exit EXIT

python - "$OUTPUT_ROOT/evidence-context.json" "$REVISION" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "contract_id": "AIGC-LOCAL-CI-EVIDENCE-CONTEXT-001",
            "source_revision": sys.argv[2],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "LOCAL_SUPPLEMENTAL_FAIL_CLOSED",
            "hosted_ci_replacement": False,
            "operator_review_required": True,
            "provider_action_performed": False,
            "terraform_apply_performed": False,
            "external_action_performed": False,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY

CURRENT_STAGE="contract_validation"
python src/aigc.py validate \
  2>&1 | tee "$OUTPUT_ROOT/logs/contract-validation.log"

CURRENT_STAGE="aec_001_validation"
python src/validate_aec_001.py \
  2>&1 | tee "$OUTPUT_ROOT/logs/aec-001-validation.log"

CURRENT_STAGE="redaction_scan"
python src/security/redaction_scanner.py \
  --paths src scripts config docs governance README.md AGENTS.md \
  AIGC_MASTER_PROMPT.md OMEGA_X_CONSTITUTION.md schemas tests reports \
  Dockerfile render.yaml fly.toml Procfile \
  2>&1 | tee "$OUTPUT_ROOT/logs/redaction-scan.log"

CURRENT_STAGE="provider_discovery_mock"
python scripts/run_provider_discovery_mock.py \
  --repository-revision "$REVISION" \
  --output-dir "$OUTPUT_ROOT/provider_discovery_simulation" \
  2>&1 | tee "$OUTPUT_ROOT/logs/provider-discovery-mock.log"

CURRENT_STAGE="terraform_validation"
export GOOGLE_OAUTH_ACCESS_TOKEN="aigc-offline-inert-plan-no-provider-action"
TERRAFORM_ROOT="infra/terraform/gcp"
PLAN_PATH="$OUTPUT_ROOT/terraform_validation/aigc-staging-inert.tfplan"
PLAN_JSON="$OUTPUT_ROOT/terraform_validation/inert-plan.json"

terraform -chdir="$TERRAFORM_ROOT" fmt -check -recursive \
  2>&1 | tee "$OUTPUT_ROOT/terraform_validation/terraform-fmt.log"
terraform -chdir="$TERRAFORM_ROOT" init -backend=false -input=false \
  2>&1 | tee "$OUTPUT_ROOT/terraform_validation/terraform-init.log"
cp "$TERRAFORM_ROOT/.terraform.lock.hcl" \
  "$OUTPUT_ROOT/terraform_validation/terraform.lock.hcl"
terraform -chdir="$TERRAFORM_ROOT" validate \
  2>&1 | tee "$OUTPUT_ROOT/terraform_validation/terraform-validate.log"
terraform -chdir="$TERRAFORM_ROOT" plan \
  -input=false \
  -lock=false \
  -refresh=false \
  -var-file=staging.tfvars.example \
  -out="$PLAN_PATH" \
  2>&1 | tee "$OUTPUT_ROOT/terraform_validation/terraform-plan.log"
terraform -chdir="$TERRAFORM_ROOT" show -json "$PLAN_PATH" > "$PLAN_JSON"

python - "$PLAN_JSON" "$OUTPUT_ROOT/terraform_validation/inert-plan-summary.json" <<'PY'
from pathlib import Path
import json
import sys

plan_path = Path(sys.argv[1])
summary_path = Path(sys.argv[2])
plan = json.loads(plan_path.read_text(encoding="utf-8"))
changes = plan.get("resource_changes") or []
if changes:
    addresses = [str(item.get("address", "unknown")) for item in changes]
    raise SystemExit(
        "Inert Terraform plan unexpectedly contains resource changes: "
        + ", ".join(addresses)
    )
summary_path.write_text(
    json.dumps(
        {
            "resource_change_count": 0,
            "provider_action_performed": False,
            "terraform_apply_performed": False,
            "external_action_performed": False,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY

CURRENT_STAGE="test_suite"
python -m pytest \
  2>&1 | tee "$OUTPUT_ROOT/test_results/pytest.log"

CURRENT_STAGE="production_readiness"
python src/aigc.py readiness \
  --artifact-root "$OUTPUT_ROOT/production_readiness" \
  2>&1 | tee "$OUTPUT_ROOT/logs/production-readiness.log"

CURRENT_STAGE="evidence_manifest"
python - "$OUTPUT_ROOT" "$REVISION" <<'PY'
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import sys

root = Path(sys.argv[1])
entries = []
for path in sorted(root.rglob("*")):
    if not path.is_file() or path.name == "evidence-manifest.json":
        continue
    entries.append(
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
    )
manifest = {
    "contract_id": "AIGC-LOCAL-CI-EVIDENCE-MANIFEST-001",
    "source_revision": sys.argv[2],
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "artifact_count": len(entries),
    "artifacts": entries,
    "hosted_ci_replacement": False,
    "operator_review_required": True,
    "provider_action_performed": False,
    "terraform_apply_performed": False,
    "external_action_performed": False,
}
(root / "evidence-manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

CURRENT_STAGE="complete"
printf 'Local supplemental evidence generated at:\n%s\n' "$OUTPUT_ROOT"
printf 'This bundle does not replace a successful hosted GitHub Actions run.\n'
