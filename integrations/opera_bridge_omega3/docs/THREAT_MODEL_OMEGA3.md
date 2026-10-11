# Opera Bridge Ω3 Threat Model

## Assets
- operator OAuth identity and scopes;
- paired-device identity/public keys;
- encrypted push tokens;
- prepared command payloads and approval nonces;
- browser navigation result receipts;
- broker master key and internal edge-to-broker credential.

## Trust boundaries
1. OpenAI host <-> public MCP edge over HTTPS.
2. MCP edge <-> internal broker using a separate high-entropy service credential.
3. Broker <-> paired device over TLS/WSS or signed HTTPS messages.
4. Human <-> device confirmation UI for consequential browser action.

## Primary threats and controls

### Stolen bearer token
Controls: issuer/audience validation, short-lived tokens at the issuer, scoped tools, TLS, no token logging. Navigation still requires device-side approval.

### OAuth confused deputy / wrong resource
Controls: canonical `OPERA_MCP_RESOURCE`, audience validation, protected-resource metadata, and resource-specific authorization configuration.

### Compromised MCP edge
Controls: edge does not hold device private keys or mobile push tokens; broker is separately authenticated; device still signs approvals/results.

### Compromised broker database
Controls: push tokens encrypted with AES-GCM; master key is external to SQLite; device private keys are never broker-held; audit chain makes silent history rewriting detectable but does not itself prevent database deletion.

### Replay of approval
Controls: one-use nonce stored only as a hash, command expiry, state transition from PREPARED only, signed device approval.

### Command substitution
Controls: command ID, device ID, action/payload and expiry are broker-bound; the device UI must display exact target before signing approval.

### Lost/stolen device
Controls: explicit revocation, epoch increment, rejection of revoked devices. Production relay should bind every device session to the current epoch.

### SSRF / arbitrary schemes
Controls: navigation accepts only `http://` and `https://`; no `file:`, `javascript:`, `data:`, internal shell, native-messaging command or OS URL execution.

### Prompt injection from web content
Controls: browser content is evidence/data only and never authority. No page text may grant OAuth scope, approve navigation, revoke a device, or change broker configuration.

### Push abuse
Controls: push is wake/notification only; it carries no browser authority. Push credentials are optional and absent in local validation.

### DoS / command spam
Controls: durable rate buckets per device, expiry, bounded payloads at ingress in production reverse proxy, and separate public/internal surfaces. Internet-facing load limits remain to be measured.

## Residual risks before production
- external OAuth issuer interoperability is untested;
- no real TLS/WSS deployment receipt;
- no independent penetration test;
- iOS/Android binaries are not signed or device-tested;
- APNs/FCM transmissions are not implemented;
- broker relay session epoch enforcement is not yet end-to-end proven;
- SQLite is appropriate for single-instance deployment but not HA without a deliberate replication design.
