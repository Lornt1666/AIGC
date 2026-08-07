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
class VaultDataScope:
    """A data scope structurally bound to one employer vault."""

    scope_id: str
    vault_id: str
    employer_id: str
    classification: ConfidentialityClass
    purpose: str

    def __post_init__(self) -> None:
        for name in ("scope_id", "vault_id", "employer_id", "purpose"):
            _require_text(name, getattr(self, name))

    @classmethod
    def from_legacy(
        cls,
        value: str,
        *,
        vault_id: str,
        employer_id: str,
        classification: ConfidentialityClass,
        purpose: str,
    ) -> "VaultDataScope":
        """Explicit, validated migration adapter for legacy string scopes."""
        _require_text("legacy scope", value)
        return cls(
            scope_id=value,
            vault_id=vault_id,
            employer_id=employer_id,
            classification=classification,
            purpose=purpose,
        )


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
        for value in self.allowed_jurisdictions + self.prohibited_jurisdictions:
            _require_text("jurisdiction", value)

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
        for value in self.allowed_tools + self.prohibited_tools:
            _require_text("tool", value)

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
        for value in (
            self.allowed_models
            + self.prohibited_models
            + self.allowed_providers
            + self.prohibited_providers
        ):
            _require_text("model/provider", value)

    def permits_provider(self, provider: str) -> bool:
        if provider in self.prohibited_providers:
            return False
        return not self.allowed_providers or provider in self.allowed_providers

    def permits_model(self, model: str) -> bool:
        if model in self.prohibited_models:
            return False
        return not self.allowed_models or model in self.allowed_models


@dataclass(frozen=True)
class DataPolicy:
    employer_vault_id: str
    employer_id: str
    allowed_data_scopes: tuple[VaultDataScope, ...]
    cross_employer_retrieval_allowed: bool = False
    cross_employer_prompt_context_allowed: bool = False

    def __post_init__(self) -> None:
        _require_text("employer_vault_id", self.employer_vault_id)
        _require_text("employer_id", self.employer_id)
        if not self.allowed_data_scopes:
            raise ValueError("allowed_data_scopes must not be empty")
        if self.cross_employer_retrieval_allowed or self.cross_employer_prompt_context_allowed:
            raise ValueError("cross-employer data use is prohibited by the platform baseline")
        if any(not isinstance(scope, VaultDataScope) for scope in self.allowed_data_scopes):
            raise TypeError("allowed_data_scopes must contain VaultDataScope objects")
        if len({scope.scope_id for scope in self.allowed_data_scopes}) != len(self.allowed_data_scopes):
            raise ValueError("scope IDs must be unique")
        for scope in self.allowed_data_scopes:
            if scope.vault_id != self.employer_vault_id or scope.employer_id != self.employer_id:
                raise ValueError("data scope is not bound to the declared employer vault")


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
        if self.data.employer_id != self.employer_id:
            raise ValueError("data policy must bind to the employer policy employer")


@dataclass(frozen=True)
class PlatformBaseline:
    jurisdiction: JurisdictionPolicy
    confidentiality: ConfidentialityPolicy
    tools: ToolPolicy
    models: ModelPolicy
    security: SecurityPolicy
    human_review: HumanReviewPolicy
    verification: VerificationPolicy
    retention: RetentionPolicy = RetentionPolicy(365, True)


@dataclass(frozen=True)
class EffectivePolicy:
    employer_policy: EmployerPolicy
    allowed_jurisdictions: tuple[str, ...]
    prohibited_jurisdictions: tuple[str, ...]
    cross_border_allowed: bool
    allowed_tools: tuple[str, ...]
    prohibited_tools: tuple[str, ...]
    external_api_allowed: bool
    open_source_allowed: bool
    allowed_models: tuple[str, ...]
    prohibited_models: tuple[str, ...]
    allowed_providers: tuple[str, ...]
    prohibited_providers: tuple[str, ...]
    minimum_confidentiality_class: ConfidentialityClass
    external_training_use_allowed: bool
    allowed_data_scopes: tuple[VaultDataScope, ...]
    retention_days: int
    deletion_required_after_retention: bool
    minimum_security_level: int
    minimum_privacy_level: int
    review_required_for_external_effects: bool
    review_required_for_restricted_work: bool
    licensed_review_required_when_legally_restricted: bool
    independent_verification_required: bool
    evidence_required: bool
    maximum_cost_cad: float
    maximum_token_budget: int
    maximum_compute_seconds: int
    maximum_task_duration: timedelta

    @property
    def policy_id(self) -> str:
        return self.employer_policy.policy_id

    @property
    def employer_id(self) -> str:
        return self.employer_policy.employer_id

    @property
    def vault_id(self) -> str:
        return self.employer_policy.vault_id


class EmployerPolicyCompiler:
    """Compile a complete, strict intersection of platform and employer controls."""

    def compile(self, *, platform: PlatformBaseline, employer: EmployerPolicy) -> EffectivePolicy:
        prohibited_jurisdictions = self._union(
            platform.jurisdiction.prohibited_jurisdictions,
            employer.jurisdiction.prohibited_jurisdictions,
        )
        allowed_jurisdictions = self._effective_allowlist(
            platform.jurisdiction.allowed_jurisdictions,
            employer.jurisdiction.allowed_jurisdictions,
            prohibited_jurisdictions,
            "jurisdiction",
        )

        prohibited_tools = self._union(platform.tools.prohibited_tools, employer.tools.prohibited_tools)
        allowed_tools = self._effective_allowlist(
            platform.tools.allowed_tools,
            employer.tools.allowed_tools,
            prohibited_tools,
            "tool",
        )

        prohibited_providers = self._union(
            platform.models.prohibited_providers,
            employer.models.prohibited_providers,
        )
        allowed_providers = self._effective_allowlist(
            platform.models.allowed_providers,
            employer.models.allowed_providers,
            prohibited_providers,
            "provider",
        )

        prohibited_models = self._union(
            platform.models.prohibited_models,
            employer.models.prohibited_models,
        )
        allowed_models = self._effective_allowlist(
            platform.models.allowed_models,
            employer.models.allowed_models,
            prohibited_models,
            "model",
        )

        confidentiality = max(
            (platform.confidentiality.minimum_class, employer.confidentiality.minimum_class),
            key=lambda value: _CONFIDENTIALITY_RANK[value],
        )

        return EffectivePolicy(
            employer_policy=employer,
            allowed_jurisdictions=allowed_jurisdictions,
            prohibited_jurisdictions=prohibited_jurisdictions,
            cross_border_allowed=(
                platform.jurisdiction.cross_border_allowed
                and employer.jurisdiction.cross_border_allowed
            ),
            allowed_tools=allowed_tools,
            prohibited_tools=prohibited_tools,
            external_api_allowed=platform.tools.external_api_allowed and employer.tools.external_api_allowed,
            open_source_allowed=platform.tools.open_source_allowed and employer.tools.open_source_allowed,
            allowed_models=allowed_models,
            prohibited_models=prohibited_models,
            allowed_providers=allowed_providers,
            prohibited_providers=prohibited_providers,
            minimum_confidentiality_class=confidentiality,
            external_training_use_allowed=(
                platform.confidentiality.external_training_use_allowed
                and employer.confidentiality.external_training_use_allowed
            ),
            allowed_data_scopes=tuple(
                sorted(employer.data.allowed_data_scopes, key=lambda scope: scope.scope_id)
            ),
            retention_days=min(platform.retention.retention_days, employer.retention.retention_days),
            deletion_required_after_retention=(
                platform.retention.deletion_required_after_retention
                or employer.retention.deletion_required_after_retention
            ),
            minimum_security_level=max(
                platform.security.minimum_security_level,
                employer.security.minimum_security_level,
            ),
            minimum_privacy_level=max(
                platform.security.minimum_privacy_level,
                employer.security.minimum_privacy_level,
            ),
            review_required_for_external_effects=(
                platform.human_review.review_required_for_external_effects
                or employer.human_review.review_required_for_external_effects
            ),
            review_required_for_restricted_work=(
                platform.human_review.review_required_for_restricted_work
                or employer.human_review.review_required_for_restricted_work
            ),
            licensed_review_required_when_legally_restricted=(
                platform.human_review.licensed_review_required_when_legally_restricted
                or employer.human_review.licensed_review_required_when_legally_restricted
            ),
            independent_verification_required=(
                platform.verification.independent_verification_required
                or employer.verification.independent_verification_required
            ),
            evidence_required=(
                platform.verification.evidence_required
                or employer.verification.evidence_required
            ),
            maximum_cost_cad=employer.maximum_cost_cad,
            maximum_token_budget=employer.maximum_token_budget,
            maximum_compute_seconds=employer.maximum_compute_seconds,
            maximum_task_duration=employer.maximum_task_duration,
        )

    @staticmethod
    def _union(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(left) | set(right)))

    @staticmethod
    def _effective_allowlist(
        left: tuple[str, ...],
        right: tuple[str, ...],
        prohibited: tuple[str, ...],
        label: str,
    ) -> tuple[str, ...]:
        if left and right:
            candidates = set(left) & set(right)
        elif left:
            candidates = set(left)
        elif right:
            candidates = set(right)
        else:
            candidates = set()
        result = tuple(sorted(candidates - set(prohibited)))
        if left and right and not result:
            raise ValueError(f"no {label} satisfies both platform and employer policy")
        return result
