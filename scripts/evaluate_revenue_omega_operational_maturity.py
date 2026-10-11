from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from src.revenue_omega.operational_maturity import evaluate_operational_maturity


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Evaluate Revenue-Ω operational maturity without external action.")
    parser.add_argument(
        "--input",
        type=Path,
        default=root / "config" / "revenue_omega_v1_operational_maturity.json",
    )
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError("dimensions must be an object")
    observed = {
        name: (
            str(value["observed_level"]),
            tuple(str(item) for item in value.get("evidence_refs", [])),
            str(value.get("blocker", "")),
        )
        for name, value in dimensions.items()
    }
    report = evaluate_operational_maturity(observed)
    output = {
        "candidate_branch": payload.get("candidate_branch"),
        "source_status": payload.get("status"),
        "weighted_score": report.weighted_score,
        "strict_score": report.strict_score,
        "complete": report.complete,
        "blockers": report.blockers,
        "dimensions": [asdict(item) for item in report.dimensions],
        "external_action_performed": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if report.complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
