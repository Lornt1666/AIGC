# AIGC Operator Cockpit Runbook

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Purpose

The Operator Cockpit is a local, human-governed control plane for AIGC.

It provides two primary controls:

1. **Run governed cycle** — prepares, validates, audits, and refreshes internal work artifacts.
2. **Accept selected action** — records one scoped human approval decision for one visible review packet.

The cockpit does not submit, message, bid, apply, request payment, use credentials, automate external platforms, or hide uncertainty.

## Launch

From the repository root:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run .\src\dashboard\operator_cockpit_app.py
```

Windows convenience launcher:

```powershell
.\RUN_AIGC_COCKPIT.bat
```

PowerShell launcher:

```powershell
.\scripts\run_operator_cockpit.ps1
```

The launchers do not install dependencies by default. To combine setup and launch for a local operator workstation, opt in explicitly:

```powershell
$env:AIGC_INSTALL_DEPENDENCIES = "1"
.\scripts\run_operator_cockpit.ps1
```

## Enterprise control model

The cockpit follows these operating controls:

- **Least privilege** — it reads and writes local governed artifacts only.
- **Separation of duties** — Run prepares; Review evaluates; Accept records scoped consent; manual handoff remains separate.
- **Explicit scope** — every review packet displays recipient, platform, action, artifact preview, risk, expiry, and hash.
- **Auditability** — decisions are routed through `src/aigc.py` and recorded in the existing state store and audit files.
- **No hidden execution** — acceptance does not perform a platform action and preserves `external_action_performed=false`.
- **Emergency stop** — the cockpit can enable the runtime stop flag before further approvals or phase execution.
- **Deny and revise path** — human review can deny or request revision instead of accepting.
- **Secret isolation** — secret values remain out of the repo; Phase 11 fake-test validates the scaffold without logging live values.
- **Contract validation** — the governed cycle ends with schema validation.

## What the Run button does

The Run button executes this internal sequence:

1. Runtime preflight.
2. Connector governance.
3. Secret-vault fake test.
4. Opportunity radar.
5. Ology assessment.
6. Proposal drafting.
7. Human approval packet generation.
8. Finance and contract ledger.
9. Compliance and legal review.
10. Sub-agent planning.
11. Fidelity forge.
12. Customer satisfaction continuum.
13. Quality-state kernel.
14. Ascended work-order governor.
15. Productization readiness.
16. Observability refresh.
17. Contract validation.

The sequence can stop on the first failed governance step. Each command output is visible in the cockpit and can be downloaded as a run receipt.

## What the Accept button does

The Accept button only records the visible, selected packet as approved for Phase 6 eligibility. It calls the existing exact-phrase approval gate only after you manually type the exact required phrase in the UI.

Accept does not:

- send or submit anything;
- message a customer, employer, platform, or public issue;
- use credentials;
- request payment;
- accept a contract;
- change the artifact after approval;
- bypass compliance or expiry checks;
- hide risk, blockers, or uncertainty.

Expired packets must be regenerated before acceptance.

## Manual handoff remains separate

After acceptance, Phase 6 may create a manual handoff or dry-run receipt. The default project posture remains governed and non-autonomous for external actions.

Recommended commands after one accepted packet:

```powershell
python .\src\aigc.py run phase6
python .\src\aigc.py close-loop --execution-mode manual_handoff
```

The resulting handoff instructs the operator to manually verify the recipient, platform, artifact hash, and scope before any external submission.

## Procurement procedure

The governed procurement procedure is defined in `docs/AIGC_PROCUREMENT_PROCEDURE.md`. It is process-only: it may organize research, evidence, comparison, permit drafting, and review, but it does not authorize purchase, payment, vendor account changes, paid trial activation, or contract acceptance.

## Operator rules

- Accept only one action at a time.
- Never accept an expired packet.
- Never accept a packet whose artifact preview is unclear, incomplete, or misaligned.
- Use Revise when the work product is not professional, precise, compliant, or transparent.
- Use Deny when the proposed action is out of scope, unsafe, non-compliant, or strategically weak.
- Use emergency stop when behavior is surprising, unclear, or outside the stated boundary.
