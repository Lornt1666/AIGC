#!/usr/bin/env python3
"""Deterministic, fail-closed AIGC master-document conformance gate.

This script validates document presence and structural invariants only. It does
not prove code behavior, legal enforceability, or production readiness.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Mapping

REQUIRED_DOCS = (
    "docs/master/README.md",
    "docs/master/AIGC_MVP_MASTER_SPECIFICATION.md",
    "docs/master/AIGC_CONTROL_TO_EVIDENCE_TRACEABILITY_STANDARD.md",
    "docs/master/AIGC_WIRING_AND_INTERFACE_REGISTRY.md",
    "docs/master/AIGC_IMPLEMENTATION_AUDIT_AND_CERTIFICATION_DOSSIER.md",
    "docs/master/AIGC_VERIFICATION_AND_PRODUCTION_ACCEPTANCE_PLAN.md",
    "docs/master/AIGC_OPERATIONS_SECURITY_AND_RECOVERY_RUNBOOK.md",
    "docs/master/AIGC_OPERATOR_RESPONSIBILITY_AND_AUTHORIZED_USE_ACKNOWLEDGMENT.md",
    "docs/master/AIGC_DOCUMENTATION_GOVERNANCE_AND_ENFORCEMENT_AGENTS.md",
)
WIRE_ID = re.compile(r"^\|\s*(W-\d{3})\s*\|", re.MULTILINE)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def validate_documents(documents: Mapping[str, str]) -> list[str]:
    """Return all structural violations found in a path-to-text mapping."""
    errors: list[str] = []
    for path in REQUIRED_DOCS:
        if path not in documents:
            errors.append(f"required document missing: {path}")
        elif not documents[path].strip():
            errors.append(f"required document is empty: {path}")

    registry_path = "docs/master/AIGC_WIRING_AND_INTERFACE_REGISTRY.md"
    registry = documents.get(registry_path, "")
    wire_ids = WIRE_ID.findall(registry)
    if len(wire_ids) != 45:
        errors.append(f"{registry_path}: expected 45 wire rows; found {len(wire_ids)}")
    duplicates = sorted({wire_id for wire_id in wire_ids if wire_ids.count(wire_id) > 1})
    if duplicates:
        errors.append(f"{registry_path}: duplicate wire IDs: {', '.join(duplicates)}")
    expected_ids = {f"W-{number:03d}" for number in range(1, 46)}
    missing_ids = sorted(expected_ids - set(wire_ids))
    unexpected_ids = sorted(set(wire_ids) - expected_ids)
    if missing_ids:
        errors.append(f"{registry_path}: missing wire IDs: {', '.join(missing_ids)}")
    if unexpected_ids:
        errors.append(f"{registry_path}: unexpected wire IDs: {', '.join(unexpected_ids)}")

    audit_path = "docs/master/AIGC_IMPLEMENTATION_AUDIT_AND_CERTIFICATION_DOSSIER.md"
    audit = documents.get(audit_path, "").lower()
    if "not certified" not in audit or "blocked" not in audit:
        errors.append(f"{audit_path}: must explicitly preserve NOT CERTIFIED / BLOCKED disposition")
    if not any(status in audit for status in ("implemented_unverified", "spec_only", "partial")):
        errors.append(f"{audit_path}: required implementation-status vocabulary is missing")

    legal_path = "docs/master/AIGC_OPERATOR_RESPONSIBILITY_AND_AUTHORIZED_USE_ACKNOWLEDGMENT.md"
    legal = documents.get(legal_path, "").lower()
    for phrase in ("draft", "legal review", "does not", "non-waivable", "operator responsibilities"):
        if phrase not in legal:
            errors.append(f"{legal_path}: missing legal safeguard/section phrase: {phrase}")

    agents_path = "docs/master/AIGC_DOCUMENTATION_GOVERNANCE_AND_ENFORCEMENT_AGENTS.md"
    agents = documents.get(agents_path, "").lower()
    for phrase in ("fail-closed", "doc-gate-01", "specified", "must not", "current boundary"):
        if phrase not in agents:
            errors.append(f"{agents_path}: missing enforcement safeguard/section phrase: {phrase}")

    index_path = "docs/master/README.md"
    index = documents.get(index_path, "")
    for required_name in (
        "AIGC_OPERATOR_RESPONSIBILITY_AND_AUTHORIZED_USE_ACKNOWLEDGMENT.md",
        "AIGC_DOCUMENTATION_GOVERNANCE_AND_ENFORCEMENT_AGENTS.md",
    ):
        if required_name not in index:
            errors.append(f"{index_path}: new master document not indexed: {required_name}")
    return errors


def load_documents(root: Path) -> tuple[dict[str, str], list[str]]:
    documents: dict[str, str] = {}
    errors: list[str] = []
    for relative in REQUIRED_DOCS:
        path = root / relative
        try:
            documents[relative] = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            errors.append(f"required document missing: {relative}")
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read {relative}: {type(exc).__name__}: {exc}")
    return documents, errors


def validate_local_links(root: Path, documents: Mapping[str, str]) -> list[str]:
    errors: list[str] = []
    for relative, content in documents.items():
        for target in MARKDOWN_LINK.findall(content):
            target = target.strip().split("#", 1)[0].split("?", 1)[0]
            if not target or target.startswith(("https://", "http://", "mailto:", "tel:")):
                continue
            candidate = (root / relative).parent / target
            try:
                candidate.resolve().relative_to(root.resolve())
            except ValueError:
                errors.append(f"{relative}: local link escapes repository: {target}")
                continue
            if not candidate.is_file():
                errors.append(f"{relative}: broken local link: {target}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="repository root (default: parent of scripts/)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    root = args.root.resolve()
    documents, errors = load_documents(root)
    errors.extend(validate_documents(documents))
    errors.extend(validate_local_links(root, documents))
    report = {
        "validator": "DOC-GATE-01",
        "repository_root": str(root),
        "documents_checked": len(documents),
        "errors": errors,
        "result": "FAIL" if errors else "PASS",
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"DOC-GATE-01: {report['result']} ({len(documents)} documents loaded)")
        for error in errors:
            print(f"ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
