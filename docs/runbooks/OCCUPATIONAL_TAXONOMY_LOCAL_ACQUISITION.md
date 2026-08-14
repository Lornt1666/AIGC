# Occupational Taxonomy Local Acquisition Runbook

This runbook executes sealed commission `WC_AIGC_OCCUPATIONAL_TAXONOMY_ACQUISITION_001` in a normal local Python environment with outbound HTTPS.

## Preconditions

- checkout branch `design/occupational-autonomy-v2`
- Python environment satisfies the repository runtime dependencies
- outbound HTTPS is available
- no canonical registry admission authority is assumed

## Execute a bounded source first

```bash
python scripts/occupational_procurement_runner.py --authority NOC --observed-version NOC=2021.0
```

Then O*NET:

```bash
python scripts/occupational_procurement_runner.py --authority ONET --observed-version ONET=30.3
```

Run all currently configured source contracts only after exact-version observations are available:

```bash
python scripts/occupational_procurement_runner.py \
  --observed-version ISCO=ISCO-08 \
  --observed-version NOC=2021.0 \
  --observed-version SOC=2018 \
  --observed-version ONET=30.3 \
  --observed-version ESCO=1.2.1
```

## Evidence locations

Raw payloads are quarantined content-addressably under:

```text
data/occupational/quarantine/sha256/<prefix>/<sha256>
```

Receipts are emitted under:

```text
evidence/occupational_procurement/local/
```

Each successful acquisition produces an immutable acquisition receipt. Each normalizable package then produces a dry-run receipt. `summary.json` always records `canonical_registry_mutated=false` and `admission_requested=false`.

## Fail-closed rules

Do not continue to canonical admission when any of the following occurs:

- version mismatch
- redirect outside the official allowlist
- unexpected media type
- download or archive expansion limit violation
- checksum mismatch
- hostile archive entry
- unsupported normalization format
- dry-run immutable-history conflict

A successful local run is evidence for a later admission decision; it is not admission authority.
