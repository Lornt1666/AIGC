from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gemini_workflow.evidence import JsonlEvidenceStore  # noqa: E402
from src.gemini_workflow.models import (  # noqa: E402
    GeminiAssessment,
    HumanDecisionRequest,
    OpportunityIntake,
)
from src.gemini_workflow.provider import StubGeminiProvider  # noqa: E402
from src.gemini_workflow.service import GeminiWorkflowService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="reports/artifacts/gemini_workflow_smoke",
    )
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assessment = GeminiAssessment(
        fit_score=82,
        recommendation="pursue",
        rationale=[
            "The requested work matches the supplied capability profile.",
            "The scope can be reviewed before any external commitment.",
        ],
        evidence_basis=[
            {
                "input_pointer": "/description",
                "observation": (
                    "The fixture describes an internal, governed validation."
                ),
                "impact": "positive",
            }
        ],
        assumptions=["Customer identity and contract terms remain unverified."],
        risks=[],
        clarifying_questions=["What is the required delivery date?"],
        proposed_scope=["Prepare an internal reviewable scope draft."],
        ai_use_disclosure=(
            "AI assisted with opportunity assessment and scope drafting; "
            "a human reviewed the result before use."
        ),
        human_review_required=True,
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        evidence_path = Path(temp_dir) / "events.jsonl"
        service = GeminiWorkflowService(
            provider=StubGeminiProvider(assessment),
            evidence_store=JsonlEvidenceStore(evidence_path),
        )
        execution = service.create_workflow(
            OpportunityIntake(
                title="Synthetic CI opportunity",
                description=(
                    "Offline fixture used to validate governance and evidence "
                    "contracts without contacting Gemini or another provider."
                ),
                source_url="https://example.invalid/opportunity",
                constraints=[
                    "No external business action.",
                    "Human review required.",
                ],
                ai_assistance_permitted=True,
                ai_disclosure_required=True,
            )
        )
        decision = service.decide(
            execution.run_id,
            HumanDecisionRequest(
                decision="approve",
                reason="The synthetic internal draft passed offline review.",
            ),
        )
        events = [
            item.model_dump(mode="json")
            for item in service.get_workflow(execution.run_id)
        ]

    if execution.payload["live_model_call"] is not False:
        raise SystemExit("Offline smoke must never claim a live Gemini call")
    if any(item["model_api_call_performed"] for item in events):
        raise SystemExit("Offline smoke must never record a model API call")
    if any(item["external_business_action_performed"] for item in events):
        raise SystemExit(
            "Offline smoke must never record an external business action"
        )

    report = {
        "mode": "offline_contract_smoke",
        "live_gemini_call_performed": False,
        "model_api_call_performed": False,
        "external_business_action_performed": False,
        "human_decision_recorded": decision.status == "human_approve",
        "event_count": len(events),
        "contracts_verified": [
            "structured_assessment",
            "input_evidence_pointers",
            "deterministic_policy",
            "human_decision",
            "record_integrity_hash",
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
