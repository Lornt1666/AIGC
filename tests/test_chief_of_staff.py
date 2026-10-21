"""Chief of Staff orchestration contract tests; offline and side-effect-free."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aigc_chief_of_staff import STAGES, build_runbook, validate_stage_graph, render_report

BRIEF_PATH = ROOT / "config" / "archon_genesis_aigc_brief.json"
BRIEF = json.loads(BRIEF_PATH.read_text(encoding="utf-8"))

class ChiefOfStaffTests(unittest.TestCase):
    def test_runbook_is_deterministic(self):
        self.assertEqual(build_runbook(BRIEF), build_runbook(copy.deepcopy(BRIEF)))

    def test_dependency_graph_is_valid(self):
        validate_stage_graph()
        self.assertEqual(len({x["id"] for x in STAGES}), len(STAGES))

    def test_cycle_is_rejected(self):
        graph = [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_stage_graph(graph)

    def test_unknown_dependency_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown dependency"):
            validate_stage_graph([{"id": "a", "depends_on": ["missing"]}])

    def test_duplicates_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_stage_graph([{"id": "a", "depends_on": []}, {"id": "a", "depends_on": []}])

    def test_only_real_local_stages_marked_complete(self):
        result = build_runbook(BRIEF)
        by_id = {x["stage_id"]: x for x in result["work_orders"]}
        self.assertEqual(by_id["chief-of-staff"]["status"], "COMPLETE")
        self.assertEqual(by_id["archon-genesis"]["status"], "COMPLETE")
        self.assertEqual(by_id["contract-gate"]["status"], "PASS")
        self.assertEqual(by_id["ceo-approval"]["agent"], "AIGC CEO Agent")
        self.assertEqual(by_id["human-acceptance"]["depends_on"], ["ceo-approval"])
        for stage_id in ("aer-review", "red-review", "blue-review", "green-remediation", "independent-verification", "ceo-approval", "human-acceptance", "release-assurance"):
            self.assertEqual(by_id[stage_id]["status"], "BLOCKED_INPUTS")

    def test_authority_cannot_be_escalated(self):
        result = build_runbook(BRIEF)
        self.assertFalse(result["authority"]["chief_of_staff_may_grant_permissions"])
        self.assertFalse(result["authority"]["chief_of_staff_may_execute_external_actions"])
        self.assertFalse(result["authority"]["chief_of_staff_may_merge_or_deploy"])
        self.assertEqual(result["authority"]["release_decision_authority"], "existing canonical Release Assurance only")
        self.assertEqual(result["authority"]["release_decision"], "NOT_MADE")

    def test_report_discloses_actual_execution_boundary(self):
        report = render_report(build_runbook(BRIEF))
        self.assertIn("BLOCKED_INPUTS", report)
        self.assertIn("Specialist work orders are not evidence that those agents ran", report)

    def test_cli_emits_runbook_and_report(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "out"
            proc = subprocess.run([sys.executable, str(ROOT / "src" / "aigc_chief_of_staff.py"),
                "--input", str(BRIEF_PATH), "--output-dir", str(out)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((out / "chief_of_staff_runbook.json").is_file())
            self.assertTrue((out / "chief_of_staff_report.md").is_file())
            self.assertTrue((out / "documentation" / "README.md").is_file())
            self.assertTrue((out / "documentation" / "documentation_manifest.json").is_file())
            result = json.loads((out / "chief_of_staff_runbook.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "BLOCK")
            self.assertEqual(result["documentation_pack"]["status"], "GENERATED_DRAFT")
            self.assertEqual(result["documentation_pack"]["index_path"], "documentation/README.md")


    def test_cli_delegates_to_evidence_workflow_when_versioned_inputs_are_supplied(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            envelope_path = root / "envelope.json"
            inputs_path = root / "inputs.json"
            output = root / "out"
            envelope_path.write_text(json.dumps({
                "schema_version": "1.0", "policy_id": "aigc-team-assurance-v1",
                "repository": "Lornt1666/AIGC", "commit_sha": "a" * 40,
                "tree_sha": "b" * 40, "policy_digest": "c" * 64,
                "invocation_id": "chief-of-staff-test-run",
                "producer_identity": "test-fixture",
                "issued_at_utc": "2026-10-21T00:00:00Z",
                "expires_at_utc": "2026-10-22T00:00:00Z", "evidence_refs": [],
            }), encoding="utf-8")
            inputs_path.write_text("{}", encoding="utf-8")
            proc = subprocess.run([
                sys.executable, str(ROOT / "src" / "aigc_chief_of_staff.py"),
                "--input", str(BRIEF_PATH), "--output-dir", str(output),
                "--evidence-envelope", str(envelope_path), "--evidence-inputs", str(inputs_path),
            ], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads((output / "chief_of_staff_execution.json").read_text(encoding="utf-8"))
            self.assertEqual(result["release_decision"], "BLOCK")
            self.assertFalse(result["authentication_configured"])
            self.assertTrue((output / "evidence_workflow" / "evidence.jsonl").is_file())

if __name__ == "__main__":
    unittest.main()
