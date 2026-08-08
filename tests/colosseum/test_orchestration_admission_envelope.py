from dataclasses import replace

import pytest

from scripts.validate_governed_orchestration_bundle import (
    build_admission_fixture,
)
from src.colosseum.admission import OrchestrationAdmissionEnvelope
from src.colosseum.orchestration import canonical_sha256


def test_admission_envelope_round_trip_is_lossless() -> None:
    envelope = build_admission_fixture()
    record = envelope.to_record()
    assert OrchestrationAdmissionEnvelope.from_record(record).to_record() == record


def test_unauthorized_work_order_is_rejected() -> None:
    envelope = build_admission_fixture()
    with pytest.raises(ValueError, match="authorized WorkOrder"):
        replace(
            envelope,
            work_order=replace(envelope.work_order, authorized=False),
        )


def test_missing_work_order_obligation_is_rejected() -> None:
    envelope = build_admission_fixture()
    expanded = replace(
        envelope.work_order,
        requirement_ids=(
            *envelope.work_order.requirement_ids,
            "requirement-not-covered",
        ),
    )
    with pytest.raises(ValueError, match="every WorkOrder obligation"):
        replace(envelope, work_order=expanded)


def test_engagement_mismatch_is_rejected() -> None:
    envelope = build_admission_fixture()
    with pytest.raises(ValueError, match="engagements differ"):
        replace(
            envelope,
            work_order=replace(
                envelope.work_order,
                engagement_id="different-engagement",
            ),
        )


def test_authority_tampering_is_rejected_even_with_recomputed_digest() -> None:
    envelope = build_admission_fixture()
    record = envelope.to_record()
    record["authority"] = dict(record["authority"])
    record["authority"]["execution_authorized"] = True
    unsigned = dict(record)
    unsigned.pop("record_sha256")
    record["record_sha256"] = canonical_sha256(unsigned)
    with pytest.raises(ValueError, match="prohibited authority"):
        OrchestrationAdmissionEnvelope.from_record(record)
