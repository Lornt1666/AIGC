# AIGC APEX Authorization Reconstruction V1

Status: `READ-ONLY CURRENT-AUTHORITY RECONSTRUCTION — NO AUTHORITY GRANTED`

## Purpose

Reconstruct present authorization state from historical Phase-5 authorization packets without treating old approval language, expired packets, execution flags, or earlier completion summaries as reusable authority.

## Canonical input

Default source:

`data/phase5_authorizations/aigc_phase5_authorization_packets.json`

The existing repository source contains the historical action namespace used by the earlier AIGC Phase-5 workflow. The reconstruction tool reads those records; it does not mutate them.

## State model

```text
CURRENT_PENDING
CURRENT_APPROVED
CURRENT_DENIED
CURRENT_REVISION_REQUIRED
EXPIRED_PENDING
EXPIRED_APPROVED
EXPIRED_DENIED
EXPIRED_REVISION_REQUIRED
HISTORICAL_EXECUTED
INVALID
```

Only `CURRENT_APPROVED` may report `current_authority=true`, and only when the packet is not expired, approval is true, and Phase-6 authorization is true.

## Non-reuse laws

```text
expired approval != current authority
historical execution != reusable permit
approval text != execution receipt
phase6 authorization without approval = invalid
contradictory approved/denied/revise state = invalid
duplicate action ID = reconstruction defect
```

An execution flag is classified as historical evidence because the original action may already have consumed its bounded authority. It is not automatically replayable.

## Time integrity

Created/expiry timestamps must be timezone-aware and expiry must be later than creation. Naive timestamps are invalid rather than silently interpreted as UTC.

## CLI

```text
python scripts/reconstruct_apex_authorization_register.py
```

Optional fixed-time replay:

```text
python scripts/reconstruct_apex_authorization_register.py --now 2026-08-09T10:00:00+00:00
```

The output includes exact record counts, unique action IDs, current-authority count, historical/expired count, invalid records, duplicates and normalized record states.

## Relationship to APEX completion

The reconstruction output is evidence for the G1 authorization ledger. It does not itself satisfy `24/24` terminal completion. Each reconstructed action still requires a current disposition under the relevant modern AIGC gate:

```text
VERIFIED_COMPLETE
NOT_REQUIRED
DENIED_WITH_ACCEPTED_ALTERNATIVE
or explicit unresolved/blocking state
```

The stale summary count must therefore be recomputed from the exact action identities and their current evidence.

## Authority boundary

```text
read_authorization_history=true
classify_current_validity=true
authority_granted_by_reconstruction=false
external_action_performed=false
```
