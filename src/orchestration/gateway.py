from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List


REQUIRED_CORRELATION_FIELDS = {
    "workflow_execution_id",
    "audit_event_id",
    "work_order_id",
    "action_permit_id",
    "requires_human_approval",
    "external_action_performed",
}

SECRET_VALUE_PATTERNS = [
    "sk-",
    "ghp_",
    "xoxb-",
    "bearer ",
    "api_key=",
    "client_secret=",
    "password=",
]

LOCAL_PATH_PATTERNS = [
    "C:\\Users\\",
    "C:/Users/",
    "/home/",
    "/Users/",
]


@dataclass(frozen=True)
class TemplateValidationResult:
    path: str
    valid: bool
    findings: List[str]


def validate_n8n_template(path: Path) -> TemplateValidationResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    findings: List[str] = []
    if payload.get("dryRun") is not True:
        findings.append("dryRun must be true.")
    if payload.get("externalActionNodesDisabled") is not True:
        findings.append("externalActionNodesDisabled must be true.")
    if payload.get("humanApprovalWaitStep") is not True:
        findings.append("humanApprovalWaitStep must be true.")
    fields = set(payload.get("correlationFields", []))
    missing_fields = REQUIRED_CORRELATION_FIELDS - fields
    if missing_fields:
        findings.append(f"missing correlation fields: {sorted(missing_fields)}")
    for node in payload.get("nodes", []):
        if node.get("externalAction") is True and node.get("disabled") is not True:
            findings.append(f"external action node is not disabled: {node.get('name', '<unnamed>')}")
    findings.extend(_scan_payload(payload))
    return TemplateValidationResult(path=str(path), valid=not findings, findings=findings)


def validate_n8n_templates(root: Path) -> List[TemplateValidationResult]:
    template_root = root / "workflows" / "n8n"
    if not template_root.exists():
        raise FileNotFoundError(f"n8n template directory not found: {template_root}")
    return [validate_n8n_template(path) for path in sorted(template_root.glob("*.template.json"))]


def assert_n8n_templates_safe(root: Path) -> List[TemplateValidationResult]:
    results = validate_n8n_templates(root)
    failures = [result for result in results if not result.valid]
    if failures:
        summary = "; ".join(f"{result.path}: {result.findings}" for result in failures)
        raise ValueError(f"n8n template validation failed: {summary}")
    return results


def _scan_payload(payload: Any) -> List[str]:
    findings: List[str] = []
    for path, value in _walk(payload):
        lowered = str(value).lower()
        if path.lower().endswith(".credentials"):
            findings.append(f"credential key present at {path}")
        if isinstance(value, str):
            if "http://" in lowered or "https://" in lowered:
                findings.append(f"literal URL present at {path}")
            if "production" in lowered or "prod." in lowered:
                findings.append(f"production wording present at {path}")
            if any(pattern.lower() in lowered for pattern in SECRET_VALUE_PATTERNS):
                findings.append(f"secret-like value present at {path}")
            if any(pattern in value for pattern in LOCAL_PATH_PATTERNS):
                findings.append(f"local path present at {path}")
    return findings


def _walk(value: Any, prefix: str = "$") -> Iterable[tuple[str, Any]]:
    yield prefix, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f"{prefix}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{prefix}[{index}]")
