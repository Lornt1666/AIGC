from src.core.omega_worker_connector_pilot import (
    ConnectorPilotError,
    PilotEvidence,
    ReadOnlyConnectorPilot,
    ReadOnlyPilotPolicy,
)
from src.core.omega_worker_connector_pilot_verification import (
    ConnectorEvidenceValidator,
    ConnectorPilotVerificationError,
    ConnectorPilotVerificationHarness,
    VerificationCase,
)


class Adapter:
    connector_id = "synthetic-readonly"

    def __init__(self, evidence=None):
        self.evidence = evidence or PilotEvidence(
            self.connector_id,
            "allowed/ref",
            "e-1",
            {"ok": True},
            "2099-01-01T00:00:00Z",
        )
        self.calls = 0

    def read(self, evidence_reference, credential):
        self.calls += 1
        return self.evidence


class IdentitySwapAdapter(Adapter):
    def read(self, evidence_reference, credential):
        result = super().read(evidence_reference, credential)
        return PilotEvidence("other-connector", result.evidence_reference, result.evidence_id, result.payload, result.observed_at)


def policy():
    return ReadOnlyPilotPolicy("pilot-1", "synthetic-readonly", ("allowed/ref",))


def harness():
    return ConnectorPilotVerificationHarness(
        ReadOnlyConnectorPilot(policy()),
        validator=ConnectorEvidenceValidator(observed_after="2026-01-01T00:00:00Z"),
    )


def test_happy_path_and_no_write_surface():
    adapter = Adapter()
    result = harness().read_and_validate(
        adapter, evidence_reference="allowed/ref", credential=object()
    )
    assert result.evidence_id == "e-1"
    assert adapter.calls == 1
    assert not any(name in dir(ReadOnlyConnectorPilot) for name in ("write", "authorize", "discover_target", "discover_credential"))


def test_revoked_or_missing_credential_fails_closed():
    case = VerificationCase("revoked-credential", "missing credential", ConnectorPilotError)
    result = harness().run_case(
        case,
        lambda: harness().read_and_validate(
            Adapter(), evidence_reference="allowed/ref", credential=None
        ),
    )
    assert result.passed


def test_unauthorized_reference_fails_closed():
    case = VerificationCase("unauthorized-reference", "reference outside allowlist", ConnectorPilotError)
    result = harness().run_case(
        case,
        lambda: harness().read_and_validate(
            Adapter(), evidence_reference="private/ref", credential=object()
        ),
    )
    assert result.passed


def test_provenance_substitution_fails_closed():
    case = VerificationCase("provenance-substitution", "connector identity swap", ConnectorPilotError)
    result = harness().run_case(
        case,
        lambda: harness().read_and_validate(
            IdentitySwapAdapter(), evidence_reference="allowed/ref", credential=object()
        ),
    )
    assert result.passed


def test_stale_evidence_is_rejected():
    stale = PilotEvidence(
        "synthetic-readonly", "allowed/ref", "stale-1", {"ok": True}, "2025-01-01T00:00:00Z"
    )
    case = VerificationCase("stale-evidence", "evidence predates cutoff", ConnectorPilotVerificationError)
    result = harness().run_case(
        case,
        lambda: harness().read_and_validate(
            Adapter(stale), evidence_reference="allowed/ref", credential=object()
        ),
    )
    assert result.passed


def test_malformed_payload_is_rejected():
    malformed = PilotEvidence(
        "synthetic-readonly", "allowed/ref", "malformed-1", {}, "2099-01-01T00:00:00Z"
    )
    case = VerificationCase("malformed-payload", "empty payload", ConnectorPilotVerificationError)
    result = harness().run_case(
        case,
        lambda: harness().read_and_validate(
            Adapter(malformed), evidence_reference="allowed/ref", credential=object()
        ),
    )
    assert result.passed


def test_malformed_timestamp_is_rejected():
    malformed = PilotEvidence(
        "synthetic-readonly", "allowed/ref", "malformed-time", {"ok": True}, "not-a-timestamp"
    )
    case = VerificationCase("malformed-timestamp", "invalid observation time", ConnectorPilotVerificationError)
    result = harness().run_case(
        case,
        lambda: harness().read_and_validate(
            Adapter(malformed), evidence_reference="allowed/ref", credential=object()
        ),
    )
    assert result.passed


def test_simulated_outage_and_replay_are_detected():
    class OutageAdapter(Adapter):
        def read(self, evidence_reference, credential):
            raise ConnectionError("synthetic outage")

    outage = VerificationCase("simulated-outage", "connector unavailable", ConnectionError)
    replay = VerificationCase("replay", "stale replayed evidence", ConnectorPilotVerificationError)
    stale = PilotEvidence(
        "synthetic-readonly", "allowed/ref", "replay-1", {"ok": True}, "2024-01-01T00:00:00Z"
    )
    results = harness().run_suite({
        "outage": (outage, lambda: harness().read_and_validate(
            OutageAdapter(), evidence_reference="allowed/ref", credential=object()
        )),
        "replay": (replay, lambda: harness().read_and_validate(
            Adapter(stale), evidence_reference="allowed/ref", credential=object()
        )),
    })
    assert {item.case_id for item in results} == {"simulated-outage", "replay"}


def test_authority_expansion_remains_rejected():
    for kwargs in (
        {"external_writes": True},
        {"financial_authority": True},
        {"autonomous_target_selection": True},
        {"credential_injection_required": False},
    ):
        try:
            ReadOnlyPilotPolicy("pilot-1", "synthetic-readonly", ("allowed/ref",), **kwargs)
        except ConnectorPilotError:
            continue
        assert False, f"unsafe policy accepted: {kwargs}"
