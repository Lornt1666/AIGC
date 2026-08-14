---
name: browser-connection-bootstrap
description: Establish and verify a user-authorized Opera Browser Connector session, then execute narrowly scoped authenticated browser workflows such as the bounded GitHub Actions capacity remediation. Use when the browser connector is installed but disconnected, target authentication must be verified, or a pre-authorized browser action must run fail-closed with receipts.
---

# Browser Connection Bootstrap

Use this skill to cross the browser-automation trust boundary without confusing **permission**, **authentication**, **authorization**, **execution**, or **evidence**.

## Root invariant

> The skill may detect and use a browser connection after the user grants it. It may never grant, synthesize, bypass, or silently retry the user-controlled connection permission itself.

```text
user_permission != target_authentication
connection != authorization
write_executed != write_verified
budget_authorized != budget_saved
```

## Supported connector

Primary connector: `Opera_Browser_Connector`

Expected capabilities:

- `list-tabs` — connection probe and tab discovery;
- `go-to-page` — bounded navigation;
- `tab-content` — accessibility-tree inspection;
- `tab-content-jq-search-query` — focused page-state inspection;
- `screenshot` — visual corroboration only when the accessibility tree is insufficient;
- `close-tab` — close only tabs opened by the skill when cleanup is appropriate.

## Constitutional precedence

This skill remains subordinate to:

```text
CareerConstitution
  > CareerMandate
  > WorkCommission
  > OutcomeContract
  > AuthorityEnvelope
  > BrowserActionPlan
  > Tool call
```

The skill cannot broaden its target, budget, recipient, account, action class, or expiry because a web page offers additional controls.

## Connection state machine

```text
DISCONNECTED
  -> USER_PERMISSION_REQUIRED
  -> CONNECTED_UNAUTHENTICATED
  -> CONNECTED_AUTHENTICATED
  -> READY_READ_ONLY
  -> ACTION_BOUND
  -> BOUNDED_WRITE_VERIFIED
  -> CI_ATTEMPTED

Cross-cutting:
BLOCKED | REVOKED
```

### Probe procedure

1. Call `list-tabs` once.
2. If the connector reports disconnected, unavailable, or permission denied:
   - set `USER_PERMISSION_REQUIRED`;
   - tell the operator exactly: enable Opera Browser Connector → **Allow AI connection**, and sign into Opera if required;
   - stop. Do not loop, retry, use another browser, or attempt OS-level permission automation.
3. After the operator reports the permission was enabled, call `list-tabs` once more. The operator's statement does not itself prove connection.
4. A connection is established only when the connector returns a valid tab list.
5. Navigate only to a target admitted by the current WorkCommission.
6. Inspect the target page to establish whether the required account is authenticated.
7. If sign-in, MFA, CAPTCHA, recovery, password, or identity verification is required, stop at `CONNECTED_UNAUTHENTICATED` and hand control to the user. Never capture or automate secret credentials.

## Read-only behavior

Once connected and authenticated, begin in `READY_READ_ONLY`.

Read-only actions may:

- inspect current account identity;
- inspect GitHub Actions usage, budgets, policies, and runner-admission notices;
- inspect the exact PR, workflow run, job, and artifact state;
- compare observed state with the active authorization record;
- prepare an exact action digest.

Read-only evidence does not grant write authority.

## Consequential browser actions

Before a bounded write:

1. Resolve the exact authorization source.
2. Bind account, product, target page, action, amount/scope, stop conditions, purpose, and expiry.
3. Compute an action digest.
4. Revalidate the authorization immediately before the final save/submit action.
5. Execute only the bound action.
6. Re-read the page after save.
7. Emit a sanitized receipt.

Stop if the page displays an unexpected account, payment-method change, identity challenge, broader product scope, higher amount, missing stop-at-budget protection, or material UI ambiguity.

## Current GitHub Actions capacity-remediation profile

Authorization source: AIGC issue `#218` and the current operator authorization.

```text
account = Lornt1666
product = GitHub Actions
currency = USD
maximum_additional_budget_usd <= 12
stop_usage_at_budget = true
purpose = exact-head AIGC validation only
expires_on = 2026-09-01
payment_method_change = prohibited
unrelated_product_budget_change = prohibited
```

Execution sequence:

```text
probe connector
-> verify GitHub authentication and account
-> read Actions usage and budget state
-> verify current authorization is unexpired
-> prepare exact <= USD 12 action digest
-> save budget with Stop usage at budget enabled
-> re-read persisted state
-> emit remediation receipt
-> permit exactly one exact-current-head PR #225 CI attempt
-> inspect runner_id, steps, logs, tests, and artifacts
-> no blind retry
```

`CI_RETRY_ELIGIBLE` becomes true only after the saved budget state is re-read and exactly matches the action plan.

## Receipt requirements

Record only non-sensitive fields:

```text
skill_version
connector
connection_state
target_service
target_account
authorization_reference
action_digest
requested_budget_usd
stop_usage_at_budget
persisted_state_verified
observed_at
ci_retry_eligible
external_action_performed
```

Never record passwords, cookies, tokens, authorization headers, payment card or bank details, MFA values, recovery codes, or full sensitive screenshots.

## Failure behavior

```text
connector unavailable -> USER_PERMISSION_REQUIRED
user permission absent -> USER_PERMISSION_REQUIRED
GitHub signed out -> CONNECTED_UNAUTHENTICATED
wrong GitHub account -> BLOCKED
expired authorization -> BLOCKED
budget > USD 12 -> BLOCKED
Stop usage disabled -> BLOCKED
payment-method prompt -> BLOCKED
persisted state mismatch -> BLOCKED
second CI attempt without classified repair/transient cause -> BLOCKED
```

## Non-goals

This skill does not install Opera, toggle `Allow AI connection`, impersonate the user, bypass authentication, solve CAPTCHA, bypass MFA, change payment methods, expose credentials, or create authority that does not already exist.
