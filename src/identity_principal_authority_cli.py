from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "core" / "identity" / "principal_authority_binding.py"
SPEC = importlib.util.spec_from_file_location("principal_authority_binding", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def fail(result: str, reason: str, detail: str | None = None) -> int:
    payload: dict[str, object] = {
        "result": result,
        "reason_codes": [reason],
        "external_action_performed": False,
    }
    if detail:
        payload["detail"] = detail
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a local synthetic AIGC principal-authority bundle."
    )
    parser.add_argument(
        "--bundle",
        required=True,
        help="Path to a repository-local synthetic authorization bundle",
    )
    parser.add_argument("--now", help="Optional ISO-8601 evaluation timestamp")
    args = parser.parse_args()

    path = Path(args.bundle).resolve()
    if ROOT not in path.parents:
        return fail("DENY", "BUNDLE_PATH_OUTSIDE_REPOSITORY")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return fail("DENY", "INVALID_BUNDLE", str(exc))

    now = datetime.now(timezone.utc)
    if args.now:
        try:
            now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        except ValueError:
            return fail("DENY", "INVALID_EVALUATION_TIME")

    try:
        decision = MODULE.PrincipalAuthorityBindingKernel().evaluate(
            request=value.get("request", {}),
            principals=value.get("principals", []),
            memberships=value.get("memberships", []),
            sessions=value.get("sessions", []),
            policies=value.get("policies", []),
            approvals=value.get("approvals", []),
            revocations=value.get("revocations", []),
            now=now,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        return fail("INDETERMINATE", "AUTHORITY_EVALUATION_FAILED", str(exc))

    print(json.dumps(decision.receipt, indent=2, sort_keys=True))
    return 0 if decision.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
