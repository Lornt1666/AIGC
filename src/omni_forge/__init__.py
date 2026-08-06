"""REGENEXCALIBUR :: OMNI-FORGE-V-SUPREME domain kernel.

This package defines deterministic, fail-closed contracts only. It grants no
cloud, deployment, production, public-access, model-call, financial, email, or
automatic-merge authority.
"""

from .authorization import AuthorizationPacket, AuthorityDecision
from .budget import BudgetEnvelope
from .domain import AgentInvocation, DataClassification, Environment
from .evidence import EvidenceReceipt
from .graph_validator import GraphValidationError, validate_graph
from .state_machine import ExecutionState, transition

__all__ = [
    "AgentInvocation",
    "AuthorizationPacket",
    "AuthorityDecision",
    "BudgetEnvelope",
    "DataClassification",
    "Environment",
    "EvidenceReceipt",
    "ExecutionState",
    "GraphValidationError",
    "transition",
    "validate_graph",
]
