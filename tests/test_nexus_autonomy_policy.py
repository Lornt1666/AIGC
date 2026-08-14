from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.core.nexus.autonomy_policy import assess_autonomy
from src.domain.nexus.autonomy import ActionIntent


def intent(**overrides):
    payload = {
        "intent_id": "ACT-AUTONOMY01",
        "effect_class": "PURE",
    }
    payload.update(overrides)
    return ActionIntent(**payload)


def test_pure_reasoning_uses_autonomous_policy_path():
    result = assess_autonomy(intent())
    assert result.disposition == "AUTONOMOUS_POLICY_PATH"
    assert result.authority_requirement == "POLICY"
    assert result.material_consequence is False
    assert result.execution_may_continue_without_new_authority is True
    assert result.authority_granted is False
    assert result.external_action_performed is False


def test_local_observation_is_autonomous():
    result = assess_autonomy(intent(effect_class="READ_LOCAL"))
    assert result.consequence_class == "OBSERVATIONAL"
    assert result.disposition == "AUTONOMOUS_POLICY_PATH"


def test_public_zero_cost_external_read_is_autonomous_policy_path():
    result = assess_autonomy(
        intent(effect_class="READ_EXTERNAL", public_read_only=True)
    )
    assert result.consequence_class == "EXTERNAL_READ"
    assert result.material_consequence is False
    assert "PUBLIC_READ_POLICY_PATH" in result.reason_codes


def test_reversible_internal_sandbox_is_autonomous():
    result = assess_autonomy(
        intent(effect_class="WRITE_REVERSIBLE", internal_sandbox_only=True)
    )
    assert result.consequence_class == "REVERSIBLE_INTERNAL"
    assert result.disposition == "AUTONOMOUS_POLICY_PATH"


@pytest.mark.parametrize(
    ("kwargs", "expected_class"),
    [
        ({"persistent_internal_mutation": True}, "PERSISTENT_INTERNAL"),
        ({"effect_class": "WRITE_REVERSIBLE", "external_mutation": True}, "EXTERNAL_MUTATION"),
        ({"effect_class": "COMMUNICATION"}, "COMMUNICATION"),
        ({"effect_class": "FINANCIAL", "financial_spend_cad": Decimal("1.00")}, "FINANCIAL"),
        ({"legal_commitment": True}, "LEGAL"),
        ({"effect_class": "SECURITY_SENSITIVE"}, "SECURITY_SENSITIVE"),
        ({"effect_class": "DEPLOYMENT"}, "PRODUCTION"),
        ({"physical_effect": True}, "PHYSICAL"),
        ({"destructive": True}, "DESTRUCTIVE"),
        ({"effect_class": "WRITE_IRREVERSIBLE"}, "IRREVERSIBLE"),
    ],
)
def test_material_consequence_requires_explicit_authority(kwargs, expected_class):
    result = assess_autonomy(intent(**kwargs))
    assert result.consequence_class == expected_class
    assert result.material_consequence is True
    assert result.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY"
    assert result.authority_requirement == "EXPLICIT"
    assert result.execution_may_continue_without_new_authority is False
    assert result.reasoning_may_continue is True
    assert result.preparation_may_continue is True


def test_existing_explicit_authority_allows_autonomous_continuation_inside_envelope():
    result = assess_autonomy(
        intent(
            effect_class="COMMUNICATION",
            existing_explicit_authority=True,
            permit_id="PERMIT-AUTONOMY01",
        )
    )
    assert result.disposition == "AUTONOMOUS_WITHIN_EXISTING_AUTHORITY"
    assert result.authority_requirement == "EXISTING_EXPLICIT"
    assert result.execution_may_continue_without_new_authority is True


def test_private_external_read_requires_explicit_authority():
    result = assess_autonomy(
        intent(
            effect_class="READ_EXTERNAL",
            public_read_only=True,
            accesses_private_data=True,
        )
    )
    assert result.material_consequence is True
    assert result.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY"
    assert "PRIVATE_DATA_ACCESS" in result.reason_codes


def test_credentialed_external_read_requires_explicit_authority():
    result = assess_autonomy(
        intent(
            effect_class="READ_EXTERNAL",
            public_read_only=True,
            credentials_required=True,
        )
    )
    assert result.material_consequence is True
    assert "CREDENTIAL_USE" in result.reason_codes


def test_authorized_spend_envelope_is_enforced_even_when_authority_exists():
    result = assess_autonomy(
        intent(
            effect_class="FINANCIAL",
            financial_spend_cad=Decimal("5.01"),
            authorized_spend_cad=Decimal("5.00"),
            existing_explicit_authority=True,
            permit_id="PERMIT-AUTONOMY02",
        )
    )
    assert result.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY"
    assert "AUTHORIZED_SPEND_ENVELOPE_EXCEEDED" in result.reason_codes


def test_indeterminate_outcome_requires_read_only_reconciliation_and_no_retry():
    result = assess_autonomy(
        intent(effect_class="READ_EXTERNAL", outcome_indeterminate=True)
    )
    assert result.consequence_class == "INDETERMINATE"
    assert result.disposition == "READ_ONLY_RECONCILIATION"
    assert result.authority_requirement == "RECONCILIATION"
    assert result.automatic_retry_allowed is False
    assert result.reasoning_may_continue is True


def test_assessment_identity_is_deterministic():
    item = intent(effect_class="READ_EXTERNAL", public_read_only=True)
    assert assess_autonomy(item).assessment_id == assess_autonomy(item).assessment_id


def test_existing_authority_requires_a_permit_reference():
    with pytest.raises(ValidationError):
        intent(existing_explicit_authority=True)


def test_permit_reference_cannot_claim_unvalidated_authority():
    with pytest.raises(ValidationError):
        intent(permit_id="PERMIT-AUTONOMY03")


def test_public_read_flag_is_only_valid_for_external_reads():
    with pytest.raises(ValidationError):
        intent(effect_class="PURE", public_read_only=True)


def test_internal_sandbox_cannot_relabel_deployment_as_safe():
    with pytest.raises(ValidationError):
        intent(effect_class="DEPLOYMENT", internal_sandbox_only=True)
