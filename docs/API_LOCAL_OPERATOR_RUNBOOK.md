# AIGC Local Operator API Runbook

Status: feature-branch implementation under `BOOTSTRAP_OPERATOR_ASSURANCE`.

## Boundary

- Bind only to `127.0.0.1`.
- Local synthetic authorization only (`IAL0/AAL0/FAL0`).
- No credentials, live identity, deployment, connector execution, or external action.
- `production_identity_access` remains blocking.
- This API is a local control surface, not a production deployment.

## Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.\scripts\start_local_api.ps1
```

Open:

- `http://127.0.0.1:8765/`
- `http://127.0.0.1:8765/docs`

## Verify

```powershell
python -m pytest
python .\src\validate_aec_001.py
python .\src\aigc.py validate
.\scripts\smoke_local_api.ps1
```

## Stop

```powershell
.\scripts\stop_local_api.ps1
```

## Seagate installation gate

Do not install to the Seagate volume until this API PR is merged and the resulting `main` revision is verified. Detect the drive by volume label rather than assuming a drive letter. Clone fresh into `<SEAGATE>:\AIGC\repository`, create a local virtual environment, rerun all validation, and keep the server bound to `127.0.0.1`.

## Live-deployment prerequisites

Before any internet-facing deployment, AIGC still requires:

1. production identity and session management;
2. transactional persistence;
3. secrets management;
4. TLS termination and network policy;
5. staging verification;
6. monitoring, recovery, backups, and rollback evidence;
7. approved external connector policy;
8. accessibility and security review;
9. production readiness above the governed threshold.

## Rollback

Revert the single squash merge. No production state migration is involved.
