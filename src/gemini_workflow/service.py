from __future__ import annotations

import hashlib
import json
import math
from typing import Any
from urllib.parse import urlsplit
import uuid

from .control_store import (
    EmergencyState,
    EmergencyStopActiveError,
    InMemoryRuntimeControlStore,
    RunReservation,
    RuntimeControlStore,
)
from .evidence import (
    EvidenceConflictError,
    EvidenceStore,
    EvidenceStoreError,
    StoredWorkflowEvent,
)
from .models import (
    GeminiAssessment,
    HumanDecisionRequest,
    OperatorIdentity,
    OpportunityIntake,
    WorkflowRecord,
)
from .policy import evaluate_policy
from .provider import (
    AssessmentProvider,
    GeminiProviderError,
    SYSTEM_INSTRUCTION,
)
from .redaction import (
    contains_secret_material,
    redact_text,
    redact_value,
    safe_source_url,
)
from .runtime_limits import RuntimeLimits


class GeminiWorkflowStateError(RuntimeError):
    """Raised when a governed workflow transition is invalid."""


class GeminiWorkflowInProgressError(GeminiWorkflowStateError):
    """Raised when an idempotent request is already executing."""

    def __init__(self, run_id: str) -> None:
        super().__init__("An identical Gemini workflow is already executing")
        self.run_id = run_id


class GeminiWorkflowService:
    def __init__(
        self,
        *,
        provider: AssessmentProvider,
        evidence_store: EvidenceStore,
        control_store: RuntimeControlStore | None = None,
        runtime_limits: RuntimeLimits | None = None,
        source_revision: str = "",
        runtime_revision: str = "",
        model_name: str = "",
        max_output_tokens: int = 1_200,
    ) -> None:
        self.provider = provider
        self.evidence_store = evidence_store
        provider_settings = getattr(provider, "settings", None)
        self._live_provider_configured = provider_settings is not None
        if self._live_provider_configured and control_store is None:
            raise ValueError(
                "Live Gemini service requires an explicit durable control store"
            )
        self.control_store = (
            control_store
            if control_store is not None
            else InMemoryRuntimeControlStore()
        )
        self.runtime_limits = runtime_limits or RuntimeLimits()
        self.source_revision = source_revision or ""
        self.runtime_revision = runtime_revision or ""
        self.model_name = (
            model_name
            or getattr(provider_settings, "model", "")
            or getattr(provider, "model", "")
            or "unknown-model"
        )
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be greater than zero")
        self.max_output_tokens = max_output_tokens

    def create_workflow(
        self,
        intake: OpportunityIntake,
        *,
        actor: OperatorIdentity | None = None,
        idempotency_key: str | None = None,
    ) -> WorkflowRecord:
        if self._live_provider_configured and actor is None:
            raise GeminiWorkflowStateError(
                "Live Gemini execution requires an authenticated actor"
            )
        if self._live_provider_configured and idempotency_key is None:
            raise GeminiWorkflowStateError(
                "Live Gemini execution requires an Idempotency-Key"
            )
        actor = actor or _offline_actor()
        if actor.role != "operator":
            raise GeminiWorkflowStateError(
                "Only the operator role may execute Gemini assessments"
            )
        if not intake.ai_assistance_permitted:
            raise GeminiWorkflowStateError(
                "AI assistance is not permitted for this intake"
            )
        if urlsplit(str(intake.source_url)).scheme != "https":
            raise GeminiWorkflowStateError("source_url must use HTTPS")
        if any(
            contains_secret_material(value)
            for value in (
                intake.title,
                intake.description,
                *intake.constraints,
                str(intake.source_url),
            )
        ):
            raise GeminiWorkflowStateError(
                "Secret-like material is not permitted in a Gemini intake"
            )

        sanitized_input, input_summary = _sanitize_intake(intake)
        input_sha256 = _hash_json(sanitized_input)
        run_id = f"AIGC-GEMINI-RUN-{uuid.uuid4()}"
        correlation_id = f"AIGC-CORR-{uuid.uuid4()}"
        effective_key = (
            idempotency_key
            if idempotency_key is not None
            else f"offline-{uuid.uuid4()}"
        )
        reserved_tokens = _estimate_reserved_tokens(
            sanitized_input,
            max_output_tokens=self.max_output_tokens,
        )
        reservation = self.control_store.reserve_run(
            run_id=run_id,
            principal_id=actor.stable_principal_id,
            idempotency_key=effective_key,
            request_sha256=input_sha256,
            model=self.model_name,
            source_revision=self.source_revision,
            reserved_tokens=reserved_tokens,
            limits=self.runtime_limits,
        )
        if reservation.replayed:
            return self._resolve_replay(reservation)
        run_id = reservation.run_id

        try:
            self.control_store.assert_epoch_current(
                run_id=run_id,
                expected_epoch=reservation.stop_epoch,
            )
        except EmergencyStopActiveError:
            self.control_store.fail_run(run_id=run_id, state="stopped")
            raise

        start_event = {
            "event_type": "workflow_started",
            "run_id": run_id,
            "correlation_id": correlation_id,
            "status": "executing",
            "payload": {
                "input_sha256": input_sha256,
                "input_summary": input_summary,
                "source_revision": self.source_revision or None,
                "runtime_revision": self.runtime_revision or None,
                "reserved_tokens": reserved_tokens,
                "stop_epoch": reservation.stop_epoch,
                "model_api_call_status": "not_attempted",
                "model_api_call_performed": False,
                "external_business_action_performed": False,
            },
            "model_api_call_status": "not_attempted",
            "model_api_call_performed": False,
            "external_business_action_performed": False,
            "external_action_performed": False,
        }
        try:
            self.evidence_store.append_with_receipt(start_event)
        except EvidenceStoreError:
            self.control_store.fail_run(
                run_id=run_id,
                state="evidence_missing",
            )
            raise

        try:
            self.control_store.assert_epoch_current(
                run_id=run_id,
                expected_epoch=reservation.stop_epoch,
            )
            self.control_store.mark_executing(run_id=run_id)
        except EmergencyStopActiveError:
            self.control_store.fail_run(run_id=run_id, state="stopped")
            self._best_effort_failure(
                run_id=run_id,
                correlation_id=correlation_id,
                status="stopped_before_provider_call",
                failure_class="EmergencyStopActive",
                call_status="not_attempted",
                call_performed=False,
            )
            raise

        try:
            generation = self.provider.assess(
                intake,
                correlation_id=correlation_id,
            )
        except Exception as exc:
            call_status = getattr(
                exc,
                "model_api_call_status",
                "attempted_outcome_unknown",
            )
            call_performed = getattr(
                exc,
                "model_api_call_performed",
                None,
            )
            failure_written = self._best_effort_failure(
                run_id=run_id,
                correlation_id=correlation_id,
                status="failed_closed",
                failure_class=type(exc).__name__,
                call_status=call_status,
                call_performed=call_performed,
            )
            self.control_store.fail_run(
                run_id=run_id,
                state="failed" if failure_written else "evidence_missing",
            )
            if isinstance(exc, GeminiProviderError):
                raise
            raise GeminiProviderError(
                "Gemini provider failed unexpectedly",
                model_api_call_status=call_status,
                model_api_call_performed=call_performed,
            ) from exc

        try:
            self.control_store.assert_epoch_current(
                run_id=run_id,
                expected_epoch=reservation.stop_epoch,
            )
        except EmergencyStopActiveError:
            self._best_effort_failure(
                run_id=run_id,
                correlation_id=correlation_id,
                status="stopped_after_provider_call",
                failure_class="EmergencyStopEpochChanged",
                call_status=(
                    "confirmed"
                    if generation.live_model_call
                    else "not_attempted"
                ),
                call_performed=generation.live_model_call,
            )
            self.control_store.fail_run(run_id=run_id, state="stopped")
            raise

        assessment_raw, assessment_redactions = redact_value(
            generation.assessment.model_dump(mode="json")
        )
        assessment = GeminiAssessment.model_validate(assessment_raw)
        policy = evaluate_policy(intake, assessment)
        input_summary["redactions_applied"] += assessment_redactions

        payload: dict[str, Any] = {
            "provider": generation.provider,
            "transport": generation.transport,
            "model": generation.model,
            "response_id": generation.response_id,
            "finish_reason": generation.finish_reason,
            "latency_ms": generation.latency_ms,
            "usage": generation.usage.model_dump(mode="json"),
            "live_model_call": generation.live_model_call,
            "model_api_call_performed": generation.live_model_call,
            "model_api_call_status": (
                "confirmed" if generation.live_model_call else "not_attempted"
            ),
            "external_business_action_performed": False,
            "prompt_template_version": "aigc-gemini-opportunity-v1",
            "input_sha256": input_sha256,
            "input_summary": input_summary,
            "assessment": assessment.model_dump(mode="json"),
            "assessment_sha256": _hash_json(
                assessment.model_dump(mode="json")
            ),
            "policy": policy.model_dump(mode="json"),
            "human_review_required": True,
            "assessment_grounding": (
                "supplied_input_only_not_externally_verified"
            ),
            "source_revision": self.source_revision or None,
            "runtime_revision": self.runtime_revision or None,
            "reserved_tokens": reserved_tokens,
            "stop_epoch": reservation.stop_epoch,
        }
        status = (
            "pending_human_review"
            if policy.outcome == "allow_internal_draft"
            else policy.outcome
        )
        execution_event = {
            "event_type": "gemini_execution",
            "run_id": run_id,
            "correlation_id": correlation_id,
            "status": status,
            "payload": payload,
            "model_api_call_status": (
                "confirmed" if generation.live_model_call else "not_attempted"
            ),
            "model_api_call_performed": generation.live_model_call,
            "external_business_action_performed": False,
            "external_action_performed": False,
        }
        try:
            self.control_store.assert_epoch_current(
                run_id=run_id,
                expected_epoch=reservation.stop_epoch,
            )
            stored = self.evidence_store.append_with_receipt(execution_event)
        except EmergencyStopActiveError:
            self.control_store.fail_run(run_id=run_id, state="stopped")
            self._best_effort_failure(
                run_id=run_id,
                correlation_id=correlation_id,
                status="stopped_before_success_evidence",
                failure_class="EmergencyStopEpochChanged",
                call_status=(
                    "confirmed"
                    if generation.live_model_call
                    else "not_attempted"
                ),
                call_performed=generation.live_model_call,
            )
            raise
        except EvidenceStoreError:
            self.control_store.fail_run(
                run_id=run_id,
                state="evidence_missing",
            )
            self._best_effort_failure(
                run_id=run_id,
                correlation_id=correlation_id,
                status="provider_succeeded_evidence_missing",
                failure_class="EvidencePersistenceFailure",
                call_status=(
                    "confirmed"
                    if generation.live_model_call
                    else "not_attempted"
                ),
                call_performed=generation.live_model_call,
            )
            raise

        actual_tokens = (
            generation.usage.total_tokens
            if generation.usage.total_tokens is not None
            else reserved_tokens
        )
        self.control_store.complete_run(
            run_id=run_id,
            expected_epoch=reservation.stop_epoch,
            actual_tokens=actual_tokens,
            execution_event_id=stored.record.event_id,
            evidence_object_uri=stored.receipt.object_uri,
            evidence_generation=stored.receipt.generation,
        )
        return stored.record

    def get_workflow(self, run_id: str) -> list[WorkflowRecord]:
        reservation = self.control_store.get_run(run_id)
        events = self.evidence_store.events_for_run(run_id)
        if not events:
            raise GeminiWorkflowStateError("Workflow run not found")
        visible = [
            event
            for event in events
            if event.event_type
            not in {"gemini_execution", "operator_decision"}
        ]
        if reservation.state == "completed":
            visible.append(self._completed_execution(reservation))
            if getattr(reservation, "decision_event_id", None):
                decision = self.evidence_store.event_by_receipt(
                    run_id=reservation.run_id,
                    event_id=reservation.decision_event_id,
                    object_uri=reservation.decision_object_uri,
                    generation=reservation.decision_generation,
                )
                if decision.event_type != "operator_decision":
                    raise EvidenceStoreError(
                        "Completed decision receipt is not a decision event"
                    )
                visible.append(decision)
        return sorted(visible, key=lambda item: item.created_at)

    def runtime_receipt(self, run_id: str) -> RunReservation:
        return self.control_store.get_run(run_id)

    def emergency_state(self) -> EmergencyState:
        return self.control_store.get_emergency_state()

    def activate_emergency_stop(
        self,
        *,
        actor: OperatorIdentity,
        reason: str,
    ) -> EmergencyState:
        if actor.role not in {"operator", "runtime_admin"}:
            raise GeminiWorkflowStateError(
                "Only an operator or runtime administrator may stop Gemini"
            )
        return self.control_store.activate_emergency_stop(
            actor_principal_id=actor.stable_principal_id,
            reason=reason,
        )

    def clear_emergency_stop(
        self,
        *,
        actor: OperatorIdentity,
        reason: str,
        expected_epoch: int,
        exact_phrase: str,
    ) -> EmergencyState:
        if actor.role != "runtime_admin":
            raise GeminiWorkflowStateError(
                "Only a runtime administrator may clear the Gemini stop"
            )
        return self.control_store.clear_emergency_stop(
            actor_principal_id=actor.stable_principal_id,
            reason=reason,
            expected_epoch=expected_epoch,
            exact_phrase=exact_phrase,
        )

    def decide(
        self,
        run_id: str,
        request: HumanDecisionRequest,
        *,
        actor: OperatorIdentity,
    ) -> WorkflowRecord:
        if actor.role != "operator":
            raise GeminiWorkflowStateError(
                "Only the operator role may record a workflow decision"
            )
        request.validate_for_transition()
        reservation = self.control_store.get_run(run_id)
        if reservation.state != "completed":
            raise GeminiWorkflowStateError(
                "Only a completed, receipt-bound execution may be reviewed"
            )
        if getattr(reservation, "decision_event_id", None):
            raise GeminiWorkflowStateError(
                "An operator decision has already been recorded"
            )
        self.control_store.assert_epoch_current(
            run_id=run_id,
            expected_epoch=reservation.stop_epoch,
        )
        execution = self._completed_execution(reservation)
        if (
            request.decision == "approve"
            and execution.status != "pending_human_review"
        ):
            raise GeminiWorkflowStateError(
                "This workflow is not eligible for approval; resolve policy findings"
            )
        if execution.status not in {
            "pending_human_review",
            "clarification_required",
            "blocked",
        }:
            raise GeminiWorkflowStateError(
                "This workflow is not eligible for an operator decision"
            )

        reason, reason_redactions = redact_text(request.reason)
        instructions, instruction_redactions = redact_text(
            request.revision_instructions
        )
        event = {
            "event_type": "operator_decision",
            "run_id": execution.run_id,
            "correlation_id": execution.correlation_id,
            "status": f"operator_{request.decision}",
            "payload": {
                "decision": request.decision,
                "reason": reason,
                "revision_instructions": instructions,
                "redactions_applied": (
                    reason_redactions + instruction_redactions
                ),
                "approved_for_internal_use": request.decision == "approve",
                "approved_for_external_action": False,
                "external_business_action_performed": False,
                "operator_subject_sha256": actor.subject_sha256,
                "operator_principal_id": actor.stable_principal_id,
                "operator_auth_method": actor.auth_method,
                "identity_assurance": actor.identity_assurance,
                "operator_attestation_recorded": True,
                "human_identity_verified": (
                    False
                ),
                "identity_claim_scope": (
                    "shared_credential_or_attestation_not_verified_human"
                ),
                "binds_to_assessment_sha256": execution.payload.get(
                    "assessment_sha256"
                ),
                "binds_to_source_revision": execution.payload.get(
                    "source_revision"
                ),
                "binds_to_runtime_revision": execution.payload.get(
                    "runtime_revision"
                ),
                "binds_to_stop_epoch": reservation.stop_epoch,
                "binds_to_execution_event_id": execution.event_id,
                "binds_to_execution_object_uri": (
                    reservation.evidence_object_uri
                ),
                "binds_to_execution_generation": (
                    reservation.evidence_generation
                ),
            },
            "model_api_call_status": "not_attempted",
            "model_api_call_performed": False,
            "external_business_action_performed": False,
            "external_action_performed": False,
        }
        try:
            self.control_store.assert_epoch_current(
                run_id=run_id,
                expected_epoch=reservation.stop_epoch,
            )
            stored = (
                self.evidence_store.append_operator_decision_with_receipt(
                    event
                )
            )
            self.control_store.complete_decision(
                run_id=run_id,
                expected_epoch=reservation.stop_epoch,
                decision_event_id=stored.record.event_id,
                decision_object_uri=stored.receipt.object_uri,
                decision_generation=stored.receipt.generation,
            )
            return stored.record
        except EvidenceConflictError as exc:
            raise GeminiWorkflowStateError(str(exc)) from exc

    def _resolve_replay(self, reservation: RunReservation) -> WorkflowRecord:
        if reservation.state == "completed":
            return self._completed_execution(reservation)
        if reservation.state in {"reserved", "executing"}:
            raise GeminiWorkflowInProgressError(reservation.run_id)
        raise GeminiWorkflowStateError(
            "This idempotency key belongs to a terminal non-retriable run; "
            "use a new key only after accountable review"
        )

    def _completed_execution(
        self,
        reservation: RunReservation,
    ) -> WorkflowRecord:
        if (
            reservation.state != "completed"
            or not reservation.execution_event_id
        ):
            raise GeminiWorkflowStateError(
                "Workflow execution is not receipt-bound and completed"
            )
        execution = self.evidence_store.event_by_receipt(
            run_id=reservation.run_id,
            event_id=reservation.execution_event_id,
            object_uri=reservation.evidence_object_uri,
            generation=reservation.evidence_generation,
        )
        if execution.event_type != "gemini_execution":
            raise EvidenceStoreError(
                "Completed runtime receipt is not a Gemini execution event"
            )
        return execution

    def _best_effort_failure(
        self,
        *,
        run_id: str,
        correlation_id: str,
        status: str,
        failure_class: str,
        call_status: str,
        call_performed: bool | None,
    ) -> bool:
        try:
            self.evidence_store.append_with_receipt(
                {
                    "event_type": "gemini_failure",
                    "run_id": run_id,
                    "correlation_id": correlation_id,
                    "status": status,
                    "payload": {
                        "failure_class": failure_class,
                        "model_api_call_status": call_status,
                        "model_api_call_performed": call_performed,
                        "external_business_action_performed": False,
                        "source_revision": self.source_revision or None,
                        "runtime_revision": self.runtime_revision or None,
                    },
                    "model_api_call_status": call_status,
                    "model_api_call_performed": call_performed,
                    "external_business_action_performed": False,
                    "external_action_performed": False,
                }
            )
            return True
        except EvidenceStoreError:
            return False


def _sanitize_intake(
    intake: OpportunityIntake,
) -> tuple[dict[str, Any], dict[str, Any]]:
    title, title_redactions = redact_text(intake.title)
    description, description_redactions = redact_text(intake.description)
    constraints: list[str] = []
    constraint_redactions = 0
    for value in intake.constraints:
        clean, count = redact_text(value)
        constraints.append(clean)
        constraint_redactions += count
    redaction_count = (
        title_redactions + description_redactions + constraint_redactions
    )
    sanitized_input = {
        "title": title,
        "description": description,
        "source_url": safe_source_url(str(intake.source_url)),
        "constraints": constraints,
        "ai_assistance_permitted": intake.ai_assistance_permitted,
        "ai_disclosure_required": intake.ai_disclosure_required,
    }
    input_summary = {
        "title": title,
        "description_excerpt": description[:500],
        "source_origin": sanitized_input["source_url"],
        "constraint_count": len(intake.constraints),
        "redactions_applied": redaction_count,
        "ai_disclosure_required": intake.ai_disclosure_required,
        "provenance": "operator_supplied_unverified",
    }
    return sanitized_input, input_summary


def _estimate_reserved_tokens(
    sanitized_input: dict[str, Any],
    *,
    max_output_tokens: int,
) -> int:
    encoded = json.dumps(
        sanitized_input,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    estimated_prompt = math.ceil(
        (len(encoded) + len(SYSTEM_INSTRUCTION)) / 4
    )
    return max_output_tokens + max(1, estimated_prompt)


def _offline_actor() -> OperatorIdentity:
    return OperatorIdentity(
        principal_id="f" * 64,
        subject_sha256="f" * 64,
        role="operator",
        auth_method="offline_test",
        identity_assurance="offline_test",
    )


def _hash_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
