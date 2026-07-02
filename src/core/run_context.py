from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

@dataclass(frozen=True)
class RunContext:
    run_id: str
    operator: str
    root: str
    state_db_path: str
    runtime_mode: str
    external_actions_allowed: bool = False
    approval_required_for_external_actions: bool = True
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(
        cls,
        root: Path,
        runtime_mode: str,
        state_db_path: Path | None = None,
        operator: str = "Justice Gray Maciocha",
    ) -> "RunContext":
        resolved_root = root.resolve()
        db_path = state_db_path or resolved_root / "memory" / "aigc_state.sqlite"
        return cls(
            run_id=f"AIGC-RUN-{uuid.uuid4()}",
            operator=operator,
            root=str(resolved_root),
            state_db_path=str(db_path),
            runtime_mode=runtime_mode,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
