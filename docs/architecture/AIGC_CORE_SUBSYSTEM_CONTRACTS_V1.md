# AIGC Core Subsystem Contracts V1

Status: `LOCAL CONTRACTS VERIFIED — DEPLOYMENT AND EXTERNAL AUTHORITY NOT IMPLIED`

This slice turns SILVA, HexGate, VANIS, Correlation Station, and CHORUS from names in a governance document into executable, deterministic, fail-closed contracts.

| Subsystem | Executable contract boundary | Local proof |
|---|---|---|
| SILVA | Required platform checks must be explicit and pass | An unverified required platform returns `BLOCKED` |
| HexGate | Exactly six boolean gates; any false gate denies | Missing or false gates return `BLOCKED_PERMISSION` |
| VANIS | Provider, capability, and cost are closed and bounded | Unlisted or over-budget routes do not dispatch |
| Correlation Station | Evidence lineage is ordered and cannot carry authority | Forward references and evidence-derived authority are rejected |
| CHORUS | Consequential intent is presented for approval | Presentation never becomes consent or execution authority |

The validation scope is deliberately `LOCAL_CONTRACT_ONLY`. Passing it proves contract structure and deterministic behavior. It does not prove cloud deployment, hardware compatibility, provider identity, public traffic, financial authority, or production readiness.

Run:

```bash
python scripts/validate_aigc_subsystem_contracts.py --require-pass
python -m pytest -q tests/test_aigc_subsystem_contracts.py
```

The canonical receipt contains the contract-set hash, per-subsystem results, a receipt hash, and explicit zero values for provider calls, authority, and external action.
