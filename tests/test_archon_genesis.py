"""Offline contract tests for ARCHON-GENESIS; no network, model calls, or side effects."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from archon_genesis import CompileError, compile_architecture, digest, validate_input, render_markdown

BRIEF = {
    "schema_version": "1.0",
    "project_id": "AIGC",
    "objective": "Build a governed autonomous workforce that ingests a synthetic work order, decomposes tasks, produces validated artifacts, and records exact-revision evidence without bypassing policy or human approval.",
    "constraints": {"budget": "near-zero incremental spend", "compute": "existing CI and local/offline execution where feasible", "privacy": "do not expose secrets or private data", "schedule": "unknown", "latency": "unknown", "regulatory": "unknown", "hardware": "unknown"},
    "interfaces": [
        {"name": "GitHub repository", "access": "read", "revision_binding": "exact commit and tree SHA"},
        {"name": "GitHub Actions", "access": "execute", "scope": "CI tests only; availability not guaranteed"},
        {"name": "Canonical Release Assurance", "access": "unknown", "scope": "existing sole release decision authority"},
    ],
    "scale_reliability_target": {"availability": "unknown", "throughput": "unknown", "latency": "unknown", "recovery": "unknown", "durability": "persist evidence with revision binding"},
    "risk_class": "high",
    "approval_policy": {"human_review_required": True, "prohibited": ["self-approval", "secret creation", "external writes without authorization", "merge or deployment by compiler"], "release_authority": "existing canonical Release Assurance only"},
    "requested_mode": "propose",
    "source_refs": [{"kind": "repository", "ref": "Lornt1666/AIGC"}, {"kind": "architecture_spec", "ref": "docs/ARCHON_GENESIS_META_AGENT_COMPILER_SPEC.md"}],
}


class ArchonGenesisTests(unittest.TestCase):
    def test_compilation_is_deterministic(self):
        first = compile_architecture(BRIEF)
        second = compile_architecture(copy.deepcopy(BRIEF))
        self.assertEqual(first, second)
        self.assertEqual(first["input_digest_sha256"], digest(BRIEF))
        self.assertEqual(first["status"], "PASS")

    def test_unknown_fields_rejected(self):
        value = copy.deepcopy(BRIEF)
        value["god_mode"] = True
        with self.assertRaisesRegex(CompileError, "unknown fields"):
            validate_input(value)

    def test_missing_fields_rejected(self):
        value = copy.deepcopy(BRIEF)
        del value["approval_policy"]
        with self.assertRaisesRegex(CompileError, "missing required fields"):
            validate_input(value)

    def test_invalid_risk_and_mode_rejected(self):
        for key, bad in (("risk_class", "omnipotent"), ("requested_mode", "execute")):
            value = copy.deepcopy(BRIEF)
            value[key] = bad
            with self.subTest(key=key), self.assertRaises(CompileError):
                validate_input(value)

    def test_bad_interface_access_rejected(self):
        value = copy.deepcopy(BRIEF)
        value["interfaces"][0]["access"] = "admin"
        with self.assertRaisesRegex(CompileError, "access must be"):
            validate_input(value)

    def test_high_risk_uses_hierarchy_and_preserves_authority(self):
        result = compile_architecture(BRIEF)
        self.assertEqual(result["topology"]["type"], "HIERARCHICAL")
        self.assertEqual(result["authority"]["release_decision_authority"], "existing canonical Release Assurance only")
        self.assertFalse(result["authority"]["compiler_may_execute"])
        self.assertFalse(result["authority"]["external_writes_performed"])

    def test_no_agent_can_be_its_own_reviewer(self):
        result = compile_architecture(BRIEF)
        for agent in result["agents"]:
            self.assertNotEqual(agent["id"], agent["reviewer"])
            self.assertTrue(agent["must_not"])

    def test_red_team_is_synthetic_and_green_team_propose_only(self):
        result = compile_architecture(BRIEF)
        agents = {x["id"]: x for x in result["agents"]}
        self.assertTrue(any("live attacks" in item for item in agents["RED-01"]["must_not"]))
        self.assertTrue(any("apply changes" in item for item in agents["GREEN-01"]["must_not"]))

    def test_report_and_prompt_outputs_are_reproducible(self):
        result = compile_architecture(BRIEF)
        report = render_markdown(result)
        self.assertIn("Authority boundary", report)
        self.assertIn("UNKNOWN", report)
        self.assertEqual(set(result["system_prompts"]), {x["id"] for x in result["agents"]})

    def test_cli_writes_only_requested_proposal_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            brief_path = root / "brief.json"
            out = root / "out"
            brief_path.write_text(json.dumps(BRIEF), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(ROOT / "src" / "archon_genesis.py"), "--input", str(brief_path), "--output-dir", str(out)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((out / "archon_genesis_result.json").is_file())
            self.assertTrue((out / "archon_genesis_report.md").is_file())
            self.assertTrue((out / "prompts" / "archon-01.txt").is_file())
            payload = json.loads((out / "archon_genesis_result.json").read_text(encoding="utf-8"))
            self.assertFalse(payload["authority"]["external_writes_performed"])


if __name__ == "__main__":
    unittest.main()
