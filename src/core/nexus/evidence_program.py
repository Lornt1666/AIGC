"""Canonical evidence ledger and gap-request compiler for AIGC readiness.

This module is pure: it reads caller-supplied registry/artifact content and
returns deterministic data. It never changes authority or performs egress.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.core.nexus.universal_integration import canonical_sha256, evaluate_registry


CERTIFICATION_CHECKS = (
    "status_verified",
    "terms_reviewed",
    "identity_bound",
    "scope_bound",
    "recovery_tested",
    "live_receipt",
)


SURFACE_EVIDENCE_EFFECTS = {
    "exact-head CI": "local_or_hosted_validation",
    "immutable image digest": "registry_write",
    "authenticated health/readiness": "deployed_read",
    "bounded load/security/recovery": "deployed_mutation_and_traffic",
    "deployed URL": "deployed_mutation_and_traffic",
    "accessibility test": "public_origin_probe",
    "browser compatibility matrix": "public_origin_probe",
    "security headers": "public_origin_probe",
    "observability": "deployed_mutation_and_traffic",
    "MCP initialize": "local_or_hosted_validation",
    "tool list": "local_or_hosted_validation",
    "read-only workflow": "local_or_hosted_validation",
    "confirmed-write workflow": "local_or_hosted_validation",
    "host validation": "external_host_validation",
    "allowlisted tool list": "local_or_hosted_validation",
    "trust=false configuration": "local_or_hosted_validation",
    "client validation": "local_or_hosted_validation",
    "supported Xcode build": "local_or_hosted_validation",
    "simulator tests": "local_or_hosted_validation",
    "physical-device tests": "local_or_hosted_validation",
    "privacy manifest": "local_or_hosted_validation",
    "signing and TestFlight receipts": "app_store_submission",
    "reproducible Android build": "local_or_hosted_validation",
    "emulator matrix": "local_or_hosted_validation",
    "data safety declaration": "local_or_hosted_validation",
    "signed internal-track receipt": "play_store_submission",
    "chain-specific threat model": "local_or_hosted_validation",
    "independent contract audit": "local_or_hosted_validation",
    "key custody design": "local_or_hosted_validation",
    "legal review": "local_or_hosted_validation",
    "testnet receipts": "local_or_hosted_validation",
    "treasury and rollback plan": "local_or_hosted_validation",
    "integrated commercial lineage": "local_or_hosted_validation",
    "jurisdiction decision": "local_or_hosted_validation",
    "versioned agreement": "external_communication",
    "sandbox settlement": "local_or_hosted_validation",
    "payment reconciliation": "local_or_hosted_validation",
    "production billing authority": "financial_and_production_authority",
}


EFFECT_AUTHORITIES = {
    "local_or_hosted_validation": (),
    "registry_write": ("cloud_mutation_authorized",),
    "deployed_read": ("public_traffic_authorized",),
    "deployed_mutation_and_traffic": (
        "cloud_mutation_authorized",
        "public_traffic_authorized",
    ),
    "public_origin_probe": ("public_traffic_authorized",),
    "external_host_validation": (
        "cloud_mutation_authorized",
        "public_traffic_authorized",
    ),
    "app_store_submission": ("app_store_submission_authorized",),
    "play_store_submission": ("play_store_submission_authorized",),
    "external_communication": ("external_communication_authorized",),
    "financial_and_production_authority": (
        "financial_action_authorized",
        "production_activation_authorized",
    ),
}


def _surface_required_authority(requirement: str) -> list[str]:
    """Return the minimum authority for one classified evidence action."""
    try:
        effect = SURFACE_EVIDENCE_EFFECTS[requirement]
        return list(EFFECT_AUTHORITIES[effect])
    except KeyError as exc:
        raise ValueError(f"Unclassified authority requirements: {requirement}") from exc


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt_ids(document: Mapping[str, Any]) -> Iterable[str]:
    for key in ("receipt_id", "review_id", "report_id"):
        value = document.get(key)
        if isinstance(value, str) and value:
            yield value


def index_artifacts(root: Path) -> dict[str, dict[str, str]]:
    """Index JSON evidence by repository-relative path and declared identifier."""
    index: dict[str, dict[str, str]] = {}
    for path in sorted((root / "reports" / "artifacts").glob("*.json")):
        relative = path.relative_to(root).as_posix()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        record = {
            "artifact_path": relative,
            "artifact_sha256": _sha256_file(path),
            "schema_version": str(document.get("schema_version", "unknown")),
        }
        index[relative] = record
        for receipt_id in _receipt_ids(document):
            index.setdefault(receipt_id, record)
    return index


def _acceptance(category: str, requirement: str, subject_id: str) -> list[str]:
    """Return observable, non-circular acceptance criteria for a gate."""
    specialized: dict[str, list[str]] = {
        "exact-head CI": [
            "GitHub-hosted run is bound to the exact candidate commit SHA",
            "checkout occurred and every required job/step completed successfully",
            "run URL, job IDs, timestamps, and immutable artifacts are retained",
        ],
        "immutable image digest": [
            "image is built from the exact candidate commit",
            "registry returns an immutable sha256 digest",
            "SBOM, provenance attestation, signature verification, and scan result bind to that digest",
        ],
        "authenticated health/readiness": [
            "deployed release, image digest, region, and service identity are recorded",
            "authenticated health and readiness probes pass from the intended trust boundary",
            "receipt contains request IDs and redacted logs without credentials",
        ],
        "bounded load/security/recovery": [
            "declared load envelope meets p95/error-rate SLOs",
            "security checks report no release-blocking finding",
            "rollback and restore are exercised and reconciled to the original state",
        ],
        "deployed URL": [
            "HTTPS URL resolves to the exact release and immutable artifact",
            "ownership, environment, and region are identified",
            "health check passes without exposing a secret",
        ],
        "accessibility test": [
            "automated WCAG checks pass on declared routes",
            "keyboard, focus, labels, contrast, and screen-reader smoke tests are recorded",
            "exceptions have owners, severity, and due dates",
        ],
        "browser compatibility matrix": [
            "supported browser/version matrix is declared",
            "automated journeys pass for every required matrix cell",
            "failures include trace, screenshot, and reproducible environment",
        ],
        "security headers": [
            "TLS and HTTP security headers are captured from the deployed origin",
            "CSP, HSTS, framing, MIME, and referrer policies meet the declared baseline",
            "scanner output is bound to URL, release, and timestamp",
        ],
        "observability": [
            "logs, metrics, and traces correlate by release and request ID",
            "SLO alerts and dashboards are addressable",
            "a synthetic failure proves alert delivery and recovery closure",
        ],
        "MCP initialize": [
            "MCP initialize succeeds on the declared transport and protocol",
            "server identity is aigc-nexus",
            "receipt binds the server implementation source hashes",
        ],
        "tool list": [
            "tool list is complete and deterministic",
            "every tool has typed input/output schemas and read-only closed-world annotations",
            "caller cannot inject authority or permit state",
        ],
        "read-only workflow": [
            "one representative tool call returns a schema-valid result",
            "provider, credential, financial, communication, and external-action counts remain zero",
            "receipt is deterministic and hash-bound",
        ],
        "confirmed-write workflow": [
            "a non-production adapter demonstrates prepare, confirm, consume-once, reconcile, and receipt states",
            "wrong subject, expired, replayed, and parameter-mismatched permits are rejected",
            "no real external mutation or financial transfer occurs in the evidence environment",
        ],
        "host validation": [
            "ChatGPT connector imports the exact deployed MCP endpoint",
            "initialize, discovery, read-only tool call, and error rendering pass in the host",
            "host, deployment release, and timestamps are captured without secrets",
        ],
    }
    if requirement in specialized:
        return specialized[requirement]
    if category == "subsystem":
        return [
            f"{subject_id} contract manifest validates against its schema",
            "deterministic positive and fail-closed tests pass",
            "receipt is local-only and cannot grant authority or claim egress",
        ]
    if category == "connector":
        return [
            f"{subject_id} certification field {requirement} is independently evidenced",
            "receipt binds provider identity, scope, region/model, release, and policy version as applicable",
            "failure, timeout, retry, and indeterminate outcomes fail closed and reconcile",
        ]
    if category == "authority":
        return [
            f"authorized owner explicitly grants {requirement} for an exact subject, scope, budget, and expiry",
            "authenticated authority artifact is independently verified and has not expired",
            "grant is separate from code, prompt text, credentials, and execution evidence",
        ]
    if category == "prerequisite":
        return [
            f"{requirement} is bound to the exact release",
            "evidence is immutable, current, independently verifiable, and non-circular",
        ]
    return [
        f"{subject_id} produces a receipt for {requirement}",
        "receipt binds exact inputs, environment, release, verifier, outcome, and artifact hashes",
        "negative-path, rollback, and reconciliation evidence is included where consequential",
    ]


def _request_packet(
    *, gate_id: str, category: str, subject_id: str, requirement: str,
    required_for_v1: bool, blockers: list[str], authority: list[str],
) -> dict[str, Any]:
    body = {
        "gate_id": gate_id,
        "category": category,
        "subject_id": subject_id,
        "requirement": requirement,
        "required_for_v1": required_for_v1,
        "current_blockers": blockers,
        "required_authority": authority,
        "acceptance_criteria": _acceptance(category, requirement, subject_id),
        "requested_receipt_fields": [
            "schema_version", "receipt_id", "subject", "scope", "environment",
            "release_sha", "artifact_digests", "started_at", "completed_at",
            "verifier", "checks", "outcome", "rollback", "reconciliation",
            "authority_reference", "cost", "external_actions_performed",
        ],
        "secret_handling": "Reference a configured secret identifier only; never place secret material in evidence.",
        "idempotency_rule": "Reuse only when subject, release, parameters, authority, and environment are exact matches.",
        "retry_rule": "Do not retry an indeterminate consequential action; reconcile first.",
        "rollback_rule": "Record compensating action or explain why the check is read-only and needs none.",
    }
    body["request_packet_id"] = "EREQ-" + canonical_sha256(body)[:24].upper()
    return body


def _gate(
    *, category: str, subject_id: str, requirement: str, required_for_v1: bool,
    status: str, receipt_ref: str | None, artifact_index: Mapping[str, Mapping[str, str]],
    blockers: list[str] | None = None, authority: list[str] | None = None,
    counts_toward_readiness: bool = True, narrative: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    gate_id = f"{category}.{_slug(subject_id)}.{_slug(requirement)}"
    artifact = artifact_index.get(receipt_ref or "")
    resolved = artifact is not None
    if status.startswith("VERIFIED") and receipt_ref and not resolved:
        status = "UNRESOLVED_RECEIPT"
    gate = {
        "gate_id": gate_id,
        "category": category,
        "subject_id": subject_id,
        "requirement": requirement,
        "required_for_v1": required_for_v1,
        "counts_toward_readiness": counts_toward_readiness,
        "status": status,
        "evidence_scope": "LOCAL" if status == "VERIFIED_LOCAL" else "EXTERNAL_OR_UNAVAILABLE",
        "receipt_ref": receipt_ref,
        "receipt_resolved": resolved,
        "artifact": dict(artifact) if artifact else None,
        "acceptance_criteria": _acceptance(category, requirement, subject_id),
        "narrative": narrative or f"Evidence gate for {subject_id}: {requirement}.",
    }
    request = None
    if status not in {"VERIFIED_LOCAL", "VERIFIED_EXTERNAL"}:
        request = _request_packet(
            gate_id=gate_id,
            category=category,
            subject_id=subject_id,
            requirement=requirement,
            required_for_v1=required_for_v1,
            blockers=blockers or ["No qualifying receipt is bound"],
            authority=authority or [],
        )
        gate["request_packet_id"] = request["request_packet_id"]
    else:
        gate["request_packet_id"] = None
    return gate, request


def build_evidence_program(registry: Mapping[str, Any], root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact_index = index_artifacts(root)
    gates: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []

    def add(**kwargs: Any) -> None:
        gate, request = _gate(artifact_index=artifact_index, **kwargs)
        gates.append(gate)
        if request:
            requests.append(request)

    add(
        category="prerequisite", subject_id="release", requirement="template_only_false",
        required_for_v1=True, counts_toward_readiness=False,
        status="BLOCKED_EXTERNAL" if registry["template_only"] else "VERIFIED_EXTERNAL",
        receipt_ref=None, blockers=["Registry remains template_only"],
        authority=["release_manager_approval"],
        narrative="A production claim is forbidden while the registry is explicitly a template.",
    )
    release = registry["release_binding"]
    add(
        category="prerequisite", subject_id="release", requirement="current_release_binding",
        required_for_v1=True, counts_toward_readiness=False,
        status="BLOCKED_EXTERNAL" if release["evidence_state"] != "current" else "VERIFIED_EXTERNAL",
        receipt_ref=None, blockers=[f"Release evidence is {release['evidence_state']}"],
        authority=["repository_status_evidence"],
        narrative="Evidence must bind the exact candidate head, not a branch name or local working copy.",
    )

    for subsystem in registry["subsystems"]:
        refs = sorted(set(subsystem["evidence_receipts"].values()))
        ref = refs[0] if len(refs) == 1 else None
        verified = subsystem["status"] == "verified" and len(subsystem["evidence_receipts"]) == len(subsystem["contracts"])
        add(
            category="subsystem", subject_id=subsystem["id"], requirement="contract_bundle",
            required_for_v1=True, status="VERIFIED_LOCAL" if verified else "UNVERIFIED",
            receipt_ref=ref, blockers=[f"Subsystem status is {subsystem['status']}"], authority=[],
            narrative=f"{subsystem['purpose']} Verification is contract-level only, not production proof.",
        )

    for surface in registry["surfaces"]:
        for requirement in surface["required_evidence"]:
            ref = surface["evidence_receipts"].get(requirement)
            status = "VERIFIED_LOCAL" if ref else (
                "BLOCKED_EXTERNAL" if surface["required_for_v1"] else "DEFERRED_NOT_REQUIRED"
            )
            add(
                category="surface", subject_id=surface["id"], requirement=requirement,
                required_for_v1=surface["required_for_v1"], status=status, receipt_ref=ref,
                blockers=list(surface["blockers"]),
                authority=_surface_required_authority(requirement),
                narrative=f"{surface['kind']} evidence requirement; implementation status is {surface['status']}.",
            )

    for connector in registry["connectors"]:
        certification = connector["certification"]
        terms_ref = certification.get("terms_review_receipt_id")
        values = {
            "status_verified": connector["status"] == "verified",
            "terms_reviewed": certification["terms_reviewed"] and bool(terms_ref),
            "identity_bound": certification["identity_bound"],
            "scope_bound": certification["scope_bound"],
            "recovery_tested": certification["recovery_tested"],
            "live_receipt": bool(certification["live_receipt_ids"]),
        }
        for requirement in CERTIFICATION_CHECKS:
            refs = certification["live_receipt_ids"] if requirement in {"recovery_tested", "live_receipt"} else []
            ref = terms_ref if requirement in {"terms_reviewed", "scope_bound"} else (refs[0] if refs else None)
            status = "VERIFIED_LOCAL" if values[requirement] else (
                "BLOCKED_EXTERNAL" if connector["required_for_v1"] else "DEFERRED_NOT_REQUIRED"
            )
            add(
                category="connector", subject_id=connector["id"], requirement=requirement,
                required_for_v1=connector["required_for_v1"], status=status, receipt_ref=ref,
                blockers=[f"Connector status is {connector['status']}", f"Certification {requirement} is not evidenced"],
                authority=["cloud_mutation_authorized"] if requirement not in {"terms_reviewed", "scope_bound"} else [],
                narrative=f"Connector certification dimension for class {connector['class']}.",
            )

    required_authorities = set(registry["completion_policy"]["required_authorities"])
    for name, value in registry["authority"].items():
        is_required = name in required_authorities
        add(
            category="authority", subject_id="aigc", requirement=name,
            required_for_v1=is_required, counts_toward_readiness=is_required,
            status="ASSERTED_CONFIG_ONLY" if value else (
                "BLOCKED_EXTERNAL" if is_required else "DEFERRED_NOT_REQUIRED"
            ),
            receipt_ref=None, blockers=[f"Authority flag {name} is {str(value).lower()}"],
            authority=[name],
            narrative="Authority is a separate authenticated artifact; a true configuration flag alone is not proof.",
        )

    required_counted = [g for g in gates if g["required_for_v1"] and g["counts_toward_readiness"]]
    resolved_required = [g for g in required_counted if g["status"] in {"VERIFIED_LOCAL", "VERIFIED_EXTERNAL"}]
    legacy = evaluate_registry(registry)
    program: dict[str, Any] = {
        "schema_version": "aigc.evidence-program.v1",
        "program_id": "AIGC-EVIDENCE-PROGRAM-V1",
        "evidence_scope": "LOCAL_LEDGER_AND_EXTERNAL_REQUESTS_NO_EXTERNAL_EXECUTION",
        "registry_sha256": canonical_sha256(registry),
        "legacy_readiness": legacy.to_dict(),
        "receipt_resolved_readiness": {
            "applicable_required_checks": len(required_counted),
            "verified_required_checks": len(resolved_required),
            "verified_applicable_ratio": round(len(resolved_required) / len(required_counted), 6),
        },
        "coverage": {
            "all_gates": len(gates),
            "required_counted_gates": len(required_counted),
            "required_prerequisites": 2,
            "deferred_or_optional_gates": sum(not g["required_for_v1"] for g in gates),
            "open_request_packets": len(requests),
            "required_open_request_packets": sum(r["required_for_v1"] for r in requests),
        },
        "gates": gates,
        "production_ready": False,
        "authority_granted": False,
        "external_action_performed": False,
    }
    program["program_sha256"] = canonical_sha256(program)
    request_bundle: dict[str, Any] = {
        "schema_version": "aigc.evidence-request-bundle.v1",
        "bundle_id": "AIGC-EVIDENCE-REQUESTS-V1",
        "purpose": "Exact receipt requests for every unresolved required and optional registry gate.",
        "requests": requests,
        "authority_granted": False,
        "external_action_performed": False,
    }
    request_bundle["bundle_sha256"] = canonical_sha256(request_bundle)
    return program, request_bundle
