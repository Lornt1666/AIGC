# RX-148 Live Closure Workflow — Operator Runbook

## Security posture

This workflow is read-only. It fetches live GitHub state, verifies signed receipts against a separately managed trusted-key file, and evaluates the closure matrix. It never assigns reviewers, changes branch protections, merges, deploys, or releases. RX-19 is the sole release decision authority.

The runner deliberately fails closed. Do not store production private keys in the repository. The trusted-key file must be provisioned through an independently protected admin channel; do not accept a key solely because it arrived in the same receipt bundle being verified.

## Components

- `src/aigc_runtime/github_evidence.py`: live, read-only GitHub API acquisition and pagination.
- `src/aigc_runtime/receipt_verifier.py`: Ed25519 signature and claim-binding verification.
- `src/aigc_runtime/closure_workflow.py`: deterministic nine-gate matrix and blocker output.
- `scripts/aigc_closure_check.py`: evaluates an already acquired JSON snapshot.
- `scripts/aigc_closure_live.py`: runs live acquisition, verifies supplied signed evidence, then evaluates closure.
- `tests/test_aigc_closure_workflow.py` and `tests/test_aigc_evidence_adapters.py`: negative tests.

## Run from a clean checkout

Use a virtual environment and install the repository's pinned/ranged requirements as documented by the project. Supply a least-privilege GitHub token through the environment, not a command-line argument:

```sh
export GITHUB_TOKEN='(provision securely; do not paste into shell history)'
PYTHONPATH=src python scripts/aigc_closure_live.py \
  --repository Lornt1666/AIGC \
  --pr 330 \
  --trusted-keys /secure/path/rx148-trusted-keys.json \
  --receipts /secure/path/rx148-receipts.json \
  --required-ci-job validate \
  --required-ci-job 'revalidate_locked_releases (v0-12, 4af438408894c348ec766bfccc730b3a62a8f69d)' \
  --required-ci-job 'revalidate_locked_releases (v0-13, 119625b87bec93fb895d176023d47265eed8b9b9)' \
  --output rx148-closure-result.json
```

Job names must match the repository's actual required-check policy exactly. Obtain the policy from an authorized administrator; do not infer it from whichever checks happen to pass. Re-fetch the live head immediately before final review and packet handoff.

## Trusted key document

Expected JSON shape:

```json
{
  "schema_version": "rx148.trusted-keys.v1",
  "trust_store_id": "externally-managed-policy-identifier",
  "keys": [
    {
      "key_id": "admin-managed-key-id",
      "public_key_b64": "base64-encoded-32-byte-Ed25519-public-key",
      "issuer": "authenticated-issuer-identity",
      "allowed_purposes": [
        "repository-protection-readback",
        "independent-review",
        "build-provenance",
        "human-acceptance",
        "rx19-handoff",
        "rx19-release-decision",
        "artifact-manifest"
      ],
      "status": "ACTIVE"
    }
  ],
  "revoked_receipt_ids": []
}
```

The trust-store file is security-sensitive policy, not a user-supplied convenience file. The code validates signatures against it; it cannot prove that the file itself was provisioned correctly. Key rotation, revocation, custody, and reviewer/approver identity-to-role mapping remain external controls.

## Signed receipt bundle

The receipt bundle uses `schema_version: rx148.receipts.v1` and contains signed envelopes named `protection`, `review`, `provenance`, `acceptance`, `rx19_handoff`, `rx19_decision`, and `artifact`, plus `policy_version` and `evidence_digest`. Every envelope contains `key_id`, `payload`, and base64 Ed25519 `signature` over canonical UTF-8 JSON (sorted keys, compact separators, no ASCII escaping). Each payload must include `issuer`, `purpose`, unique `receipt_id`, `issued_at`, `expires_at`, and `candidate_sha`, plus its gate-specific claims. Exact field names must match the closure evaluator's contract.

The runner rejects missing keys, unauthorized purpose, invalid signature, expired/future receipts, revoked IDs, and candidate mismatch. Signed receipts must come from independently trusted key holders. Do not fabricate receipts or treat a sample fixture as authorization.

## Known deliberate blockers / limitations

1. The current live adapter reads PR metadata, workflow runs/attempt jobs, status/checks, reviews/comments, and branch-protection endpoints. A 403/404 protection read is UNVERIFIABLE, not evidence that protection is absent.
2. The runner does **not yet download GitHub artifact ZIP bytes and independently recompute the archive/file digests**. Therefore an artifact manifest claim alone must not be promoted to PASS. Complete and independently test that adapter before release use.
3. The REST response is not a signed administrator attestation. The signed protection receipt must bind the exact base and release branches and be independently authorized.
4. The runner does not infer the required-check policy; pass every required job name from an administrator-approved policy.
5. Signature verification does not alone establish the issuer's organizational authority. The protected trust store must encode that authority, and key lifecycle controls must be reviewed.
6. The evaluator result is an evidence report only. Even a fully passing matrix never executes release; only RX-19's separately authenticated decision can authorize release.
7. All RX-149–RX-161 agent registry entries remain disabled/R0/specification-only until each service passes implementation, isolated tests, independent review, and authorized activation.

## Exit codes

- `0`: evidence matrix reports all gates passing, including authenticated RX-19 decision; no action is performed.
- `2`: BLOCK, invalid input, unavailable live evidence, failed signature, or incomplete gate evidence.

Preserve the exact result file and its manifest digest as an audit artifact. Any candidate SHA, required-check policy, trusted key, or evidence change requires reevaluation and may invalidate dependent receipts.
