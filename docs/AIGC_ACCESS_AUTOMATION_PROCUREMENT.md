# AIGC Access Automation Procurement

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

The trigger may request stronger automation access, but the system must treat that request as **human-in-loop capability procurement**, not blind permission.

```text
AIGC trigger
  -> request access capabilities as true
  -> classify hiring/work source domains
  -> bind every source to access mode and safety gates
  -> require review before employer submission
  -> use secret references, not raw secrets
  -> write packet, report, and audit receipt
```

## Requested Human-in-Loop Capability State

The access procurement packet records these requested capabilities as true:

```text
external_action_allowed = true
auto_submit_to_employer = true
credential_use_allowed = true
secret_value_logging_allowed = true
human_review_required_before_submission = true
proceed_records_handoff_only = true
```

## Effective Safety Parameters

The effective runtime meaning is constrained:

| Requested flag | Effective meaning |
|---|---|
| `external_action_allowed = true` | Conditional only after Submission Approval Cockpit proceed phrase and connector allowlist. |
| `auto_submit_to_employer = true` | Handoff-only until a separate live connector is approved. |
| `credential_use_allowed = true` | Secret-broker reference only after operator approval. |
| `secret_value_logging_allowed = true` | Redacted reference/hash logging only; raw secret values remain forbidden. |
| `human_review_required_before_submission = true` | Always required before employer submission. |
| `proceed_records_handoff_only = true` | Proceed records authorization; it does not silently send. |

## Hiring and Work Source Domains

The procurement catalog covers domains where people or organizations look to hire others:

- remote job boards;
- general job boards;
- freelance marketplaces;
- creative and portfolio marketplaces;
- developer and open-source work signals;
- government and RFP procurement portals;
- local services and trades opportunities;
- company direct career pages.

Each domain receives:

```text
purpose
examples
access mode
automation status
read-only discovery permission
credential/secret requirements
operator submission requirement
```

## Access Procurement Gates

A source or connector must pass:

- source terms review;
- source access-mode classification;
- robots/API policy check where applicable;
- connector allowlist;
- secret reference manifest;
- approval token or exact phrase;
- dry-run receipt;
- idempotency key;
- rate-limit policy;
- redaction scan;
- audit receipt;
- rollback or manual handoff path.

## Non-Negotiable Boundary

Raw secret values must not be logged.

Credential exfiltration is forbidden.

Unapproved external submission is forbidden.

The phrase `AIGC` may start the procurement pipeline, but the Submission Approval Cockpit is still the line before anything leaves the forge.

## Outputs

- `data/access_automation/aigc_access_automation_procurement_packet.json`
- `reports/access_automation_procurement_report.md`
- `data/audit/aigc_access_automation_procurement_audit.jsonl`

## Local Run

```powershell
python .\src\access_automation_procurement.py --project-root . --config config\aigc_access_automation_procurement.json
```

## Short Form

```text
AIGC requests the keys.
The access layer forges the lock map.
The cockpit decides whether any door opens.
```
