from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUTHORIZATIONS_PATH = Path("data/phase5_authorizations/aigc_phase5_authorization_packets.json")
DEFAULT_WORK_ORDERS_PATH = Path("data/phase23_work_orders/aigc_phase23_work_order_governance_records.json")

SAFETY_BOUNDARY = [
    "The cockpit never performs external submission, messaging, bidding, payment, credential use, or platform automation.",
    "Run prepares, validates, audits, and generates reviewable artifacts only.",
    "Accept records one exact scoped Phase 5 decision and keeps external_action_performed=false.",
    "Manual handoff remains separate, visible, and revocable by emergency stop.",
    "Deny and Revise remain first-class outcomes; acceptance is never assumed.",
]

ENTERPRISE_RUN_SEQUENCE = [
    ("Runtime preflight", ("run", "phase14"), "internal_preflight"),
    ("Connector governance", ("run", "phase10"), "read_only_connector_registry"),
    ("Secret-vault fake test", ("run", "phase11"), "no_secret_value_logging"),
    ("Opportunity radar", ("run", "phase2"), "approved_sources_read_only"),
    ("Ology assessment", ("run", "phase3"), "internal_assessment_only"),
    ("Proposal drafting", ("run", "phase4"), "internal_draft_only"),
    ("Human approval packet generation", ("run", "phase5"), "human_review_required"),
    ("Finance and contract ledger", ("run", "phase15"), "internal_finance_tracking_only"),
    ("Compliance and legal review", ("run", "phase16"), "internal_compliance_review_only"),
    ("Sub-agent planning", ("run", "phase19"), "internal_planning_only"),
    ("Fidelity forge", ("run", "phase20"), "internal_quality_review_only"),
    ("Customer satisfaction continuum", ("run", "phase21"), "internal_customer_fit_scoring_only"),
    ("Quality-state kernel", ("run", "phase22"), "internal_uncertainty_model_only"),
    ("Ascended work-order governor", ("run", "phase23"), "internal_work_order_governance_only"),
    ("Autonomic business pipeline", ("run", "phase24"), "internal_business_pipeline_readiness_only"),
    ("Productization readiness", ("run", "phase18"), "internal_release_readiness_only"),
    ("Observability refresh", ("run", "phase12"), "internal_observability_only"),
    ("Contract validation", ("validate",), "schema_contract_validation"),
]


@dataclass(frozen=True)
class GovernedCommand:
    label: str
    command: List[str]
    safety_class: str


@dataclass(frozen=True)
class CommandResult:
    label: str
    command: List[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class AuthorizationReview:
    action_id: str
    authorization_id: str
    proposal_id: str
    opportunity_id: str
    decision: str
    recipient: str
    platform: str
    proposed_external_action: str
    risk_class: str
    safety_status: str
    artifact_type: str
    artifact_hash: str
    artifact_preview: str
    required_phrase: str
    denial_phrase: str
    revision_phrase_template: str
    expires_at: str
    expired: bool
    ai_disclosure_status: str
    quality_state: str
    required_next_actions: List[str]
    blocked_actions: List[str]
    external_action_performed: bool


def resolve_project_path(root: Path, path: str | Path) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return root / value


def load_json_list(path: Path) -> List[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list at {path}")
    return [item for item in payload if isinstance(item, dict)]


def load_authorization_packets(
    root: Path = PROJECT_ROOT,
    authorizations_path: Path = DEFAULT_AUTHORIZATIONS_PATH,
) -> List[dict[str, Any]]:
    return load_json_list(resolve_project_path(root, authorizations_path))


def load_work_order_governance_records(
    root: Path = PROJECT_ROOT,
    work_orders_path: Path = DEFAULT_WORK_ORDERS_PATH,
) -> List[dict[str, Any]]:
    return load_json_list(resolve_project_path(root, work_orders_path))


def index_work_orders_by_proposal(work_orders: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in work_orders:
        proposal_id = str(item.get("proposal_id", "") or item.get("work_order_id", ""))
        if proposal_id:
            indexed[proposal_id] = item
    return indexed


def summarize_authorizations(
    packets: Iterable[dict[str, Any]],
    work_orders: Iterable[dict[str, Any]] | None = None,
) -> List[AuthorizationReview]:
    work_order_index = index_work_orders_by_proposal(work_orders or [])
    reviews = [
        summarize_authorization_packet(packet, work_order_index.get(str(packet.get("proposal_id", ""))))
        for packet in packets
    ]
    return sorted(reviews, key=lambda item: (item.expired, item.decision != "pending", item.action_id))


def summarize_authorization_packet(
    packet: dict[str, Any],
    work_order: dict[str, Any] | None = None,
) -> AuthorizationReview:
    artifact = packet.get("artifact", {}) or {}
    classification = packet.get("classification", {}) or {}
    checks = packet.get("checks", {}) or {}
    approval = packet.get("approval", {}) or {}
    phase6_status = packet.get("phase6_status", {}) or {}
    work_order = work_order or {}
    ascended = work_order.get("ascended_output_v2", {}) or {}
    return AuthorizationReview(
        action_id=str(packet.get("action_id", "")),
        authorization_id=str(packet.get("authorization_id", "")),
        proposal_id=str(packet.get("proposal_id", "")),
        opportunity_id=str(packet.get("opportunity_id", "")),
        decision=str(packet.get("decision", "unknown")),
        recipient=str(packet.get("recipient", "")),
        platform=str(packet.get("platform", "")),
        proposed_external_action=str(packet.get("proposed_external_action", "")),
        risk_class=str(classification.get("risk_class", "unknown")),
        safety_status=str(classification.get("safety_status", "unknown")),
        artifact_type=str(artifact.get("artifact_type", "")),
        artifact_hash=str(artifact.get("artifact_hash", "")),
        artifact_preview=str(artifact.get("artifact_preview", "")),
        required_phrase=str(approval.get("required_phrase", "")),
        denial_phrase=str(approval.get("denial_phrase", "")),
        revision_phrase_template=str(approval.get("revision_phrase_template", "")),
        expires_at=str(packet.get("expires_at", "")),
        expired=authorization_expired(packet),
        ai_disclosure_status=str(checks.get("ai_disclosure_status", "unknown")),
        quality_state=str(ascended.get("quality_state", work_order.get("status", "not_available"))),
        required_next_actions=[str(item) for item in ascended.get("required_next_actions", [])],
        blocked_actions=[str(item) for item in ascended.get("blocked_actions", [])],
        external_action_performed=bool(phase6_status.get("external_action_performed", False)),
    )


def render_review_markdown(review: AuthorizationReview) -> str:
    required_actions = "\n".join(f"- {item}" for item in review.required_next_actions[:12]) or "- None recorded."
    blocked_actions = "\n".join(f"- {item}" for item in review.blocked_actions[:12]) or "- No blocked-action list found."
    preview = review.artifact_preview.strip() or "No artifact preview available."
    return f"""## Human Review Packet: {review.action_id}

**Recipient:** {review.recipient or "Not specified"}  
**Platform:** {review.platform or "Not specified"}  
**Decision State:** {review.decision}  
**Expired:** {"Yes" if review.expired else "No"}  
**Risk:** {review.risk_class} / {review.safety_status}  
**AI Disclosure:** {review.ai_disclosure_status}  
**Quality State:** {review.quality_state}

### Proposed External Action
{review.proposed_external_action or "No proposed action recorded."}

### Artifact
- Type: `{review.artifact_type or "unknown"}`
- SHA-256 hash: `{review.artifact_hash or "missing"}`

```text
{preview[:2400]}
```

### Required Next Actions
{required_actions}

### Blocked Actions
{blocked_actions}

### What Accept Does
Accept records this exact action as approved for Phase 6 eligibility inside the local governance ledger.

### What Accept Does Not Do
Accept does not submit, message, bid, apply, request payment, use credentials, automate a platform, hide uncertainty, or bypass compliance.
"""


def build_aigc_command(root: Path, *args: str) -> List[str]:
    return [
        sys.executable,
        str(root / "src" / "aigc.py"),
        "--root",
        str(root),
        *args,
    ]


def build_enterprise_run_commands(root: Path = PROJECT_ROOT) -> List[GovernedCommand]:
    return [
        GovernedCommand(
            label=label,
            command=build_aigc_command(root, *command_args),
            safety_class=safety_class,
        )
        for label, command_args, safety_class in ENTERPRISE_RUN_SEQUENCE
    ]


def build_accept_command(
    root: Path,
    review: AuthorizationReview,
    typed_phrase: str,
    authorizations_path: Path = DEFAULT_AUTHORIZATIONS_PATH,
) -> List[str]:
    if not accept_phrase_matches_required(review, typed_phrase):
        raise ValueError("Typed acceptance phrase does not match the required phrase.")
    return build_aigc_command(
        root,
        "approve",
        "--action-id",
        review.action_id,
        "--phrase",
        typed_phrase,
        "--authorizations-path",
        str(authorizations_path),
    )


def accept_phrase_matches_required(review: AuthorizationReview, typed_phrase: str) -> bool:
    return bool(review.required_phrase) and typed_phrase == review.required_phrase


def build_deny_command(
    root: Path,
    review: AuthorizationReview,
    authorizations_path: Path = DEFAULT_AUTHORIZATIONS_PATH,
) -> List[str]:
    return build_aigc_command(
        root,
        "deny",
        "--action-id",
        review.action_id,
        "--phrase",
        review.denial_phrase,
        "--authorizations-path",
        str(authorizations_path),
    )


def build_revise_command(
    root: Path,
    review: AuthorizationReview,
    revision_instructions: str,
    authorizations_path: Path = DEFAULT_AUTHORIZATIONS_PATH,
) -> List[str]:
    phrase = f"Revise action {review.action_id}: {revision_instructions.strip()}"
    return build_aigc_command(
        root,
        "revise",
        "--action-id",
        review.action_id,
        "--phrase",
        phrase,
        "--authorizations-path",
        str(authorizations_path),
    )


def run_command(
    command: Sequence[str],
    root: Path,
    label: str = "",
    timeout_seconds: int = 120,
) -> CommandResult:
    try:
        result = subprocess.run(
            list(command),
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=max(1, timeout_seconds),
        )
        return CommandResult(
            label=label or " ".join(command),
            command=list(command),
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return CommandResult(
            label=label or " ".join(command),
            command=list(command),
            returncode=124,
            stdout=stdout,
            stderr=(stderr + f"\nTimed out after {max(1, timeout_seconds)} seconds.").strip(),
        )


def run_command_sequence(commands: Iterable[GovernedCommand], root: Path, stop_on_failure: bool = True) -> List[CommandResult]:
    results: List[CommandResult] = []
    for governed_command in commands:
        result = run_command(governed_command.command, root=root, label=governed_command.label)
        results.append(result)
        if stop_on_failure and not result.ok:
            break
    return results


def authorization_expired(packet: dict[str, Any]) -> bool:
    expires_at = parse_datetime(str(packet.get("expires_at", "")))
    if expires_at is None:
        return True
    return datetime.now(timezone.utc) > expires_at


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def reviews_to_dicts(reviews: Iterable[AuthorizationReview]) -> List[dict[str, Any]]:
    return [asdict(review) for review in reviews]
