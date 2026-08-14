# AIGC Occupational Procurement Relay V1

## Purpose

Acquire authoritative occupational source payloads without permitting acquisition code to mutate AIGC's canonical occupational registry.

## Control chain

```text
Official Source
-> SourceProcurementContract
-> HTTPS/host/version/media checks
-> streamed hash
-> quarantine CAS
-> AcquisitionReceipt
-> RawSourcePackage
-> source adapter
-> dry-run ingestion
-> conflict/crosswalk review
-> separate admission authority
```

## Constitutional separation

```text
procure != import
import != admit
source_verified != normalization_verified
normalization_verified != canonical_ingestion_authorized
```

`SourceProcurementContract.canonical_commit_allowed` is permanently false. The relay cannot promote its own output into canonical occupational truth.

## Procurement states

```text
DISCOVERED
-> SOURCE_VERIFIED
-> ACQUIRING
-> ACQUIRED
-> HASH_VERIFIED
-> QUARANTINED
-> NORMALIZED
-> DRY_RUN_COMPLETE
-> REVIEW_REQUIRED
-> ADMISSION_ELIGIBLE
```

Failure states include `SOURCE_CHANGED`, `VERSION_MISMATCH`, `CHECKSUM_MISMATCH`, `UNSUPPORTED_FORMAT`, and `ACQUISITION_BLOCKED`.

## Network policy

- HTTPS only.
- Endpoint host must be allowlisted by the sealed source contract.
- Redirects may not escape the allowlist.
- Downloads have explicit byte ceilings.
- Media types may be constrained per dataset.
- Expected SHA-256 may be pinned when the publisher provides or an upstream evidence step establishes it.
- Acquisition receipts record source URL, final URL, byte size, content type, observed/requested version, hash and state.

## Archive policy

ZIP archives are treated as hostile data. Before adapter use the archive guard rejects:

- absolute paths;
- `..` path traversal;
- encrypted members;
- uncompressed expansion above the contract ceiling.

No archive entry is executed.

## Quarantine

Payloads are stored content-addressably:

```text
<quarantine_root>/sha256/<first-two-hex>/<full-sha256>
```

This makes identical payload acquisition idempotent and preserves immutable source evidence.

## Admission rule

```text
CANONICAL_ADMISSION :=
    acquisition_receipt_valid
    AND exact_version_verified
    AND payload_hash_verified
    AND source_adapter_succeeds
    AND dry_run_succeeds
    AND immutable_history_conflicts = 0
    AND required_crosswalk_review_passes
    AND separate_admission_authority_valid
```

The procurement relay itself can never satisfy the final authority term.

## Current WorkCommission boundary

`WC_AIGC_OCCUPATIONAL_TAXONOMY_ACQUISITION_001` permits official acquisition, checksum computation, quarantine, normalization and dry-run reporting. It does not permit canonical registry admission, merge, deployment, billing changes or unrelated repository work.
