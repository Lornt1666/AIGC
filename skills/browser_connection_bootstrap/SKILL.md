# Browser Connection Bootstrap Skill

## Purpose

Provide AIGC with a bounded browser-connector bootstrap procedure that detects whether the Opera Browser Connector is available, verifies that the user has explicitly enabled the browser trust boundary, and then performs only authorized browser navigation and read/write actions.

This skill **cannot bypass, synthesize, or toggle** Opera's `Allow AI connection` permission. That permission is user-controlled and remains outside agent authority.

## Constitutional binding

This skill is subordinate to:

1. `CareerConstitution`
2. `CareerMandate`
3. `WorkCommission`
4. `OutcomeContract`
5. `AuthorityEnvelope`

The skill may never expand its own authority.

## States

```text
DISCONNECTED
USER_PERMISSION_REQUIRED
CONNECTED_UNAUTHENTICATED
CONNECTED_AUTHENTICATED
READY_READ_ONLY
READY_BOUNDED_WRITE
BLOCKED
REVOKED
```

## Connection algorithm

1. Call the browser connector `list-tabs` capability.
2. If the connector returns a disconnected/not-authorized condition:
   - set state `USER_PERMISSION_REQUIRED`;
   - emit a precise instruction telling the operator to enable Opera Browser Connector → `Allow AI connection`;
   - perform no retry loop and no alternate bypass.
3. If connected, enumerate open tabs.
4. Navigate only to a target explicitly admitted by the active WorkCommission.
5. Read the accessibility tree to determine whether the target account is authenticated.
6. If authentication is absent, set `CONNECTED_UNAUTHENTICATED` and require user sign-in. Do not automate passwords, MFA, CAPTCHA, recovery codes, or identity challenges unless a separately authorized connector explicitly supports a safe flow.
7. If authenticated and the active authority is read-only, set `READY_READ_ONLY`.
8. If a bounded write is explicitly authorized, bind the exact action, target, amount/scope, and expiry before setting `READY_BOUNDED_WRITE`.
9. Before every consequential browser action, revalidate the current WorkCommission, OutcomeContract, AuthorityEnvelope, and action digest.
10. Record a receipt containing the target URL class, action class, result, timestamp, and any external state needed for verification. Never store secrets, session cookies, authorization headers, payment details, or raw credential values.

## Required safety properties

```text
browser_permission_bypass = false
credential_theft = false
captcha_bypass = false
mfa_bypass = false
ambient_authority = false
silent_scope_growth = false
secret_logging = false
auto_retry_on_permission_denial = false
```

## GitHub Actions billing remediation profile

When the active WorkCommission authorizes the current AIGC GitHub Actions remediation, this skill may:

- verify authenticated GitHub state;
- navigate to billing / Actions usage and budget settings;
- read current Actions usage and current budget state;
- set a GitHub Actions budget only when an exact bounded financial authorization is current;
- enable `Stop usage at budget` only when required by the authorization;
- save the setting;
- re-read the page to verify the persisted value;
- emit a non-sensitive remediation receipt.

For the current authorized AIGC remediation, the permitted bound is:

```text
account = Lornt1666
product = GitHub Actions
maximum_additional_budget_usd <= 12
stop_usage_at_budget = true
purpose = exact-head AIGC validation only
expires = 2026-09-01
```

The skill must fail closed if the UI shows a different account, a broader budget, missing stop-at-budget protection, an expired authorization, or any unexpected payment/identity prompt.

## Success condition

A browser session is considered connected only when:

```text
connector_available
AND user_permission_present
AND target_session_state_observed
```

A bounded write is complete only when:

```text
authority_valid
AND action_digest_bound
AND write_executed
AND persisted_state_re-read
AND evidence_receipt_recorded
```

## Non-goals

This skill does not install Opera, enable the connector permission, impersonate the user, bypass authentication, expose credentials, or create authority that does not already exist.
