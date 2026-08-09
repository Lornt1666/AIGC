from __future__ import annotations

from dataclasses import asdict
import json

from src.revenue_omega.sandbox_proof import run_sandbox_proof


def main() -> int:
    receipt = run_sandbox_proof()
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    return 0 if (
        receipt.status == "SANDBOX_SETTLED"
        and receipt.final_invoice_state == "SETTLED"
        and not receipt.network_call_performed
        and not receipt.real_money_moved
        and not receipt.external_action_performed
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
