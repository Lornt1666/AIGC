# Ω Mission OS Policy Enforcement Layer

The Policy Enforcement Layer is a subordinate decision service between a proposed action and any
execution broker. It returns a decision and receipt only.

```text
Mission Kernel proposal
→ Identity Kernel authorization evidence
→ Sensorium and emergency-stop evidence
→ Policy Enforcement Layer
→ decision receipt
→ separately governed execution broker
```

It creates no constitution, authority registry, identity provider, approval authority, review
authority, provider client, or external-action executor.

Validation:

```text
python -m py_compile src/mission_os/policy/*.py
pytest -q tests/test_policy_enforcement.py tests/test_policy_negative_cases.py tests/test_policy_receipts.py
```

Hosted CI remains required before review advancement.
