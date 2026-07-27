from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlsplit
import uuid

from .evidence import (
    EvidenceConflictError,
    EvidenceStore,
    EvidenceStoreError,
)
from .models import (
    GeminiAssessment,
    HumanDecisionRequest,
    OperatorIdentity,
    OpportunityIntake,
    WorkflowRecord,
)
from .policy import evaluate_policy
from .provider import AssessmentProvider, GeminiProviderError
from .redaction import (
    contains_secret_material,
    redact_text,
    redact_value,
    safe_source_url,
)


class GeminiWorkflowStateError(RuntimeError):
    """Raised when a governed workflow transition is invalid."""


class GeminiWorkflowService:
    def __init__(
        self,
        *,
        provider: AssessmentProvider,
        evidence_store: EvidenceStore,
        source_revision: str = "",
        runtime_revision: str = "",
    ) -> None:
        self.provider = provider
        self.evidence_store = evidence_store
        self.source_revision = source_revision or ""
        self.runtime_revision = runtime_revision or ""

    def create_workflow(self, intake: OpportunityIntake) -> WorkflowRecord:
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

        run_id = f"AIGC-GEMINI-RUN-{uuid.uuid4()}"
        correlation_id = f"AIGC-CORR-{uuid.uuid4()}"
        title, title_redactions = redact_text(intake.title)
        description, description_redactions = redact_text(intake.description)
        constraints: list[str] = []
        constraint_redactions = 0
        for value in intake.constraints:
            clean, count = redact_text(value)
            constraints.append(clean)
            constraint_redactions += count
        redaction_count = (
            title_redactions
            + description_redactions
            + constraint_redactions
        )
        sanitized_input = {
            "title": title,
            "description": description,
            "source_url": safe_source_url(str(intake.source_url)),
            "constraints": constraints,
            "ai_assistance_permitted": intake.ai_assistance_permitted,
            "ai_disclosure_required": intake.ai_disclosure_required,
        }
        input_sha256 = _hash_json(sanitized_input)
        input_summary = {
            "title": title,
            "description_excerpt": description[:500],
            "source_origin": sanitized_input["source_url"],
            "constraint_count": len(intake.constraints),
            "redactions_applied": redaction_count,
            "ai_disclosure_required": intake.ai_disclosure_required,
            "provenance": "operator_supplied_unverified",
        }
        self.evidence_store.append(
            {
                "event_type": "workflow_started",
                "run_id": run_id,
                "correlation_id": correlation_id,
                "status": "executing",
                "payload": {
                    "input_sha256": input_sha256,
                    "input_summary": input_summary,
                    "source_revision": self.source_revision or None,
                    "runtime_revision": self.runtime_revision or None,
                    "model_api_call_status": "not_attempted",
                    "model_api_call_performed": False,
                    "external_business_action_performed": False,
                },
                "model_api_call_status": "not_attempted",
                "model_api_call_performed": False,
                "external_business_action_performed": False,
                "external_action_performed": False,
            }
        )
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
            self.evidence_store.append(
                {
                    "event_type": "gemini_failure",
                    "run_id": run_id,
                    "correlation_id": correlation_id,
                    "status": "failed_closed",
                    "payload": {
                        "failure_class": type(exc).__name__,
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
            if isinstance(exc, GeminiProviderError):
                raise
            raise GeminiProviderError(
                "Gemini provider failed unexpectedly",
                model_api_call_status=call_status,
                model_api_call_performed=call_performed,
            ) from exc

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
            return self.evidence_store.append(execution_event)
        except EvidenceStoreError:
            try:
                self.evidence_store.append(
                    {
                        "event_type": "gemini_failure",
                        "run_id": run_id,
                        "correlation_id": correlation_id,
                        "status": "failed_closed",
                        "payload": {
                            "failure_class": "EvidencePersistenceFailure",
                            "model_api_call_status": (
                                "confirmed"
                                if generation.live_model_call
                                else "not_attempted"
                            ),
                            "model_api_call_performed": (
                                generation.live_model_call
                            ),
                            "external_business_action_performed": False,
                            "source_revision": self.source_revision or None,
                            "runtime_revision": self.runtime_revision or None,
                        },
                        "model_api_call_status": (
                            "confirmed"
                            if generation.live_model_call
                            else "not_attempted"
                        ),
                        "model_api_call_performed": generation.live_model_call,
                        "external_business_action_performed": False,
                        "external_action_performed": False,
                    }
                )
            except EvidenceStoreError:
                pass
            raise

    def get_workflow(self, run_id: str) -> list[WorkflowRecord]:
        events = self.evidence_store.events_for_run(run_id)
        if not events:
            raise GeminiWorkflowStateError("Workflow run not found")
        return events

    def decide(
        self,
        run_id: str,
        request: HumanDecisionRequest,
        *,
        actor: OperatorIdentity,
    ) -> WorkflowRecord:
        request.validate_for_transition()
        events = self.get_workflow(run_id)
        execution = next(
            (item for item in events if item.event_type == "gemini_execution"),
            None,
        )
        if execution is None:
            raise GeminiWorkflowStateError("Gemini execution event is missing")
        if any(item.event_type == "operator_decision" for item in events):
            raise GeminiWorkflowStateError(
                "An operator decision has already been recorded"
            )
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
                "operator_auth_method": actor.auth_method,
                "identity_assurance": actor.identity_assurance,
                "operator_attestation_recorded": True,
                "human_identity_verified": False,
                "binds_to_assessment_sha256": execution.payload.get(
                    "assessment_sha256"
                ),
                "binds_to_source_revision": execution.payload.get(
                    "source_revision"
                ),
            },
            "model_api_call_status": "not_attempted",
            "model_api_call_performed": False,
            "external_business_action_performed": False,
            "external_action_performed": False,
        }
        try:
            return self.evidence_store.append_operator_decision(event)
        except EvidenceConflictError as exc:
            raise GeminiWorkflowStateError(str(exc)) from exc


def _hash_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
