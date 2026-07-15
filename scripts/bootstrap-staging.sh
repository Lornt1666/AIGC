#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || fail "git is required"
command -v python >/dev/null 2>&1 || fail "python is required"

REVISION="$(git rev-parse HEAD)"
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] \
  || fail "Could not bind execution to an exact Git revision"

[[ -z "$(git status --porcelain)" ]] \
  || fail "A clean working tree is required"

DISCOVERY_RUNNER="scripts/run_provider_discovery_mock.py"
[[ -f "$DISCOVERY_RUNNER" ]] \
  || fail "Provider-discovery runner is absent. PR #112 must be admitted first."

OUTPUT_ROOT="artifacts/staging_bootstrap/${REVISION}"
DISCOVERY_OUTPUT="${OUTPUT_ROOT}/provider_discovery"
mkdir -p "$DISCOVERY_OUTPUT"

echo "=== AIGC Staging Preparation ==="
echo "Revision: ${REVISION}"
echo "Mode: MOCK_ONLY"
echo "External actions: disabled"

echo "[1/4] Validating repository contracts"
python src/aigc.py validate

echo "[2/4] Running mock-only provider discovery"
python "$DISCOVERY_RUNNER" \
  --repository-revision "$REVISION" \
  --output-dir "$DISCOVERY_OUTPUT"

echo "[3/4] Evaluating the generated target specification"
python - "$REVISION" "$OUTPUT_ROOT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

from src.core.staging_procurement_evaluator import evaluate_staging_procurement

revision = sys.argv[1]
output_root = Path(sys.argv[2])
discovery_root = output_root / "provider_discovery"
pack_path = discovery_root / "target_specification_submission.json"
if not pack_path.exists():
    raise SystemExit(f"Missing generated pack: {pack_path}")

pack = json.loads(pack_path.read_text(encoding="utf-8"))
evaluation = evaluate_staging_procurement(
    procurement_pack=pack,
    exact_revision=revision,
)

evaluation_path = output_root / "staging_procurement_evaluation.json"
evaluation_path.write_text(
    json.dumps(evaluation, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

summary = {
    "exact_revision": revision,
    "pack_status": evaluation["pack_status"],
    "target_specification_complete": evaluation["target_specification_complete"],
    "discovery_authorization_effective": (
        evaluation["discovery_authorization_effective"]
    ),
    "discovery_evidence_accepted": evaluation["discovery_evidence_accepted"],
    "ready_for_operator_review": evaluation["ready_for_operator_review"],
    "next_gate": "PROVIDER_DISCOVERY_AUTHORIZATION",
    "external_action_performed": False,
}
summary_path = output_root / "preparation_summary.json"
summary_path.write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(json.dumps(summary, indent=2))
PY

echo "[4/4] Evaluating canonical production readiness"
python src/aigc.py readiness

cat <<EOF

Preparation completed safely.

Artifacts:
  ${OUTPUT_ROOT}

No provider read, Terraform apply, identity configuration,
secret access, resource creation, or external action occurred.

Next required gate:
  Exact-revision provider-discovery authorization.

EOF
