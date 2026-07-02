from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.phase2_radar import CONNECTORS, Classifier, OpportunityRecord, RadarScorer, load_json


class Phase13ReplayAuditLedger:
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


class RealDataReplaySandbox:
    SOURCE_ALIASES = {
        "github_issues": "github",
        "github": "github",
        "weworkremotely": "weworkremotely",
        "wwr": "weworkremotely",
        "remoteok": "remoteok",
        "remotive": "remotive",
    }

    def __init__(self, root: Path, config_path: Path):
        self.root = root.resolve()
        self.config = json.loads(config_path.read_text(encoding="utf-8"))
        phase_config = self.config["phase13b"]
        self.output_path = self.resolve(phase_config["output_file"])
        self.report_path = self.resolve(phase_config["report_file"])
        self.ledger = Phase13ReplayAuditLedger(self.resolve(phase_config["audit_file"]))
        self.classifier = Classifier()
        self.scorer = RadarScorer()

    def replay(self, source: str, limit: int) -> Dict[str, Any]:
        source_slug = self.SOURCE_ALIASES.get(source, source)
        allowed = set(self.config["phase13b"].get("allowed_sources", []))
        if source not in allowed and source_slug not in allowed and source != "github_issues":
            raise ValueError(f"Source not allowed for Phase 13B replay: {source}")
        phase2_config = load_json(self.root / "config" / "phase2_sources.json")
        source_config = self._source_config(phase2_config, source_slug)
        run_config = {
            **phase2_config.get("run", {}),
            "max_per_source": limit,
            "timeout_seconds": self.config["phase13b"].get("timeout_seconds", 20),
            "user_agent": self.config["phase13b"].get("user_agent", "AIGC-Phase13B-RealDataReplay/0.1 read-only"),
        }
        connector_type = CONNECTORS.get(source_config.get("connector"))
        if connector_type is None:
            raise ValueError(f"Connector not implemented for source: {source}")
        connector = connector_type(source_config, run_config)
        self.ledger.record("phase13b_replay_started", {
            "source": source,
            "source_slug": source_slug,
            "limit": limit,
            "external_action_performed": False,
            "mode": "read_only_get",
        })
        fetch_result = connector.fetch()
        records = self._dedupe(fetch_result.normalized_records)[:limit]
        processed: List[OpportunityRecord] = []
        for record in records:
            record = self.classifier.classify(record)
            record = self.scorer.score(record)
            processed.append(record)
        payload = {
            "phase": "Phase 13B - Real Data Replay Sandbox",
            "generated_at": utc_now(),
            "source": source,
            "source_platform": fetch_result.source_name,
            "raw_records": len(fetch_result.raw_records),
            "processed_records": len(processed),
            "external_action_performed": False,
            "forbidden_actions_confirmed": self.config.get("forbidden_actions", []),
            "records": [asdict(item) for item in processed],
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(self.report(payload), encoding="utf-8")
        self.ledger.record("phase13b_replay_complete", {
            "source": source,
            "raw_records": len(fetch_result.raw_records),
            "processed_records": len(processed),
            "external_action_performed": False,
        })
        return payload

    def _source_config(self, phase2_config: Dict[str, Any], source_slug: str) -> Dict[str, Any]:
        for source in phase2_config.get("sources", []):
            if source.get("slug") == source_slug:
                return {**source, "enabled": True}
        raise ValueError(f"Source not found in Phase 2 config: {source_slug}")

    def _dedupe(self, records: List[OpportunityRecord]) -> List[OpportunityRecord]:
        seen = set()
        output: List[OpportunityRecord] = []
        for record in records:
            key = (record.source_platform.lower(), record.title.lower(), record.employer.lower(), record.source_url.lower())
            if key in seen:
                continue
            seen.add(key)
            output.append(record)
        return output

    def report(self, payload: Dict[str, Any]) -> str:
        top = [
            {
                "title": item["title"],
                "employer": item["employer"],
                "score": item["radar_score"],
                "decision": item["radar_decision"],
                "url": item["source_url"],
            }
            for item in payload["records"][:10]
        ]
        return "\n".join([
            "# AIGC Phase 13B Real Data Replay Report",
            "",
            f"Generated At: {payload['generated_at']}",
            f"Source: {payload['source_platform']}",
            f"Raw Records: {payload['raw_records']}",
            f"Processed Records: {payload['processed_records']}",
            "",
            "External Action Performed: No",
            "",
            "Safety Boundary:",
            "- No applications",
            "- No messages",
            "- No bids",
            "- No submissions",
            "- No credential use",
            "- No employer contact",
            "",
            "Top Records:",
            json.dumps(top, indent=2),
        ]) + "\n"

    def resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 13B real public read-only data replay.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "phase13_sandbox_arena.json")
    parser.add_argument("--source", choices=["remoteok", "remotive", "weworkremotely", "github_issues"], default="remoteok")
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    replay = RealDataReplaySandbox(root=args.root, config_path=args.config)
    payload = replay.replay(source=args.source, limit=args.limit)
    print(replay.report(payload))
    print(f"Output exported: {replay.output_path}")
    print(f"Report exported: {replay.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
