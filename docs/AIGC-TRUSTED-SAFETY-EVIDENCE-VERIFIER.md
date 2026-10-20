# AIGC trusted safety evidence verifier

## Purpose and trust boundary

Phase 6 accepts safety claims only as signed, action-bound evidence records. The verifier does not create evidence, call a platform, or infer a successful check from model output or boolean flags. Missing trust configuration or any failed/missing check blocks execution.

Each record has a `payload` and HMAC-SHA256 `signature`. The canonical payload binds:
- issuer, evidence ID, check ID, pass/fail result;
- issuance and expiry timestamps with explicit timezone;
- policy and verifier versions;
- authorization ID, action ID, proposal ID;
- SHA-256 of the exact artifact, recipient, platform, and execution scope.

Required checks: `platform_policy`, `ai_disclosure`, and `privacy`. Duplicate evidence IDs, unknown issuers, bad signatures, future-issued/stale/expired records, mismatched bindings, unknown checks, failed results, and missing required checks fail closed.

## Trust provisioning

Set `AIGC_SAFETY_EVIDENCE_HMAC_KEYS_JSON` at runtime to a JSON object mapping three distinct, explicitly provisioned issuer IDs to secrets of at least 32 bytes, and set `AIGC_SAFETY_EVIDENCE_POLICY_VERSION` to the exact currently approved policy version. Example placeholders only:

```json
{
  "policy-checker": "<inject-from-secret-manager-at-runtime>",
  "disclosure-checker": "<inject-from-secret-manager-at-runtime>",
  "privacy-checker": "<inject-from-secret-manager-at-runtime>"
}
```

The verifier requires the three required checks to be attested by distinct trusted issuers and rejects records whose policy version differs from the configured current version. This prevents one issuer or a stale policy receipt from satisfying all controls.

Never commit a real key, embed it in work orders, or let the LLM choose or retrieve it. Provision secrets only to trusted checkers and the verifier through a secret manager. CI test keys are synthetic and must never be deployed.

HMAC is appropriate only where a shared secret can be protected. For stronger separation of duties, use a KMS-backed asymmetric signature adapter so the verifier holds public keys and only approved checkers can sign. Production provisioning must include key rotation, issuer revocation, audit logging, and a documented policy owner.

## Current limitations

- This PR implements verification and the Phase 6 enforcement hook, not the platform-specific checkers that produce trustworthy evidence.
- No evidence is automatically trusted merely because an AI agent claims a check passed.
- With no configured trusted issuers, Phase 6 blocks. Do not configure production trust keys until each issuer's identity, implementation, key custody, and control scope have been independently reviewed.
- Live API execution remains separately blocked by the existing adapter.
