from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from src.apex_completion.authorization_reconstruction import reconstruct_authorization_register


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Reconstruct current AIGC authorization state from historical packets.")
    parser.add_argument(
        "--source",
        type=Path,
        default=root / "data" / "phase5_authorizations" / "aigc_phase5_authorization_packets.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--now", default="")
    args = parser.parse_args()

    payload = json.loads(args.source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("authorization source must contain a JSON list")
    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(timezone.utc)
        if args.now
        else datetime.now(timezone.utc)
    )
    report = reconstruct_authorization_register(payload, now=now)
    output = {
        "generated_at": now.isoformat(),
        "source": str(args.source),
        "total_records": report.total_records,
        "unique_action_ids": report.unique_action_ids,
        "current_authority_count": report.current_authority_count,
        "historical_or_expired_count": report.historical_or_expired_count,
        "invalid_count": report.invalid_count,
        "duplicate_action_ids": report.duplicate_action_ids,
        "records": [asdict(item) for item in report.records],
        "external_action_performed": False,
        "authority_granted_by_reconstruction": False,
    }
    encoded = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if report.invalid_count == 0 and not report.duplicate_action_ids else 2


if __name__ == "__main__":
    raise SystemExit(main())
