from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from src.domain.nexus.contracts import NexusContract


CoordinatorWorkflow = Literal[
    "APPLY_JOBS",
    "ARTICULATE_PRACTICES",
    "SUBMIT_WORK",
    "INVOICE_HOURS",
]
Modality = Literal["TEXT", "AUDIO", "VISION", "STRUCTURED_DATA"]

DiagnosticDisposition = Literal["AUTO_REMEDIATED", "ESCALATED_FOR_APPROVAL"]
RemediationMode = Literal["AUTO_LOCAL", "ESCALATE"]


class CoordinatorRequest(NexusContract):
    """Non-authoritative input for a local workflow plan."""

    request_id: str = Field(pattern=r"^RXREQ-[A-Z0-9_-]{6,64}$")
    workflow: CoordinatorWorkflow
    objective: str = Field(min_length=1, max_length=2000)
    target_ref: str | None = Field(default=None, min_length=1, max_length=500)
    artifact_refs: tuple[str, ...] = Field(default=(), max_length=50)
    consent_artifact_ref: str | None = Field(
        default=None, pattern=r"^consent://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{1,480}$"
    )
    credential_ref: str | None = Field(
        default=None, pattern=r"^gsm://[A-Za-z0-9._/-]{3,480}$"
    )
    requested_modalities: tuple[Modality, ...] = ("TEXT",)

    @model_validator(mode="after")
    def require_unique_artifacts(self) -> "CoordinatorRequest":
        if len(self.artifact_refs) != len(set(self.artifact_refs)):
            raise ValueError("artifact_refs must be unique")
        if not self.requested_modalities:
            raise ValueError("at least one modality is required")
        if len(self.requested_modalities) != len(set(self.requested_modalities)):
            raise ValueError("requested_modalities must be unique")
        return self


class DiagnosticScenario(NexusContract):
    schema_version: Literal["regenexcalibur.diagnostic-scenario.v1"]
    scenario_id: str = Field(pattern=r"^[a-z][a-z0-9_]{3,80}$")
    detection_code: Literal[
        "PRE_CRED_EXPIRY",
        "BUILD_DEP_CONFLICT_POST",
        "DB_DEADLOCK_IN_CONCURRENCY",
        "NET_PARTITION_IN_RETRY",
        "AUTH_FORBIDDEN",
        "FORMAT_REJECT_POST",
    ]
    classification: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,80}$")
    remediation_mode: RemediationMode
    expected_blocker: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{2,120}$")
    observed_at: datetime
    injection: dict[str, str]
    remediation_plan: tuple[str, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def enforce_escalation_blocker(self) -> "DiagnosticScenario":
        if self.remediation_mode == "ESCALATE" and self.expected_blocker is None:
            raise ValueError("escalating scenarios require expected_blocker")
        if self.remediation_mode == "AUTO_LOCAL" and self.expected_blocker is not None:
            raise ValueError("local auto-remediation cannot carry an external blocker")
        return self


class AuditEntryPost(NexusContract):
    audit_entry_id: str = Field(pattern=r"^AUDIT-RX-[A-F0-9]{24}$")
    timestamp: datetime
    actor_agent_id: Literal["AGENT-DOCTRINE-DIAGNOSTIC"]
    operator_consent_token_id: None = None
    action: str = Field(min_length=1, max_length=300)
    justification: str = Field(min_length=1, max_length=1000)
    affix_metadata: dict[str, str]
    external_action_performed: Literal[False] = False
    authority_granted: Literal[False] = False
