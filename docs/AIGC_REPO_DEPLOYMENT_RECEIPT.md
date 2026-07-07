# AIGC Repository Deployment Receipt

Generated: 2026-07-07

## Action Executed

PR #12 was moved from draft to ready-for-review and merged into `main` as a squash merge.

## Merge Details

- PR: #12
- Source branch: `codex/operator-cockpit-run-accept`
- Target branch: `main`
- Expected head SHA used for merge guard: `3de434375690365fa27cec57f06a0275baa73388`
- Main merge commit: `9f20fb2b4cc47be6d59b4b75870b79d973d25a48`
- Merge method: squash

## Repository Deployment Meaning

The governed AIGC Autonomic Worker Command Center, Phase 24 autonomic business pipeline, procured control layers, cloud launch files, tests, runbooks, and sellable package documentation are now deployed into the repository default branch.

## Verification Before Merge

- PR was open.
- PR was mergeable.
- PR head was clean and matched the requested head SHA.
- GitHub Actions reported success for the PR head.

## Post-Merge Boundary

No cloud account was accessed.
No cloud deployment was executed.
No credential was read.
No live connector was executed.
No procurement purchase was made.
No external employer/customer action was performed.

## Live Launch Next Steps

To launch locally:

```powershell
python -m pip install -r requirements.txt
$env:AIGC_COMMAND_CENTER_TOKEN="set-a-private-operator-token"
uvicorn src.webapp.app:app --host 127.0.0.1 --port 8000
```

To launch with Docker:

```powershell
docker build -t aigc-governed-worker .
docker run --rm -p 127.0.0.1:8000:8000 -e PORT=8000 --env-file <operator-env-file> aigc-governed-worker
```

To deploy on Cloud Run, create the required Secret Manager token first, then run:

```powershell
.\scripts\deploy_cloud_run.ps1 -ProjectId YOUR_PROJECT_ID -Region us-central1 -ServiceName aigc-governed-worker
```

## Governance Reminder

The command center is intentionally configured to fail closed unless `AIGC_COMMAND_CENTER_TOKEN` is set outside Git. Do not expose command endpoints publicly without authentication.
