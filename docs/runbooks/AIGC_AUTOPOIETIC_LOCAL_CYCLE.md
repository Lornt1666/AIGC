# Runbook: AIGC Autopoietic Local Cycle

## Purpose

Run and verify one deterministic, finite, reversible, zero-egress AIGC ecosystem improvement cycle.

## Preconditions

- Python 3.11 or newer;
- repository checkout containing this slice;
- dependencies from the repository requirements installed;
- no external credentials are required;
- no cloud account is required;
- no network access is required by the runtime itself.

## Execute the reference cycle

From the repository root:

```bash
PYTHONPATH=. python scripts/run_autopoietic_cycle.py
```

Write a local result artifact:

```bash
PYTHONPATH=. python scripts/run_autopoietic_cycle.py \
  --output reports/artifacts/aigc_autopoietic_reference_cycle.json
```

The expected reference disposition is:

```text
terminal_status = PASS
phase = PROMOTED_SHADOW
canonical_state_mutated = false
external_action_performed = false
network_calls_performed = 0
provider_calls_performed = 0
processes_spawned = 0
secrets_accessed = 0
```

## Run validation

```bash
python -m compileall -q src/autopoiesis scripts
PYTHONPATH=. python -m pytest -q tests/test_autopoietic_ecosystem.py
PYTHONPATH=. python scripts/validate_aigc_autopoietic_ecosystem.py
```

Required local acceptance:

```text
pytest failures = 0
compile errors = 0
validation checks failed = 0
all_checks_passed = true
```

## Plan without mutation

Set the request field:

```json
"mode": "PLAN_ONLY"
```

The receipt must show a proposal without shadow execution or promotion.

## Activate emergency stop

Set the input state field:

```json
"emergency_stop_active": true
```

Expected receipt:

```text
phase = BLOCKED
reason = EMERGENCY_STOP_ACTIVE
executed_in_shadow = false
```

## Test the operator authority boundary

Use an objective or template with an effect such as `DEPLOYMENT`, `COMMUNICATION`, `FINANCIAL`, `SECURITY_SENSITIVE` or `WRITE_IRREVERSIBLE`.

Expected receipt:

```text
terminal_status = AWAITING_OPERATOR
operator_action_required = true
executed_in_shadow = false
external_action_performed = false
```

This runbook does not include a command for bypassing that state. A separate, reviewed execution adapter and exact permit are required.

## Inspect evidence

Important files:

```text
config/aigc_autopoietic_ecosystem.v1.json
config/aigc_adapter_fabric.v1.json
config/aigc_autopoietic_local_cycle.example.json
reports/artifacts/aigc_autopoietic_reference_cycle.json
reports/artifacts/aigc_autopoietic_local_validation.json
schemas/aigc_autopoietic_cycle_receipt.schema.json
```

Verify the receipt hash by loading the receipt through `CycleReceipt` and calling:

```python
receipt.verify_hash()
```

Verify a sequence with:

```python
ReceiptLedger.verify_chain(receipts)
```

## Recovery

### Candidate rejected

Inspect `verification.first_blocker` and the individual gates. Modify only the candidate/template defect; do not relax the constitution to make a test pass.

### Fitness regression

The kernel returns the prior state and a rolled-back receipt. Preserve that receipt as negative evidence.

### Replay detected

Create a new run ID and bind the exact previous receipt hash. Do not reuse the idempotency key.

### Stale revision

Re-inspect the current repository head, regenerate the objective/state binding and rerun local validation. Do not rewrite old receipts.

### Receipt-chain failure

Stop. Preserve the artifacts, identify the first invalid predecessor and reconstruct from the last verified receipt. Never skip a broken link.

## Prohibited operations in this runbook

- merge;
- deployment;
- public traffic;
- provider calls;
- cloud mutation;
- account or billing changes;
- external communication;
- financial action;
- canonical state promotion;
- production-readiness claims.
