# AIGC Operator Cockpit Runbook

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Purpose

The Operator Cockpit is a local, human-governed control plane for AIGC.

During the current Phase 4/5 read-only hold, it provides a read-only review
surface:

1. **Review existing Phase 4/5 evidence** — inspect existing inputs and archived packet state.
2. **Audit / Transparency** — inspect the durable policy and governance-bound curriculum.

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
- **Separation of duties** — authorized native workflow prepares; local review evaluates; exact acceptance records scoped consent; manual handoff remains separate.
- **Explicit scope** — every review packet displays recipient, platform, action, artifact preview, risk, expiry, and hash.
- **Auditability** — decisions are routed through `src/aigc.py` and recorded in the existing state store and audit files.
- **No hidden execution** — acceptance does not perform a platform action and preserves `external_action_performed=false`.
- **Emergency stop** — the cockpit can enable the runtime stop flag before further approvals or phase execution.
- **Deny and revise path** — human review can deny or request revision instead of accepting.
- **Secret isolation** — secret values remain out of the repo; Phase 11 fake-test validates the scaffold without logging live values.
- **Contract validation** — an authorized native review workflow validates artifacts before uploading its receipt.

## Current hold behavior

The authoritative active policy is `config/phase2_to5_cycle_policy.json`. While
it is active, the cockpit disables:

- Phase 2–5 artifact regeneration;
- work-order and paycheque run controls;
- packet accept, deny, and revise controls;
- workflow initiation, connector activation, and production operations.

The permitted current action is read-only review of existing Phase 4 inputs and
archived expired Phase 5 packets, followed by at most one non-mutating internal
improvement proposal. Its implementation requires separate approval.

## Future authorized review cycle

Phase 2–5 artifacts may be generated only after separate explicit operator
authorization of `.github/workflows/aigc_phase2_to5_review.yml`. It is a
manual-dispatch-only, review-only workflow that uploads exact-revision digest
receipts and never commits or pushes generated artifacts.

After a fresh, unexpired packet from that workflow is visibly reviewed, its
exact Phase 5 phrase may be recorded through the CLI. Acceptance does not:

- send or submit anything;
- message a customer, employer, platform, or public issue;
- use credentials;
- request payment;
- accept a contract;
- change the artifact after approval;
- bypass compliance or expiry checks;
- hide risk, blockers, or uncertainty.

Expired packets remain archived and cannot be accepted. A separate authorized
native review cycle is required to produce a fresh candidate packet.

## Manual handoff remains separate

After acceptance, Phase 6 creates only a manual handoff. The default project
posture remains governed and non-autonomous for external actions.

Recommended commands after one accepted packet:

```powershell
python .\src\aigc.py run phase6
python .\src\aigc.py close-loop --execution-mode manual_handoff
```

The resulting handoff instructs the operator to manually verify the recipient, platform, artifact hash, and scope before any external submission.

After a human operator completes the handoff, record an exact manual
confirmation before generating a Phase 7 audit draft. The confirmation must
identify one execution ID, use the exact operator phrase, and contain only a
sanitized receipt reference. It records that the operator—not AIGC—performed
the external action and prevents reuse of the authorization.

## Procurement procedure

The governed procurement procedure is defined in `docs/AIGC_PROCUREMENT_PROCEDURE.md`. It is process-only: it may organize research, evidence, comparison, permit drafting, and review, but it does not authorize purchase, payment, vendor account changes, paid trial activation, or contract acceptance.

## Operator rules

- Accept only one action at a time.
- Never accept an expired packet.
- Never accept a packet whose artifact preview is unclear, incomplete, or misaligned.
- Use Revise when the work product is not professional, precise, compliant, or transparent.
- Use Deny when the proposed action is out of scope, unsafe, non-compliant, or strategically weak.
- Use emergency stop when behavior is surprising, unclear, or outside the stated boundary.
