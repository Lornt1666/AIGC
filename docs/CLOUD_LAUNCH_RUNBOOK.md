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

## Authentication boundary

The command center fails closed unless `AIGC_COMMAND_CENTER_TOKEN` is configured outside Git.

Protected routes include:

- `GET /`;
- `GET /api/pipeline`;
- `POST /api/run`;
- `GET /api/run/{run_id}`;
- `GET /api/reviews`;
- `POST /api/reviews/{action_id}/accept`;
- `POST /api/reviews/{action_id}/deny`;
- `POST /api/reviews/{action_id}/revise`;
- `POST /api/emergency-stop`.

Use one of:

- an `Authorization` bearer header containing the configured operator token;
- HTTP Basic auth with the token as the password;
- an `X-AIGC-Command-Token` header containing the configured operator token for controlled internal calls.

Do not commit the token, print it in logs, put it in a URL, or send it to a third party.

## Local launch

```powershell
python -m pip install -r requirements.txt
uvicorn src.webapp.app:app --host 127.0.0.1 --port 8000
```

Set `AIGC_COMMAND_CENTER_TOKEN` outside the repository before launching.

Then open:

```text
http://localhost:8000
```

## Docker launch

```powershell
docker build -t aigc-governed-worker .
docker run --rm -p 127.0.0.1:8000:8000 -e PORT=8000 --env-file <operator-env-file> aigc-governed-worker
```

## Render launch

1. Push this branch to GitHub.
2. Create a new Render Blueprint.
3. Select this repository.
4. Render reads `render.yaml`.
5. Set `AIGC_COMMAND_CENTER_TOKEN` in Render environment variables.
6. Put authentication in front of the service before distributing the URL.

## Fly.io launch

```powershell
fly auth login
fly launch --copy-config --name aigc-governed-worker
fly deploy
```

Set the `AIGC_COMMAND_CENTER_TOKEN` Fly secret before deployment.

## Google Cloud Run launch

```powershell
.\scripts\deploy_cloud_run.ps1 -ProjectId YOUR_PROJECT_ID -Region us-central1 -ServiceName aigc-governed-worker
```

The Cloud Run script deploys with `--no-allow-unauthenticated` and loads `AIGC_COMMAND_CENTER_TOKEN` from Secret Manager secret `aigc-command-center-token` by default. Create that secret before deployment.

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

Do not expose admin command endpoints publicly without authentication. Do not use `--allow-unauthenticated` for this service.
