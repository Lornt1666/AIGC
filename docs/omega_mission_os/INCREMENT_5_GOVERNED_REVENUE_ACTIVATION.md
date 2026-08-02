# Increment 5 — Governed Revenue Mission Activation

Status: **Implemented for review; internal preparation only**

## Purpose

Increment 5 converts the read-only Mission OS foundation into a bounded decision-support layer for the CAD 2,000 revenue mission. It prepares internal commercial artifacts while preserving the existing AIGC authority, evidence, privacy, and human-approval boundaries.

## Implemented capabilities

1. **Offer productization**
   - One fixed-scope Governed AI Workflow Blueprint.
   - Explicit deliverables, exclusions, acceptance criteria, price tiers, and delivery windows.
   - Catalog status remains `INTERNAL_DRAFT_ONLY`.

2. **Opportunity ranking**
   - Uses Phase 2 opportunities when populated.
   - Falls back transparently to Phase 3 assessment dossiers when Phase 2 is empty.
   - Scores fit, assessment strength, urgency, payment probability, operator effort, and risk.
   - Every commercial figure remains classified as estimated unless evidence proves otherwise.

3. **Internal proposal packets**
   - Binds each draft to an opportunity ID, offer ID, price, scope, exclusions, acceptance criteria, and exact revision digest.
   - Packets cannot be submitted by this module.

4. **Exact-action approval queue**
   - Creates one approval packet per exact proposal revision.
   - Initial status is `NOT_REQUESTED`.
   - No blanket authorization or self-approval is accepted.

5. **Daily operator brief**
   - Maximum 120 scheduled minutes.
   - Contains internal review tasks only.
   - Includes no outreach, submission, payment, or connector action.

6. **Evidence-linked revenue chain**
   - Opportunity → assessment → proposal → authorization → execution receipt → contract evidence → invoice → collection receipt.
   - Downstream stages remain blocked until independent evidence exists.
   - Verified collected revenue begins at zero and cannot be inferred from pipeline estimates.

## New files

- `config/mission_os_offer_catalog.json`
- `schemas/mission_activation_projection.schema.json`
- `src/mission_os/activation.py`
- `tests/test_mission_activation.py`

## API

The loopback-only, GET-only API adds:

```text
GET /api/v1/revenue/activation
```

The endpoint returns an internal projection only. It does not persist mission state or invoke an external system.

## Disabled capabilities

- External outreach
- Proposal submission
- Contract acceptance
- Invoice issuance
- Payment requests
- Payment collection
- Connector write actions

All outputs declare:

```json
{
  "external_action_authorized": false,
  "external_action_performed": false,
  "canonical_state_mutated": false
}
```

## Validation

```bash
python -m pytest tests/test_mission_activation.py
python -m pytest
```

A successful hosted CI receipt on the exact PR head is required before this increment may leave draft status.
