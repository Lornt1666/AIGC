import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.mission_os.mission_director import MissionDirector, SourceSpec


class MissionDirectorTests(unittest.TestCase):
    def _mission(self):
        return {
            "schema_version": "1.0.0",
            "mission_id": "mission_revenue_202608",
            "title": "Revenue mission",
            "objective": "Collect CAD 2000 in legitimate revenue.",
            "accountable_owner": "ACCOUNTABLE_OPERATOR",
            "state": "ACTIVE",
            "confidence": 0.5,
            "start_at": "2026-08-02T00:00:00+00:00",
            "deadline_at": "2026-09-01T05:59:59+00:00",
            "resource_envelope": {"currency": "CAD", "spend_ceiling": 0, "operator_minutes_per_day": 120, "model_call_ceiling": 100, "external_action_ceiling": 0},
            "allowed_actions": ["read_repository_artifacts", "prepare_internal_drafts"],
            "forbidden_actions": ["contact_external_parties", "spend_funds", "approve_own_actions"],
            "objectives": [{"objective_id": "obj_cash_2000", "description": "Collect revenue", "measurement": "verified cash collected", "target": 2000, "status": "IN_PROGRESS"}],
            "tasks": [
                {"task_id": "task_prepare_offer", "title": "Prepare fixed-scope offer", "state": "COMPLETED", "priority": 10, "dependency_ids": [], "approval_required": False, "external_action": False, "evidence_ids": []},
                {"task_id": "task_review_outreach", "title": "Review outreach packet", "state": "APPROVAL_REQUIRED", "priority": 9, "dependency_ids": [], "approval_required": True, "external_action": True, "evidence_ids": []}
            ],
            "dependencies": [],
            "approvals": [{"approval_id": "approval_outreach_001", "action": "external outreach", "status": "PENDING", "exact_revision": None, "expires_at": None, "evidence_ids": []}],
            "kpis": [],
            "evidence_requirements": [],
            "stop_conditions": ["deadline reached", "resource ceiling exceeded"],
            "created_at": "2026-08-02T00:00:00+00:00",
            "updated_at": "2026-08-02T00:00:00+00:00",
            "external_action_authorized": False
        }

    def test_composes_snapshot_without_mutating_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            finance = root / "finance.json"
            finance.write_text(json.dumps({"collected_revenue": 250, "estimated_revenue": 900, "currency": "CAD"}), encoding="utf-8")
            before = finance.read_bytes()
            director = MissionDirector(root, [SourceSpec("finance", "finance.json", optional=False)])
            snapshot = director.compose(self._mission(), datetime(2026, 8, 2, tzinfo=timezone.utc))
            self.assertEqual(before, finance.read_bytes())
            self.assertFalse(snapshot["external_action_performed"])
            self.assertFalse(snapshot["canonical_state_mutated"])
            self.assertEqual(snapshot["summary"]["verified_revenue"], 250)
            self.assertEqual(snapshot["summary"]["estimated_revenue"], 900)
            self.assertEqual(snapshot["summary"]["mission_progress_percent"], 50)
            self.assertIn("approval_outreach_001", snapshot["approvals_waiting"])

    def test_missing_and_invalid_sources_are_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bad.json").write_text("not-json", encoding="utf-8")
            director = MissionDirector(root, [SourceSpec("missing", "missing.json"), SourceSpec("bad", "bad.json")])
            snapshot = director.compose(self._mission(), datetime(2026, 8, 2, tzinfo=timezone.utc))
            self.assertEqual(snapshot["summary"]["sources_missing"], 1)
            self.assertEqual(snapshot["summary"]["sources_invalid"], 1)
            self.assertEqual(len(snapshot["warnings"]), 2)

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                MissionDirector(temp, [SourceSpec("escape", "../outside.json")])

    def test_requires_explicit_no_external_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            mission = self._mission()
            mission["external_action_authorized"] = True
            with self.assertRaises(ValueError):
                MissionDirector(temp, []).compose(mission)


if __name__ == "__main__":
    unittest.main()
