"""Read-only Ω Mission OS Mission Director.

The director composes allowlisted repository artifacts into a deterministic snapshot.
It never writes canonical state, invokes connectors, approves actions, or performs
external execution. Missing and malformed sources are reported rather than hidden.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    relative_path: str
    optional: bool = True


DEFAULT_SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec("phase2_opportunities", "data/phase2_processed/aigc_phase2_opportunity_queue.json"),
    SourceSpec("phase3_assessments", "data/phase3_processed/aigc_phase3_assessment_dossiers.json"),
    SourceSpec("phase4_proposals", "data/phase4_proposals/aigc_phase4_proposal_packages.json"),
    SourceSpec("phase5_authorizations", "data/phase5_authorizations/aigc_phase5_authorization_packets.json"),
    SourceSpec("phase15_finance", "data/phase15_finance/aigc_phase15_finance_ledger.json"),
    SourceSpec("phase16_compliance", "data/phase16_compliance/aigc_phase16_compliance_reviews.json"),
    SourceSpec("phase20_fidelity", "data/phase20_fidelity/aigc_phase20_fidelity_reviews.json"),
    SourceSpec("phase21_customer_satisfaction", "data/phase21_customer_satisfaction/aigc_phase21_customer_satisfaction_records.json"),
    SourceSpec("phase22_quality", "data/phase22_quality/aigc_phase22_quality_kernel_records.json"),
    SourceSpec("readiness", "data/production_readiness.json"),
)


class MissionDirector:
    """Compose a read-only mission snapshot from allowlisted local artifacts."""

    def __init__(self, repository_root: Path | str, sources: Sequence[SourceSpec] = DEFAULT_SOURCES) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.sources = tuple(sources)
        self._assert_safe_sources()

    def _assert_safe_sources(self) -> None:
        for source in self.sources:
            candidate = (self.repository_root / source.relative_path).resolve()
            if self.repository_root != candidate and self.repository_root not in candidate.parents:
                raise ValueError(f"source escapes repository root: {source.relative_path}")

    @staticmethod
    def _sha256(raw: bytes) -> str:
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _record_count(value: Any) -> int:
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            for key in ("records", "items", "opportunities", "proposals", "reviews", "packets"):
                candidate = value.get(key)
                if isinstance(candidate, list):
                    return len(candidate)
            return 1
        return 0

    def _read_source(self, spec: SourceSpec) -> tuple[dict[str, Any], Any | None]:
        path = (self.repository_root / spec.relative_path).resolve()
        if not path.exists():
            return ({
                "source_id": spec.source_id,
                "path": spec.relative_path,
                "status": "MISSING",
                "digest": None,
                "records": 0,
                "message": "optional source not present" if spec.optional else "required source not present",
            }, None)
        if not path.is_file():
            return ({
                "source_id": spec.source_id,
                "path": spec.relative_path,
                "status": "UNSUPPORTED",
                "digest": None,
                "records": 0,
                "message": "source is not a regular file",
            }, None)
        raw = path.read_bytes()
        digest = self._sha256(raw)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return ({
                "source_id": spec.source_id,
                "path": spec.relative_path,
                "status": "INVALID",
                "digest": digest,
                "records": 0,
                "message": f"invalid JSON: {exc}",
            }, None)
        return ({
            "source_id": spec.source_id,
            "path": spec.relative_path,
            "status": "AVAILABLE",
            "digest": digest,
            "records": self._record_count(value),
            "message": None,
        }, value)

    def _git_revision(self) -> str | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repository_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        revision = result.stdout.strip().lower()
        return revision if len(revision) == 40 and all(c in "0123456789abcdef" for c in revision) else None

    @staticmethod
    def _iter_dicts(value: Any) -> Iterable[Mapping[str, Any]]:
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from MissionDirector._iter_dicts(child)
        elif isinstance(value, list):
            for child in value:
                yield from MissionDirector._iter_dicts(child)

    @staticmethod
    def _revenue_totals(values: Iterable[Any]) -> tuple[float, float, str]:
        verified = 0.0
        estimated = 0.0
        currency = "CAD"
        verified_keys = {"collected", "collected_revenue", "cash_collected", "verified_revenue"}
        estimated_keys = {"estimated_revenue", "pipeline_value", "projected_revenue", "proposed_value"}
        for value in values:
            for record in MissionDirector._iter_dicts(value):
                for key, item in record.items():
                    normalized = str(key).lower()
                    if normalized == "currency" and isinstance(item, str) and len(item) == 3:
                        currency = item.upper()
                    if isinstance(item, (int, float)) and not isinstance(item, bool):
                        if normalized in verified_keys:
                            verified += max(0.0, float(item))
                        elif normalized in estimated_keys:
                            estimated += max(0.0, float(item))
        return round(verified, 2), round(estimated, 2), currency

    @staticmethod
    def _next_action(mission: Mapping[str, Any], blockers: list[str], approvals: list[str]) -> str | None:
        if approvals:
            return f"Review accountable approval {approvals[0]}; approval does not itself execute the action."
        if blockers:
            return f"Resolve blocker: {blockers[0]}"
        tasks = mission.get("tasks", [])
        ready = [task for task in tasks if isinstance(task, dict) and task.get("state") in {"READY", "PENDING"}]
        if ready:
            ready.sort(key=lambda task: float(task.get("priority", 0)), reverse=True)
            return f"Prepare task {ready[0].get('task_id')}: {ready[0].get('title')}"
        return None

    def compose(self, mission: Mapping[str, Any], generated_at: datetime | None = None) -> dict[str, Any]:
        if mission.get("external_action_authorized") is not False:
            raise ValueError("mission must explicitly set external_action_authorized=false")
        generated = generated_at or datetime.now(timezone.utc)
        statuses: list[dict[str, Any]] = []
        values: list[Any] = []
        for spec in self.sources:
            status, value = self._read_source(spec)
            statuses.append(status)
            if value is not None:
                values.append(value)

        tasks = [task for task in mission.get("tasks", []) if isinstance(task, dict)]
        completed = sum(task.get("state") == "COMPLETED" for task in tasks)
        blocked_tasks = [str(task.get("task_id")) for task in tasks if task.get("state") == "BLOCKED"]
        dependency_blockers = [
            str(dep.get("dependency_id"))
            for dep in mission.get("dependencies", [])
            if isinstance(dep, dict) and dep.get("blocking") is True and dep.get("state") != "SATISFIED"
        ]
        blockers = blocked_tasks + dependency_blockers
        approvals = [
            str(approval.get("approval_id"))
            for approval in mission.get("approvals", [])
            if isinstance(approval, dict) and approval.get("status") == "PENDING"
        ]
        progress = round((completed / len(tasks)) * 100, 2) if tasks else 0.0
        verified_revenue, estimated_revenue, currency = self._revenue_totals(values)
        source_revision = self._git_revision()
        provenance = [f"{item['source_id']}:{item['digest']}" for item in statuses if item["status"] == "AVAILABLE"]
        warnings = [
            f"{item['source_id']}: {item['status']} - {item['message']}"
            for item in statuses
            if item["status"] != "AVAILABLE"
        ]
        canonical = json.dumps(
            {"mission_id": mission.get("mission_id"), "generated_at": generated.isoformat(), "source_revision": source_revision, "provenance": provenance},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return {
            "schema_version": "1.0.0",
            "snapshot_id": f"mission_snapshot_{self._sha256(canonical)[:16]}",
            "generated_at": generated.isoformat(),
            "mode": "READ_ONLY",
            "repository_root": str(self.repository_root),
            "source_revision": source_revision,
            "mission": dict(mission),
            "source_status": statuses,
            "summary": {
                "sources_available": sum(item["status"] == "AVAILABLE" for item in statuses),
                "sources_missing": sum(item["status"] == "MISSING" for item in statuses),
                "sources_invalid": sum(item["status"] in {"INVALID", "UNSUPPORTED"} for item in statuses),
                "tasks_total": len(tasks),
                "tasks_completed": completed,
                "tasks_blocked": len(blocked_tasks),
                "mission_progress_percent": progress,
                "verified_revenue": verified_revenue,
                "estimated_revenue": estimated_revenue,
                "currency": currency,
            },
            "blockers": blockers,
            "approvals_waiting": approvals,
            "highest_impact_next_action": self._next_action(mission, blockers, approvals),
            "provenance": provenance,
            "warnings": warnings,
            "external_action_performed": False,
            "canonical_state_mutated": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compose an Ω Mission OS read-only snapshot.")
    parser.add_argument("mission", type=Path, help="Path to a governed mission JSON file")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=None, help="Optional non-canonical output path")
    args = parser.parse_args()

    mission = json.loads(args.mission.read_text(encoding="utf-8"))
    snapshot = MissionDirector(args.repo_root).compose(mission)
    rendered = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        output = args.output.resolve()
        root = args.repo_root.resolve()
        canonical_roots = [root / "data", root / "memory", root / "governance", root / "config"]
        if any(canonical == output or canonical in output.parents for canonical in canonical_roots):
            raise SystemExit("refusing to write snapshot into canonical state directories")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
