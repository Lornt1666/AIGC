"""MVP++ Documentation Architect: deterministic, evidence-aware document-pack generator.

Consumes a structured project brief and optional evidence inventory, selects the
appropriate governance/engineering document set, and writes draft documents plus
a content-addressed manifest. It never invents approvals, test outcomes, owners,
SLO values, regulatory status, or production readiness. No network/model/shell
calls or repository writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
POLICY_ID = "aigc-mvp-plus-plus-documentation-v1"
BASE_DOCS = [
    ("00-executive-charter.md", "Executive Charter and Scope", "charter"),
    ("01-requirements-and-acceptance.md", "Requirements and Acceptance Criteria", "requirements"),
    ("02-system-architecture-and-decisions.md", "System Architecture and Architecture Decision Records", "architecture"),
    ("03-risk-register-and-threat-model.md", "Risk Register and Threat Model", "risk"),
    ("04-engineering-plan-and-test-strategy.md", "Engineering Plan and Test Strategy", "engineering"),
    ("05-operations-and-incident-runbook.md", "Operations, Recovery, and Incident Runbook", "operations"),
    ("06-evidence-and-release-assurance.md", "Evidence Plan and Release Assurance", "release"),
    ("07-decisions-assumptions-and-open-questions.md", "Decision, Assumption, and Open-Question Register", "decisions"),
]
OPTIONAL_DOCS = [
    ("08-api-and-integration-contracts.md", "API and Integration Contracts", "api", ("api", "endpoint", "webhook", "integration", "connector", "mcp")),
    ("09-data-governance-and-privacy.md", "Data Governance, Privacy, and Retention", "data", ("personal data", "pii", "privacy", "retention", "database", "dataset", "user data")),
    ("10-ai-agent-governance.md", "AI/Agent Governance and Evaluation", "ai", ("agent", "llm", "model", "ai", "artificial intelligence", "prompt", "autonomous")),
    ("11-deployment-and-infrastructure.md", "Deployment and Infrastructure Plan", "infra", ("deploy", "deployment", "cloud", "kubernetes", "terraform", "infrastructure", "hosting")),
    ("12-security-and-access-control.md", "Security Architecture and Access Control", "security", ("security", "authentication", "authorization", "secret", "credential", "threat", "encryption")),
    ("13-user-experience-and-accessibility.md", "User Experience and Accessibility", "ux", ("ui", "ux", "user journey", "frontend", "dashboard", "accessibility", "interface")),
    ("14-financial-and-procurement-controls.md", "Financial, Cost, and Procurement Controls", "finance", ("budget", "cost", "billing", "procurement", "payment", "financial")),
    ("15-compliance-and-regulatory-mapping.md", "Compliance and Regulatory Applicability", "compliance", ("compliance", "regulated", "regulatory", "legal", "audit", "sox", "gdpr", "hipaa")),
]

def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()

def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)

def _safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")[:100] or "project"

def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []

def _bullet(items: list[Any], empty: str = "Not supplied. Record evidence or explicitly mark this item not applicable.") -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {_text(item).replace(chr(10), ' ')}" for item in items)

def _section(title: str, body: str) -> str:
    return f"## {title}\n\n{body.strip() or 'Not supplied. Mark as unknown until verified.'}\n"

def select_documents(brief: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Always select the core governance pack; select specialist docs by explicit brief signals."""
    serialized = _text(brief).lower()
    docs = list(BASE_DOCS)
    for filename, title, key, signals in OPTIONAL_DOCS:
        if any(signal in serialized for signal in signals):
            docs.append((filename, title, key))
    # A high-risk project always needs explicit security and compliance applicability
    # documents even if the brief has not described them in detail.
    risk = str(brief.get("risk_level", brief.get("risk", ""))).lower()
    if risk in {"high", "critical", "very high"}:
        for doc in OPTIONAL_DOCS:
            if doc[2] in {"security", "compliance"} and doc not in docs:
                docs.append(doc[:3])
    return docs

def _content(kind: str, brief: dict[str, Any], source_digest: str) -> str:
    project = str(brief.get("project_name") or brief.get("name") or brief.get("project_id") or "UNNAMED PROJECT")
    purpose = _text(brief.get("purpose") or brief.get("objective") or brief.get("problem_statement") or "Not supplied.")
    scope = _list(brief.get("scope"))
    non_goals = _list(brief.get("non_goals") or brief.get("out_of_scope"))
    requirements = _list(brief.get("requirements") or brief.get("features"))
    constraints = _list(brief.get("constraints"))
    risks = _list(brief.get("risks") or brief.get("known_risks"))
    stakeholders = _list(brief.get("stakeholders") or brief.get("owners"))
    acceptance = _list(brief.get("acceptance_criteria") or brief.get("success_criteria"))
    interfaces = _list(brief.get("interfaces") or brief.get("integrations"))
    evidence = _list(brief.get("evidence_refs") or brief.get("evidence"))
    # All generated documents carry explicit draft status, input digest, and non-approval semantics.
    head = (
        f"# {dict((x[2], x[1]) for x in BASE_DOCS + [d[:3] for d in OPTIONAL_DOCS]).get(kind, kind.title())}\n\n"
        f"> **STATUS: GENERATED DRAFT — NOT APPROVED.** This document is a structured starting point, "
        f"not proof of implementation, compliance, safety, or release readiness.\n\n"
        f"- Project: {project}\n- Policy: `{POLICY_ID}`\n- Source brief SHA-256: `{source_digest}`\n"
        f"- Generated deterministically; no model/network calls were made.\n"
    )
    if kind == "charter":
        body = _section("Executive summary", purpose) + _section("Objectives", _bullet(_list(brief.get("objectives")))) + _section("Scope", _bullet(scope)) + _section("Non-goals", _bullet(non_goals)) + _section("Stakeholders and accountable owner", _bullet(stakeholders)) + _section("Constraints", _bullet(constraints)) + _section("Success measures", _bullet(acceptance)) + _section("Approval status", "No approval is inferred. Identify the authorized approver, approval record, and date before execution or release.")
    elif kind == "requirements":
        body = _section("Problem and intended users", purpose) + _section("Requirements", _bullet(requirements)) + _section("Acceptance criteria", _bullet(acceptance)) + _section("Constraints and dependencies", _bullet(constraints + interfaces)) + _section("Traceability rule", "Every requirement must have a stable ID, source, priority, verification method, owner, and status. Do not mark complete without linked test/evidence IDs.") + _section("Unknowns", "Requirements not present in the source brief remain TBD; do not silently fill gaps.")
    elif kind == "architecture":
        body = _section("System context", purpose) + _section("Architecture inputs", f"Source brief digest: `{source_digest}`.") + _section("Known components and interfaces", _bullet(interfaces)) + _section("Architecture constraints", _bullet(constraints)) + _section("Decision records", "Create one ADR per consequential decision: context, options, decision, rationale, consequences, alternatives, owner, date, and status. No decision is inferred by this generator.") + _section("Trust boundaries and failure modes", "Map identities, data flows, trust boundaries, dependencies, failure modes, degradation behavior, and recovery paths before implementation.") + _section("Architecture status", "Proposed only; requires independent architecture/engineering review.")
    elif kind == "risk":
        body = _section("Known risks", _bullet(risks)) + _section("Risk scoring method", "For each risk record likelihood, impact, severity, evidence, owner, mitigation, residual risk, due date, and acceptance authority. Scoring values were not supplied and are not invented.") + _section("Threat-model scope", purpose) + _section("Assets and trust boundaries", "TBD — inventory assets, identities, entry points, sensitive data, external dependencies, and trust boundaries.") + _section("Abuse cases and mitigations", "Enumerate abuse cases; use synthetic/offline scenarios by default. Any live test requires separate scoped authorization.") + _section("Risk acceptance", "Unresolved critical/high risks block release unless an authorized risk owner documents an approved exception.")
    elif kind == "engineering":
        body = _section("Implementation workstreams", _bullet(requirements + scope)) + _section("Verification strategy", "Use unit, integration, contract, security, regression, and end-to-end tests as appropriate. Bind results to the exact commit and tested tree; preserve logs and artifact digests.") + _section("Quality gates", "- Static analysis and type/schema checks\n- Automated tests with observed results\n- Independent review and separation of duties\n- Security and dependency checks\n- Reproducible build and artifact provenance\n- Rollback/recovery validation") + _section("Definition of done", _bullet(acceptance)) + _section("Known limitations", "No test result is assumed by document generation.")
    elif kind == "operations":
        body = _section("Service and operating model", purpose) + _section("Dependencies", _bullet(interfaces)) + _section("Observability", "Define SLIs/SLOs, metrics, logs, traces, alert thresholds, ownership, retention, and redaction. Values must come from accountable owners and measured baselines.") + _section("Incident response", "Document severity levels, detection, triage, containment, communication, escalation, evidence preservation, recovery, and post-incident review.") + _section("Recovery and rollback", "TBD — define backup/restore objectives, rollback triggers, tested procedures, RTO/RPO where applicable, and recovery owner.") + _section("Operational readiness", "Require on-call ownership, dashboards, runbooks, capacity/cost limits, dependency failure handling, and a rehearsal before production.")
    elif kind == "release":
        body = _section("Release posture", "BLOCKED until all applicable checks, authenticated provenance, independent verification, and required human approvals pass.") + _section("Required evidence", "- Exact source commit and tested tree\n- CI run URL, final conclusion, and test output\n- SBOM/dependency and security results where applicable\n- Signed artifact and provenance attestation from trusted identity\n- Independent review and approval record\n- Rollback and operational-readiness evidence\n- Canonical release-decision receipt") + _section("Evidence supplied in brief", _bullet(evidence)) + _section("Trust rules", "A digest is not a signature. Test fixtures are not production trust. Stale, missing, unauthenticated, mismatched, or unverifiable evidence fails closed.") + _section("Decision authority", "Only the existing canonical Release Assurance authority makes the release decision.")
    elif kind == "decisions":
        body = _section("Confirmed decisions", "None are inferred by this generator. Record each accepted decision with source, decision-maker, timestamp, rationale, alternatives, and consequences.") + _section("Assumptions", "List assumptions separately from verified facts; assign an owner, validation method, and due date.") + _section("Open questions", "- What is the accountable owner?\n- What are the measurable acceptance criteria and SLOs?\n- Which data classes, integrations, and threat boundaries apply?\n- What is the rollback/recovery strategy?\n- Which evidence and approvals are required before release?") + _section("Change log", "Add dated entries for approved changes; retain prior decisions.")
    elif kind == "api":
        body = _section("Known interfaces", _bullet(interfaces)) + _section("Contract requirements", "For each interface specify owner, authentication, authorization, schema/version, idempotency, timeouts, retries, rate limits, error semantics, observability, compatibility, and deprecation.") + _section("Security boundary", "No credentials or tokens belong in examples. Use placeholders and define rotation/revocation controls.") + _section("Contract tests", "Test success, invalid input, unauthorized access, timeout, retry, duplicate delivery, partial failure, and backwards compatibility.")
    elif kind == "data":
        body = _section("Known data context", purpose) + _section("Data inventory", "Classify data, source, purpose, lawful basis where applicable, access, location, retention, deletion, and sharing. Unspecified classifications remain TBD.") + _section("Privacy and threat controls", "Apply data minimization, least privilege, encryption, redaction, retention limits, and auditable access.") + _section("Lifecycle and deletion", "Document creation, use, export, correction, retention, deletion, backups, and verification of deletion.")
    elif kind == "ai":
        body = _section("AI/agent purpose", purpose) + _section("Authority model", "Separate planner, executor, evidence producer, verifier, and release decision authority. No implicit permission escalation or self-approval.") + _section("Task and tool contracts", "Specify typed inputs/outputs, allowed/prohibited actions, budget/time limits, idempotency, retry rules, and human gates.") + _section("Evaluation", "Use versioned offline fixtures, adversarial cases, quality metrics, regression tests, and independently reviewed evidence.") + _section("Autonomy boundary", "Unknown evidence blocks consequential action. External writes, spending, secrets, deployment, and release require explicit scoped authority.")
    elif kind == "infra":
        body = _section("Infrastructure intent", purpose) + _section("Environment separation", "Separate development, test, staging, and production identities/resources. Default to least privilege and inert plans.") + _section("Infrastructure as code", "Pin providers/modules, scan configuration, review plans, protect state, and prohibit unapproved apply operations.") + _section("Deployment and rollback", "Specify approvals, artifact provenance, health checks, progressive rollout, abort criteria, rollback, and post-deploy verification. No deployment is authorized by this document.")
    elif kind == "security":
        body = _section("Security scope", purpose) + _section("Identity and access", "Document identities, roles, least privilege, MFA/service identity, review cadence, revocation, and break-glass procedures.") + _section("Secrets and cryptographic trust", "Use managed secret/key services; pin trusted identities/keys independently; define rotation and revocation. Never commit private keys.") + _section("Threat controls", _bullet(risks)) + _section("Security verification", "Require dependency, static, secret, access-control, threat-model, and incident-recovery evidence appropriate to the system.")
    elif kind == "ux":
        body = _section("Target users and journeys", purpose) + _section("Known interface requirements", _bullet(requirements)) + _section("Accessibility", "Define keyboard navigation, focus order, screen-reader semantics, contrast, responsive behavior, error recovery, and usability testing.") + _section("Acceptance evidence", "Use observable task completion, usability findings, accessibility checks, and approved design review.")
    elif kind == "finance":
        body = _section("Budget and cost inputs", _bullet(constraints)) + _section("Cost controls", "Set explicit budget caps, usage alerts, per-run limits, approval thresholds, and stop conditions. Values are TBD unless supplied.") + _section("Procurement and payment", "Require vendor assessment, terms review, owner approval, receipts, and separation of requester/approver. This document grants no spending authority.") + _section("Cost observability", "Track actual and forecast cost per workload and enforce fail-closed behavior at configured limits.")
    elif kind == "compliance":
        body = _section("Applicability status", "NOT DETERMINED. Do not claim certification or legal compliance from this document. Obtain qualified review for the jurisdictions and data/processes in scope.") + _section("Obligation mapping", "Map each applicable obligation to control, owner, implementation evidence, test/evaluation evidence, exceptions, and review date.") + _section("Audit readiness", "Retain provenance, access logs, decision records, versioned policies, approvals, and evidence with appropriate access controls.")
    else:
        body = _section("Purpose", purpose)
    return head + "\n" + body + "\n"

def generate_document_pack(brief: dict[str, Any], output_dir: Path, evidence_inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(brief, dict) or not brief:
        raise ValueError("brief must be a non-empty JSON object")
    if not isinstance(output_dir, Path):
        output_dir = Path(output_dir)
    # Embed optional evidence inventory in the input digest; its claims remain unverified unless separately validated.
    source = {"brief": brief, "evidence_inventory": evidence_inventory or {}}
    source_digest = sha256(canonical_json(source))
    docs = select_documents(brief)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for filename, title, kind in docs:
        content = _content(kind, brief, source_digest)
        path = output_dir / filename
        path.write_text(content, encoding="utf-8", newline="\n")
        records.append({"path": filename, "title": title, "kind": kind, "status": "GENERATED_DRAFT",
                        "sha256": sha256(content), "bytes": len(content.encode("utf-8"))})
    index = [
        "# MVP++ Documentation Pack Index", "",
        "> **GENERATED DRAFT — NOT APPROVED.** This index does not certify completeness, correctness, compliance, or release readiness.", "",
        f"- Project: {brief.get('project_name') or brief.get('name') or brief.get('project_id') or 'UNNAMED PROJECT'}",
        f"- Policy: `{POLICY_ID}`", f"- Source digest: `{source_digest}`", "",
        "## Generated documents", "",
    ]
    index.extend(f"- [{r['title']}]({r['path']}) — `{r['status']}`, SHA-256 `{r['sha256']}`" for r in records)
    index += ["", "## Governance rules", "", "- Generated text is a draft; approvals are never inferred.",
              "- Missing facts remain unknown/TBD and must be assigned an owner.",
              "- Hashes provide integrity comparison, not authentication.",
              "- The pack must be independently reviewed and updated against actual implementation.",
              "- Release remains blocked until applicable evidence and approvals pass.", ""]
    (output_dir / "README.md").write_text("\n".join(index), encoding="utf-8", newline="\n")
    records.insert(0, {"path": "README.md", "title": "Documentation Pack Index", "kind": "index",
                       "status": "GENERATED_DRAFT", "sha256": sha256((output_dir / "README.md").read_text(encoding="utf-8")),
                       "bytes": (output_dir / "README.md").stat().st_size})
    manifest = {
        "schema_version": SCHEMA_VERSION, "policy_id": POLICY_ID,
        "project": brief.get("project_name") or brief.get("name") or brief.get("project_id") or "UNNAMED PROJECT",
        "source_digest_sha256": source_digest, "document_count": len(records),
        "status": "GENERATED_DRAFT", "documents": records,
        "authority": {"approvals_inferred": False, "release_decision": "BLOCK",
                      "may_write_repository": False, "may_execute_external_actions": False},
    }
    manifest["manifest_sha256"] = sha256(canonical_json(manifest))
    (output_dir / "documentation_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a governed MVP++ documentation pack from a structured brief.")
    parser.add_argument("--input", required=True, help="Path to structured JSON brief")
    parser.add_argument("--output-dir", required=True, help="Output directory for generated draft documents")
    parser.add_argument("--evidence-inventory", help="Optional JSON inventory; entries are recorded as claims, not authenticated proof")
    args = parser.parse_args(argv)
    try:
        brief = json.loads(Path(args.input).read_text(encoding="utf-8"))
        inventory = json.loads(Path(args.evidence_inventory).read_text(encoding="utf-8")) if args.evidence_inventory else None
        manifest = generate_document_pack(brief, Path(args.output_dir), inventory)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": manifest["status"], "document_count": manifest["document_count"],
                      "source_digest_sha256": manifest["source_digest_sha256"],
                      "manifest_sha256": manifest["manifest_sha256"], "release_decision": manifest["authority"]["release_decision"]}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
