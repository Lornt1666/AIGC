# AIGC Cloud Launch Runbook

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Purpose

This runbook launches the AIGC Governed Worker Command Center as an internet-accessible web application.

The web application exposes:

- `GET /` — browser command center;
- `GET /health` — health check;
- `GET /api/pipeline` — exact governed business cycle;
- `POST /api/run` — start the full governed cycle;
- `GET /api/run/{run_id}` — inspect run state;
- `GET /api/reviews` — inspect human review packets;
- `POST /api/reviews/{action_id}/accept` — record typed exact-phrase acceptance for one packet;
- `POST /api/reviews/{action_id}/deny` — deny one packet;
- `POST /api/reviews/{action_id}/revise` — request revision;
- `POST /api/emergency-stop` — enable the local runtime stop flag.

## Local launch

```powershell
python -m pip install -r requirements.txt
uvicorn src.webapp.app:app --host 0.0.0.0 --port 8000
```

Then open:

```text
http://localhost:8000
```

## Docker launch

```powershell
docker build -t aigc-governed-worker .
docker run --rm -p 8000:8000 -e PORT=8000 aigc-governed-worker
```

## Render launch

1. Push this branch to GitHub.
2. Create a new Render Blueprint.
3. Select this repository.
4. Render reads `render.yaml`.
5. After launch, review authentication and sharing settings before distributing the URL.

## Fly.io launch

```powershell
fly auth login
fly launch --copy-config --name aigc-governed-worker
fly deploy
```

## Google Cloud Run launch

```powershell
.\scripts\deploy_cloud_run.ps1 -ProjectId YOUR_PROJECT_ID -Region us-central1 -ServiceName aigc-governed-worker
```

After deployment, review Cloud Run IAM policy before public sharing.

## Production controls before sale

Before selling the folder, verify:

- all tests pass;
- the repo contains no secrets;
- branch protection is enabled;
- the deployment URL is behind the intended authentication policy;
- the license and copyright terms are visible;
- generated data does not contain private client information;
- review packets and action receipts stay audit-visible;
- emergency stop is present and tested;
- pricing claims are accurate and not misleading.

## Recommended production posture

For a customer-facing product, run with authentication in front of the app. Use one of:

- Cloud Run with Identity-Aware Proxy or authenticated invoker policy;
- Cloudflare Access;
- Tailscale Funnel or Tailscale Serve for private buyers;
- Render private environment plus external auth gateway;
- Fly.io plus an auth proxy.

Do not expose admin command endpoints publicly without authentication.
