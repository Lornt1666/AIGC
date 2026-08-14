from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.core.nexus.employment_ops_policy import assess_employment_action
from src.domain.nexus.employment_ops import (
    EmploymentOpsCapabilityProfile,
    NegotiationAuthorityEnvelope,
    NegotiationDimension,
)


def test_requested_capability_cannot_be_silently_disabled():
    with pytest.raises(ValidationError):
        EmploymentOpsCapabilityProfile(
            profile_id="EOPS-HYPERALPHA_V1",
            automatic_call_answering=False,
        )


def test_self_authorization_cannot_be_enabled():
    with pytest.raises(ValidationError):
        EmploymentOpsCapabilityProfile(
            profile_id="EOPS-HYPERALPHA_V1",
            self_authorization=True,
        )


def test_sensitive_identity_disclosure_is_security_sensitive_and_blocked():
    result = assess_employment_action(
        action="DISCLOSE_SENSITIVE_IDENTITY",
        subject_ref="APP-123456",
    )
    assert result.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY"
    assert "PRIVATE_DATA_ACCESS" in result.reason_codes


def test_claimed_cost_beyond_authorized_envelope_does_not_execute():
    result = assess_employment_action(
        action="NEGOTIATE",
        subject_ref="CALL-123456",
        existing_permit_id="PERMIT-CALL_123456",
        requested_cost_cad=Decimal("2.00"),
        authorized_cost_cad=Decimal("1.00"),
    )
    assert result.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY"


def test_negotiation_dimension_rejects_inverted_bounds():
    with pytest.raises(ValidationError):
        NegotiationDimension(
            name="salary",
            unit="CAD/year",
            minimum=Decimal("90000"),
            target=Decimal("85000"),
            stretch=Decimal("95000"),
            maximum=Decimal("105000"),
        )


def test_negotiation_envelope_rejects_duplicate_dimensions():
    d1 = NegotiationDimension(name="salary", unit="CAD/year", minimum=1, target=2, stretch=3, maximum=4)
    d2 = NegotiationDimension(name="Salary", unit="CAD/year", minimum=1, target=2, stretch=3, maximum=4)
    with pytest.raises(ValidationError):
        NegotiationAuthorityEnvelope(envelope_id="NEG-DUPLICATE_123", dimensions=(d1, d2))
