from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.phase2_radar import Classifier, OpportunityRecord, RadarScorer, SourceRisk


class Phase13AuditLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, data: Dict[str, Any]) -> None:
        event = {
            "timestamp": utc_now(),
            "event_type": event_type,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


class SyntheticSimulationArena:
    def __init__(self, root: Path, config_path: Path):
        self.root = root.resolve()
        self.config = json.loads(config_path.read_text(encoding="utf-8"))
        phase_config = self.config["phase13a"]
        self.output_path = self.resolve(phase_config["output_file"])
        self.report_path = self.resolve(phase_config["report_file"])
        self.ledger = Phase13AuditLedger(self.resolve(phase_config["audit_file"]))
        self.classifier = Classifier()
        self.scorer = RadarScorer()

    def run(self) -> List[OpportunityRecord]:
        records = [self._synthetic_documentation_record(), self._synthetic_risky_record()]
        processed: List[OpportunityRecord] = []
        for record in records:
            record = self.classifier.classify(record)
            record = self.scorer.score(record)
            processed.append(record)
            self.ledger.record("synthetic_record_processed", {
                "opportunity_id": record.opportunity_id,
                "title": record.title,
                "score": record.radar_score,
                "decision": record.radar_decision,
                "risk_flags": record.risk_flags,
            })
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps([asdict(item) for item in processed], ensure_ascii=False, indent=2), encoding="utf-8")
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(self.report(processed), encoding="utf-8")
        self.ledger.record("phase13a_synthetic_simulation_complete", {"records": len(processed), "external_action_performed": False})
        return processed

    def _synthetic_documentation_record(self) -> OpportunityRecord:
        return OpportunityRecord(
            opportunity_id=f"phase13a_synthetic_{uuid.uuid4().hex[:12]}",
            source_platform="Phase13 Synthetic Sandbox",
            source_type="synthetic_non_production",
            source_url="synthetic://documentation-task",
            source_attribution_required=False,
            discovered_at=utc_now(),
            title="Synthetic API Documentation Cleanup",
            employer="Synthetic Maintainer",
            work_type="open_source_contribution",
            platform_policy_status=SourceRisk.GREEN.value,
            description_plain=(
                "Synthetic non-production task: improve API documentation, README structure, "
                "authentication examples, and developer usage notes. Deliver Markdown docs and review notes."
            ),
        )

    def _synthetic_risky_record(self) -> OpportunityRecord:
        return OpportunityRecord(
            opportunity_id=f"phase13a_synthetic_{uuid.uuid4().hex[:12]}",
            source_platform="Phase13 Synthetic Sandbox",
            source_type="synthetic_non_production",
            source_url="synthetic://risky-task",
            source_attribution_required=False,
            discovered_at=utc_now(),
            title="Synthetic Blind Apply Request",
            employer="Synthetic Employer",
            work_type="job",
            platform_policy_status=SourceRisk.YELLOW.value,
            description_plain=(
                "Synthetic non-production risky task: apply to many jobs automatically, ignore platform checks, "
                "and send repeated messages. This should be flagged by AIGC safety rules."
            ),
        )

    def report(self, records: List[OpportunityRecord]) -> str:
        return "\n".join([
            "# AIGC Phase 13A Synthetic Simulation Report",
            "",
            f"Generated At: {utc_now()}",
            "",
            f"Records: {len(records)}",
            "",
            "External Action Performed: No",
            "",
            "Results:",
            json.dumps([
                {
                    "title": item.title,
                    "score": item.radar_score,
                    "decision": item.radar_decision,
                    "risk_flags": item.risk_flags,
                    "forbidden_flags": item.forbidden_flags,
                }
                for item in records
            ], indent=2),
        ]) + "\n"

    def resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 13A synthetic simulation arena.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "phase13_sandbox_arena.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    arena = SyntheticSimulationArena(root=args.root, config_path=args.config)
    records = arena.run()
    print(arena.report(records))
    print(f"Output exported: {arena.output_path}")
    print(f"Report exported: {arena.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
