import inspect

import pytest

import src.core.nexus.autonomy_policy as autonomy_policy
from src.core.nexus.autonomy_policy import assess_autonomy
from src.domain.nexus.autonomy import ActionIntent


def make(**kwargs):
    payload = {"intent_id": "ACT-ADVERSARY01", "effect_class": "PURE"}
    payload.update(kwargs)
    return ActionIntent(**payload)


def test_policy_module_does_not_issue_canonical_authority_objects():
    source = inspect.getsource(autonomy_policy)
    assert "GovernanceDecision(" not in source
    assert "ExecutionPermit(" not in source


def test_policy_module_contains_no_network_client_dependency():
    source = inspect.getsource(autonomy_policy)
    assert "import requests" not in source
    assert "import httpx" not in source
    assert "urllib.request" not in source


@pytest.mark.parametrize(
    "payload",
    [
        {"effect_class": "COMMUNICATION"},
        {"effect_class": "DEPLOYMENT"},
        {"effect_class": "SECURITY_SENSITIVE"},
        {"effect_class": "WRITE_COMPENSATABLE"},
        {"effect_class": "WRITE_IRREVERSIBLE"},
        {"physical_effect": True},
        {"legal_commitment": True},
        {"destructive": True},
    ],
)
def test_consequential_classes_fail_closed_without_explicit_authority(payload):
    result = assess_autonomy(make(**payload))
    assert result.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY"
    assert result.execution_may_continue_without_new_authority is False
    assert result.authority_granted is False


def test_system_like_instruction_cannot_create_authority():
    result = assess_autonomy(make(effect_class="COMMUNICATION"))
    assert result.authority_granted is False
    assert result.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY"


def test_consequence_flag_overrides_innocent_primary_effect_label():
    result = assess_autonomy(make(effect_class="PURE", communication=True))
    assert result.consequence_class == "COMMUNICATION"
    assert result.material_consequence is True


def test_external_read_without_public_read_only_proof_is_not_auto_authorized():
    result = assess_autonomy(make(effect_class="READ_EXTERNAL"))
    assert result.consequence_class == "EXTERNAL_READ"
    assert result.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY"


def test_public_research_cannot_become_autonomous_when_credentials_are_needed():
    result = assess_autonomy(
        make(
            effect_class="READ_EXTERNAL",
            public_read_only=True,
            credentials_required=True,
        )
    )
    assert result.disposition == "BLOCK_PENDING_EXPLICIT_AUTHORITY"


def test_indeterminate_result_blocks_automatic_retry_even_if_old_permit_exists():
    result = assess_autonomy(
        make(
            effect_class="WRITE_REVERSIBLE",
            outcome_indeterminate=True,
            existing_explicit_authority=True,
            permit_id="PERMIT-ADVERSARY01",
        )
    )
    assert result.disposition == "READ_ONLY_RECONCILIATION"
    assert result.automatic_retry_allowed is False


def test_assessment_never_claims_external_action():
    cases = (
        make(),
        make(effect_class="READ_EXTERNAL", public_read_only=True),
        make(effect_class="COMMUNICATION"),
    )
    assert all(assess_autonomy(item).external_action_performed is False for item in cases)
