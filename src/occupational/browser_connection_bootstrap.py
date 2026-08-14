from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _canonical_sha256(value: BaseModel | dict[str, Any]) -> str:
    payload = (
        value.model_dump(mode="json", exclude_none=False)
        if isinstance(value, BaseModel)
        else value
    )
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class BrowserConnectionState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    USER_PERMISSION_REQUIRED = "USER_PERMISSION_REQUIRED"
    CONNECTED_UNAUTHENTICATED = "CONNECTED_UNAUTHENTICATED"
    CONNECTED_AUTHENTICATED = "CONNECTED_AUTHENTICATED"
    READY_READ_ONLY = "READY_READ_ONLY"
    ACTION_BOUND = "ACTION_BOUND"
    BOUNDED_WRITE_VERIFIED = "BOUNDED_WRITE_VERIFIED"
    CI_ATTEMPTED = "CI_ATTEMPTED"
    BLOCKED = "BLOCKED"
    REVOKED = "REVOKED"


class BrowserConnectionProbe(BaseModel):
    """Observed connector state. A user assertion alone is not a connection receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connector_available: bool
    user_permission_present: bool
    target_authenticated: bool = False
    target_account: str | None = Field(default=None, max_length=200)
    error_code: str | None = Field(default=None, max_length=200)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_authentication_evidence(self) -> "BrowserConnectionProbe":
        if self.target_authenticated and not (
            self.connector_available and self.user_permission_present
        ):
            raise ValueError("authenticated target requires a live permitted connector")
        if self.target_authenticated and not self.target_account:
            raise ValueError("authenticated target requires an observed account")
        return self


class GitHubActionsBudgetAuthorization(BaseModel):
    """Exact bounded authority for one GitHub Actions budget remediation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authorization_reference: str = Field(min_length=1, max_length=500)
    account: str = Field(min_length=1, max_length=200)
    product: Literal["GitHub Actions"] = "GitHub Actions"
    currency: Literal["USD"] = "USD"
    maximum_additional_budget_usd: Decimal = Field(ge=Decimal("0"))
    stop_usage_at_budget_required: Literal[True] = True
    purpose: str = Field(min_length=1, max_length=500)
    expires_on: date
    payment_method_change_allowed: Literal[False] = False
    maximum_ci_attempts_after_verified_remediation: int = Field(default=1, ge=0, le=1)

    def validate_action(
        self,
        *,
        account: str,
        requested_budget_usd: Decimal,
        stop_usage_at_budget: bool,
        purpose: str,
        observed_on: date,
    ) -> None:
        if observed_on >= self.expires_on:
            raise ValueError("budget authorization is expired")
        if account != self.account:
            raise ValueError("target account does not match authorization")
        if requested_budget_usd > self.maximum_additional_budget_usd:
            raise ValueError("requested budget exceeds authorization")
        if requested_budget_usd < Decimal("0"):
            raise ValueError("requested budget cannot be negative")
        if stop_usage_at_budget is not True:
            raise ValueError("Stop usage at budget must be enabled")
        if purpose != self.purpose:
            raise ValueError("action purpose does not match authorization")


class GitHubActionsBudgetPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authorization_reference: str
    account: str
    product: Literal["GitHub Actions"] = "GitHub Actions"
    currency: Literal["USD"] = "USD"
    requested_budget_usd: Decimal
    stop_usage_at_budget: Literal[True]
    purpose: str
    expires_on: date
    action_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @classmethod
    def create(
        cls,
        authorization: GitHubActionsBudgetAuthorization,
        *,
        requested_budget_usd: Decimal,
        observed_on: date,
    ) -> "GitHubActionsBudgetPlan":
        authorization.validate_action(
            account=authorization.account,
            requested_budget_usd=requested_budget_usd,
            stop_usage_at_budget=True,
            purpose=authorization.purpose,
            observed_on=observed_on,
        )
        unsigned = {
            "authorization_reference": authorization.authorization_reference,
            "account": authorization.account,
            "product": authorization.product,
            "currency": authorization.currency,
            "requested_budget_usd": str(requested_budget_usd),
            "stop_usage_at_budget": True,
            "purpose": authorization.purpose,
            "expires_on": authorization.expires_on.isoformat(),
        }
        return cls(**unsigned, action_digest=_canonical_sha256(unsigned))


class GitHubActionsBudgetObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    account: str
    product: Literal["GitHub Actions"] = "GitHub Actions"
    currency: Literal["USD"] = "USD"
    persisted_budget_usd: Decimal = Field(ge=Decimal("0"))
    stop_usage_at_budget: bool
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BrowserSkillReceipt(BaseModel):
    """Sanitized evidence; it grants no browser or financial authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    skill_version: Literal["aigc.browser-connection-bootstrap.v1"] = (
        "aigc.browser-connection-bootstrap.v1"
    )
    connector: Literal["Opera_Browser_Connector"] = "Opera_Browser_Connector"
    state: BrowserConnectionState
    target_service: str
    target_account: str | None = None
    authorization_reference: str | None = None
    action_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    requested_budget_usd: Decimal | None = None
    stop_usage_at_budget: bool | None = None
    persisted_state_verified: bool = False
    ci_retry_eligible: bool = False
    external_action_performed: bool = False
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BrowserConnectionBootstrapController(BaseModel):
    """Fail-closed controller for the browser-connection bootstrap skill.

    This controller cannot toggle browser permission or authenticate the user. It
    records observed state and prevents bounded writes or CI retries until all
    prerequisites are proven.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    state: BrowserConnectionState = BrowserConnectionState.DISCONNECTED
    disconnected_probe_locked: bool = False
    observed_account: str | None = None
    action_plan: GitHubActionsBudgetPlan | None = None
    persisted_state_verified: bool = False
    ci_attempt_count: int = Field(default=0, ge=0, le=1)
    block_reason: str | None = None

    def acknowledge_manual_activation(self) -> None:
        """Allow one new probe after the user reports enabling the permission.

        This is not evidence that the connector is connected.
        """

        if self.state is BrowserConnectionState.REVOKED:
            raise ValueError("skill is revoked")
        self.disconnected_probe_locked = False

    def observe_connection(self, probe: BrowserConnectionProbe) -> None:
        if self.state is BrowserConnectionState.REVOKED:
            raise ValueError("skill is revoked")
        if self.disconnected_probe_locked:
            raise ValueError(
                "connection probe locked; user activation acknowledgement is required"
            )
        if not (probe.connector_available and probe.user_permission_present):
            self.state = BrowserConnectionState.USER_PERMISSION_REQUIRED
            self.disconnected_probe_locked = True
            self.observed_account = None
            return
        self.disconnected_probe_locked = False
        if not probe.target_authenticated:
            self.state = BrowserConnectionState.CONNECTED_UNAUTHENTICATED
            self.observed_account = None
            return
        self.state = BrowserConnectionState.CONNECTED_AUTHENTICATED
        self.observed_account = probe.target_account

    def mark_read_only_ready(self) -> None:
        if self.state is not BrowserConnectionState.CONNECTED_AUTHENTICATED:
            raise ValueError("authenticated browser state is required")
        self.state = BrowserConnectionState.READY_READ_ONLY

    def bind_github_actions_budget(
        self,
        authorization: GitHubActionsBudgetAuthorization,
        *,
        requested_budget_usd: Decimal,
        observed_on: date,
    ) -> GitHubActionsBudgetPlan:
        if self.state not in {
            BrowserConnectionState.CONNECTED_AUTHENTICATED,
            BrowserConnectionState.READY_READ_ONLY,
        }:
            raise ValueError("authenticated read-only state is required")
        if self.observed_account != authorization.account:
            self.state = BrowserConnectionState.BLOCKED
            self.block_reason = "observed account does not match authorization"
            raise ValueError(self.block_reason)
        plan = GitHubActionsBudgetPlan.create(
            authorization,
            requested_budget_usd=requested_budget_usd,
            observed_on=observed_on,
        )
        self.action_plan = plan
        self.persisted_state_verified = False
        self.state = BrowserConnectionState.ACTION_BOUND
        return plan

    def verify_persisted_budget(
        self,
        observation: GitHubActionsBudgetObservation,
    ) -> None:
        if self.state is not BrowserConnectionState.ACTION_BOUND or not self.action_plan:
            raise ValueError("a bound action plan is required")
        expected = self.action_plan
        matches = all(
            (
                observation.account == expected.account,
                observation.product == expected.product,
                observation.currency == expected.currency,
                observation.persisted_budget_usd == expected.requested_budget_usd,
                observation.stop_usage_at_budget is True,
            )
        )
        if not matches:
            self.state = BrowserConnectionState.BLOCKED
            self.block_reason = "persisted GitHub Actions budget does not match plan"
            self.persisted_state_verified = False
            raise ValueError(self.block_reason)
        self.persisted_state_verified = True
        self.state = BrowserConnectionState.BOUNDED_WRITE_VERIFIED

    @property
    def ci_retry_eligible(self) -> bool:
        return (
            self.state is BrowserConnectionState.BOUNDED_WRITE_VERIFIED
            and self.persisted_state_verified
            and self.ci_attempt_count == 0
        )

    def record_ci_attempt(self, run_id: int) -> None:
        if run_id <= 0:
            raise ValueError("run_id must be positive")
        if not self.ci_retry_eligible:
            raise ValueError("CI retry is not eligible")
        self.ci_attempt_count = 1
        self.state = BrowserConnectionState.CI_ATTEMPTED

    def revoke(self, reason: str) -> None:
        normalized = reason.strip()
        if not normalized:
            raise ValueError("revocation reason is required")
        self.state = BrowserConnectionState.REVOKED
        self.block_reason = normalized
        self.persisted_state_verified = False

    def receipt(self, *, receipt_id: str) -> BrowserSkillReceipt:
        plan = self.action_plan
        return BrowserSkillReceipt(
            receipt_id=receipt_id,
            state=self.state,
            target_service="GitHub",
            target_account=self.observed_account,
            authorization_reference=(plan.authorization_reference if plan else None),
            action_digest=(plan.action_digest if plan else None),
            requested_budget_usd=(plan.requested_budget_usd if plan else None),
            stop_usage_at_budget=(plan.stop_usage_at_budget if plan else None),
            persisted_state_verified=self.persisted_state_verified,
            ci_retry_eligible=self.ci_retry_eligible,
            external_action_performed=self.persisted_state_verified,
        )
