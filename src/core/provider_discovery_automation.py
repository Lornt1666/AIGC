from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.core.provider_discovery_contracts import (
    DEFAULT_CATALOG_PATH,
    DEFAULT_FIXTURE_PATH,
    DEFAULT_TEMPLATE_PATH,
    ProviderDiscoveryAutomationError,
    ProviderExecutionDisabled,
    build_provenance_envelope,
    build_target_specification_submission,
    canonical_digest,
    execute_live,
    iso,
    load_catalog,
    load_fixture,
    load_template,
    render_command_plan,
    scan_for_sensitive_material,
    strict_validate,
    utc,
    validate_gcloud_argv,
)


def _digest(value: Any) -> str | None:
    return None if value in (None, "", [], {}) else canonical_digest(value)


def _summary(command_id: str, stdout: Any) -> dict[str, Any]:
    scan_for_sensitive_material(stdout)
    if command_id == "PROJECT_DESCRIBE" and isinstance(stdout, Mapping):
        return {
            "project_id": stdout.get("projectId"),
            "project_number": str(stdout.get("projectNumber") or ""),
            "lifecycle_state": stdout.get("lifecycleState"),
        }
    if command_id == "ENABLED_SERVICES_LIST" and isinstance(stdout, list):
        names = sorted({
            str(item.get("config", {}).get("name"))
            for item in stdout
            if isinstance(item, Mapping) and item.get("config", {}).get("name")
        })
        return {"enabled_api_service_names": names, "count": len(names)}
    if command_id == "PROJECT_IAM_POLICY" and isinstance(stdout, Mapping):
        bindings = stdout.get("bindings") if isinstance(stdout.get("bindings"), list) else []
        roles = sorted({
            str(item.get("role")) for item in bindings
            if isinstance(item, Mapping) and item.get("role")
        })
        return {"binding_count": len(bindings), "roles": roles}
    if command_id == "SERVICE_ACCOUNTS_LIST" and isinstance(stdout, list):
        emails = sorted({
            str(item.get("email")) for item in stdout
            if isinstance(item, Mapping) and item.get("email")
        })
        return {"service_account_count": len(emails), "service_account_emails": emails}
    if command_id.endswith("_SERVICE_ACCOUNT_KEYS") and isinstance(stdout, list):
        return {"user_managed_key_count": len(stdout)}
    if command_id in {"WIF_POOLS_LIST", "WIF_PROVIDERS_LIST"} and isinstance(stdout, list):
        names = sorted({
            str(item.get("name")) for item in stdout
            if isinstance(item, Mapping) and item.get("name")
        })
        return {"resource_count": len(names), "resource_names": names}
    if command_id == "SECRETS_LIST" and isinstance(stdout, list):
        names = sorted({
            str(item.get("name")) for item in stdout
            if isinstance(item, Mapping) and item.get("name")
        })
        return {"secret_count": len(names), "secret_resource_names": names}
    if command_id.endswith("_SECRET_VERSIONS_LIST") and isinstance(stdout, list):
        versions = sorted({
            str(item.get("name", "")).rsplit("/", 1)[-1]
            for item in stdout
            if isinstance(item, Mapping) and item.get("name")
        })
        return {"numeric_versions": versions, "version_count": len(versions)}
    if command_id == "STATE_BUCKET_DESCRIBE" and isinstance(stdout, Mapping):
        iam = stdout.get("iamConfiguration", {})
        return {
            "bucket_name": stdout.get("name"),
            "uniform_bucket_level_access": bool(iam.get("uniformBucketLevelAccess", {}).get("enabled")),
            "public_access_prevention": iam.get("publicAccessPrevention"),
            "versioning_enabled": bool(stdout.get("versioning", {}).get("enabled")),
            "retention_period_seconds": stdout.get("retentionPolicy", {}).get("retentionPeriod"),
        }
    return {"output_type": type(stdout).__name__}


def _command_result(command: Mapping[str, Any], response: Mapping[str, Any] | None) -> dict[str, Any]:
    base = {
        "command_id": command["command_id"], "argv": command["argv"],
        "argv_digest": command["argv_digest"], "attempt_count": 0,
        "stdout_digest": None, "stderr_digest": None, "summary": {},
    }
    if response is None:
        return {**base, "status": "MISSING_FIXTURE"}
    last, status, count = None, "FAILED", 0
    for attempt in list(response.get("attempts") or [])[:int(command["max_attempts"])]:
        last, count = attempt, count + 1
        outcome, exit_code = str(attempt.get("outcome") or "FAILED"), int(attempt.get("exit_code") or 0)
        if outcome == "SUCCESS" and exit_code == 0:
            status = "SUCCESS"
            break
        if outcome == "PERMISSION_DENIED":
            status = "PERMISSION_DENIED"
            break
        status = "TIMEOUT" if outcome == "TIMEOUT" else "FAILED"
    stdout = last.get("stdout_json") if last else None
    stderr = str(last.get("stderr") or "") if last else ""
    return {
        **base, "status": status, "attempt_count": count,
        "stdout_digest": _digest(stdout), "stderr_digest": _digest(stderr),
        "summary": _summary(command["command_id"], stdout) if status == "SUCCESS" else {},
    }


def _manual_checks(catalog: Mapping[str, Any], fixture: Mapping[str, Any]) -> list[dict[str, Any]]:
    observed, result = dict(fixture.get("manual_checks") or {}), []
    for check in catalog["manual_checks"]:
        item = dict(observed.get(check["check_id"]) or {})
        result.append({
            "check_id": check["check_id"], "status": item.get("status", "PENDING"),
            "notes": item.get("notes", "No synthetic manual-check result supplied."),
        })
    return result


def _evidence_candidate(
    results: Sequence[Mapping[str, Any]], checks: Sequence[Mapping[str, Any]],
    parameters: Mapping[str, str],
) -> dict[str, Any]:
    by_id = {item["command_id"]: item for item in results}
    failed = [item for item in results if item["status"] != "SUCCESS"]
    success = sum(item["status"] == "SUCCESS" for item in results)
    result = "FAILED" if not success else ("PARTIAL" if failed else "SUCCESS")
    project, bucket = by_id.get("PROJECT_DESCRIBE", {}), by_id.get("STATE_BUCKET_DESCRIBE", {})
    key_counts = []
    for command_id, email_key in (
        ("PLAN_SERVICE_ACCOUNT_KEYS", "plan_service_account_email"),
        ("APPLY_SERVICE_ACCOUNT_KEYS", "apply_service_account_email"),
        ("RUNTIME_SERVICE_ACCOUNT_KEYS", "runtime_service_account_email"),
    ):
        item = by_id.get(command_id, {})
        if item.get("status") == "SUCCESS":
            key_counts.append({
                "service_account_reference": (
                    f"gcp_service_account://{parameters['project_id']}/{parameters[email_key]}"
                ),
                "user_managed_key_count": item.get("summary", {}).get("user_managed_key_count", 0),
            })
    unresolved = [f"command:{item['command_id']}:{item['status']}" for item in failed]
    unresolved += [
        f"manual:{item['check_id']}:{item['status']}"
        for item in checks if item["status"] != "ACCEPTED"
    ]
    return {
        "artifact_kind": "SIMULATION_ONLY",
        "admissible_as_provider_evidence": False,
        "provider_read_performed": False,
        "external_action_performed": False,
        "result": result,
        "observed_resources": [
            {
                "resource_type": "PROJECT", "target_reference": parameters["project_reference"],
                "existence_status": "EXISTS" if project.get("status") == "SUCCESS" else "UNKNOWN",
                "evidence_digest": project.get("stdout_digest"),
            },
            {
                "resource_type": "STATE_BUCKET", "target_reference": parameters["state_bucket_reference"],
                "existence_status": "EXISTS" if bucket.get("status") == "SUCCESS" else "REQUIRES_BOOTSTRAP",
                "evidence_digest": bucket.get("stdout_digest"),
            },
        ],
        "enabled_api_service_names": by_id.get("ENABLED_SERVICES_LIST", {}).get(
            "summary", {}
        ).get("enabled_api_service_names", []),
        "service_account_key_counts": key_counts,
        "identity_platform_configuration_status": "UNKNOWN",
        "state_backend_status": "VERIFIED" if bucket.get("status") == "SUCCESS" else "MISSING",
        "unresolved_requirements": sorted(set(unresolved)),
    }


def run_mock_discovery(
    *, catalog: Mapping[str, Any], fixture: Mapping[str, Any],
    template: Mapping[str, Any], repository_revision: str,
    created_at, rollback_reference: str, ci_run_id: str | None = None,
) -> dict[str, Any]:
    catalog = strict_validate("provider_discovery_command_catalog", catalog)
    fixture = strict_validate("provider_discovery_mock_fixture", fixture)
    scan_for_sensitive_material(catalog)
    scan_for_sensitive_material(fixture)
    if fixture.get("synthetic") is not True:
        raise ProviderDiscoveryAutomationError("Only synthetic fixtures are permitted")
    parameters = fixture["parameters"]
    plan = render_command_plan(catalog, parameters)
    target = build_target_specification_submission(
        template, parameters=parameters, repository_revision=repository_revision,
        created_at=created_at,
    )
    responses = dict(fixture.get("responses") or {})
    results = [_command_result(command, responses.get(command["fixture_key"])) for command in plan]
    checks = _manual_checks(catalog, fixture)
    candidate = _evidence_candidate(results, checks, parameters)
    current = utc(created_at)
    catalog_digest, fixture_digest, plan_digest = (
        canonical_digest(catalog), canonical_digest(fixture), canonical_digest(plan)
    )
    material = {
        "revision": repository_revision, "catalog_digest": catalog_digest,
        "fixture_digest": fixture_digest, "command_plan_digest": plan_digest,
        "created_at": iso(current),
    }
    body = {
        "contract_id": "AIGC-PROVIDER-DISCOVERY-SIMULATION-REPORT-001",
        "contract_version": "1.0.0",
        "run_id": "PDSIM-" + canonical_digest(material)[:24].upper(),
        "execution_mode": "MOCK_ONLY", "repository_revision": repository_revision,
        "created_at": iso(current), "catalog_digest": catalog_digest,
        "fixture_digest": fixture_digest, "command_plan_digest": plan_digest,
        "result": candidate["result"], "no_network": True,
        "live_execution_attempted": False,
        "target_specification_submission": target, "command_results": results,
        "manual_checks": checks, "evidence_candidate": candidate,
        "raw_secret_values_present": False, "authorization_receipt_issued": False,
        "provider_action_performed": False, "external_action_performed": False,
    }
    report = dict(body)
    report["provenance_envelope"] = build_provenance_envelope(
        node_type="PROVIDER_DISCOVERY_SIMULATION", artifact=body,
        repository_revision=repository_revision, created_at=current,
        ci_run_id=ci_run_id, rollback_reference=rollback_reference,
    )
    scan_for_sensitive_material(report)
    return strict_validate("provider_discovery_simulation_report", report)


def write_mock_outputs(output_dir: str | Path, report: Mapping[str, Any]) -> list[Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs = {
        "target_specification_submission.json": report["target_specification_submission"],
        "command_plan.json": report["command_results"],
        "discovery_simulation_report.json": report,
        "provenance_envelope.json": report["provenance_envelope"],
    }
    written = []
    for name, value in outputs.items():
        path = root / name
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written
