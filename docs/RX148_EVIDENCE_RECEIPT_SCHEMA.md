# RX-148 Evidence Packet and Signed Receipt Contract

**Version:** `rx148.receipts.v1`  
**Trust boundary:** the trusted keyset must be provisioned through an independently protected administrator/KMS channel. A public key included only in the receipt bundle is not trusted.  
**Release authority:** RX-19 only.

## 1. Trust model

Every receipt is an Ed25519-signed envelope:

```json
{
  "key_id": "admin-managed-key-id",
  "payload": {
    "issuer": "approved-issuer-identity",
    "purpose": "human-acceptance",
    "receipt_id": "globally-unique-id",
    "issued_at": "2026-10-22T18:00:00Z",
    "expires_at": "2026-10-22T18:10:00Z",
    "candidate_sha": "40-character-git-commit-sha"
  },
  "signature": "base64-ed25519-signature-over-canonical-payload"
}
```

Signature bytes cover the payload canonicalized as UTF-8 JSON with sorted keys, separators `(",", ":")`, `ensure_ascii=False`, and `allow_nan=False`. The `key_id` selects a key from a separate trusted-key document; it does not make the key trusted. Keys need status, issuer, purpose allowlists, expiry/rotation and revocation policy. The verifier rejects duplicate receipt IDs within a process and claims verified receipts in the dedicated PostgreSQL `aigc_receipt_claims` ledger. Reusing a receipt ID with different claims is blocked across processes; configured single-use purposes (including `tool-permit`) are rejected on repeat. The live closure runner uses this store. However, the runtime's injected `permit_verifier` is not yet wired to a production key service and persistent permit claims, so live tool execution remains blocked.

All receipt payloads must have:
- `issuer`, `purpose`, unique `receipt_id`, strict UTC `issued_at` and `expires_at`;
- `candidate_sha` equal to the live PR head;
- `repository` and exact workflow/run bindings where relevant;
- `evidence_digest` for human acceptance, handoff and RX-19 decision;
- a purpose-specific policy version, status and evidence references.

## 2. Receipt purposes and required claims

| Bundle field | Purpose | Required signed claims beyond common fields |
|---|---|---|
| `protection` | `repository-protection-readback` | `base_branch`, `release_branch`, `status="VERIFIED"`, `readback_digest`, required checks/reviews/stale-approval/bypass policy evidence |
| `review` | `independent-review` | `review_id`, `reviewed_sha`, `qualified_independent=true`, `review_threads_verified=true`, `findings_closed_with_retest=true`, finding/retest evidence references |
| `provenance` | `build-provenance` | `source_sha`, `subject_digest`, `workflow_identity`, `builder_identity`, `attestation_reference` |
| `artifact` | `artifact-manifest` | `repository`, `artifact_id`, `run_id`, `run_attempt`, `sha256` of the ZIP, `manifest_path="manifest.json"` |
| `acceptance` | `human-acceptance` | `approver_role="authorized_human_approver"`, `decision="ACCEPT"`, `candidate_sha`, `evidence_digest`, `policy_version`, signed scope and expiry |
| `rx19_handoff` | `rx19-handoff` | `recipient="RX-19"`, `candidate_sha`, `evidence_digest`, `handoff_status="RECEIVED"` |
| `rx19_decision` | `rx19-release-decision` | `authority="RX-19"`, `decision` (`APPROVE` or `REJECT`), `candidate_sha`, `evidence_digest`, policy version |

The verifier cross-checks repository, candidate SHA, purpose, issuer, signing-key status, signature and validity window. The closure evaluator checks additional gate-specific claims. Missing claims do not default to true. A cryptographically valid signature does not independently prove the signer's role; that authorization is defined by the trusted-key policy and must be reviewed out of band.

## 3. Receipt bundle envelope

```json
{
  "schema_version": "rx148.receipts.v1",
  "policy_version": "rx148-policy-v1",
  "evidence_digest": "sha256:<digest-computed-by-prepare-mode>",
  "protection": {"key_id": "...", "payload": {}, "signature": "..."},
  "review": {"key_id": "...", "payload": {}, "signature": "..."},
  "provenance": {"key_id": "...", "payload": {}, "signature": "..."},
  "artifact": {"key_id": "...", "payload": {}, "signature": "..."},
  "acceptance": {"key_id": "...", "payload": {}, "signature": "..."},
  "rx19_handoff": {"key_id": "...", "payload": {}, "signature": "..."},
  "rx19_decision": {"key_id": "...", "payload": {}, "signature": "..."}
}
```

The ellipses above are documentation notation, not accepted values. Actual receipts must be complete signed envelopes. Never paste private keys, access tokens or signing secrets into a receipt bundle.

## 4. Canonical digest workflow

1. Run `scripts/aigc_closure_live.py --prepare` only after the exact-head CI evidence, protection readback, independent review, provenance and artifact receipt are available.
2. Preparation re-fetches the PR, jobs, checks, reviews and protection APIs; rechecks the PR head at the end; downloads the referenced artifact; and independently verifies the ZIP and manifest.
3. It emits `computed_evidence_digest`. The digest covers the candidate and base SHAs, PR state, CI runs/jobs, checks/statuses, reviews/comments, protection readbacks, signed core receipts and independent artifact-verification result. The acquisition timestamp is checked separately for freshness and is intentionally excluded from the digest so the final re-fetch can reproduce it if the evidence itself has not changed.
4. An authorized human signs acceptance bound to that digest and candidate. The RX-19 handoff and decision receipts must bind to the same digest.
5. Run the final workflow without `--prepare`. It re-fetches live state and recomputes the digest. If the head, CI, review, protection, artifact or policy evidence changes, the digest changes and old acceptance/handoff/decision receipts no longer match.
6. A passing evaluation is an evidence report only. It never performs merge, deployment or release.

## 5. Trusted key document

The key document must be protected separately from the receipt bundle and conform to:

```json
{
  "schema_version": "rx148.trusted-keys.v1",
  "trust_store_id": "managed-trust-store-name",
  "keys": [
    {
      "key_id": "admin-managed-key-id",
      "public_key_b64": "base64-raw-32-byte-ed25519-public-key",
      "issuer": "approved-issuer-identity",
      "allowed_purposes": ["human-acceptance"],
      "status": "ACTIVE"
    }
  ],
  "revoked_receipt_ids": []
}
```

Use distinct keys or tightly scoped purpose allowlists for administrators, reviewers, builders, human approvers and RX-19. Do not permit an agent to add keys, alter revocation state or assign its own issuer role.

## 6. Current known gaps

- The live GitHub adapter uses read-only REST; review-thread resolution is not obtained by that adapter. The independent reviewer receipt must attest the exact candidate and thread/finding reconciliation until a separately authorized read-only GraphQL adapter is implemented.
- GitHub REST protection JSON is not itself an administrator's signed receipt; the authenticated administrator must sign a readback receipt.
- Cross-process receipt claim storage is implemented for the closure runner. The production runtime permit-verifier adapter still needs to be integrated with the trusted key service and persistent single-use permit claims before live tool execution.
- Provenance verification validates a signed claim under trusted keys; a full Sigstore/in-toto verifier and independent builder identity policy still require integration.
- The closure runner returns BLOCK if artifact ZIP, signed manifest, exact run/attempt binding, or file digests cannot be verified.
- The trust store and receipt bundle are inputs; protect their paths and access control. Never accept an untrusted path as the trust-store source.
