# Opera Bridge Ω3 — authenticated deployable edge

## Archetype
**tool-only authenticated connector**. A widget is unnecessary for the first production gate; device confirmation remains native.

## Public boundary
The public MCP endpoint is an OAuth-protected resource server. It publishes `/.well-known/oauth-protected-resource`, requires bearer tokens, validates JWTs from configured JWKS, checks issuer/audience, and uses scopes.

Suggested scopes:
- `opera:read`
- `opera:navigate`
- `opera:devices:revoke`

The OAuth authorization server is deliberately external to this package. This can be a self-hosted standards-compliant issuer. Ω3 does not implement a home-grown password database or pretend a development issuer is production safe.

## Durable broker
SQLite/WAL persists device identity metadata, commands, revocation state, rate buckets and a hash-chained audit sequence. Secret mobile push tokens are AES-256-GCM sealed using an operator-supplied master key.

## Authority separation
OAuth client authentication != paired device identity != device-side browser approval != evidence of execution.

Navigation remains:
1. authenticated MCP prepares command;
2. broker verifies device capability and rate limit;
3. device receives/wakes;
4. human sees exact target and approves on device;
5. device signs approval;
6. device performs navigation;
7. device signs result;
8. MCP reconciles result.

No blind retry after `INDETERMINATE`.

## Push
APNs/FCM interfaces are present but intentionally inert without credentials. Even when configured, push is a wake/notification channel, not action authority.

## TLS/WSS
Use a reverse proxy such as Caddy/nginx for HTTPS/WSS. Do not expose the internal broker token. Keep the MCP edge and device relay on separate hostnames when practical.

## Not yet proven
- real OAuth issuer interoperability with ChatGPT/Codex;
- public TLS deployment;
- iOS Xcode packaging and APNs;
- Android Gradle packaging and FCM;
- real Opera desktop extension connection;
- external security review;
- load/DoS behavior on Internet-facing deployment.
