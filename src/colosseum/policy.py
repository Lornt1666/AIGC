from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from .domain import ConfidentialityClass, _require_nonnegative, _require_text


_CONFIDENTIALITY_RANK = {
    ConfidentialityClass.PUBLIC: 0,
    ConfidentialityClass.INTERNAL: 1,
    ConfidentialityClass.CONFIDENTIAL: 2,
    ConfidentialityClass.RESTRICTED: 3,
}


@dataclass(frozen=True)
class JurisdictionPolicy:
    allowed_jurisdictions: tuple[str, ...]
    prohibited_jurisdictions: tuple[str, ...] = ()
    cross_border_allowed: bool = False

    def __post_init__(self) -> None:
        if not self.allowed_jurisdictions:
            raise ValueError("allowed_jurisdictions must not be empty")
        if set(self.allowed_jurisdictions) & set(self.prohibited_jurisdictions):
            raise ValueError("jurisdiction cannot be both allowed and prohibited")

    def permits(self, jurisdiction: str) -> bool:
        return jurisdiction in self.allowed_jurisdictions and jurisdiction not in self.prohibited_jurisdictions


@dataclass(frozen=True)
class ConfidentialityPolicy:
    minimum_class: ConfidentialityClass
    cross_employer_access_allowed: bool = False
    external_training_use_allowed: bool = False

    def __post_init__(self) -> None:
        if self.cross_employer_access_allowed:
            raise ValueError("cross-employer access is prohibited by the AIGC platform baseline")


@dataclass(frozen=True)
class ToolPolicy:
    allowed_tools: tuple[str, ...] = ()
    prohibited_tools: tuple[str, ...] = ()
    external_api_allowed: bool = False
    open_source_allowed: bool = True

    def __post_init__(self) -> None:
        if set(self.allowed_tools) & set(self.prohibited_tools):
            raise ValueError("tool cannot be both allowed and prohibited")

    def permits(self, tool: str) -> bool:
        if tool in self.prohibited_tools:
            return False
        return not self.allowed_tools or tool in self.allowed_tools


@dataclass(frozen=True)
class ModelPolicy:
    allowed_models: tuple[str, ...] = ()
    prohibited_models: tuple[str, ...] = ()
    allowed_providers: tuple[str, ...] = ()
    prohibited_providers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if set(self.allowed_models) & set(self.prohibited_models):
            raise ValueError("model cannot be both allowed and prohibited")
        if set(self.allowed_providers) & set(self.prohibited_providers):
            raise ValueError("provider cannot be both allowed and prohibited")

    def permits_provider(self, provider: str) -> bool:
        if provider in self.prohibited_providers:
            return False
        return not self.allowed_providers or provider in self.allowed_providers


@dataclass(frozen=True)
class DataPolicy:
    employer_vault_id: str
    allowed_data_scopes: tuple[str, ...]
    cross_employer_retrieval_allowed: bool = False
    cross_employer_prompt_context_allowed: bool = False

    def __post_init__(self) -> None:
        _require_text("employer_vault_id", self.employer_vault_id)
        if not self.allowed_data_scopes:
            raise ValueError("allowed_data_scopes must not be empty")
        if self.cross_employer_retrieval_allowed or self.cross_employer_prompt_context_allowed:
            raise ValueError("cross-employer data use is prohibited by the platform baseline")


@dataclass(frozen=True)
class RetentionPolicy:
    retention_days: int
    deletion_required_after_retention: bool = True

    def __post_init__(self) -> None:
        _require_nonnegative("retention_days", self.retention_days)


@dataclass(frozen=True)
class HumanReviewPolicy:
    review_required_for_external_effects: bool = True
    review_required_for_restricted_work: bool = True
    licensed_review_required_when_legally_restricted: bool = True


@dataclass(frozen=True)
class SecurityPolicy:
    minimum_security_level: int
    minimum_privacy_level: int

    def __post_init__(self) -> None:
        for name in ("minimum_security_level", "minimum_privacy_level"):
            value = getattr(self, name)
            if not 0 <= value <= 3:
                raise ValueError(f"{name} must be between 0 and 3")


@dataclass(frozen=True)
class VerificationPolicy:
    independent_verification_required: bool = True
    evidence_required: bool = True


@dataclass(frozen=True)
class EmployerPolicy:
    policy_id: str
    employer_id: str
    vault_id: str
    engagement_id: str
    jurisdiction: JurisdictionPolicy
    confidentiality: ConfidentialityPolicy
    tools: ToolPolicy
    models: ModelPolicy
    data: DataPolicy
    retention: RetentionPolicy
    human_review: HumanReviewPolicy
    security: SecurityPolicy
    verification: VerificationPolicy
    maximum_cost_cad: float
    maximum_token_budget: int
    maximum_compute_seconds: int
    maximum_task_duration: timedelta

    def __post_init__(self) -> None:
        for name in ("policy_id", "employer_id", "vault_id", "engagement_id"):
            _require_text(name, getattr(self, name))
        _require_nonnegative("maximum_cost_cad", self.maximum_cost_cad)
        _require_nonnegative("maximum_token_budget", self.maximum_token_budget)
        _require_nonnegative("maximum_compute_seconds", self.maximum_compute_seconds)
        if self.maximum_task_duration.total_seconds() <= 0:
            raise ValueError("maximum_task_duration must be positive")
        if self.data.employer_vault_id != self.vault_id:
            raise ValueError("data policy must bind to the employer policy vault")


@dataclass(frozen=True)
class PlatformBaseline:
    jurisdiction: JurisdictionPolicy
    confidentiality: ConfidentialityPolicy
    tools: ToolPolicy
    models: ModelPolicy
    security: SecurityPolicy
    human_review: HumanReviewPolicy
    verification: VerificationPolicy


@dataclass(frozen=True)
class EffectivePolicy:
    employer_policy: EmployerPolicy
    allowed_jurisdictions: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_providers: tuple[str, ...]
    minimum_confidentiality_class: ConfidentialityClass
    minimum_security_level: int
    minimum_privacy_level: int
    independent_verification_required: bool
    evidence_required: bool


class EmployerPolicyCompiler:
    """Intersects employer policy with the mandatory AIGC platform baseline.

    The compiler can only preserve or tighten mandatory baseline controls; it
    never grants authority and never performs external actions.
    """

    def compile(self, *, platform: PlatformBaseline, employer: EmployerPolicy) -> EffectivePolicy:
        allowed_jurisdictions = tuple(
            sorted(
                set(platform.jurisdiction.allowed_jurisdictions)
                & set(employer.jurisdiction.allowed_jurisdictions)
            )
        )
        if not allowed_jurisdictions:
            raise ValueError("no jurisdiction satisfies both platform and employer policy")

        allowed_tools = self._intersect_optional_allowlists(
            platform.tools.allowed_tools, employer.tools.allowed_tools
        )
        prohibited_tools = set(platform.tools.prohibited_tools) | set(employer.tools.prohibited_tools)
        allowed_tools = tuple(tool for tool in allowed_tools if tool not in prohibited_tools)
        if platform.tools.allowed_tools and employer.tools.allowed_tools and not allowed_tools:
            raise ValueError("no tool satisfies both platform and employer policy")

        allowed_providers = self._intersect_optional_allowlists(
            platform.models.allowed_providers, employer.models.allowed_providers
        )
        prohibited_providers = set(platform.models.prohibited_providers) | set(employer.models.prohibited_providers)
        allowed_providers = tuple(provider for provider in allowed_providers if provider not in prohibited_providers)
        if platform.models.allowed_providers and employer.models.allowed_providers and not allowed_providers:
            raise ValueError("no provider satisfies both platform and employer policy")

        confidentiality = max(
            (platform.confidentiality.minimum_class, employer.confidentiality.minimum_class),
            key=lambda value: _CONFIDENTIALITY_RANK[value],
        )

        return EffectivePolicy(
            employer_policy=employer,
            allowed_jurisdictions=allowed_jurisdictions,
            allowed_tools=allowed_tools,
            allowed_providers=allowed_providers,
            minimum_confidentiality_class=confidentiality,
            minimum_security_level=max(
                platform.security.minimum_security_level,
                employer.security.minimum_security_level,
            ),
            minimum_privacy_level=max(
                platform.security.minimum_privacy_level,
                employer.security.minimum_privacy_level,
            ),
            independent_verification_required=(
                platform.verification.independent_verification_required
                or employer.verification.independent_verification_required
            ),
            evidence_required=platform.verification.evidence_required or employer.verification.evidence_required,
        )

    @staticmethod
    def _intersect_optional_allowlists(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
        if left and right:
            return tuple(sorted(set(left) & set(right)))
        if left:
            return tuple(sorted(set(left)))
        if right:
            return tuple(sorted(set(right)))
        return ()
