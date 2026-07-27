from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Protocol

from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_controlled_gemini_canary import (
    ControlledCanaryError,
    canonical_sha256,
    validate_ci_receipt,
)
from scripts.validate_gemini_staging_authorization import (
    StagingAuthorizationError,
    validate_authorization,
)
from src.gemini_workflow.judge_receipts import (
    JudgeReceiptClaim,
    JudgeReceiptDraft,
    JudgeReceiptError,
    JudgeReceiptPublicationService,
    PublishedJudgeReceipt,
    required_publication_phrase,
)
from src.gemini_workflow.judge_store import (
    GcsJudgeReceiptWriteResult,
    GcsJudgeReceiptWriter,
)


class JudgeReceiptCommandError(RuntimeError):
    """Raised before an unsafe or evidence-mismatched publication."""


class _ReceiptWriter(Protocol):
    def create_if_absent(
        self,
        receipt: PublishedJudgeReceipt,
    ) -> Any: ...


_SHA = re.compile(r"^[a-f0-9]{40}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
_REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
_WORKFLOW_RUN = re.compile(r"^AIGC-GEMINI-RUN-[A-Za-z0-9-]{1,80}$")
_DEPLOYMENT_SCHEMA = "aigc.gemini-staging-deployment-receipt.v1"
_RUNTIME_SCHEMA = "aigc.gemini-runtime-receipt.v1"
_PUBLICATION_SCHEMA = "aigc.judge-receipt-publication-receipt.v1"
_JUDGE_PREFIX = "judge-receipts/v1"


class _PrepareOnlyWriter:
    """A local preparation boundary that cannot publish anything."""

    def create_if_absent(self, receipt: PublishedJudgeReceipt) -> None:
        del receipt
        raise JudgeReceiptCommandError(
            "Prepare-only mode cannot publish a judge receipt"
        )


class _CapturingWriter:
    def __init__(self, writer: _ReceiptWriter) -> None:
        self._writer = writer
        self.result: GcsJudgeReceiptWriteResult | None = None

    def create_if_absent(self, receipt: PublishedJudgeReceipt) -> None:
        result = self._writer.create_if_absent(receipt)
        if not isinstance(result, GcsJudgeReceiptWriteResult):
            raise JudgeReceiptCommandError(
                "Judge receipt writer did not return a GCS generation receipt"
            )
        self.result = GcsJudgeReceiptWriteResult.model_validate(
            result.model_dump(mode="python")
        )


def validate_evidence_bundle(
    *,
    authorization: dict[str, Any],
    deployment: dict[str, Any],
    ci_receipt: dict[str, Any],
    runtime_receipt: dict[str, Any],
    gate: str,
    now: datetime | None = None,
) -> JudgeReceiptClaim:
    """Validate the exact immutable evidence used by a public claim."""

    if gate not in {"live", "judge"}:
        raise JudgeReceiptCommandError("Unsupported judge receipt gate")
    try:
        validate_authorization(
            authorization,
            gate=gate,  # type: ignore[arg-type]
            now=now,
        )
    except StagingAuthorizationError as exc:
        raise JudgeReceiptCommandError(
            f"Staging authorization failed the {gate} gate"
        ) from exc

    release_revision = authorization.get("release_revision")
    if not isinstance(release_revision, str) or not _SHA.fullmatch(
        release_revision
    ):
        raise JudgeReceiptCommandError(
            "Authorization has no exact release Git SHA"
        )
    try:
        validate_ci_receipt(
            ci_receipt,
            release_revision=release_revision,
        )
    except ControlledCanaryError as exc:
        raise JudgeReceiptCommandError(
            "A successful, non-zero-step CI receipt is required"
        ) from exc
    if ci_receipt.get("workflow_name") != "AIGC CI":
        raise JudgeReceiptCommandError(
            "CI receipt does not identify the required AIGC CI workflow"
        )
    run_id = ci_receipt.get("run_id")
    if not isinstance(run_id, str) or not run_id.isdigit():
        raise JudgeReceiptCommandError("CI receipt run_id is invalid")
    _timestamp(ci_receipt.get("captured_at"), "CI captured_at")

    _validate_deployment_receipt(
        deployment,
        authorization=authorization,
        release_revision=release_revision,
    )
    _validate_runtime_receipt(
        runtime_receipt,
        authorization=authorization,
        deployment=deployment,
        ci_receipt=ci_receipt,
        release_revision=release_revision,
    )

    evidence = _mapping(runtime_receipt, "evidence")
    try:
        return JudgeReceiptClaim(
            project_slug="AIGC",
            business_identity="RegenExcalibur",
            capability="gemini_opportunity_assessment",
            evidence_basis="live_runtime_receipt",
            workflow_run_id=_required_text(
                runtime_receipt,
                "workflow_run_id",
            ),
            source_revision=release_revision,
            runtime_revision=_required_text(
                runtime_receipt,
                "cloud_run_revision",
            ),
            evidence_record_sha256=_required_text(
                evidence,
                "record_sha256",
            ),
            evidence_generation=evidence["generation"],
            model_api_call_status="confirmed",
            model_api_call_performed=True,
            human_review_state="required",
            ai_use_disclosed=True,
            external_action_performed=False,
        )
    except (KeyError, ValidationError) as exc:
        raise JudgeReceiptCommandError(
            "Runtime receipt cannot form a judge-safe claim"
        ) from exc


def prepare_judge_receipt(
    *,
    authorization: dict[str, Any],
    deployment: dict[str, Any],
    ci_receipt: dict[str, Any],
    runtime_receipt: dict[str, Any],
    output: Path,
    now: datetime | None = None,
    service: JudgeReceiptPublicationService | None = None,
) -> JudgeReceiptDraft:
    """Prepare a local draft only; this function has no GCS writer."""

    claim = validate_evidence_bundle(
        authorization=authorization,
        deployment=deployment,
        ci_receipt=ci_receipt,
        runtime_receipt=runtime_receipt,
        gate="live",
        now=now,
    )
    publisher = service or JudgeReceiptPublicationService(
        writer=_PrepareOnlyWriter()
    )
    draft = publisher.prepare(claim)
    _write_json_create_only(output, draft.model_dump(mode="json"))
    return draft


def publish_judge_receipt(
    *,
    authorization: dict[str, Any],
    deployment: dict[str, Any],
    ci_receipt: dict[str, Any],
    runtime_receipt: dict[str, Any],
    draft: JudgeReceiptDraft,
    confirmation_phrase: str,
    output: Path,
    now: datetime | None = None,
    writer: _ReceiptWriter | None = None,
    clock: Any | None = None,
) -> dict[str, Any]:
    """Publish one previously reviewed draft through create-only GCS writes."""

    claim = validate_evidence_bundle(
        authorization=authorization,
        deployment=deployment,
        ci_receipt=ci_receipt,
        runtime_receipt=runtime_receipt,
        gate="judge",
        now=now,
    )
    validated_draft = _validate_draft(draft)
    if validated_draft.claim != claim:
        raise JudgeReceiptCommandError(
            "Judge draft does not exactly match the current evidence bundle"
        )
    required_phrase = required_publication_phrase(validated_draft)
    if confirmation_phrase != required_phrase:
        raise JudgeReceiptCommandError(
            "Publication requires the exact content-bound confirmation phrase"
        )
    _ensure_create_only_target(output)

    cloud = _mapping(authorization, "cloud")
    gcs_writer = writer or GcsJudgeReceiptWriter(
        project_id=_required_text(cloud, "project_id"),
        bucket_name=_required_text(cloud, "judge_receipt_bucket"),
        prefix=_JUDGE_PREFIX,
    )
    capture = _CapturingWriter(gcs_writer)
    publisher = JudgeReceiptPublicationService(
        writer=capture,
        clock=clock,
    )
    try:
        published = publisher.publish(
            validated_draft,
            confirmation_phrase=confirmation_phrase,
        )
    except JudgeReceiptError as exc:
        raise JudgeReceiptCommandError(
            "Create-only GCS judge receipt publication failed"
        ) from exc
    if capture.result is None:
        raise JudgeReceiptCommandError(
            "GCS publication returned no generation-pinned receipt"
        )

    publication_receipt = {
        "schema_version": _PUBLICATION_SCHEMA,
        "publication_state": "published",
        "business_identity": "RegenExcalibur",
        "repository": "Lornt1666/AIGC",
        "release_revision": authorization["release_revision"],
        "image_digest": deployment["image_digest"],
        "operator_revision": deployment["operator_revision"],
        "judge_revision": deployment["judge_revision"],
        "runtime_evidence": {
            "object_uri": runtime_receipt["evidence"]["object_uri"],
            "generation": runtime_receipt["evidence"]["generation"],
            "record_sha256": runtime_receipt["evidence"]["record_sha256"],
        },
        "published_receipt": published.model_dump(mode="json"),
        "gcs_write_receipt": capture.result.model_dump(mode="json"),
        "authorization_sha256": canonical_sha256(authorization),
        "deployment_receipt_sha256": canonical_sha256(deployment),
        "ci_receipt_sha256": canonical_sha256(ci_receipt),
        "runtime_receipt_sha256": canonical_sha256(runtime_receipt),
        "model_api_call_performed_during_publication": False,
        "external_business_action_performed": False,
        "gcs_create_only_objects_created": 2,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json_create_only(output, publication_receipt)
    return publication_receipt


def _validate_deployment_receipt(
    receipt: dict[str, Any],
    *,
    authorization: dict[str, Any],
    release_revision: str,
) -> None:
    if receipt.get("schema_version") != _DEPLOYMENT_SCHEMA:
        raise JudgeReceiptCommandError("Deployment receipt schema is invalid")
    _required_text(receipt, "build_id")
    cloud = _mapping(authorization, "cloud")
    exact_fields = {
        "project_id": cloud["project_id"],
        "region": cloud["primary_region"],
        "release_revision": release_revision,
        "operator_service": cloud["operator_service_name"],
        "judge_service": cloud["judge_service_name"],
    }
    for name, expected in exact_fields.items():
        if receipt.get(name) != expected:
            raise JudgeReceiptCommandError(
                f"Deployment receipt does not match {name}"
            )
    digest = receipt.get("image_digest")
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise JudgeReceiptCommandError(
            "Deployment receipt has no immutable image digest"
        )
    expected_image = (
        f"{cloud['primary_region']}-docker.pkg.dev/"
        f"{cloud['project_id']}/"
        f"{cloud['artifact_registry_repository']}/aigc-gemini@{digest}"
    )
    if receipt.get("immutable_image_uri") != expected_image:
        raise JudgeReceiptCommandError(
            "Deployment receipt immutable image URI is not exact"
        )
    for name in ("operator_revision", "judge_revision"):
        value = receipt.get(name)
        if not isinstance(value, str) or not _REVISION.fullmatch(value):
            raise JudgeReceiptCommandError(
                f"Deployment receipt {name} is invalid"
            )
    if receipt["operator_revision"] == receipt["judge_revision"]:
        raise JudgeReceiptCommandError(
            "Operator and judge must have separate Cloud Run revisions"
        )
    if (
        receipt.get("traffic_migration_performed") is not False
        or receipt.get("live_model_call_performed") is not False
        or receipt.get("external_business_action_performed") is not False
    ):
        raise JudgeReceiptCommandError(
            "Deployment receipt has unsafe or ambiguous action flags"
        )
    _timestamp(receipt.get("captured_at"), "deployment captured_at")


def _validate_runtime_receipt(
    receipt: dict[str, Any],
    *,
    authorization: dict[str, Any],
    deployment: dict[str, Any],
    ci_receipt: dict[str, Any],
    release_revision: str,
) -> None:
    if receipt.get("schema_version") != _RUNTIME_SCHEMA:
        raise JudgeReceiptCommandError("Runtime receipt schema is invalid")
    exact_fields = {
        "environment": "staging",
        "business_identity": "RegenExcalibur",
        "repository": "Lornt1666/AIGC",
        "release_revision": release_revision,
        "image_digest": deployment["image_digest"],
        "cloud_run_revision": deployment["operator_revision"],
        "provider": "google_vertex_ai",
        "model": authorization["gemini_model"],
        "location": authorization["cloud"]["vertex_location"],
        "model_api_call_status": "confirmed",
        "model_api_call_performed": True,
        "external_business_action_performed": False,
    }
    for name, expected in exact_fields.items():
        if receipt.get(name) != expected:
            raise JudgeReceiptCommandError(
                f"Runtime receipt does not match {name}"
            )
    run_id = receipt.get("workflow_run_id")
    if not isinstance(run_id, str) or not _WORKFLOW_RUN.fullmatch(run_id):
        raise JudgeReceiptCommandError(
            "Runtime receipt workflow_run_id is invalid"
        )
    for name in (
        "input_sha256",
        "assessment_sha256",
        "idempotency_key_sha256",
    ):
        value = receipt.get(name)
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise JudgeReceiptCommandError(
                f"Runtime receipt {name} is invalid"
            )
    if not isinstance(receipt.get("response_id_present"), bool):
        raise JudgeReceiptCommandError(
            "Runtime receipt must record response ID presence"
        )
    latency_ms = receipt.get("latency_ms")
    if (
        isinstance(latency_ms, bool)
        or not isinstance(latency_ms, int)
        or latency_ms < 0
    ):
        raise JudgeReceiptCommandError(
            "Runtime receipt latency_ms is invalid"
        )
    usage = _mapping(receipt, "usage")
    for name in ("prompt_tokens", "candidate_tokens", "total_tokens"):
        value = usage.get(name)
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise JudgeReceiptCommandError(
                f"Runtime receipt usage.{name} is invalid"
            )
    evidence = _mapping(receipt, "evidence")
    object_uri = evidence.get("object_uri")
    expected_prefix = (
        f"gs://{authorization['cloud']['evidence_bucket']}/"
        "product-evidence/gemini/"
    )
    if (
        not isinstance(object_uri, str)
        or not object_uri.startswith(expected_prefix)
        or "?" in object_uri
        or "#" in object_uri
    ):
        raise JudgeReceiptCommandError(
            "Runtime evidence object URI is outside the authorized prefix"
        )
    generation = evidence.get("generation")
    if (
        isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation <= 0
    ):
        raise JudgeReceiptCommandError(
            "Runtime evidence needs an exact positive GCS generation"
        )
    record_sha = evidence.get("record_sha256")
    if not isinstance(record_sha, str) or not _SHA256.fullmatch(record_sha):
        raise JudgeReceiptCommandError(
            "Runtime evidence record SHA-256 is invalid"
        )
    if canonical_sha256(receipt.get("ci")) != canonical_sha256(ci_receipt):
        raise JudgeReceiptCommandError(
            "Runtime receipt does not embed the exact supplied CI receipt"
        )
    _timestamp(receipt.get("captured_at"), "runtime captured_at")


def _validate_draft(draft: JudgeReceiptDraft) -> JudgeReceiptDraft:
    if not isinstance(draft, JudgeReceiptDraft):
        raise JudgeReceiptCommandError("A validated judge draft is required")
    try:
        return JudgeReceiptDraft.model_validate(
            draft.model_dump(mode="python")
        )
    except ValidationError as exc:
        raise JudgeReceiptCommandError(
            "Judge receipt draft failed integrity validation"
        ) from exc


def _mapping(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise JudgeReceiptCommandError(f"{name} must be a JSON object")
    return value


def _required_text(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise JudgeReceiptCommandError(f"{name} is required")
    return value.strip()


def _timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise JudgeReceiptCommandError(f"{name} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise JudgeReceiptCommandError(f"{name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise JudgeReceiptCommandError(f"{name} needs a timezone")
    return parsed.astimezone(timezone.utc)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JudgeReceiptCommandError(
            f"{path.name} is not readable JSON"
        ) from exc
    if not isinstance(value, dict):
        raise JudgeReceiptCommandError(
            f"{path.name} must contain a JSON object"
        )
    return value


def _load_draft(path: Path) -> JudgeReceiptDraft:
    try:
        return JudgeReceiptDraft.model_validate(_load_object(path))
    except ValidationError as exc:
        raise JudgeReceiptCommandError(
            "Judge receipt draft is invalid or has been modified"
        ) from exc


def _write_json_create_only(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except FileExistsError as exc:
        raise JudgeReceiptCommandError(
            f"Refusing to overwrite existing receipt file: {path}"
        ) from exc


def _ensure_create_only_target(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise JudgeReceiptCommandError(
            f"Publication receipt directory is not writable: {path.parent}"
        ) from exc
    if path.exists():
        raise JudgeReceiptCommandError(
            f"Refusing to overwrite existing receipt file: {path}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a local evidence-bound judge receipt by default; "
            "publish only with an explicit reviewed draft and confirmation."
        )
    )
    parser.add_argument("authorization", type=Path)
    parser.add_argument("deployment_receipt", type=Path)
    parser.add_argument("ci_receipt", type=Path)
    parser.add_argument("runtime_receipt", type=Path)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Create the sanitized receipt and index in authorized GCS.",
    )
    parser.add_argument(
        "--draft",
        type=Path,
        help="Previously prepared draft; required with --publish.",
    )
    parser.add_argument(
        "--confirmation-phrase",
        help="Exact content-bound phrase printed by prepare mode.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Create-only local draft or publication receipt path.",
    )
    args = parser.parse_args()

    authorization = _load_object(args.authorization)
    deployment = _load_object(args.deployment_receipt)
    ci_receipt = _load_object(args.ci_receipt)
    runtime_receipt = _load_object(args.runtime_receipt)
    if not args.publish:
        if args.draft is not None or args.confirmation_phrase is not None:
            parser.error(
                "--draft and --confirmation-phrase are publication-only"
            )
        output = args.output or Path(
            "reports/artifacts/gemini_staging/judge-receipt-draft.json"
        )
        draft = prepare_judge_receipt(
            authorization=authorization,
            deployment=deployment,
            ci_receipt=ci_receipt,
            runtime_receipt=runtime_receipt,
            output=output,
        )
        print(
            json.dumps(
                {
                    "mode": "prepare_only",
                    "draft_path": str(output),
                    "draft_sha256": draft.draft_sha256,
                    "required_publication_phrase": (
                        required_publication_phrase(draft)
                    ),
                    "gcs_objects_created": 0,
                    "external_business_action_performed": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.draft is None or args.confirmation_phrase is None:
        parser.error(
            "--publish requires --draft and --confirmation-phrase"
        )
    output = args.output or Path(
        "reports/artifacts/gemini_staging/"
        "judge-receipt-publication.json"
    )
    result = publish_judge_receipt(
        authorization=authorization,
        deployment=deployment,
        ci_receipt=ci_receipt,
        runtime_receipt=runtime_receipt,
        draft=_load_draft(args.draft),
        confirmation_phrase=args.confirmation_phrase,
        output=output,
    )
    print(
        json.dumps(
            {
                "mode": "published",
                "publication_receipt_path": str(output),
                "receipt_id": result["published_receipt"]["receipt_id"],
                "object_uri": result["gcs_write_receipt"]["receipt"][
                    "object_uri"
                ],
                "generation": result["gcs_write_receipt"]["receipt"][
                    "generation"
                ],
                "model_api_call_performed_during_publication": False,
                "external_business_action_performed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except JudgeReceiptCommandError as exc:
        raise SystemExit(f"Judge receipt command blocked: {exc}") from exc
