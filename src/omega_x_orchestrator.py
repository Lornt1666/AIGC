from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class PatchDecision(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DENIED = "denied"
    REVISION_REQUIRED = "revision_required"
    BLOCKED = "blocked"


@dataclass
class OmegaMemoryEvent:
    event_id: str
    timestamp: str
    event_type: str
    phase: str
    agent: str
    summary: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OmegaEvolutionPatch:
    patch_id: str
    created_at: str
    patch_type: str
    target: str
    reason: str
    proposed_change: Dict[str, Any]
    safety_impact: str
    approval_required: bool
    decision: str = PatchDecision.PENDING.value


class OmegaXMemoryManager:
    def __init__(self, memory_root: Path):
        self.root = memory_root.expanduser().resolve()
        self.memory_dir = self.root / "memory"
        self.audit_dir = self.root / "audit"
        self.patch_dir = self.root / "patches"
        self.db_path = self.memory_dir / "omega_memory.sqlite"
        self._ensure_structure()
        self._init_db()

    def _ensure_structure(self) -> None:
        required_dirs = [
            self.memory_dir,
            self.audit_dir,
            self.patch_dir / "pending",
            self.patch_dir / "accepted",
            self.patch_dir / "denied",
            self.patch_dir / "blocked",
            self.root / "config",
            self.root / "deliverables",
            self.root / "vector_index",
        ]
        for directory in required_dirs:
            directory.mkdir(parents=True, exist_ok=True)

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    data_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evolution_patches (
                    patch_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    patch_type TEXT NOT NULL,
                    target TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    proposed_change_json TEXT NOT NULL,
                    safety_impact TEXT NOT NULL,
                    approval_required INTEGER NOT NULL,
                    decision TEXT NOT NULL
                )
            """)
            conn.commit()

    def record_event(self, event: OmegaMemoryEvent) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_events
                (event_id, timestamp, event_type, phase, agent, summary, data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.timestamp,
                    event.event_type,
                    event.phase,
                    event.agent,
                    event.summary,
                    json.dumps(event.data, ensure_ascii=False),
                ),
            )
            conn.commit()
        jsonl_path = self.memory_dir / "omega_events.jsonl"
        with jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    def create_patch(self, patch: OmegaEvolutionPatch) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evolution_patches
                (patch_id, created_at, patch_type, target, reason, proposed_change_json,
                 safety_impact, approval_required, decision)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patch.patch_id,
                    patch.created_at,
                    patch.patch_type,
                    patch.target,
                    patch.reason,
                    json.dumps(patch.proposed_change, ensure_ascii=False),
                    patch.safety_impact,
                    int(patch.approval_required),
                    patch.decision,
                ),
            )
            conn.commit()
        target_dir = self.patch_dir / patch.decision
        if not target_dir.exists():
            target_dir = self.patch_dir / "pending"
        patch_path = target_dir / f"{patch.patch_id}.json"
        patch_path.write_text(json.dumps(asdict(patch), ensure_ascii=False, indent=2), encoding="utf-8")

    def list_pending_patches(self) -> List[OmegaEvolutionPatch]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT patch_id, created_at, patch_type, target, reason,
                       proposed_change_json, safety_impact, approval_required, decision
                FROM evolution_patches
                WHERE decision = ?
                ORDER BY created_at DESC
                """,
                (PatchDecision.PENDING.value,),
            ).fetchall()
        return [
            OmegaEvolutionPatch(
                patch_id=row[0],
                created_at=row[1],
                patch_type=row[2],
                target=row[3],
                reason=row[4],
                proposed_change=json.loads(row[5]),
                safety_impact=row[6],
                approval_required=bool(row[7]),
                decision=row[8],
            )
            for row in rows
        ]


class OmegaXSafetyGate:
    FORBIDDEN_CHANGE_TERMS = [
        "remove_human_approval",
        "disable_audit",
        "disable_privacy",
        "disable_security",
        "hide_ai_use",
        "permit_spam",
        "permit_impersonation",
        "permit_forbidden_scraping",
        "auto_apply_without_approval",
        "delete_negative_outcomes",
        "rewrite_history",
    ]
    BEHAVIOR_CHANGING_TYPES = {
        "agent_prompt_update",
        "scoring_weight_update",
        "safety_rule_update",
        "approval_rule_update",
        "domain_status_update",
        "connector_update",
        "execution_rule_update",
    }

    def inspect_patch(self, patch: OmegaEvolutionPatch) -> OmegaEvolutionPatch:
        blob = json.dumps(asdict(patch), ensure_ascii=False).lower()
        if any(term in blob for term in self.FORBIDDEN_CHANGE_TERMS):
            patch.decision = PatchDecision.BLOCKED.value
            patch.approval_required = True
            patch.safety_impact = "blocked_forbidden_evolution"
            return patch
        if patch.patch_type in self.BEHAVIOR_CHANGING_TYPES:
            patch.approval_required = True
        return patch


class OmegaXOrchestrator:
    def __init__(self, memory_root: Path, operator: str = "Justice Gray Maciocha"):
        self.operator = operator
        self.memory = OmegaXMemoryManager(memory_root)
        self.safety = OmegaXSafetyGate()

    def record_phase_update(
        self,
        phase: str,
        agent: str,
        summary: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> OmegaMemoryEvent:
        event = OmegaMemoryEvent(
            event_id=f"OMEGA-EVENT-{uuid.uuid4()}",
            timestamp=utc_now(),
            event_type="phase_update",
            phase=phase,
            agent=agent,
            summary=summary,
            data=data or {},
        )
        self.memory.record_event(event)
        return event

    def propose_patch(
        self,
        patch_type: str,
        target: str,
        reason: str,
        proposed_change: Dict[str, Any],
        safety_impact: str = "neutral",
    ) -> OmegaEvolutionPatch:
        seed = json.dumps({
            "patch_type": patch_type,
            "target": target,
            "reason": reason,
            "change": proposed_change,
            "created_at": utc_now(),
        }, ensure_ascii=False)
        patch = OmegaEvolutionPatch(
            patch_id="AIGC-OMEGA-PATCH-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper(),
            created_at=utc_now(),
            patch_type=patch_type,
            target=target,
            reason=reason,
            proposed_change=proposed_change,
            safety_impact=safety_impact,
            approval_required=True,
        )
        patch = self.safety.inspect_patch(patch)
        self.memory.create_patch(patch)
        self.record_phase_update(
            phase="omega_x",
            agent="Omega-X Orchestrator",
            summary=f"Proposed evolution patch {patch.patch_id}",
            data=asdict(patch),
        )
        return patch

    def validate_patch_approval(self, patch: OmegaEvolutionPatch, operator_response: str) -> OmegaEvolutionPatch:
        accept = f"I, {self.operator}, accept evolution patch {patch.patch_id}."
        deny = f"I, {self.operator}, deny evolution patch {patch.patch_id}."
        revise_prefix = f"Revise evolution patch {patch.patch_id}:"
        if patch.decision == PatchDecision.BLOCKED.value:
            self.memory.create_patch(patch)
            return patch
        response = operator_response.strip()
        if response == accept:
            patch.decision = PatchDecision.ACCEPTED.value
        elif response == deny:
            patch.decision = PatchDecision.DENIED.value
        elif response.startswith(revise_prefix):
            patch.decision = PatchDecision.REVISION_REQUIRED.value
        else:
            patch.decision = PatchDecision.DENIED.value
        self.memory.create_patch(patch)
        self.record_phase_update(
            phase="omega_x",
            agent="Omega-X Orchestrator",
            summary=f"Patch decision recorded: {patch.patch_id} -> {patch.decision}",
            data=asdict(patch),
        )
        return patch

    def signature_update(self) -> str:
        pending = self.memory.list_pending_patches()
        return "\n".join([
            "OMEGA-X SIGNATURE UPDATE",
            "Operator:",
            self.operator,
            "System:",
            "AIGC - Artificial Intelligence Gladiator Colosseum",
            "Role:",
            "Apex self-supervised orchestrator",
            "Memory Root:",
            str(self.memory.root),
            f"Pending Evolution Patches: {len(pending)}",
            "Pending Patch IDs:",
            json.dumps([patch.patch_id for patch in pending], indent=2),
            "Safety Status:",
            "Human approval gates preserved.",
            "Audit logging preserved.",
            "Privacy/security checks preserved.",
            "External action restrictions preserved.",
            "Approval Rule:",
            f"I, {self.operator}, accept evolution patch [PATCH_ID].",
        ]).strip() + "\n"


def load_json_dict(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_memory_root(project_root: Path, config: Dict[str, Any]) -> Path:
    value = (config.get("omega_x", {}) or {}).get("memory_root", "memory/omega_x")
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root / path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Initialize or inspect Omega-X memory supervision.")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--config", type=Path, default=default_root / "config" / "omega_x_config.json")
    parser.add_argument("--propose-demo-patch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json_dict(args.config)
    operator = (config.get("omega_x", {}) or {}).get("operator", "Justice Gray Maciocha")
    omega = OmegaXOrchestrator(memory_root=resolve_memory_root(args.project_root, config), operator=operator)
    omega.record_phase_update(
        phase="omega_x",
        agent="Omega-X Orchestrator",
        summary="Initialized Omega-X memory supervision.",
        data={"external_action_performed": False},
    )
    if args.propose_demo_patch:
        omega.propose_patch(
            patch_type="ology_framework_update",
            target="phase3_ology_assessment",
            reason="Add reader-level analysis to documentation opportunities.",
            proposed_change={
                "add_question": "Who is the target reader: beginner, intermediate, advanced, developer, customer, internal team, or executive?"
            },
            safety_impact="neutral",
        )
    print(omega.signature_update())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
