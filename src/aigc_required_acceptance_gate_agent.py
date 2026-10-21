"""Strict, read-only acceptance coordinator for AIGC canonical CI evidence."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

SHA = re.compile(r"^[0-9a-f]{40}$")
CORE_STEPS = {
    "Checkout exact requested revision",
    "Verify exact requested checkout",
    "Install and verify dependencies",
    "Resolve tested tree",
    "Execute shared canonical validation runner",
    "Compile governed Gemini release",
    "Run Governor Agent policy tests",
    "Run Governor integration milestone gate tests",
    "Run read-only CI validation agent tests",
    "Run OIDC identity verifier tests",
    "Scan release-only paths for secret-like content",
    "Run focused Gemini controls with warnings as errors",
    "Run governed Gemini workflow offline smoke",
    "Emit exact-head admission receipt",
    "Upload canonical validation evidence",
}


class RequiredAcceptanceGateAgent:
    """Inspect one immutable workflow run and fail closed on missing proof."""

    def __init__(self, client: Any, reviewer_authenticator: Any, release_assurance: Any = None):
        self.client = client
        self.reviewer_authenticator = reviewer_authenticator
        self.release_assurance = release_assurance

    def inspect(self, *, repository: str, run_id: int, expected_sha: str,
                expected_tree_sha: str, independent_review: Mapping[str, Any] | None = None,
                human_acceptance: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not SHA.fullmatch(expected_sha):
            return self._blocked(["invalid_expected_sha"], run_id, expected_sha)
        if not SHA.fullmatch(expected_tree_sha):
            return self._blocked(["invalid_expected_tree_sha"], run_id, expected_sha)
        reasons: list[str] = []
        run = self.client.get_run(repository, run_id)
        jobs = self.client.get_jobs(repository, run_id)
        artifacts = self.client.get_artifacts(repository, run_id)
        if run.get("id") != run_id:
            reasons.append("run_id_mismatch")
        if run.get("head_sha") != expected_sha:
            reasons.append("run_head_sha_mismatch")
        if run.get("head_commit", {}).get("tree_id") != expected_tree_sha:
            reasons.append("run_tree_sha_mismatch")
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            reasons.append("full_workflow_not_successful")
        if not jobs:
            reasons.append("jobs_missing")

        step_report = []
        failure_signals = []
        for job in jobs:
            if job.get("status") != "completed" or job.get("conclusion") != "success":
                reasons.append("job_not_successful:" + str(job.get("name", "unknown")))
            steps = job.get("steps") if isinstance(job.get("steps"), list) else []
            seen = set()
            for step in steps:
                name = str(step.get("name", ""))
                seen.add(name)
                conclusion = str(step.get("conclusion") or "missing")
                step_report.append({"job": job.get("name"), "name": name,
                                    "status": step.get("status"), "conclusion": conclusion})
                if name in CORE_STEPS and conclusion != "success":
                    reasons.append("required_step_not_success:" + name)
            for missing in sorted(CORE_STEPS - seen):
                reasons.append("required_step_missing:" + missing)
            if job.get("conclusion") == "failure" and job.get("id") is not None:
                try:
                    raw = self.client.get_job_logs(repository, int(job["id"]))
                    lines = [line.strip() for line in str(raw).splitlines()
                             if re.search(r"(?i)(error|failed|failure|traceback|assertion)", line)]
                    failure_signals.extend(lines[-20:])
                except Exception:
                    reasons.append("job_logs_unavailable:" + str(job.get("name", "unknown")))

        matching = [a for a in artifacts if expected_sha in str(a.get("name", ""))
                    and a.get("expired") is not True
                    and (a.get("workflow_run") or {}).get("head_sha") == expected_sha
                    and (a.get("workflow_run") or {}).get("id") == run_id]
        artifact_report = None
        if len(matching) != 1:
            reasons.append("exact_run_artifact_missing_or_ambiguous")
        else:
            artifact = matching[0]
            try:
                data = self.client.download_artifact(repository, int(artifact["id"]))
                digest = hashlib.sha256(data).hexdigest()
                advertised = str(artifact.get("digest", "")).removeprefix("sha256:")
                if not re.fullmatch(r"[0-9a-f]{64}", advertised) or digest != advertised:
                    reasons.append("artifact_digest_mismatch")
                parsed = self._read_zip(data)
                receipt = parsed.get("exact_head_admission_receipt.json")
                if not isinstance(receipt, Mapping):
                    reasons.append("exact_head_receipt_missing")
                    receipt = {}
                bindings = {
                    "requested_head_sha": expected_sha, "observed_head_sha": expected_sha,
                    "requested_revision": expected_sha, "workflow_revision": expected_sha,
                    "tested_tree_sha": expected_tree_sha, "workflow_run_id": run_id,
                    "repository": repository,
                }
                for key, expected in bindings.items():
                    if receipt.get(key) != expected:
                        reasons.append("receipt_binding_mismatch:" + key)
                stage_records = [v for v in parsed.values()
                                 if isinstance(v, Mapping) and isinstance(v.get("stage_id"), str)]
                if not stage_records:
                    reasons.append("stage_records_missing")
                for record in stage_records:
                    stage = str(record.get("stage_id"))
                    if record.get("target_sha") != expected_sha:
                        reasons.append("stage_sha_mismatch:" + stage)
                    if record.get("tested_tree_sha") != expected_tree_sha:
                        reasons.append("stage_tree_mismatch:" + stage)
                    if record.get("run_id") != run_id:
                        reasons.append("stage_run_mismatch:" + stage)
                    if str(record.get("status", "")).lower() not in {"success", "passed", "pass"}:
                        reasons.append("stage_failed:" + stage)
                artifact_report = {
                    "artifact_id": artifact.get("id"), "name": artifact.get("name"),
                    "advertised_sha256": "sha256:" + advertised,
                    "computed_sha256": "sha256:" + digest,
                    "members": sorted(parsed), "receipt": dict(receipt),
                    "stage_count": len(stage_records),
                }
            except Exception as exc:
                reasons.append("artifact_inspection_failed:" + type(exc).__name__)

        review = None
        if artifact_report and independent_review:
            try:
                review = self.reviewer_authenticator.verify(
                    independent_review, expected_sha=expected_sha,
                    artifact_digest=artifact_report["computed_sha256"])
            except Exception as exc:
                reasons.append("independent_review_invalid:" + type(exc).__name__)
        else:
            reasons.append("independent_review_missing")
        if not isinstance(human_acceptance, Mapping) or human_acceptance.get("accepted") is not True:
            reasons.append("explicit_human_acceptance_missing")
        elif (human_acceptance.get("subject_sha") != expected_sha
              or not str(human_acceptance.get("human_id", "")).strip()):
            reasons.append("human_acceptance_subject_or_identity_invalid")

        reasons = sorted(set(reasons))
        report = {
            "schema_version": "aigc-required-acceptance-gate/1.0",
            "repository": repository, "run_id": run_id, "expected_sha": expected_sha,
            "expected_tree_sha": expected_tree_sha, "run_status": run.get("status"),
            "run_conclusion": run.get("conclusion"), "jobs_count": len(jobs),
            "steps_inspected": step_report,
            "sanitized_failure_signals": [
                re.sub(r"(?i)(token|password|secret|api[_-]?key)(\s*[:=]\s*)[^\s,;]+",
                       r"\1\2[REDACTED]", x)[:500] for x in failure_signals],
            "artifact": artifact_report, "authenticated_review": review,
            "human_acceptance": dict(human_acceptance) if isinstance(human_acceptance, Mapping) else None,
            "reasons": reasons, "status": "READY_FOR_RELEASE_ASSURANCE" if not reasons else "BLOCK",
            "release_decision": "BLOCK", "submitted_to_release_assurance": False,
            "automatic_changes_performed": False,
        }
        if not reasons and self.release_assurance is not None:
            decision = self.release_assurance.evaluate(report)
            report["release_assurance_decision"] = decision
            report["submitted_to_release_assurance"] = True
            report["release_decision"] = decision.get("decision", "BLOCK") if isinstance(decision, Mapping) else "BLOCK"
        return report

    @staticmethod
    def _read_zip(data: bytes) -> dict[str, Any]:
        import io
        import zipfile
        parsed = {}
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.infolist()) > 200:
                raise ValueError("artifact member limit exceeded")
            total = 0
            for info in archive.infolist():
                path = info.filename.replace("\\", "/")
                if path.startswith("/") or any(part in {"", ".", ".."} for part in path.split("/")):
                    raise ValueError("unsafe artifact path")
                total += info.file_size
                if info.file_size > 2 * 1024 * 1024 or total > 25 * 1024 * 1024:
                    raise ValueError("artifact expansion limit exceeded")
                if path.endswith(".json"):
                    obj = json.loads(archive.read(info).decode("utf-8"))
                    if isinstance(obj, Mapping):
                        parsed[path] = obj
        return parsed

    @staticmethod
    def _blocked(reasons: list[str], run_id: int, expected_sha: str) -> dict[str, Any]:
        return {"schema_version": "aigc-required-acceptance-gate/1.0",
                "run_id": run_id, "expected_sha": expected_sha, "reasons": reasons,
                "status": "BLOCK", "release_decision": "BLOCK",
                "submitted_to_release_assurance": False, "automatic_changes_performed": False}
