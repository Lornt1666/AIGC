from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.core.epistemic.canonicalization import canonical_sha256
from src.core.nexus.employment_ops_policy import assess_employment_action
from src.domain.nexus.employment_ops import (
    EmploymentOpsCapabilityProfile,
    EmploymentOpsReadiness,
    NegotiationAuthorityEnvelope,
    NegotiationDimension,
)


def test_hyperalpha_capability_profile_enforces_requested_true_flags():
    profile = EmploymentOpsCapabilityProfile(profile_id="EOPS-HYPERALPHA_V1")
    assert profile.hyperalpha_employment_ops is True
    assert profile.automatic_call_answering is True
    assert profile.automatic_speech_to_caller is True
    assert profile.automatic_negotiation is True
    assert profile.real_time_stt is True
    assert profile.real_time_tts is True
    assert profile.self_authorization is False
    assert profile.model_consensus_as_authority is False


def test_safe_reasoning_and_preparation_actions_remain_autonomous():
    result = assess_employment_action(action="FIT_SCORING", subject_ref="JOB-123456")
    assert result.disposition == "AUTONOMOUS_POLICY_PATH"
    assert result.material_consequence is False


def test_external_submission_requires_authority():
    result = assess_employment_action(action="SUBMIT_APPLICATION", subject_ref="APP-123456")
    assert result.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY"
    assert result.material_consequence is True


def test_telephony_speech_requires_authority_without_standing_permit():
    result = assess_employment_action(action="SPEAK_TO_CALLER", subject_ref="CALL-123456")
    assert result.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY"
    assert result.consequence_class == "COMMUNICATION"


def test_telephony_speech_can_run_inside_existing_bounded_authority():
    result = assess_employment_action(
        action="SPEAK_TO_CALLER",
        subject_ref="CALL-123456",
        existing_permit_id="PERMIT-CALL_123456",
    )
    assert result.disposition == "AUTONOMOUS_WITHIN_EXISTING_AUTHORITY"


def test_negotiation_bounds_are_ordered():
    dimension = NegotiationDimension(
        name="salary",
        unit="CAD/year",
        minimum=Decimal("70000"),
        target=Decimal("85000"),
        stretch=Decimal("95000"),
        maximum=Decimal("105000"),
    )
    envelope = NegotiationAuthorityEnvelope(envelope_id="NEG-SALARY_123456", dimensions=(dimension,))
    assert envelope.may_accept_binding_offer is False


def test_operational_activation_requires_empirical_evidence():
    profile = EmploymentOpsCapabilityProfile(profile_id="EOPS-HYPERALPHA_V1")
    with pytest.raises(ValidationError):
        EmploymentOpsReadiness(
            capability_profile_hash=canonical_sha256(profile),
            operationally_active=True,
        )
