from __future__ import annotations

from typing import Protocol

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class GenerationRuntime(Protocol):
    model_id: str

    def generate(
        self, *, prompt: str, maximum_new_tokens: int, temperature: float
    ) -> str: ...


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=16000)
    maximum_new_tokens: int = Field(default=128, ge=1, le=4096)
    temperature: float = Field(default=1.0, gt=0, le=5)


def create_llm_serving_app(runtime: GenerationRuntime | None = None) -> FastAPI:
    app = FastAPI(
        title="AIGC LLM Foundry Serving Boundary",
        version="1.0.0",
        description="Disabled-by-default local model serving boundary.",
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "ok": True,
            "runtime_loaded": runtime is not None,
            "production_activation": False,
            "provider_calls_performed": 0,
        }

    @app.post("/generate")
    def generate(request: GenerateRequest) -> dict[str, object]:
        if runtime is None:
            raise HTTPException(
                status_code=503,
                detail="no admitted model runtime is loaded",
            )
        completion = runtime.generate(
            prompt=request.prompt,
            maximum_new_tokens=request.maximum_new_tokens,
            temperature=request.temperature,
        )
        return {
            "model_id": runtime.model_id,
            "completion": completion,
            "production_activation": False,
        }

    return app
