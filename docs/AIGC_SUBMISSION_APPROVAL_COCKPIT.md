# AIGC Submission Approval Cockpit

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

The final approval is not hidden automation.

The operator views the audit of the submission, then chooses:

```text
Review Only
Proceed
Deny
```

Proceed means approval for submission handoff. It does not silently submit externally unless a future live connector exists, is explicitly approved, and passes all gates.

## Decision Buttons

| Decision | Meaning |
|---|---|
| `review_only` | View the audit and keep the decision pending. |
| `proceed` | Record `approved_for_submission_handoff` only after exact phrase confirmation. |
| `deny` | Record `denied_by_operator` and block submission handoff. |

## Exact Phrases

Proceed requires:

```text
PROCEED AIGC SUBMISSION
```

Deny requires:

```text
DENY AIGC SUBMISSION
```

## Outputs

The cockpit writes:

- `data/submission_approval/aigc_submission_approval_decision.json`
- `reports/submission_approval_cockpit.md`
- `data/audit/aigc_submission_approval_audit.jsonl`

## Local Commands

Review only:

```powershell
python .\src\submission_approval_cockpit.py --project-root . --config config\aigc_submission_approval_cockpit.json --decision review_only
```

Proceed:

```powershell
python .\src\submission_approval_cockpit.py --project-root . --config config\aigc_submission_approval_cockpit.json --decision proceed --phrase "PROCEED AIGC SUBMISSION"
```

Deny:

```powershell
python .\src\submission_approval_cockpit.py --project-root . --config config\aigc_submission_approval_cockpit.json --decision deny --phrase "DENY AIGC SUBMISSION"
```

## Safety Boundary

The cockpit performs no external action, credential use, secret logging, or live employer submission.

It records the decision and the audit state only.

## Short Form

```text
View the audit.
Proceed or deny.
Nothing leaves without the operator.
```
