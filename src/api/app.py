from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from src.api.composition import build_container

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "governance" / "identity" / "local_identity_simulation.json"


class AuthorizationBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: dict[str, Any]
    principals: list[dict[str, Any]]
    memberships: list[dict[str, Any]]
    sessions: list[dict[str, Any]]
    policies: list[dict[str, Any]]
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    revocations: list[dict[str, Any]] = Field(default_factory=list)


def create_app(*, database_path: str | Path | None = None) -> FastAPI:
    container = build_container(database_path)
    application = FastAPI(
        title="AIGC Local Operator API",
        version="1.1.0-local",
        description="Localhost-only, non-production AIGC control surface. IAL0/AAL0/FAL0.",
    )
    application.state.container = container

    @application.get("/", response_class=HTMLResponse)
    def operator_console() -> str:
        return """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>AIGC Local Operator</title><style>body{font-family:system-ui;max-width:760px;margin:2rem auto;padding:0 1rem}a,button{font-size:1rem}code{background:#eee;padding:.15rem .3rem}section{margin:1.5rem 0}*:focus{outline:3px solid currentColor;outline-offset:3px}</style></head><body><main><h1>AIGC Local Operator API</h1><p><strong>Local simulation only.</strong> Production identity remains blocked.</p><section><h2>Status</h2><ul><li><a href='/health'>Health</a></li><li><a href='/api/v1/system/status'>System status</a></li><li><a href='/api/v1/readiness'>Readiness</a></li><li><a href='/docs'>OpenAPI</a></li></ul></section><section><h2>Boundary</h2><p><code>127.0.0.1</code> only. No credentials, deployment, live identity, or external action.</p></section></main></body></html>"""

    @application.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "mode": "local_simulation",
            "persistence": "sqlite",
            "external_action_performed": False,
        }

    @application.get("/api/v1/system/status")
    def system_status() -> dict[str, Any]:
        return {
            "system": "AIGC",
            "mode": "local_simulation",
            "identity_assurance": {"ial": "IAL0", "aal": "AAL0", "fal": "FAL0"},
            "authorization_receipt_persistence": "sqlite_local",
            "production_identity_access": "blocking",
            "deployment_authorized": False,
            "external_action_performed": False,
        }

    @application.get("/api/v1/readiness")
    def readiness() -> dict[str, Any]:
        return {
            "production_ready": False,
            "production_identity_access": {"state": "partial", "blocking": True},
            "authorization_receipt_persistence": {"state": "implemented_internal", "blocking": False},
            "evidence_scope": "local_behavioral_simulation",
            "exact_main_ci_observed": False,
            "external_action_performed": False,
        }

    @application.get("/api/v1/identity/contracts")
    def identity_contracts() -> dict[str, Any]:
        root = ROOT / "governance" / "schemas" / "identity"
        return {
            "contracts": sorted(path.name for path in root.glob("*.schema.json")),
            "external_action_performed": False,
        }

    @application.post("/api/v1/identity/authorize")
    def authorize(bundle: AuthorizationBundle) -> dict[str, Any]:
        try:
            return container.authorization_service.authorize(
                request=bundle.request,
                principals=bundle.principals,
                memberships=bundle.memberships,
                sessions=bundle.sessions,
                policies=bundle.policies,
                approvals=bundle.approvals,
                revocations=bundle.revocations,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "AUTHORIZATION_EVALUATION_FAILED", "message": str(exc)},
            ) from exc

    @application.get("/api/v1/audit/receipts/{receipt_id}")
    def audit_receipt(receipt_id: str) -> dict[str, Any]:
        receipt = container.authorization_service.get_receipt(receipt_id)
        if receipt is None:
            raise HTTPException(status_code=404, detail={"code": "RECEIPT_NOT_FOUND"})
        return receipt

    @application.get("/api/v1/identity/example")
    def identity_example() -> dict[str, Any]:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    return application


app = create_app()
