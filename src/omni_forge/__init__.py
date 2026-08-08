"""REGENEXCALIBUR :: OMNI-FORGE governed execution substrate.

This package defines deterministic, fail-closed contracts only. AIGC's Digital
Work Colosseum remains the canonical product and domain ontology. OMNI-FORGE
grants no cloud, deployment, production, public-access, live-model, financial,
email, merge, automatic-merge, or App Store authority.
"""

from .authorization import AuthorizationPacket, AuthorityDecision
from .budget import BudgetEnvelope
from .colosseum_compat import (
    CANONICAL_BINDING_SCHEMA_VERSION,
    REPOSITORY_ONLY_ACTION,
    CanonicalExecutionBinding,
    canonical_metadata,
)
from .domain import AgentInvocation, DataClassification, Environment
from .evidence import EvidenceReceipt
from .graph_validator import GraphValidationError, validate_graph
from .state_machine import ExecutionState, transition

__all__ = [
    "AgentInvocation",
    "AuthorizationPacket",
    "AuthorityDecision",
    "BudgetEnvelope",
    "CANONICAL_BINDING_SCHEMA_VERSION",
    "CanonicalExecutionBinding",
    "DataClassification",
    "Environment",
    "EvidenceReceipt",
    "ExecutionState",
    "GraphValidationError",
    "REPOSITORY_ONLY_ACTION",
    "canonical_metadata",
    "transition",
    "validate_graph",
]
