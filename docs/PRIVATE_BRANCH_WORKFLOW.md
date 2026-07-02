# Private Repo Branch Workflow

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

GitHub branch protection is not available on this private repository without GitHub Pro or making the repository public. Keep the repository private and use local guardrails plus CI until protected branches are available.

## Local Guardrail Setup

Install the versioned Git hooks once per clone:

```powershell
.\scripts\install_local_git_guards.ps1
```

macOS / Linux / Git Bash:

```bash
./scripts/install_local_git_guards.sh
```

The hooks block:

- direct commits on `main`
- direct pushes to `main`
- pushes that fail local validation, tests, or secret scanning

## Daily Workflow

Start every change from `main`:

```powershell
git switch main
git pull --ff-only
git switch -c codex/my-change
```

Run checks before publishing:

```powershell
python .\src\aigc.py validate
python -m pytest
python .\src\security\redaction_scanner.py --paths src config docs README.md AGENTS.md OMEGA_X_CONSTITUTION.md schemas tests reports
```

Push the feature branch:

```powershell
git push -u origin codex/my-change
```

Open a draft PR:

```powershell
gh pr create --draft --base main --head codex/my-change --title "[codex] my change"
```

Only merge after CI is green and the diff has been reviewed.

## Main Branch Rule

Treat `main` as protected even if GitHub cannot enforce it yet.

Allowed:

- merge reviewed PRs into `main`
- run CI on PRs and feature branch pushes
- keep the repository private

Blocked:

- direct local commits to `main`
- direct local pushes to `main`
- bypassing validation to land unreviewed runtime changes

Emergency overrides exist only for deliberate recovery work:

```powershell
$env:AIGC_ALLOW_MAIN_COMMIT="1"
$env:AIGC_ALLOW_MAIN_PUSH="1"
```

Clear those variables immediately after the emergency.

