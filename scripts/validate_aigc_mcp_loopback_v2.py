#!/usr/bin/env python3
"""Produce a deterministic local MCP-over-HTTP contract receipt.

The check uses an in-process loopback ASGI client. It does not bind a public
socket, call a provider, use credentials, or validate a ChatGPT/Gemini host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.epistemic.canonicalization import canonical_sha256
from src.integrations.mcp.server import build_mcp_server


DEFAULT_OUTPUT = ROOT / "reports/artifacts/aigc_mcp_loopback_local_validation_v2.json"
SOURCE_PATHS = (
    "src/integrations/mcp/server.py",
    "src/integrations/mcp/tools.py",
    "src/operations/employer_sandbox.py",
)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_receipt() -> dict[str, object]:
    app = build_mcp_server(host="127.0.0.1", port=8000).streamable_http_app()
    headers = {"Accept": "application/json, text/event-stream"}
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        initialized = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "aigc-evidence", "version": "2"},
                },
            },
        )
        listed = client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        called = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "aigc_run_employer_sandbox",
                    "arguments": {"mode": "sandbox"},
                },
            },
        )

    initialize_body = initialized.json()
    list_body = listed.json()
    call_body = called.json()
    tools = sorted(list_body.get("result", {}).get("tools", []), key=lambda item: item["name"])
    structured = call_body.get("result", {}).get("structuredContent", {})
    annotations_valid = all(
        item.get("annotations")
        == {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
        for item in tools
    )
    statuses = {
        "initialize": initialized.status_code == 200
        and initialize_body.get("result", {}).get("serverInfo", {}).get("name")
        == "aigc-nexus",
        "tools_list": listed.status_code == 200 and len(tools) > 0,
        "tool_call": called.status_code == 200
        and call_body.get("result", {}).get("isError") is False
        and structured.get("terminal_status") == "PASS",
        "read_only_annotations": annotations_valid,
    }
    receipt: dict[str, object] = {
        "schema_version": "aigc.mcp-loopback-validation.v2",
        "receipt_id": "MCP-LOOPBACK-V2-20260814",
        "evidence_scope": "LOCAL_IN_PROCESS_STREAMABLE_HTTP_NOT_HOST_VALIDATION",
        "transport": "streamable-http",
        "bind_host": "127.0.0.1",
        "path": "/mcp",
        "protocol_version": "2025-06-18",
        "checks": {key: "PASS" if value else "FAIL" for key, value in statuses.items()},
        "server_name": initialize_body.get("result", {}).get("serverInfo", {}).get("name"),
        "tools": [
            {
                "name": item["name"],
                "annotations": item.get("annotations"),
                "input_schema_sha256": canonical_sha256(item.get("inputSchema", {})),
                "output_schema_present": bool(item.get("outputSchema")),
            }
            for item in tools
        ],
        "tool_count": len(tools),
        "sandbox_receipt_id": structured.get("receipt_id"),
        "source_files": {
            relative: _file_sha256(ROOT / relative) for relative in SOURCE_PATHS
        },
        "provider_calls_performed": 0,
        "credentials_accessed": False,
        "external_actions_performed": 0,
        "authority_granted": False,
        "chatgpt_host_validation_performed": False,
        "gemini_client_validation_performed": False,
        "public_deployment_performed": False,
        "terminal_status": "PASS" if all(statuses.values()) else "FAIL",
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt = build_receipt()
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != serialized:
            print(f"MCP receipt is stale: {args.output}", file=sys.stderr)
            return 1
        print(f"MCP receipt is current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if receipt["terminal_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
