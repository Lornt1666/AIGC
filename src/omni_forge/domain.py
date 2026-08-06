from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Mapping, Sequence

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class Environment(str, Enum):
    TEST = "TEST"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    SANITIZED_NON_PERSONAL = "SANITIZED_NON_PERSONAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    PERSONAL = "PERSONAL"
    RESTRICTED = "RESTRICTED"


@dataclass(frozen=True)
class AgentInvocation:
    invocation_id: str
    agent_role: str
    allowed_inputs: tuple[str, ...]
    allowed_outputs: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    maximum_tokens: int
    maximum_cost_cad: float
    deadline_epoch_seconds: int
    data_classification: DataClassification
    authorization_scope: tuple[str, ...]
    parent_trace_id: str
    schema_digest: str
    environment: Environment = Environment.TEST
    metadata: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def compile(
        cls,
        *,
        invocation_id: str,
        agent_role: str,
        allowed_inputs: Sequence[str],
        allowed_outputs: Sequence[str],
        allowed_tools: Sequence[str],
        maximum_tokens: int,
        maximum_cost_cad: float,
        deadline_epoch_seconds: int,
        data_classification: DataClassification,
        authorization_scope: Sequence[str],
        parent_trace_id: str,
        schema_digest: str,
        environment: Environment = Environment.TEST,
        metadata: Mapping[str, str] | None = None,
    ) -> "AgentInvocation":
        invocation = cls(
            invocation_id=invocation_id.strip(),
            agent_role=agent_role.strip(),
            allowed_inputs=tuple(sorted(set(allowed_inputs))),
            allowed_outputs=tuple(sorted(set(allowed_outputs))),
            allowed_tools=tuple(sorted(set(allowed_tools))),
            maximum_tokens=maximum_tokens,
            maximum_cost_cad=float(maximum_cost_cad),
            deadline_epoch_seconds=deadline_epoch_seconds,
            data_classification=data_classification,
            authorization_scope=tuple(sorted(set(authorization_scope))),
            parent_trace_id=parent_trace_id.strip(),
            schema_digest=schema_digest,
            environment=environment,
            metadata=dict(metadata or {}),
        )
        invocation.verify()
        return invocation

    def verify(self) -> None:
        if not self.invocation_id or not self.agent_role or not self.parent_trace_id:
            raise ValueError("invocation identity, role and parent trace are required")
        if not _SHA256.fullmatch(self.schema_digest):
            raise ValueError("schema_digest must be a lowercase SHA-256 digest")
        if self.maximum_tokens <= 0:
            raise ValueError("maximum_tokens must be positive")
        if not 0 <= self.maximum_cost_cad <= 200:
            raise ValueError("maximum_cost_cad must be between CAD 0 and CAD 200")
        if self.deadline_epoch_seconds <= 0:
            raise ValueError("deadline must be positive")
        if self.environment is Environment.PRODUCTION:
            raise PermissionError("production agent invocation is not authorized")
        if self.data_classification in {
            DataClassification.PERSONAL,
            DataClassification.RESTRICTED,
        }:
            raise PermissionError("sensitive data is prohibited in the initial kernel")
        prohibited_tools = {
            "gmail.send",
            "github.merge",
            "github.auto_merge",
            "cloud.deploy",
            "cloud.create_resource",
            "financial.purchase",
            "model.live_call",
        }
        requested = prohibited_tools.intersection(self.allowed_tools)
        if requested:
            raise PermissionError(
                "initial kernel prohibits external-effect tools: "
                + ", ".join(sorted(requested))
            )
