"""Fixed JSON bridge between portable MCP hosts and the governed AIGC core."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from typing import Any, Literal

from src.integrations.mcp.tools import (
    get_aigc_status,
    plan_aigc_llm_lifecycle,
    plan_aigc_wealth_work,
    seed_aigc_regenexcalibur_universe,
)
from src.operations.employer_sandbox import run_employer_sandbox


BridgeOperation = Literal[
    "aigc_get_status",
    "aigc_render_control_center",
    "aigc_run_employer_sandbox",
    "aigc_seed_regenexcalibur_universe",
    "aigc_plan_wealth_work",
    "aigc_plan_llm_lifecycle",
]


def aigc_get_status() -> dict[str, object]:
    return {
        **get_aigc_status(),
        "plugin": {
            "transport": "stdio_or_streamable_http",
            "streamable_http_path": "/mcp",
            "host_validation": "NOT_PERFORMED",
            "public_deployment": "NOT_PERFORMED",
        },
    }


def aigc_render_control_center() -> dict[str, object]:
    status = aigc_get_status()
    return {
        "schema_version": "aigc.control-center.v1",
        "title": "AIGC Control Center",
        "summary": status["system"],
        "readiness": status["readiness"],
        "connectors": status["connectors"],
        "wealth_operator": status["wealth_operator"],
        "available_actions": [
            "inspect_status",
            "run_zero_egress_employer_sandbox",
            "seed_zero_egress_regenexcalibur_universe",
            "plan_governed_wealth_work",
            "plan_governed_llm_lifecycle",
        ],
        "blocked_actions": [
            "external_provider_call",
            "external_message",
            "application_submission",
            "cloud_mutation",
            "production_activation",
            "application_submission",
            "contract_acceptance",
            "invoice_send",
            "financial_transaction",
            "funds_transfer",
            "trade_execution",
        ],
        "widget_required": False,
        "authority_granted": False,
        "external_action_performed": False,
    }


def dispatch_bridge_request(request: Mapping[str, Any]) -> dict[str, object]:
    allowed_keys = {"operation", "arguments"}
    unknown = sorted(set(request).difference(allowed_keys))
    if unknown:
        raise ValueError(f"unknown bridge request fields: {', '.join(unknown)}")
    operation = request.get("operation")
    arguments = request.get("arguments", {})
    if not isinstance(arguments, Mapping):
        raise ValueError("bridge arguments must be an object")
    if operation == "aigc_get_status":
        if arguments:
            raise ValueError("aigc_get_status accepts no arguments")
        return aigc_get_status()
    if operation == "aigc_render_control_center":
        if arguments:
            raise ValueError("aigc_render_control_center accepts no arguments")
        return aigc_render_control_center()
    if operation == "aigc_run_employer_sandbox":
        permitted = {"mode", "pack_id", "capability_id", "scenario"}
        extra = sorted(set(arguments).difference(permitted))
        if extra:
            raise ValueError(f"unknown employer sandbox fields: {', '.join(extra)}")
        return run_employer_sandbox(**dict(arguments))
    if operation == "aigc_seed_regenexcalibur_universe":
        permitted = {"requested_evolution_depth"}
        extra = sorted(set(arguments).difference(permitted))
        if extra:
            raise ValueError(f"unknown RegenExcalibur fields: {', '.join(extra)}")
        return seed_aigc_regenexcalibur_universe(**dict(arguments))
    if operation == "aigc_plan_wealth_work":
        permitted = {
            "request_id",
            "action",
            "objective",
            "target_ref",
            "financial_amount_cad",
            "evidence_refs",
        }
        extra = sorted(set(arguments).difference(permitted))
        if extra:
            raise ValueError(f"unknown wealth work fields: {', '.join(extra)}")
        return plan_aigc_wealth_work(**dict(arguments))
    if operation == "aigc_plan_llm_lifecycle":
        if arguments:
            raise ValueError("aigc_plan_llm_lifecycle accepts no arguments")
        return plan_aigc_llm_lifecycle()
    raise ValueError("unknown bridge operation")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one fixed AIGC plugin bridge request")
    parser.add_argument("--request", help="JSON request; stdin is used when omitted")
    args = parser.parse_args(argv)
    raw = args.request if args.request is not None else sys.stdin.read()
    response = dispatch_bridge_request(json.loads(raw))
    print(json.dumps(response, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
