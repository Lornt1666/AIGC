"""Machine-enforced AIGC APEX completion, evidence, and authorization controls."""

from .authorization_reconstruction import (
    AuthorizationReconstructionReport,
    ReconstructedAuthorization,
    reconstruct_authorization_register,
)
from .engine import CompletionEvaluation, evaluate_snapshot
from .models import EvidenceBinding, GateRecord, ProgramSnapshot

__all__ = [
    "AuthorizationReconstructionReport",
    "CompletionEvaluation",
    "EvidenceBinding",
    "GateRecord",
    "ProgramSnapshot",
    "ReconstructedAuthorization",
    "evaluate_snapshot",
    "reconstruct_authorization_register",
]
