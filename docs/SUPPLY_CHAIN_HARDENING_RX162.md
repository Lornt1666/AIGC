# AIGC dependency and container supply-chain hardening (RX-162)

Status: **design and execution gate; not yet production-complete**.

## Why this gate exists

The current `requirements.txt` and `requirements-gemini.txt` use version ranges. The Dockerfile's `pip check` detects inconsistent installed dependencies, but does not make resolution reproducible or verify artifact hashes. The Compose file also uses image tags rather than immutable digests for PostgreSQL, Redis, Qdrant, and the Python base image.

The Python Packaging Authority's secure-install guidance says hash-checking mode requires every direct and transitive dependency to be pinned and hashed, and recommends `--only-binary :all:` where compatible. See [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/) and [repeatable installs](https://pip.pypa.io/en/stable/topics/repeatable-installs/). NIST SP 800-218 recommends integrating secure development practices into the software lifecycle rather than relying on a single scanner: [NIST SSDF](https://csrc.nist.gov/pubs/sp/800/218/final).

## Required implementation sequence

1. Resolve dependencies in a clean, controlled Python 3.12 Linux environment matching the production image architecture. Include both runtime and Gemini dependencies if both are installed in the shipped image.
2. Generate a complete lock file with exact versions and SHA-256 hashes for every direct and transitive dependency. Review the resolution diff; do not generate or approve the lock from an untrusted environment.
3. Verify the lock is complete with a clean installation using pip hash-checking mode. The final Docker build must install from the lock file with `--require-hashes`; do not leave the ranged requirement files as the container installation input.
4. Run `pip check`, `pip-audit --strict`, unit/integration tests, and image build against the same lock and exact source SHA.
5. Pin every external container image to an approved digest, including both Python stages and PostgreSQL, Redis, and optional Qdrant. Renovation must be a reviewed digest update, not an implicit floating-tag pull.
6. Produce an SBOM and provenance attestation for the built image. Verify issuer, repository, workflow identity, source SHA, and artifact digest at deployment. An attestation being present is not the same as its trust policy being satisfied.
7. Retain the lock, SBOM, provenance, vulnerability report, build logs, image digest, and test receipts as one candidate-bound evidence bundle.

## Candidate acceptance tests

- A clean build with the committed lock succeeds without resolving any unpinned package.
- Altering a package artifact without updating the committed SHA-256 causes installation to fail.
- Removing a transitive dependency from the lock causes the build to fail rather than resolve it silently.
- A clean rebuild from the same source, lock, base-image digests, build arguments, and target platform produces an inspectable image and build provenance. If byte-for-byte reproducibility is required, explicitly test it; do not infer it from pinned inputs alone.
- Deployment rejects an image whose digest, source revision, provenance issuer, or workflow identity differs from the approved candidate.
- A vulnerability finding has a documented disposition (upgrade, mitigation, or accepted risk with owner and expiry); a scanner exit code alone is not a risk decision.

## Guardrails

- Do not fabricate package hashes or copy hashes from unrelated package versions/platforms.
- Do not enable hash-checking until the lock is complete; partial hash lists are not a valid security boundary.
- Do not use `pip freeze` output from a developer workstation as an unquestioned production lock.
- Do not publish or trust production attestations from untrusted pull-request code.
- Do not mark the gate PASS based only on `pip check`, `pip-audit`, image build success, or an SBOM file existing.

## Current evidence boundary

At candidate `b8b7902d246aa4dbe430056add82d60a2f9aa468`, the Dockerfile runs `pip check` after installing ranged `requirements.txt`. This is useful dependency-consistency validation, but the hash lock, digest pinning, provenance verification, and deployment enforcement described above are still open. This document records the implementation requirements; it is not evidence that those controls have been implemented.
