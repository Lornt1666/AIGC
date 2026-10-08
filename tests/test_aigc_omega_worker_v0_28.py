from dataclasses import dataclass

import pytest

from src.core.omega_worker_connector_admission import (
    ConnectorAdmissionError,
    ReadOnlyAdmissionPolicy,
    ReadOnlyConnectorAdmission,
)
from src.core.omega_worker_connector_pilot import PilotEvidence


@dataclass
class Adapter:
    connector_id: str = "sandbox.connector"

    def read(self, evidence_reference: str, credential: object) -> PilotEvidence:
        assert credential == "explicit-test-credential"
        return PilotEvidence(
            connector_id=self.connector_id,
            evidence_reference=evidence_reference,
            evidence_id="evidence-001",
            payload={"status": "ok"},
            observed_at="2026-10-07T00:00:00Z",
        )


def policy() -> ReadOnlyAdmissionPolicy:
    return ReadOnlyAdmissionPolicy(
        policy_id="policy-028",
        connector_id="sandbox.connector",
    )


def test_explicit_credential_and_allowlisted_reference_are_admitted() -> None:
    admission = ReadOnlyConnectorAdmission(
        policy(),
        allowed_references=("sandbox://fixture/001",),
    )
    evidence, receipt = admission.admit(
        Adapter(),
        evidence_reference="sandbox://fixture/001",
        credential="explicit-test-credential",
    )
    assert evidence.evidence_id == "evidence-001"
    assert receipt.admitted is True
    assert receipt.connector_id == "sandbox.connector"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"external_writes": True},
        {"financial_authority": True},
        {"credential_discovery": True},
        {"target_discovery": True},
        {"permission_inference": True},
        {"sandbox_only": False},
    ],
)
def test_authority_expansion_is_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ConnectorAdmissionError):
        ReadOnlyAdmissionPolicy(
            policy_id="policy-028",
            connector_id="sandbox.connector",
            **kwargs,
        )


def test_missing_credential_fails_closed() -> None:
    admission = ReadOnlyConnectorAdmission(
        policy(),
        allowed_references=("sandbox://fixture/001",),
    )
    with pytest.raises(ConnectorAdmissionError):
        admission.admit(
            Adapter(),
            evidence_reference="sandbox://fixture/001",
            credential=None,
        )


def test_unknown_reference_fails_closed() -> None:
    admission = ReadOnlyConnectorAdmission(
        policy(),
        allowed_references=("sandbox://fixture/001",),
    )
    with pytest.raises(ConnectorAdmissionError):
        admission.admit(
            Adapter(),
            evidence_reference="sandbox://fixture/999",
            credential="explicit-test-credential",
        )


def test_connector_identity_swap_fails_closed() -> None:
    admission = ReadOnlyConnectorAdmission(
        policy(),
        allowed_references=("sandbox://fixture/001",),
    )
    with pytest.raises(ConnectorAdmissionError):
        admission.admit(
            Adapter(connector_id="unadmitted.connector"),
            evidence_reference="sandbox://fixture/001",
            credential="explicit-test-credential",
        )


def test_provenance_substitution_fails_closed() -> None:
    class SubstitutionAdapter(Adapter):
        def read(self, evidence_reference: str, credential: object) -> PilotEvidence:
            return PilotEvidence(
                connector_id=self.connector_id,
                evidence_reference="sandbox://fixture/substituted",
                evidence_id="evidence-002",
                payload={"status": "ok"},
                observed_at="2026-10-07T00:00:00Z",
            )

    admission = ReadOnlyConnectorAdmission(
        policy(),
        allowed_references=("sandbox://fixture/001",),
    )
    with pytest.raises(ConnectorAdmissionError):
        admission.admit(
            SubstitutionAdapter(),
            evidence_reference="sandbox://fixture/001",
            credential="explicit-test-credential",
        )
