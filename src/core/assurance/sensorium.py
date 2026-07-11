from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HEALTH_STATES = {
    "healthy",
    "degraded",
    "stale",
    "misconfigured",
    "unavailable",
    "untrusted_input",
}

SEVERITIES = {"info", "low", "medium", "high", "critical"}


@dataclass(frozen=True)
class SensoriumResult:
    passed: bool
    observation: dict[str, Any]
    finding: dict[str, Any] | None
    reason_codes: tuple[str, ...]


class AssuranceSensorium:
    """Deterministic local assurance sensing.

    The Sensorium observes declared repository evidence and emits EIAP-compatible
    Observation and Finding payloads. It never approves, merges, deploys, grants
    authority, accesses credentials, or performs network actions.
    """

    def observe(
        self,
        *,
        observation_id: str,
        sensor_id: str,
        revision: str,
        signal: str,
        health_state: str,
        domain: str,
        severity: str = "info",
        confidence: float = 1.0,
        blocking: bool = False,
        artifact: str | None = None,
    ) -> SensoriumResult:
        reasons: list[str] = []

        if len(revision) < 7:
            reasons.append("INVALID_REVISION")
        if health_state not in HEALTH_STATES:
            reasons.append("INVALID_SENSOR_HEALTH")
        if severity not in SEVERITIES:
            reasons.append("INVALID_SEVERITY")
        if not 0 <= confidence <= 1:
            reasons.append("INVALID_CONFIDENCE")
        if not signal.strip():
            reasons.append("EMPTY_SIGNAL")

        observation = {
            "contract_version": "1.0.0",
            "contract_type": "observation",
            "payload": {
                "observation_id": observation_id,
                "sensor_id": sensor_id,
                "revision": revision,
                "signal": signal,
                "health_state": health_state,
                "domain": domain,
                "artifact": artifact,
            },
        }

        finding: dict[str, Any] | None = None
        if health_state != "healthy" or blocking or severity in {"high", "critical"}:
            finding = {
                "contract_version": "1.0.0",
                "contract_type": "finding",
                "payload": {
                    "finding_id": f"FIND-{observation_id}",
                    "domain": domain,
                    "revision": revision,
                    "severity": severity,
                    "confidence": confidence,
                    "blocking": bool(blocking or health_state in {"unavailable", "untrusted_input"}),
                    "state": "open",
                    "observation_id": observation_id,
                    "artifact": artifact,
                    "reason_codes": tuple(reasons) or (f"SENSOR_{health_state.upper()}",),
                },
            }

        return SensoriumResult(not reasons, observation, finding, tuple(reasons))

    @staticmethod
    def aggregate(findings: list[dict[str, Any]]) -> str:
        """Fail-closed aggregation for advisory assurance findings."""
        if any(bool(item.get("payload", {}).get("blocking")) for item in findings):
            return "blocking"
        if any(item.get("payload", {}).get("severity") in {"high", "critical"} for item in findings):
            return "request_changes"
        if findings:
            return "pass_with_observations"
        return "pass"
