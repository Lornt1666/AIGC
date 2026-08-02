# Increment 4 — Executive Dashboard and Revenue Adapters

Status: **Implemented for review; read-only and non-authoritative**

## Added

- `src/mission_os/revenue.py` reads the existing Phase 2, 3, 4, 5, 6, 15, 16, 20, 21, and 22 artifacts without modifying them.
- `src/mission_os/dashboard.py` converts the validated mission snapshot and revenue projection into a compact executive payload and local HTML dashboard.
- `src/mission_os/api.py` now exposes GET-only dashboard and revenue routes.
- `tests/test_mission_dashboard_revenue.py` verifies financial classification and method restrictions.

## Routes

- `GET /dashboard` — local HTML executive view.
- `GET /api/v1/dashboard` — JSON dashboard projection.
- `GET /api/v1/revenue/pipeline` — repository-derived revenue funnel and financial classifications.

## Revenue truth model

The adapter keeps the following states distinct:

- estimated pipeline;
- contracted value;
- invoiced value;
- verified collected cash.

Collected revenue is counted only when the finance record contains an evidence or receipt reference. Estimated, proposed, or pipeline values are never promoted to collected revenue.

## Dashboard boundary

The dashboard cannot approve actions, transition Quests, invoke connectors, contact external parties, submit proposals, spend funds, issue invoices, request payment, collect payment, deploy infrastructure, or alter evidence. It emits `external_action_performed: false` and `canonical_state_mutated: false`.

## CI repair

CI run #1951 exposed an unrelated time-decay defect in the static local identity simulation fixture: six tests failed with `SESSION_TOO_OLD`. The local-development adapter now rebases only the synthetic local session window at evaluation time. It remains LOCAL_SIMULATION with IAL0/AAL0/FAL0 and does not affect production identity providers or grant additional authority.

## Local launch

```bash
uvicorn src.mission_os.api:app --host 127.0.0.1 --port 8010
```

Then open `/dashboard` locally.

## Tests

```bash
python -m pytest tests/test_mission_director.py tests/test_mission_projection.py tests/test_mission_dashboard_revenue.py tests/api/test_identity_bound_work_acceptance.py tests/api/test_review_evidence_gate.py
```

A passing hosted CI receipt is required before this increment is considered validated.
