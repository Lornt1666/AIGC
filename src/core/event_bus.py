from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from src.core.result_envelope import ResultEnvelope
from src.core.state_store import AIGCStateStore, RuntimeEvent


class EventBus:
    def __init__(self, state_store: AIGCStateStore):
        self.state_store = state_store

    def publish(
        self,
        event_type: str,
        phase: str,
        status: str,
        summary: str,
        data: Dict[str, Any] | None = None,
        external_action_performed: bool = False,
    ) -> RuntimeEvent:
        return self.state_store.insert_event(
            event_type=event_type,
            phase=phase,
            status=status,
            summary=summary,
            data=data or {},
            external_action_performed=external_action_performed,
        )

    def publish_result(self, event_type: str, result: ResultEnvelope) -> RuntimeEvent:
        return self.publish(
            event_type=event_type,
            phase=result.phase,
            status=result.status,
            summary=result.summary,
            data=result.to_json_ready(),
            external_action_performed=result.external_action_performed,
        )


def build_event_bus(db_path: str | Path) -> EventBus:
    return EventBus(AIGCStateStore(db_path))
