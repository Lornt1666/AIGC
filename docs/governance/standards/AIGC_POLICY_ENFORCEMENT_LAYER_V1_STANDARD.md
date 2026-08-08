# AIGC Policy Enforcement Layer v1 Standard

Authority class: `standard`
Constitutional authority: `false`
Subordinate to: `AEC-001`

## Purpose

Define one deterministic, fail-closed policy evaluation boundary for consequential AIGC actions.

The layer consumes canonical governance authority from the Governance Registry, authorization
evidence from the Identity Kernel, observed state from the Assurance Sensorium and emergency-stop
sources, planning context from the Mission Kernel, and review conventions from EIAP.

It does not authenticate users, issue authority, approve work, execute tools, merge pull requests,
deploy AIGC, activate production, send Gmail, perform financial actions, or expose secret material.

## Positive protections

- `direct_main_write_prevention=true`
- `automatic_merge_prevention=true`
- `aigc_deployment_lock=true`
- `production_activation_lock=true`
- `provider_mutation_scope_enforcement=true`
- `gmail_send_prevention=true`
- `financial_commitment_prevention=true`
- `raw_secret_output_prevention=true`
- `arbitrary_shell_prevention=true`
- `self_approval_prevention=true`

## Allowed decisions

`ALLOW`, `ALLOW_WITH_APPROVAL`, `DENY`, `INSUFFICIENT_EVIDENCE`,
and `EMERGENCY_STOP_LOCKED`.

## Precedence

AEC-001 prohibition > emergency stop > explicit deny > scope/revision mismatch >
authority failure > approval failure > privacy/secret violation > replay >
execution-surface prohibition > approval-gated allow > explicit allow > default deny.

Repository files are structural evidence. Local tests are unit-test evidence.
Hosted CI, staging, and production evidence require separate receipts.
