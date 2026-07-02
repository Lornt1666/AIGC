# AIGC Productization Runbook

This runbook keeps productization private, auditable, and gated.

## Local Readiness

Run:

```powershell
python .\src\aigc.py run phase18
python .\src\aigc.py validate
python -m pytest
python .\src\security\redaction_scanner.py --paths src config docs README.md AGENTS.md AIGC_MASTER_PROMPT.md OMEGA_X_CONSTITUTION.md schemas tests reports
```

Expected:

- Phase 18 status is `internal_release_candidate`.
- Contract validation passes.
- Tests pass.
- Redaction scanner reports no findings.
- GitHub Actions passes on the private repository.

## Release Boundaries

Phase 18 does not deploy, publish, distribute, enable live connectors, use credentials, contact employers, submit applications, or perform external execution.

Any release outside the private repository requires explicit operator approval.

## Manual Gates

Before any release candidate is distributed or deployed, confirm:

- The GitHub repository is private.
- `LICENSE` states All Rights Reserved.
- No raw secrets are present in repo files, prompts, memory, audit logs, or release artifacts.
- CI is green on `main`.
- Local git guards are installed.
- Live connectors remain disabled unless approved through the AIGC approval path.
