"""Canonical AIGC Digital Work Colosseum contracts and planning kernel.

This package defines fail-closed domain and planning types. It grants no live
job, employer, cloud, model, financial, merge, deployment, or App Store
authority. Orchestration-kernel V1 produces plans only.
"""

from .benchmarks import ComputeBenchmark
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
from .orchestration import (
    AgentAssignment,
    AgentRoleDefinition,
    CapabilityMatch,
    CompletionCriterion,
    DefinitionOfDone,
    EvidenceRequirement,
    HumanReviewRequirement,
    SchedulingDecision,
    SwarmPlan,
    SwarmScheduler,
    Task,
    TaskDAG,
    TaskDependency,
    TaskState,
    VerificationAssignment,
    VerificationPlan,
)
from .policy import (
    ConfidentialityPolicy,
    DataPolicy,
    EffectivePolicy,
    EmployerPolicy,
    EmployerPolicyCompiler,
    HumanReviewPolicy,
    JurisdictionPolicy,
    ModelPolicy,
    PlatformBaseline,
    RetentionPolicy,
    SecurityPolicy,
    ToolPolicy,
    VerificationPolicy,
)

__all__ = [name for name in globals() if not name.startswith("_")]
