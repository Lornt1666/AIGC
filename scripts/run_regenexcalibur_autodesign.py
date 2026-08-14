from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.autodesign import AutodesignRequest, run_shadow_autodesign_campaign


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the bounded RegenExcalibur self-autodesign shadow campaign"
    )
    parser.add_argument(
        "--request",
        type=Path,
        default=ROOT
        / "config"
        / "aigc_regenexcalibur_autodesign_request.v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "reports"
        / "artifacts"
        / "aigc_regenexcalibur_autodesign_shadow_campaign.json",
    )
    args = parser.parse_args()

    request = AutodesignRequest.model_validate_json(
        args.request.read_text(encoding="utf-8")
    )
    receipt = run_shadow_autodesign_campaign(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"{receipt['terminal_status']} iterations={len(receipt['iteration_receipts'])} "
        f"remaining={len(receipt['remaining_capabilities'])} "
        f"{receipt['receipt_sha256']}"
    )
    return 0 if receipt["zero_egress"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
