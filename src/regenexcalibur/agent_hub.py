from __future__ import annotations

from src.regenexcalibur.doctrine_models import Modality


MODALITY_ADAPTERS: dict[Modality, dict[str, object]] = {
    "TEXT": {
        "interface": "LLMAdapter",
        "supported_payloads": ["text/plain", "application/json"],
        "status": "LOCAL_CONTRACT_READY",
    },
    "AUDIO": {
        "interface": "AudioAdapter",
        "supported_payloads": ["audio/wav", "audio/mpeg"],
        "status": "PLUGIN_REQUIRED",
    },
    "VISION": {
        "interface": "VisionAdapter",
        "supported_payloads": ["image/jpeg", "image/png", "application/pdf"],
        "status": "PLUGIN_REQUIRED",
    },
    "STRUCTURED_DATA": {
        "interface": "StructuredDataAdapter",
        "supported_payloads": ["application/json", "text/csv"],
        "status": "LOCAL_CONTRACT_READY",
    },
}


def modality_plan(modalities: tuple[Modality, ...]) -> list[dict[str, object]]:
    return [
        {
            "modality": modality,
            **MODALITY_ADAPTERS[modality],
            "provider_call_performed": False,
            "external_action_performed": False,
        }
        for modality in modalities
    ]
