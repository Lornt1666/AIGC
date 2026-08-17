from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from jsonschema import Draft202012Validator, FormatChecker
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validate_colosseum_persistence import build_fixture
from src.colosseum.admission import OrchestrationAdmissionEnvelope
from src.colosseum.domain import (
    CapabilityEvidence,
    CapabilityVerdict,
    WorkOrder,
)
from src.colosseum.governed_bundle import GovernedOrchestrationBundle


NOW = datetime(2026, 8, 7, tzinfo=timezone.utc)


def build_work_order() -> WorkOrder:
    return WorkOrder(
        "work-validation",
        "engagement-validation",
        "Produce a synthetic validated artifact",
        ("requirement-validation",),
        ("acceptance-validation",),
        True,
    )


def build_governed_fixture() -> GovernedOrchestrationBundle:
    effective, definition, dag, plan = build_fixture()
    capability_evidence = (
        CapabilityEvidence(
            "cap-coding",
            "software",
            "coding",
            CapabilityVerdict.VERIFIED_CAPABLE,
            ("benchmark-coding",),
            ("deliverable-coding",),
            2,
            2,
            False,
            ("evidence://coding",),
            NOW,
        ),
        CapabilityEvidence(
            "cap-verification",
            "quality",
            "verification",
            CapabilityVerdict.VERIFIED_CAPABLE,
            ("benchmark-verification",),
            ("deliverable-verification",),
            2,
            2,
            False,
            ("evidence://verification",),
            NOW,
        ),
    )
    return GovernedOrchestrationBundle(
        as_of=NOW,
        effective_policy=effective,
        definitions_of_done=(definition,),
        task_dag=dag,
        swarm_plan=plan,
        capability_evidence=capability_evidence,
    )


def build_admission_fixture() -> OrchestrationAdmissionEnvelope:
    return OrchestrationAdmissionEnvelope(
        work_order=build_work_order(),
        governed_bundle=build_governed_fixture(),
    )


def validate_record(
    root: Path,
    schema_path: str,
    record: dict[str, object],
) -> None:
    schema = json.loads((root / schema_path).read_text(encoding="utf-8"))
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(record)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("schema", "roundtrip", "all"),
        default="all",
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()

    bundle = build_governed_fixture()
    bundle_record = bundle.to_record()
    envelope = build_admission_fixture()
    envelope_record = envelope.to_record()
    result: dict[str, object] = {
        "schema_version": "1.0.0",
        "mode": args.mode,
        "external_action_performed": False,
        "production_activation_authorized": False,
    }
    if args.mode in {"schema", "all"}:
        validate_record(
            args.project_root,
            "schemas/colosseum/governed_orchestration_bundle.schema.json",
            bundle_record,
        )
        validate_record(
            args.project_root,
            "schemas/colosseum/orchestration_admission_envelope.schema.json",
            envelope_record,
        )
        result["schema_validation"] = "PASS"
    if args.mode in {"roundtrip", "all"}:
        reconstructed_bundle = GovernedOrchestrationBundle.from_record(
            bundle_record
        )
        if reconstructed_bundle.to_record() != bundle_record:
            raise SystemExit("governed orchestration round trip lost information")
        reconstructed_envelope = OrchestrationAdmissionEnvelope.from_record(
            envelope_record
        )
        if reconstructed_envelope.to_record() != envelope_record:
            raise SystemExit("admission envelope round trip lost information")
        result["round_trip_validation"] = "PASS"
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
