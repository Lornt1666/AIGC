# RegenExcalibur Opera Bridge Ω3

Ω3 advances the local Ω2 prototype into a deployable, fail-closed connector architecture.

## What Ω3 adds

- OAuth 2.1 resource-server boundary for the public MCP endpoint.
- Protected-resource metadata and `WWW-Authenticate` challenges.
- JWT/JWKS validation with issuer, audience/resource and scope checks.
- Durable SQLite device/command/audit state.
- AES-GCM encryption for push tokens and other broker-held secret material.
- Device revocation and epoch-based invalidation.
- Per-subject and per-device rate limiting.
- Append-only hash-chained audit receipts.
- APNs/FCM adapter interfaces that remain inert when credentials are absent.
- Internal broker authentication so the public MCP edge is not a transparent proxy.
- TLS/WSS deployment templates for a reverse proxy.
- No deployment, credentials, billing, push notification, or browser action is performed by this source package.

## Trust boundaries

`ChatGPT/Codex -> HTTPS OAuth MCP edge -> authenticated internal broker -> outbound device relay`

A device remains the authority boundary for browser navigation. OAuth authentication proves which operator/client is asking; it does not silently grant a browser mutation. Navigation is still prepare -> visible device confirmation -> signed execution result.

## Production inputs

Required before exposure:
- `OPERA_MCP_RESOURCE` canonical HTTPS MCP resource identifier
- `OPERA_OAUTH_ISSUER`
- `OPERA_OAUTH_JWKS_URI`
- `OPERA_OAUTH_AUDIENCE`
- `OPERA_BROKER_INTERNAL_TOKEN`
- `OPERA_BRIDGE_MASTER_KEY_B64` (32 random bytes, base64url)
- TLS hostname/certificate at the reverse proxy

Optional:
- APNs/FCM credentials for wake notifications

See `docs/OMEGA3.md`.
