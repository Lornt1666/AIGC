from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable

from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.core.nexus.articulation_controller import ContributionRequest, FixtureContribution
from src.core.nexus.provider_runtime import NexusProviderRuntime, bind_provider_request_digest
from src.domain.nexus.contextualization import RepositoryContext
from src.domain.nexus.contracts import ChangeSet, ContextEnvelope, EffectClass, WorkOrder
from src.domain.nexus.provider_runtime import ProviderInvocation, ProviderRuntimeExecution


class ProviderContributionResolutionError(RuntimeError):
    def __init__(self, message: str, *, execution: ProviderRuntimeExecution | None = None) -> None:
        super().__init__(message)
        self.execution = execution


@dataclass(frozen=True)
class ProviderContributionRoute:
    route_key: str
    provider_id: str
    capability: str
    model_or_resource: str
    resource_ref: str
    purpose: str
    bounded_prompt: str
    reserved_usage_units: int
    maximum_input_units: int
    maximum_output_units: int
    request_timeout_seconds: int = 30
    maximum_cost_cad: Decimal = Decimal("0.00")
    requested_effect_class: EffectClass = "PURE"
    uncertainty: float = 0.0

    def __post_init__(self) -> None:
        if not self.route_key.strip() or len(self.route_key) > 128:
            raise ValueError("route_key must contain 1..128 non-whitespace characters")
        if self.provider_id != "offline_deterministic":
            raise ValueError("this release gate permits only offline_deterministic routes")
        if self.requested_effect_class != "PURE":
            raise ValueError("this release gate permits only PURE provider routes")
        if self.maximum_cost_cad != Decimal("0.00"):
            raise ValueError("this release gate requires maximum_cost_cad=0.00")
        if self.reserved_usage_units < 1:
            raise ValueError("reserved_usage_units must be greater than zero")
        if self.maximum_input_units < 0 or self.maximum_output_units < 1:
            raise ValueError("provider route input/output ceilings are invalid")
        if self.maximum_input_units + self.maximum_output_units > self.reserved_usage_units:
            raise ValueError("provider route usage partition exceeds its reservation")
        if not 1 <= self.request_timeout_seconds <= 120:
            raise ValueError("provider route timeout must be between 1 and 120 seconds")
        if not self.bounded_prompt.strip() or len(self.bounded_prompt) > 20000:
            raise ValueError("bounded_prompt must contain 1..20000 characters")
        if not self.capability.strip() or not self.model_or_resource.strip():
            raise ValueError("capability and model_or_resource are required")
        if not self.resource_ref.strip() or not self.purpose.strip():
            raise ValueError("resource_ref and purpose are required")
        if not 0.0 <= self.uncertainty <= 1.0:
            raise ValueError("uncertainty must be between zero and one")


class GovernedProviderContributionResolver:
    """Bind provider-visible untrusted context into the admitted NexusProviderRuntime."""

    def __init__(
        self,
        *,
        work_order: WorkOrder,
        context: ContextEnvelope,
        change_set: ChangeSet,
        principal: str,
        exact_revision: str,
        session_id: str,
        runtime: NexusProviderRuntime,
        authoritative_clock: Callable[[], datetime],
        routes: tuple[ProviderContributionRoute, ...],
        repository_context: RepositoryContext | None = None,
    ) -> None:
        if context.work_order_id != work_order.work_order_id:
            raise ValueError("ContextEnvelope is not bound to the supplied WorkOrder")
        if change_set.work_order_id != work_order.work_order_id:
            raise ValueError("ChangeSet is not bound to the supplied WorkOrder")
        if change_set.parent_state_hash != context.state_hash:
            raise ValueError("ChangeSet parent_state_hash does not match ContextEnvelope state_hash")
        if not principal.strip() or not exact_revision.strip() or not session_id.strip():
            raise ValueError("principal, exact_revision, and session_id are required")
        if repository_context is not None and repository_context.exact_revision != exact_revision:
            raise ValueError("RepositoryContext exact revision does not match resolver exact revision")

        route_map = {item.route_key: item for item in routes}
        if len(route_map) != len(routes):
            raise ValueError("duplicate provider contribution route keys are not permitted")
        if not route_map:
            raise ValueError("at least one provider contribution route is required")
        self._work_order = work_order
        self._context = context
        self._change_set = change_set
        self._principal = principal
        self._exact_revision = exact_revision
        self._session_id = session_id
        self._runtime = runtime
        self._authoritative_clock = authoritative_clock
        self._routes = route_map
        self._repository_context = repository_context

    def route_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._routes))

    def _validate_projection_binding(self, request: ContributionRequest) -> None:
        projection = request.context_projection
        if projection is not None:
            projected_parent_ids = tuple(item.message_id for item in projection.parent_messages)
            if projected_parent_ids != request.parent_message_ids:
                raise ProviderContributionResolutionError("projected parent-message lineage mismatch")
        if request.repository_context_id is None:
            if projection is not None and projection.repository_context_id is not None:
                raise ProviderContributionResolutionError("repository projection requires repository_context_id")
            return
        if self._repository_context is None:
            raise ProviderContributionResolutionError("repository_context_id requires a pre-bound RepositoryContext")
        if request.repository_context_id != self._repository_context.context_id:
            raise ProviderContributionResolutionError("repository_context_id does not match pre-bound RepositoryContext")
        if self._repository_context.exact_revision != self._exact_revision:
            raise ProviderContributionResolutionError("repository context exact revision mismatch")
        if projection is None or projection.repository_context_id != self._repository_context.context_id:
            raise ProviderContributionResolutionError("repository context must be present in context projection")
        if projection.repository_records != self._repository_context.records:
            raise ProviderContributionResolutionError("projected repository records do not match pre-bound RepositoryContext")

    def build_invocation(self, request: ContributionRequest) -> ProviderInvocation:
        if request.session_id != self._session_id:
            raise ProviderContributionResolutionError("ContributionRequest session_id mismatch")
        if request.created_at.tzinfo is None or request.created_at.utcoffset() is None:
            raise ProviderContributionResolutionError("ContributionRequest.created_at must be timezone-aware")
        self._validate_projection_binding(request)
        try:
            route = self._routes[request.fixture_key]
        except KeyError as exc:
            raise ProviderContributionResolutionError(
                f"unknown provider contribution route: {request.fixture_key}"
            ) from exc

        input_payload = self._compile_input(route, request)
        if len(input_payload) > 180000:
            raise ProviderContributionResolutionError("combined provider context exceeds bounded input ceiling")
        identity = {
            "route_key": route.route_key,
            "provider_id": route.provider_id,
            "capability": route.capability,
            "model_or_resource": route.model_or_resource,
            "resource_ref": route.resource_ref,
            "purpose": route.purpose,
            "requested_effect_class": route.requested_effect_class,
            "reserved_usage_units": route.reserved_usage_units,
            "maximum_input_units": route.maximum_input_units,
            "maximum_output_units": route.maximum_output_units,
            "request_timeout_seconds": route.request_timeout_seconds,
            "maximum_cost_cad": str(route.maximum_cost_cad),
            "principal": self._principal,
            "exact_revision": self._exact_revision,
            "work_order_id": self._work_order.work_order_id,
            "context_id": self._context.context_id,
            "change_set_id": self._change_set.change_set_id,
            "parent_state_hash": self._change_set.parent_state_hash,
            "input_payload": input_payload,
        }
        identity_digest = canonical_sha256(identity)
        invocation = ProviderInvocation(
            invocation_id="PINV-" + identity_digest[:24].upper(),
            request_id="TREQ-" + canonical_sha256({"request": identity})[:24].upper(),
            change_set_id=self._change_set.change_set_id,
            parent_state_hash=self._change_set.parent_state_hash,
            principal=self._principal,
            provider_id=route.provider_id,
            capability=route.capability,
            model_or_resource=route.model_or_resource,
            exact_revision=self._exact_revision,
            request_digest="0" * 64,
            idempotency_key=canonical_sha256({"idempotency": identity}),
            reserved_usage_units=route.reserved_usage_units,
            maximum_input_units=route.maximum_input_units,
            maximum_output_units=route.maximum_output_units,
            request_timeout_seconds=route.request_timeout_seconds,
            maximum_cost_cad=route.maximum_cost_cad,
            resource_ref=route.resource_ref,
            purpose=route.purpose,
            requested_effect_class=route.requested_effect_class,
            input_payload=input_payload,
            permit_id=None,
        )
        return bind_provider_request_digest(invocation)

    def resolve(self, request: ContributionRequest) -> FixtureContribution:
        invocation = self.build_invocation(request)
        authoritative_now = self._authoritative_clock()
        if authoritative_now.tzinfo is None or authoritative_now.utcoffset() is None:
            raise ProviderContributionResolutionError("authoritative_clock must return a timezone-aware datetime")
        try:
            execution = self._runtime.execute(invocation, authoritative_now=authoritative_now, permit=None)
        except Exception as exc:
            raise ProviderContributionResolutionError(
                f"provider runtime blocked contribution resolution: {type(exc).__name__}"
            ) from exc
        self._validate_success(execution)
        attempt = execution.attempt
        assert attempt.response_payload is not None
        usage = attempt.usage_units if attempt.usage_units is not None else invocation.reserved_usage_units
        return FixtureContribution(
            fixture_key=request.fixture_key,
            provider_id=attempt.provider_id,
            model_label=attempt.model_or_resource,
            primary_claim=attempt.response_payload,
            content=attempt.response_payload,
            evidence_refs=(execution.receipt.receipt_id,),
            uncertainty=self._routes[request.fixture_key].uncertainty,
            accounted_tokens=usage,
            cost_cad=attempt.cost_cad,
        )

    @staticmethod
    def _compile_input(route: ProviderContributionRoute, request: ContributionRequest) -> str:
        payload = {
            "classification": "UNTRUSTED_PROVIDER_INPUT",
            "bounded_prompt": route.bounded_prompt,
            "session_id": request.session_id,
            "round_id": request.round_id,
            "role": request.role,
            "response_type": request.response_type,
            "parent_message_ids": request.parent_message_ids,
            "created_at": request.created_at.isoformat(),
            "context_projection": (
                request.context_projection.model_dump(mode="json")
                if request.context_projection is not None
                else None
            ),
        }
        return canonical_json_bytes(payload).decode("utf-8")

    @staticmethod
    def _validate_success(execution: ProviderRuntimeExecution) -> None:
        attempt = execution.attempt
        audit = execution.audit
        receipt = execution.receipt
        if attempt.status != "succeeded" or receipt.execution_status != "succeeded":
            raise ProviderContributionResolutionError(
                "provider runtime did not produce a successful contribution", execution=execution
            )
        if attempt.response_payload is None or attempt.response_digest is None:
            raise ProviderContributionResolutionError(
                "successful provider contribution requires payload and response digest", execution=execution
            )
        if audit.provider_api_calls_performed != 0 or audit.network_calls_performed != 0:
            raise ProviderContributionResolutionError("live/network provider activity is prohibited", execution=execution)
        if audit.credentials_used != 0 or audit.external_actions_performed != 0:
            raise ProviderContributionResolutionError("credentials/external actions are prohibited", execution=execution)
        if audit.spend_cad != Decimal("0.00") or attempt.cost_cad != Decimal("0.00"):
            raise ProviderContributionResolutionError("provider contribution must remain at CAD 0.00", execution=execution)
