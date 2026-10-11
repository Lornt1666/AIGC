# Ω3 Production Gate

The package remains **LOCAL_PROTOTYPE_VALIDATED** until every applicable item has evidence.

- [ ] Operator-controlled HTTPS hostname exists.
- [ ] TLS certificate and HTTPS/WSS redirect/header behavior verified.
- [ ] OAuth 2.1 issuer selected and configured.
- [ ] Protected-resource metadata is publicly reachable.
- [ ] ChatGPT/Codex OAuth login succeeds with PKCE and exact resource/audience.
- [ ] `opera:read`, `opera:navigate`, and `opera:devices:revoke` scope behavior is independently tested.
- [ ] Broker internal credential generated and never exposed to client/device logs.
- [ ] 32-byte broker master key stored outside SQLite/source control.
- [ ] Device pairing UI requires authenticated operator intent.
- [ ] Revoked-device relay sessions are rejected using current auth epoch.
- [ ] Desktop Opera extension is loaded and tested in a current compatible Opera build.
- [ ] iOS companion + Share Extension builds in Xcode and works from Opera Share Sheet.
- [ ] Android companion builds and receives Opera Sharesheet URLs.
- [ ] APNs/FCM wake path, if enabled, is bounded and cannot execute browser actions.
- [ ] Navigation prepare -> device approval -> signed result is proven end to end.
- [ ] `INDETERMINATE` does not auto-retry.
- [ ] Rate-limit, replay, signature, expiry, revocation, SSRF, auth-bypass and cross-device tests pass.
- [ ] Logs contain no OAuth tokens, push tokens, cookies, authorization headers or browser credentials.
- [ ] Backup/restore and audit retention are defined.
- [ ] Independent security review completed.
