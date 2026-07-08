from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = "config/aigc_submission_approval_cockpit.json"
PHASE_NAME = "submission_approval_cockpit"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_json_if_exists(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_text_if_exists(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8", errors="ignore")


def load_config(root: Path, config_path: str) -> Dict[str, Any]:
    return load_json_if_exists(resolve_path(root, config_path), {})


def build_decision(root: Path, config: Dict[str, Any], decision: str, phrase: str) -> Dict[str, Any]:
    allowed = set(config.get("allowed_decisions", ["review_only", "proceed", "deny"]))
    if decision not in allowed:
        decision = "review_only"
    inputs = config.get("inputs", {})
    employer_packet_path = resolve_path(root, inputs.get("employer_packet", ""))
    employer_report_path = resolve_path(root, inputs.get("employer_report", ""))
    employer_audit_path = resolve_path(root, inputs.get("employer_audit", ""))
    gate_packet_path = resolve_path(root, inputs.get("auto_approval_gate_packet", ""))

    employer_packet = load_json_if_exists(employer_packet_path, {})
    gate_packet = load_json_if_exists(gate_packet_path, {})
    employer_report = load_text_if_exists(employer_report_path, "")
    employer_audit = load_text_if_exists(employer_audit_path, "")

    phrase_required = ""
    phrase_matched = False
    final_state = "pending_review"
    if decision == "proceed":
        phrase_required = config.get("required_proceed_phrase", "PROCEED AIGC SUBMISSION")
        phrase_matched = phrase.strip() == phrase_required
        final_state = "approved_for_submission_handoff" if phrase_matched else "blocked_phrase_mismatch"
    elif decision == "deny":
        phrase_required = config.get("required_deny_phrase", "DENY AIGC SUBMISSION")
        phrase_matched = phrase.strip() == phrase_required
        final_state = "denied_by_operator" if phrase_matched else "blocked_phrase_mismatch"
    else:
        final_state = "review_only_pending_decision"

    readiness = employer_packet.get("submission_readiness", {}) if isinstance(employer_packet, dict) else {}
    discipline = employer_packet.get("occupational_discipline_recognition", {}) if isinstance(employer_packet, dict) else {}

    return {
        "phase": PHASE_NAME,
        "generated_at": utc_now(),
        "status": final_state,
        "operator_decision_requested": decision,
        "required_phrase": phrase_required,
        "phrase_matched": phrase_matched,
        "button_state": {
            "review_only_available": True,
            "proceed_available": True,
            "deny_available": True,
            "proceed_records_handoff_only": True,
            "external_submission_performed": False,
        },
        "audit_view": {
            "employer_packet_found": employer_packet_path.exists(),
            "employer_report_found": employer_report_path.exists(),
            "employer_audit_found": employer_audit_path.exists(),
            "auto_approval_gate_packet_found": gate_packet_path.exists(),
            "employer_report_preview": employer_report[:4000],
            "employer_audit_preview": employer_audit[-4000:],
            "auto_approval_decision_counts": gate_packet.get("summary", {}).get("decision_counts", {}) if isinstance(gate_packet, dict) else {},
        },
        "submission_summary": {
            "primary_discipline": discipline.get("primary_discipline", "unknown"),
            "recognition_confidence": discipline.get("recognition_confidence", "unknown"),
            "readiness_score": readiness.get("readiness_score", 0),
            "recommended_decision": readiness.get("recommended_decision", "human_review_before_submission"),
            "submission_allowed_without_human": False,
        },
        "safety_result": {
            "external_action_performed": False,
            "auto_submitted_to_employer": False,
            "credential_use_performed": False,
            "secret_values_logged": False,
            "submission_handoff_authorized": final_state == "approved_for_submission_handoff",
            "submission_handoff_blocked": final_state != "approved_for_submission_handoff",
        },
    }


def render_cockpit(decision: Dict[str, Any]) -> str:
    summary = decision.get("submission_summary", {})
    audit = decision.get("audit_view", {})
    return f"""# AIGC Submission Approval Cockpit

Generated At: {decision['generated_at']}

Status: `{decision['status']}`

## Audit View

- Employer packet found: `{audit.get('employer_packet_found')}`
- Employer report found: `{audit.get('employer_report_found')}`
- Employer audit found: `{audit.get('employer_audit_found')}`
- Auto-approval gate packet found: `{audit.get('auto_approval_gate_packet_found')}`
- Gate decision counts: `{audit.get('auto_approval_decision_counts')}`

## Submission Summary

- Primary discipline: `{summary.get('primary_discipline')}`
- Recognition confidence: `{summary.get('recognition_confidence')}`
- Readiness score: `{summary.get('readiness_score')}`
- Recommended decision: `{summary.get('recommended_decision')}`
- Submission allowed without human: `false`

## Decision Buttons

### Review Only

Use when you want to inspect the audit without approving or denying:

```powershell
python .\src\submission_approval_cockpit.py --project-root . --config config\aigc_submission_approval_cockpit.json --decision review_only
```

### Proceed

Records approval for submission handoff only. It does not submit externally by itself.

```powershell
python .\src\submission_approval_cockpit.py --project-root . --config config\aigc_submission_approval_cockpit.json --decision proceed --phrase "PROCEED AIGC SUBMISSION"
```

### Deny

Blocks submission handoff.

```powershell
python .\src\submission_approval_cockpit.py --project-root . --config config\aigc_submission_approval_cockpit.json --decision deny --phrase "DENY AIGC SUBMISSION"
```

## Employer Report Preview

```text
{audit.get('employer_report_preview', '')}
```

## Latest Audit Preview

```text
{audit.get('employer_audit_preview', '')}
```

## Safety Boundary

No external action, credential use, secret logging, or employer submission occurred. A proceed decision only authorizes a future submission handoff after human review.
"""


def write_outputs(root: Path, config: Dict[str, Any], decision: Dict[str, Any]) -> Tuple[Path, Path, Path]:
    outputs = config.get("outputs", {})
    decision_path = resolve_path(root, outputs.get("decision", "data/submission_approval/aigc_submission_approval_decision.json"))
    cockpit_path = resolve_path(root, outputs.get("cockpit", "reports/submission_approval_cockpit.md"))
    audit_path = resolve_path(root, outputs.get("audit", "data/audit/aigc_submission_approval_audit.jsonl"))
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    cockpit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    cockpit_path.write_text(render_cockpit(decision), encoding="utf-8")
    audit_record = {
        "event_id": f"AIGC-SUBMISSION-APPROVAL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "generated_at": decision["generated_at"],
        "phase": PHASE_NAME,
        "status": decision["status"],
        "operator_decision_requested": decision["operator_decision_requested"],
        "phrase_matched": decision["phrase_matched"],
        "external_action_performed": False,
        "auto_submitted_to_employer": False,
        "submission_handoff_authorized": decision["safety_result"]["submission_handoff_authorized"],
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_record, ensure_ascii=False) + "\n")
    return decision_path, cockpit_path, audit_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIGC submission approval cockpit.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--decision", choices=["review_only", "proceed", "deny"], default="review_only")
    parser.add_argument("--phrase", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    config = load_config(root, args.config)
    decision = build_decision(root, config, args.decision, args.phrase)
    decision_path, cockpit_path, audit_path = write_outputs(root, config, decision)
    print(json.dumps({
        "phase": PHASE_NAME,
        "status": decision["status"],
        "decision_path": str(decision_path),
        "cockpit_path": str(cockpit_path),
        "audit_path": str(audit_path),
        "external_action_performed": False,
        "auto_submitted_to_employer": False,
        "submission_handoff_authorized": decision["safety_result"]["submission_handoff_authorized"],
    }, indent=2))
    return 0 if decision["status"] != "blocked_phrase_mismatch" else 2


if __name__ == "__main__":
    raise SystemExit(main())
