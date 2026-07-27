from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlsplit
import uuid

from .evidence import EvidenceConflictError, EvidenceStore
from .models import (
    GeminiAssessment,
    HumanDecisionRequest,
    OpportunityIntake,
    WorkflowRecord,
)
from .policy import evaluate_policy
from .provider import AssessmentProvider
from .redaction import redact_text, redact_value, safe_source_url


class GeminiWorkflowStateError(RuntimeError):
    """Raised when a governed workflow transition is invalid."""


class GeminiWorkflowService:
    def __init__(
        self,
        *,
        provider: AssessmentProvider,
        evidence_store: EvidenceStore,
    ) -> None:
        self.provider = provider
        self.evidence_store = evidence_store

    def create_workflow(self, intake: OpportunityIntake) -> WorkflowRecord:
        if not intake.ai_assistance_permitted:
            raise GeminiWorkflowStateError(
                "AI assistance is not permitted for this intake"
            )
        if urlsplit(str(intake.source_url)).scheme != "https":
            raise GeminiWorkflowStateError("source_url must use HTTPS")

        run_id = f"AIGC-GEMINI-RUN-{uuid.uuid4()}"
        correlation_id = f"AIGC-CORR-{uuid.uuid4()}"
        generation = self.provider.assess(
            intake,
            correlation_id=correlation_id,
        )
        assessment_raw, assessment_redactions = redact_value(
            generation.assessment.model_dump(mode="json")
        )
        assessment = GeminiAssessment.model_validate(assessment_raw)
        policy = evaluate_policy(intake, assessment)
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
            + assessment_redactions
        )
        sanitized_input = {
            "title": title,
            "description": description,
            "source_url": safe_source_url(str(intake.source_url)),
            "constraints": constraints,
            "ai_assistance_permitted": intake.ai_assistance_permitted,
            "ai_disclosure_required": intake.ai_disclosure_required,
        }

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
            "external_business_action_performed": False,
            "prompt_template_version": "aigc-gemini-opportunity-v1",
            "input_sha256": _hash_json(sanitized_input),
            "input_summary": {
                "title": title,
                "description_excerpt": description[:500],
                "source_url": sanitized_input["source_url"],
                "constraint_count": len(intake.constraints),
                "redactions_applied": redaction_count,
                "ai_disclosure_required": intake.ai_disclosure_required,
            },
            "assessment": assessment.model_dump(mode="json"),
            "assessment_sha256": _hash_json(
                assessment.model_dump(mode="json")
            ),
            "policy": policy.model_dump(mode="json"),
            "human_review_required": True,
        }
        status = (
            "pending_human_review"
            if policy.outcome == "allow_internal_draft"
            else policy.outcome
        )
        return self.evidence_store.append(
            {
                "event_type": "gemini_execution",
                "run_id": run_id,
                "correlation_id": correlation_id,
                "status": status,
                "payload": payload,
                "model_api_call_performed": generation.live_model_call,
                "external_business_action_performed": False,
                "external_action_performed": False,
            }
        )

    def get_workflow(self, run_id: str) -> list[WorkflowRecord]:
        events = self.evidence_store.events_for_run(run_id)
        if not events:
            raise GeminiWorkflowStateError("Workflow run not found")
        return events

    def decide(
        self,
        run_id: str,
        request: HumanDecisionRequest,
    ) -> WorkflowRecord:
        request.validate_for_transition()
        events = self.get_workflow(run_id)
        execution = next(
            (item for item in events if item.event_type == "gemini_execution"),
            None,
        )
        if execution is None:
            raise GeminiWorkflowStateError("Gemini execution event is missing")
        if any(item.event_type == "human_decision" for item in events):
            raise GeminiWorkflowStateError(
                "A human decision has already been recorded"
            )
        if execution.status != "pending_human_review":
            raise GeminiWorkflowStateError(
                "This workflow is not eligible for approval; resolve policy findings"
            )

        reason, reason_redactions = redact_text(request.reason)
        instructions, instruction_redactions = redact_text(
            request.revision_instructions
        )
        event = {
            "event_type": "human_decision",
            "run_id": execution.run_id,
            "correlation_id": execution.correlation_id,
            "status": f"human_{request.decision}",
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
            },
            "model_api_call_performed": False,
            "external_business_action_performed": False,
            "external_action_performed": False,
        }
        try:
            return self.evidence_store.append_human_decision(event)
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
