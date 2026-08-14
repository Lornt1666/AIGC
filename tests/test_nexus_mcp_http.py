from __future__ import annotations

from fastapi.testclient import TestClient

from src.integrations.mcp.server import build_mcp_server


def test_streamable_http_initializes_and_lists_wealth_operator_on_loopback():
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
                    "clientInfo": {"name": "aigc-test", "version": "1"},
                },
            },
        )
        listed = client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )

    assert initialized.status_code == 200
    assert initialized.json()["result"]["serverInfo"]["name"] == "aigc-nexus"
    assert listed.status_code == 200
    tools = {item["name"]: item for item in listed.json()["result"]["tools"]}
    wealth_tool = tools["aigc_plan_wealth_work"]
    assert wealth_tool["annotations"] == {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    assert "permit_id" not in wealth_tool["inputSchema"]["properties"]
    assert "existing_explicit_authority" not in wealth_tool["inputSchema"]["properties"]
    doctrine_tool = tools["aigc_plan_regenexcalibur_workflow"]
    diagnostics_tool = tools["aigc_run_regenexcalibur_diagnostics"]
    alpha_tool = tools["aigc_compose_alpha_plan"]
    assert doctrine_tool["annotations"]["readOnlyHint"] is True
    assert diagnostics_tool["annotations"]["readOnlyHint"] is True
    assert alpha_tool["annotations"]["readOnlyHint"] is True
    assert "permit_id" not in alpha_tool["inputSchema"]["properties"]
    assert "permit_id" not in doctrine_tool["inputSchema"]["properties"]
