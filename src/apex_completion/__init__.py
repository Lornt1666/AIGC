"""Machine-enforced AIGC APEX completion scoring and evidence bindings."""

from .engine import CompletionEvaluation, evaluate_snapshot
from .models import EvidenceBinding, GateRecord, ProgramSnapshot

__all__ = [
    "CompletionEvaluation",
    "EvidenceBinding",
    "GateRecord",
    "ProgramSnapshot",
    "evaluate_snapshot",
]
