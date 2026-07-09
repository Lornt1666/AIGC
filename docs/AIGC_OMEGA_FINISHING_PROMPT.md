# AIGC Omega Finishing Prompt Doctrine

## Purpose

This document captures the highest-level finishing directive for AIGC: convert the repository from governed architecture into a clean, runnable, local operator program.

AIGC must be wired correctly, properly, cleanly, freshly, responsibly, professionally, securely, lawfully, testably, maintainably, visibly, locally, and operably.

## Prime Objective

AIGC must become a practical program that can be run on a Windows computer with:

- a local desktop launch path;
- a local app interface;
- a unified CLI;
- a governed work-order system;
- a Run button;
- Accept, Revise, Deny, and Emergency Stop paths;
- artifact generation;
- schema validation;
- redaction scanning;
- tests;
- setup instructions;
- audit receipts;
- no live external execution by default;
- preserved human authority.

## Final Operating Test

The project is not finished until all of these are true:

- AIGC launches locally.
- AIGC has a visible UI.
- AIGC can run a work order.
- AIGC can prepare a paycheque pipeline without committing externally.
- AIGC can validate artifacts.
- AIGC can show generated artifacts.
- AIGC can run health checks.
- AIGC can emergency-stop.
- AIGC can be set up by following docs.
- Tests pass.
- Redaction scan passes.
- No unsafe external action exists.
- No secrets are committed.
- README tells the truth.
- Pull request body tells the truth.
- A human can operate it without guessing.

## Non-Negotiable Governance Law

AIGC must never:

- auto-apply;
- auto-submit;
- auto-accept;
- auto-pay;
- auto-purchase;
- auto-deploy;
- auto-use credentials;
- log secrets;
- impersonate a human;
- bypass platform rules;
- bypass human approval;
- approve itself;
- treat symbolic language as execution authority.

AIGC may prepare, structure, rank, draft, summarize, validate, and generate reviewable artifacts.

Only the operator may click platform-level commit buttons such as Submit, Apply, Accept, Pay, Purchase, or Deploy.

## Local Program Surfaces

### Beginner Surface

```powershell
.\RUN_AIGC_PROGRAM.bat
.\scripts\run_aigc_program.ps1
```

### Operator Surface

```powershell
python .\src\aigc.py status
python .\src\aigc.py validate
python .\src\aigc.py run work-order --input .\config\example_work_order.json
python .\src\aigc.py run paycheque --input .\config\paycheque_workflow.json
python .\src\aigc.py run governance-smoke
python .\src\aigc.py run cockpit-smoke
```

### Developer Surface

```powershell
python -m pytest
python .\src\security\redaction_scanner.py --paths src config docs README.md AGENTS.md AIGC_MASTER_PROMPT.md OMEGA_X_CONSTITUTION.md schemas tests scripts .github
git diff --check
```

## Finishing Order

1. Inspect the repo.
2. Map existing launchers, CLI commands, UI files, schemas, tests, docs, and workflows.
3. Prefer integration over duplication.
4. Wire the local launch path.
5. Wire health checks.
6. Wire the work-order path.
7. Wire the paycheque pipeline path.
8. Wire the cockpit UI.
9. Wire artifact visibility.
10. Wire validation.
11. Wire emergency stop.
12. Document setup.
13. Test everything.
14. Keep the PR draft until validation proves readiness.

## Finishing Signature

AIGC opens. AIGC runs. AIGC validates. AIGC prepares earning actions. AIGC produces evidence. AIGC waits for human authority.
