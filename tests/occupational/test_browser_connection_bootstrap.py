from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.occupational.browser_connection_bootstrap import (
    BrowserConnectionBootstrapController,
    BrowserConnectionProbe,
    BrowserConnectionState,
    GitHubActionsBudgetAuthorization,
    GitHubActionsBudgetObservation,
)


def _authorization() -> GitHubActionsBudgetAuthorization:
    return GitHubActionsBudgetAuthorization(
        authorization_reference="Lornt1666/AIGC#218",
        account="Lornt1666",
        maximum_additional_budget_usd=Decimal("12"),
        purpose="exact-head AIGC validation only",
        expires_on=date(2026, 9, 1),
    )


def _connected_controller() -> BrowserConnectionBootstrapController:
    controller = BrowserConnectionBootstrapController()
    controller.observe_connection(
        BrowserConnectionProbe(
            connector_available=True,
            user_permission_present=True,
            target_authenticated=True,
            target_account="Lornt1666",
        )
    )
    controller.mark_read_only_ready()
    return controller


def test_disconnected_probe_requires_manual_activation_and_does_not_loop() -> None:
    controller = BrowserConnectionBootstrapController()
    probe = BrowserConnectionProbe(
        connector_available=False,
        user_permission_present=False,
        error_code="BROWSER_NOT_CONNECTED",
    )

    controller.observe_connection(probe)
    assert controller.state is BrowserConnectionState.USER_PERMISSION_REQUIRED

    with pytest.raises(ValueError, match="probe locked"):
        controller.observe_connection(probe)

    controller.acknowledge_manual_activation()
    controller.observe_connection(
        BrowserConnectionProbe(
            connector_available=True,
            user_permission_present=True,
            target_authenticated=False,
        )
    )
    assert controller.state is BrowserConnectionState.CONNECTED_UNAUTHENTICATED


def test_user_claim_does_not_create_authenticated_connection() -> None:
    controller = BrowserConnectionBootstrapController()
    controller.acknowledge_manual_activation()
    assert controller.state is BrowserConnectionState.DISCONNECTED
    with pytest.raises(ValueError, match="authenticated browser state"):
        controller.mark_read_only_ready()


def test_wrong_account_fails_closed() -> None:
    controller = BrowserConnectionBootstrapController()
    controller.observe_connection(
        BrowserConnectionProbe(
            connector_available=True,
            user_permission_present=True,
            target_authenticated=True,
            target_account="OtherAccount",
        )
    )
    controller.mark_read_only_ready()

    with pytest.raises(ValueError, match="does not match authorization"):
        controller.bind_github_actions_budget(
            _authorization(),
            requested_budget_usd=Decimal("12"),
            observed_on=date(2026, 8, 14),
        )
    assert controller.state is BrowserConnectionState.BLOCKED


def test_budget_above_ceiling_is_rejected() -> None:
    controller = _connected_controller()
    with pytest.raises(ValueError, match="exceeds authorization"):
        controller.bind_github_actions_budget(
            _authorization(),
            requested_budget_usd=Decimal("12.01"),
            observed_on=date(2026, 8, 14),
        )


def test_expired_authorization_is_rejected() -> None:
    controller = _connected_controller()
    with pytest.raises(ValueError, match="expired"):
        controller.bind_github_actions_budget(
            _authorization(),
            requested_budget_usd=Decimal("12"),
            observed_on=date(2026, 9, 1),
        )


def test_ci_retry_requires_verified_persisted_state() -> None:
    controller = _connected_controller()
    controller.bind_github_actions_budget(
        _authorization(),
        requested_budget_usd=Decimal("12"),
        observed_on=date(2026, 8, 14),
    )
    assert not controller.ci_retry_eligible
    with pytest.raises(ValueError, match="not eligible"):
        controller.record_ci_attempt(31836992808)


def test_persisted_state_mismatch_blocks_ci() -> None:
    controller = _connected_controller()
    controller.bind_github_actions_budget(
        _authorization(),
        requested_budget_usd=Decimal("12"),
        observed_on=date(2026, 8, 14),
    )

    with pytest.raises(ValueError, match="does not match plan"):
        controller.verify_persisted_budget(
            GitHubActionsBudgetObservation(
                account="Lornt1666",
                persisted_budget_usd=Decimal("12"),
                stop_usage_at_budget=False,
            )
        )
    assert controller.state is BrowserConnectionState.BLOCKED
    assert not controller.ci_retry_eligible


def test_verified_budget_allows_exactly_one_ci_attempt() -> None:
    controller = _connected_controller()
    plan = controller.bind_github_actions_budget(
        _authorization(),
        requested_budget_usd=Decimal("12"),
        observed_on=date(2026, 8, 14),
    )
    assert len(plan.action_digest) == 64

    controller.verify_persisted_budget(
        GitHubActionsBudgetObservation(
            account="Lornt1666",
            persisted_budget_usd=Decimal("12"),
            stop_usage_at_budget=True,
        )
    )
    assert controller.ci_retry_eligible

    receipt = controller.receipt(receipt_id="BCR_AIGC_001")
    assert receipt.persisted_state_verified
    assert receipt.ci_retry_eligible
    assert receipt.external_action_performed

    controller.record_ci_attempt(31836992809)
    assert controller.state is BrowserConnectionState.CI_ATTEMPTED
    assert not controller.ci_retry_eligible

    with pytest.raises(ValueError, match="not eligible"):
        controller.record_ci_attempt(31836992810)
