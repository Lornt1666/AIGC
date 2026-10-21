import json
import unittest
from pathlib import Path

from archon_genesis import compile_architecture, render_report, DEFAULT_AGENTS

ROOT = Path(__file__).resolve().parents[1]

class ArchonGenesisTests(unittest.TestCase):
    def test_aigc_brief_compiles_deterministically(self):
        brief = json.loads((ROOT / "config" / "archon_genesis_aigc_brief.json").read_text(encoding="utf-8"))
        first = compile_architecture(brief)
        second = compile_architecture(brief)
        self.assertEqual(first["output_digest"], second["output_digest"])
        self.assertEqual(first["architecture_status"], "PROPOSED_REQUIRES_INDEPENDENT_REVIEW")
        self.assertEqual(first["agent_count"], len(DEFAULT_AGENTS))
        self.assertFalse(first["authority"]["may_execute_agents"])
        self.assertEqual(first["authority"]["canonical_release_authority"], "Release Assurance Agent")

    def test_duplicate_agent_ids_block(self):
        agent = dict(DEFAULT_AGENTS[0])
        result = compile_architecture({"project": "test", "agents": [agent, dict(agent)]})
        self.assertEqual(result["architecture_status"], "BLOCKED")
        self.assertTrue(any("duplicate_agent_id" == f["code"] for f in result["findings"]))

    def test_unknown_dependency_blocks(self):
        agent = dict(DEFAULT_AGENTS[0])
        agent["depends_on"] = ["missing_agent"]
        result = compile_architecture({"project": "test", "agents": [agent]})
        self.assertEqual(result["architecture_status"], "BLOCKED")
        self.assertTrue(any(f["code"] == "unknown_dependency:missing_agent" for f in result["findings"]))

    def test_dependency_cycle_blocks(self):
        a = dict(DEFAULT_AGENTS[0])
        b = dict(DEFAULT_AGENTS[1])
        a["depends_on"] = ["architecture_contract_engineer"]
        b["depends_on"] = ["context_evidence_curator"]
        result = compile_architecture({"project": "test", "agents": [a, b]})
        self.assertEqual(result["architecture_status"], "BLOCKED")
        self.assertTrue(any(f["code"].startswith("dependency_cycle:") for f in result["findings"]))

    def test_privilege_escalation_request_blocks(self):
        agent = dict(DEFAULT_AGENTS[0])
        agent["permissions"] = ["admin"]
        result = compile_architecture({"project": "test", "agents": [agent]})
        self.assertEqual(result["architecture_status"], "BLOCKED")
        self.assertTrue(any(f["code"] == "forbidden_autonomy_requested" for f in result["findings"]))

    def test_self_approval_blocks(self):
        agent = dict(DEFAULT_AGENTS[0])
        agent["self_authorizes"] = True
        result = compile_architecture({"project": "test", "agents": [agent]})
        self.assertEqual(result["architecture_status"], "BLOCKED")
        self.assertTrue(any(f["code"] == "authority_boundary_violation" for f in result["findings"]))

    def test_invalid_brief_rejected(self):
        for brief in ({}, {"project": "x", "agents": []}, {"project": "", "agents": DEFAULT_AGENTS}):
            with self.subTest(brief=brief):
                with self.assertRaises(ValueError):
                    compile_architecture(brief)

    def test_report_is_human_readable(self):
        result = compile_architecture({"project": "test"})
        report = render_report(result)
        self.assertIn("ARCHON-GENESIS Architecture Proposal", report)
        self.assertIn("Independent Contract", report)
        self.assertIn("does not execute", report)

if __name__ == "__main__":
    unittest.main()
