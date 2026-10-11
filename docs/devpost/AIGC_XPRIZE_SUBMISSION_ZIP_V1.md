# AIGC XPRIZE Submission ZIP V1

Status: `BUILDER IMPLEMENTED — FINAL PACKAGE BLOCKED ON EVIDENCE / EXACT-HEAD CI`

## Purpose

The live Build with Gemini XPRIZE submission requirements report:

```text
video_required = true
zip_file_required = true
website_required = false
```

AIGC therefore treats the ZIP as a governed evidence artifact rather than an arbitrary archive.

## Builder

```text
scripts/build_xprize_submission_zip.py
```

Template:

```text
config/xprize_submission_zip_manifest.example.json
```

The committed template is deliberately inert:

```text
template_only = true
internal_zip_build_authorized = false
devpost_upload_authorized = false
devpost_submission_authorized = false
```

Copy/reconstruct a non-template manifest only after the exact evidence set is ready.

## Required properties

Every packaged entry must have:

```text
required = true
evidence_state = EVIDENCED | NOT_APPLICABLE
redaction_reviewed = true
expected_sha256 = exact 64-character digest
```

A final package is bound to:

```text
repository = Lornt1666/AIGC
Devpost project id
exact release SHA
exact source file digests
exact archive paths
```

## Text security

Text formats are scanned through the repository's canonical `RedactionScanner` immediately before packaging.

Supported scanned text suffixes:

```text
.json
.jsonl
.md
.txt
.csv
.toml
.yaml
.yml
```

Any secret-like finding blocks the build.

## Binary security

Binary evidence is deliberately limited to:

```text
.pdf
.png
.jpg
.jpeg
```

The text scanner cannot establish that images/PDF rendering contains no PII, credential, private URL or other sensitive content. Therefore every binary must carry:

```text
redaction_reviewed = true
expected_sha256 = exact reviewed bytes
```

Changing a reviewed binary invalidates its digest and blocks packaging until review is repeated.

## Path safety

The builder rejects:

```text
absolute source paths
.. traversal
source paths escaping the project root
symlink sources
duplicate archive paths
archive traversal
collision with the internal package manifest
```

## Deterministic package

The ZIP is deterministic for identical input bytes/manifest identity:

```text
sorted archive order
fixed ZIP member timestamp = 1980-01-01T00:00:00Z
fixed regular-file permissions
stable internal manifest serialization
```

The internal archive contains:

```text
AIGC_SUBMISSION_PACKAGE_MANIFEST.json
```

with source/archive paths, file SHA-256 values, sizes, repository, project and release identity.

After packaging, a sidecar receipt records:

```text
zip_sha256
package_manifest_sha256
entry_count
per-entry hashes
canonical text secret scan = PASS
binary redaction review requirement = true
release SHA
captured_at
external_action_performed = false
devpost_upload_performed = false
devpost_submission_performed = false
```

The dynamic sidecar timestamp is intentionally outside the ZIP so identical evidence produces identical ZIP bytes.

## Anti-authority-smuggling rule

The builder may receive:

```text
internal_zip_build_authorized = true
```

because creating a local archive is reversible/internal.

The same manifest is rejected if it attempts to assert:

```text
devpost_upload_authorized = true
```

or:

```text
devpost_submission_authorized = true
```

Those remain separate consequential actions.

## Intended final evidence set

The template currently reserves package locations for:

```text
eligibility / pre-existing resources
entrant identity
category/impact
fresh exact-head CI
immutable GCP deployment receipt
live Gemini runtime receipt
project-running evidence
P&L
redacted customer evidence
final claim/evidence matrix
final Devpost answer set
judge-access guide
```

Missing files or non-final evidence states fail closed.

## Current disposition

```text
builder implementation = PRESENT
adversarial tests = PRESENT
final evidence set = INCOMPLETE
final package manifest = NOT AUTHORIZED / NOT COMPLETE
final ZIP = NOT BUILT
Devpost upload = NOT AUTHORIZED
Devpost submission = NOT AUTHORIZED
```

Do not mark `submission_zip_file` as `EVIDENCED` until the final archive has a retained SHA-256 receipt and the exact uploaded bytes are confirmed on Devpost.
