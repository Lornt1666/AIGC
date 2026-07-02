#!/usr/bin/env sh
set -eu

SOURCE="${1:-remoteok}"
LIMIT="${2:-10}"
python ./src/phase13_real_data_replay.py --source "$SOURCE" --limit "$LIMIT"
