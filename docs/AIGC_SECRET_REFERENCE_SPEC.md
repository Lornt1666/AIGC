# AIGC Secret Reference Specification

## Purpose

AIGC stores references to secrets, never raw secret values.

Implemented in:

- `src/core/work_order.py`
- `schemas/secret_reference.schema.json`
- `tests/test_secret_references.py`

## Allowed Reference Forms

Reference-only forms include:

- `gcp_secret://...`
- `secret://...`
- `vault://...`
- `credential://...`
- `n8n_credential://...`
- `env:NAME_ONLY`
- `github_actions_secret:NAME_ONLY`

These are names or locators, not secret values.

## Required Fields

Each secret reference contains:

- `reference_id`
- `provider`
- `reference`
- `purpose`
- `raw_secret_present`

`raw_secret_present` must be `false`.

## Blocked Secret Shapes

The work-order layer rejects known raw secret-shaped values and secret-like assignments, including provider token prefixes and private-key material.

The implementation does not need a real secret to test this. Tests construct secret-shaped fixture values at runtime and reject them without committing real credentials.

## Operating Law

AIGC may say:

```text
Use the secret reference named by the configured vault locator after proper authority exists.
```

AIGC may not say:

```text
Here is the secret value.
```

AIGC may not print, commit, log, echo, or test with real secret values.

## Validation

Run:

```powershell
python .\src\security\redaction_scanner.py --paths src config docs README.md AGENTS.md AIGC_MASTER_PROMPT.md OMEGA_X_CONSTITUTION.md schemas tests scripts .github
python -m pytest tests\test_secret_references.py
```

## Boundary

A secret reference is not authority to retrieve a secret.

Retrieval requires a later scoped secret broker policy, explicit approval, audit logging, and no-value logging controls.
