# Production Evidence Signing and Verification — AWS KMS Adapter

**Status: CODED; CRYPTOGRAPHIC UNIT TESTS ADDED; LIVE CLOUD CONFIGURATION NOT YET VERIFIED.**

## Design

- src/aigc_kms_signer.py uses AWS KMS asymmetric RSA signing with RSASSA_PSS_SHA_256.
- The private key remains non-exportable in AWS KMS. The adapter accepts a KMS key ID/ARN, not a private-key file.
- The signer hashes canonical report bytes with SHA-256 and asks KMS to sign the digest using MessageType=DIGEST, so reports larger than KMS's raw-message limit can be signed.
- Verification uses a separately pinned RSA public-key PEM, an expected signer identity, and an operator-managed trust-root ID.
- The evidence workflow can explicitly enable this adapter using --aws-kms. It defaults to unsigned/unauthenticated operation and fails closed on downstream handoffs when authentication is absent.
- The runtime obtains AWS credentials through boto3's default credential chain. Prefer a short-lived workload identity/assumed role with only kms:Sign on the single approved key. Do not put static AWS credentials or private keys in the repository.

## Example

```bash
python src/aigc_evidence_workflow.py \\
  --envelope envelope.json \\
  --inputs specialist-inputs.json \\
  --output-dir artifacts/evidence \\
  --aws-kms \\
  --kms-key-id arn:aws:kms:REGION:ACCOUNT:key/KEY_ID \\
  --signer-identity aigc-release-evidence-prod \\
  --trust-root-id security-owned-kms-public-key-v1 \\
  --trusted-public-key-file /run/secrets/aigc-kms-public-key.pem \\
  --aws-region REGION
```

The public-key file must be provisioned from the independently verified KMS public key, and its fingerprint must be reviewed/pinned out-of-band. The example path is a placeholder; this command has not been run against a live AWS account in this change.

## Tests

tests/test_kms_signer.py generates ephemeral test-only RSA keys in memory and uses a fake KMS client to exercise digest signing, successful verification, tamper rejection, identity mismatch, wrong-key rejection, and evidence-workflow integration. This is cryptographic adapter testing, not proof of live IAM/KMS configuration.

## Independent retention adapter

src/aigc_evidence_archive.py now provides an S3 Object Lock adapter that uploads a bundle with COMPLIANCE retention and exact-version metadata, then checks the returned object version, retention mode/date, content length, metadata, and full read-back digest. tests/test_evidence_archive.py exercises positive and negative paths with a fake S3 client. This is adapter-level validation only; it does not establish that an actual AWS bucket is configured or that a real object was retained.

A local JSONL hash chain is tamper-evident only relative to a separately preserved digest. It is not immutable or independently retained. Before production acceptance, archive signed reports, the canonical receipt bundle, and the exact release artifact into separately administered retention-locked storage, then independently verify bucket policy, object version ID, retention mode/date, content digest, access policy, and retrieval. Do not treat this requirement as satisfied by GitHub Actions artifact retention alone.

## Deployment gates still open

1. Provision an approved asymmetric KMS key and least-privilege workload identity outside the repository.
2. Independently pin and review the public-key fingerprint and signer identity.
3. Run the adapter against the real KMS key using the intended CI identity; verify both valid and tampered payloads.
4. Provision retention-locked remote evidence storage and independently test write/read/retention behavior using src/aigc_evidence_archive.py.
5. Retain separate authenticated attestations for the canonical receipt bundle and the actual release artifact.
6. Obtain independent security review and explicit human acceptance. Release remains BLOCK until the canonical Release Assurance Agent receives all required evidence.
