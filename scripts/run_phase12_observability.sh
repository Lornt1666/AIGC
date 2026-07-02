#!/usr/bin/env sh
set -eu

ROOT="${1:-.}"
python ./src/phase12_observability_dashboard.py --root "$ROOT" --export
