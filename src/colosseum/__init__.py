"""Canonical AIGC Digital Work Colosseum domain contracts.

This package defines bounded, dependency-light domain types only. It grants no
external authority and performs no live job, employer, cloud, model, financial,
or App Store actions.
"""

from .benchmarks import ComputeBenchmark
from .domain import (
    AgentCell,
    CapabilityEvidence,
    CapabilityVerdict,
    ConfidentialityClass,
    Deliverable,
    DeliverableState,
    EmployerVault,
    Engagement,
    Opportunity,
    PresenceRequirement,
    Swarm,
    Verification,
    VerificationStatus,
    WorkLedger,
    WorkLedgerEntry,
    WorkOrder,
)
from .compute_exchange import (
    ComputeAdmission,
    ComputeCandidate,
    ComputePerformanceObservation,
    ComputeRequirement,
    ExecutionPortfolio,
    PortfolioOutcome,
    PortfolioPrediction,
    ResourceType,
)

__all__ = [
    "ComputeBenchmark",
    "AgentCell",
    "CapabilityEvidence",
    "CapabilityVerdict",
    "ConfidentialityClass",
    "Deliverable",
    "DeliverableState",
    "EmployerVault",
    "Engagement",
    "Opportunity",
    "PresenceRequirement",
    "Swarm",
    "Verification",
    "VerificationStatus",
    "WorkLedger",
    "WorkLedgerEntry",
    "WorkOrder",
    "ComputeAdmission",
    "ComputeCandidate",
    "ComputePerformanceObservation",
    "ComputeRequirement",
    "ExecutionPortfolio",
    "PortfolioOutcome",
    "PortfolioPrediction",
    "ResourceType",
]
