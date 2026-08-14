from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.coordination.models import (
    CoordinationEngineeringReceipt,
    CoordinationEngineeringRequest,
)


def main() -> int:
    outputs = {
        ROOT / "schemas" / "aigc_coordination_engineering_request.schema.json": (
            CoordinationEngineeringRequest.model_json_schema()
        ),
        ROOT / "schemas" / "aigc_coordination_engineering_receipt.schema.json": (
            CoordinationEngineeringReceipt.model_json_schema()
        ),
    }
    for path, schema in outputs.items():
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
