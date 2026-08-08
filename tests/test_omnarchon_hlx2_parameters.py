from __future__ import annotations

from copy import deepcopy

import pytest

from src.core.omnarchon_hlx2_parameters import (
    OmnarchonParametersError,
    build_receipt,
    load_parameters,
    validate_parameters,
)


def test_parameters_validate_and_preserve_authority() -> None:
    parameters = load_parameters()
    safety = parameters["safety_and_authority"]

    assert parameters["architecture"]["name"] == "OMNARCHON-OMEGA-X"
    assert parameters["architecture"]["execution_kernel"] == "HLX2"
    assert parameters["epistemic_governance"]["omniscient_scale_approximation"] is True
    assert parameters["epistemic_governance"]["literal_omniscience_claim_allowed"] is False
    assert parameters["metatranscended_archetype_engine"]["enabled"] is True
    assert safety["operator_review_required"] is True
    assert safety["automatic_merge_allowed"] is False
    assert safety["automatic_external_commitment_allowed"] is False
    assert safety["terraform_apply_allowed"] is False
    assert safety["external_action_performed"] is False


def test_receipt_is_deterministic_and_non_authorizing() -> None:
    parameters = load_parameters()

    first = build_receipt(parameters)
    second = build_receipt(parameters)

    assert first == second
    assert first["architecture"] == "OMNARCHON-OMEGA-X"
    assert first["execution_kernel"] == "HLX2"
    assert first["operator_review_required"] is True
    assert first["automatic_merge_allowed"] is False
    assert first["automatic_external_commitment_allowed"] is False
    assert first["external_action_performed"] is False


def test_self_approval_cannot_be_enabled() -> None:
    parameters = load_parameters()
    changed = deepcopy(parameters)
    changed["safety_and_authority"]["automation_can_self_approve"] = True

    with pytest.raises(OmnarchonParametersError):
        validate_parameters(changed, _schema())


def test_literal_omniscience_cannot_be_claimed() -> None:
    parameters = load_parameters()
    changed = deepcopy(parameters)
    changed["epistemic_governance"]["literal_omniscience_claim_allowed"] = True

    with pytest.raises(OmnarchonParametersError):
        validate_parameters(changed, _schema())


def test_archetypes_must_change_operational_design() -> None:
    parameters = load_parameters()
    changed = deepcopy(parameters)
    changed["metatranscended_archetype_engine"]["decorative_archetypes_allowed"] = True

    with pytest.raises(OmnarchonParametersError):
        validate_parameters(changed, _schema())


def test_protected_aigc_authority_cannot_be_removed() -> None:
    parameters = load_parameters()
    changed = deepcopy(parameters)
    changed["aigc_binding"]["must_not_replace"].remove("hosted_ci_evidence")

    with pytest.raises(OmnarchonParametersError, match="not protected"):
        validate_parameters(changed, _schema())


def _schema() -> dict:
    import json
    from src.core.omnarchon_hlx2_parameters import DEFAULT_SCHEMA_PATH

    return json.loads(DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8"))
