from __future__ import annotations

from fastapi import FastAPI

from src.coordination import CoordinationEngineeringRequest, engineer_coordination_plan
from src.coordination.models import CoordinationEngineeringReceipt
from src.regenexcalibur.diagnostics import run_all_diagnostics
from src.regenexcalibur.doctrine_coordinator import plan_regenexcalibur_workflow
from src.regenexcalibur.doctrine_models import CoordinatorRequest


def create_regenexcalibur_app() -> FastAPI:
    app = FastAPI(
        title="RegenExcalibur AIGC Coordinator",
        version="1.0.0-local",
        description="Governed local planning and diagnostic surface; no external execution.",
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "PASS",
            "service": "RegenEx::AIGC",
            "external_execution_enabled": False,
            "authority_granted": False,
        }

    @app.post("/v1/coordinator/plan")
    def plan(request: CoordinatorRequest) -> dict[str, object]:
        return plan_regenexcalibur_workflow(request)

    @app.post("/v1/diagnostics/run")
    def diagnostics() -> dict[str, object]:
        return run_all_diagnostics()

    @app.post(
        "/v1/coordination/engineer",
        response_model=CoordinationEngineeringReceipt,
        summary="Engineer a deterministic AIGC coordination plan",
    )
    def engineer_coordination(
        request: CoordinationEngineeringRequest,
    ) -> dict[str, object]:
        return engineer_coordination_plan(request)

    return app


app = create_regenexcalibur_app()
