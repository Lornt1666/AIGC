from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from enforce_master_docs import REQUIRED_DOCS, validate_documents, validate_local_links


def valid_documents() -> dict[str, str]:
    docs = {path: "# Document\nContent.\n" for path in REQUIRED_DOCS}
    docs["docs/master/AIGC_WIRING_AND_INTERFACE_REGISTRY.md"] = "\n".join(
        f"| W-{number:03d} | test wire |" for number in range(1, 46)
    )
    docs["docs/master/AIGC_IMPLEMENTATION_AUDIT_AND_CERTIFICATION_DOSSIER.md"] = (
        "NOT CERTIFIED — BLOCKED; IMPLEMENTED_UNVERIFIED; SPEC_ONLY; PARTIAL"
    )
    docs["docs/master/AIGC_OPERATOR_RESPONSIBILITY_AND_AUTHORIZED_USE_ACKNOWLEDGMENT.md"] = (
        "DRAFT for legal review. This document does not waive non-waivable rights. "
        "Operator responsibilities are recorded."
    )
    docs["docs/master/AIGC_DOCUMENTATION_GOVERNANCE_AND_ENFORCEMENT_AGENTS.md"] = (
        "fail-closed DOC-GATE-01 is specified. The agent must not exceed its current boundary."
    )
    docs["docs/master/README.md"] = (
        "AIGC_OPERATOR_RESPONSIBILITY_AND_AUTHORIZED_USE_ACKNOWLEDGMENT.md "
        "AIGC_DOCUMENTATION_GOVERNANCE_AND_ENFORCEMENT_AGENTS.md"
    )
    return docs


class MasterDocumentationGateTests(unittest.TestCase):
    def test_valid_document_structure_passes(self) -> None:
        self.assertEqual(validate_documents(valid_documents()), [])

    def test_missing_required_document_fails(self) -> None:
        docs = valid_documents()
        del docs[REQUIRED_DOCS[0]]
        self.assertTrue(any("required document missing" in error
                            for error in validate_documents(docs)))

    def test_duplicate_wire_id_fails(self) -> None:
        docs = valid_documents()
        docs["docs/master/AIGC_WIRING_AND_INTERFACE_REGISTRY.md"] += "\n| W-001 | duplicate |"
        errors = validate_documents(docs)
        self.assertTrue(any("duplicate wire IDs" in error for error in errors))

    def test_missing_wire_id_fails(self) -> None:
        docs = valid_documents()
        docs["docs/master/AIGC_WIRING_AND_INTERFACE_REGISTRY.md"] = "\n".join(
            f"| W-{number:03d} | test wire |" for number in range(1, 45)
        )
        errors = validate_documents(docs)
        self.assertTrue(any("expected 45 wire rows" in error for error in errors))
        self.assertTrue(any("missing wire IDs" in error for error in errors))

    def test_certification_claim_without_blocked_status_fails(self) -> None:
        docs = valid_documents()
        docs["docs/master/AIGC_IMPLEMENTATION_AUDIT_AND_CERTIFICATION_DOSSIER.md"] = (
            "CERTIFIED and PRODUCTION READY"
        )
        self.assertTrue(any("NOT CERTIFIED / BLOCKED" in error
                            for error in validate_documents(docs)))

    def test_local_link_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            docs = {"docs/master/README.md": "[outside](../../../outside.md)"}
            errors = validate_local_links(root, docs)
            self.assertTrue(any("escapes repository" in error for error in errors))

    def test_broken_local_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            docs = {"docs/master/README.md": "[missing](missing.md)"}
            errors = validate_local_links(root, docs)
            self.assertTrue(any("broken local link" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
