# AIGC Diamond Protocol v2

## Status

GOVERNED DEVELOPMENT STANDARD — PRODUCTION AUTHORITY NOT GRANTED

This document converts the AIGC hardening analysis into a repository-local engineering standard. It does not enable production, external sending, GitHub mutation, autonomous approval, or new provider authority.

## Prime invariant

**Intelligence proposes. Declarative policy constrains. Human authority approves. The Mission OS execution kernel verifies. Connectors execute only the exact authorized capability. Evidence records what actually happened.**

## Laws

### 1. Separation of powers

AI/model output is never execution authority. Reasoning may propose actions; policy may constrain them; a human operator grants scoped authorization; the execution kernel independently verifies that authorization; external connectors receive only the exact capability and resource scope that survived those gates.

### 2. Fail-closed baseline

Missing, expired, invalid, unreadable, malformed, unversioned, or unverifiable approval, policy, schema, signature, replay state, emergency-stop state, or execution lease resolves to `BLOCKED` or `EXCEPTIONAL_HALT`. Safe fallback remains dry-run or manual handoff.

### 3. Credential isolation

Raw secrets must not be committed to source control, embedded in configuration, included in model prompts, copied into long-lived logs, or included in durable evidence artifacts. Secret retrieval must use the governed Secret Broker and provider secret-reference resources. One-time credential/bootstrap delivery, when unavoidable, must use an explicitly approved secure channel and must not be persisted by AIGC.

### 4. Evidence integrity

Operational claims require runtime evidence. Code demonstrates capability structure; execution receipts demonstrate operational reality. Ledger canonicalization and digest algorithms are versioned contracts and must not be changed without an explicit migration and backward-verification plan.

### 5. Untrusted-input isolation

RSS, HTML, API responses, external Markdown, job descriptions, user-supplied documents, and model-generated text are untrusted data. They may never grant authority, alter policy, expand tool capability, or override system instructions. Prompt-injection detection is advisory; typed interfaces, capability enforcement, provenance, policy, and authorization are the security boundary.

### 6. Policy decision/enforcement separation

Policy Decision Points (PDP) and Policy Enforcement Points (PEP) remain separate. A declarative policy engine may be introduced behind a stable interface, but policy-engine `ERROR`, `UNKNOWN`, `TIMEOUT`, `UNAVAILABLE`, `MALFORMED`, `UNVERSIONED`, or `SIGNATURE_INVALID` results are equivalent to deny.

Every policy decision must bind at least:

- policy revision/digest;
- subject/actor;
- capability;
- resource;
- environment;
- authorization context;
- issued/decision time;
- expiry where applicable;
- decision evidence digest.

### 7. Cryptographic authority

Production authorization should migrate from software-held shared HMAC secrets toward asymmetric signatures backed by non-exportable KMS/HSM key material. Signed envelopes must bind key provider, key identifier/version, signing algorithm, authorization digest, environment, source revision, policy revision, issued-at, and expiry. Key rotation must preserve historical verification.

### 8. Provenance and trace continuity

Every governed work item must carry immutable correlation identifiers from ingestion through evidence. At minimum use applicable values for `trace_id`, `run_id`, opportunity/work-order ID, authorization ID, execution ID, and source revision. W3C TraceContext/OpenTelemetry may correlate runtime work but is never authorization evidence.

### 9. Isolation by risk

Untrusted parsing, model-mediated transformation, dynamic rendering, and connector execution use minimum privilege. Higher-risk workloads should support unprivileged execution, filesystem allowlists, read-only roots where practical, bounded writable scratch space, CPU/memory/time ceilings, network egress policy, process/capability restrictions, and ephemeral execution environments. Isolation uncertainty fails closed for governed external execution.

### 10. Authoritative replay protection

Replay prevention uses deterministic authoritative state with atomic reservation. Probabilistic structures such as Bloom filters may only optimize pre-filtering; they may not be the source of truth. Execution uniqueness must bind the idempotency key to authorization, capability, resource, and environment with explicit TTL/retention semantics.

### 11. Supply-chain provenance

No production artifact is promotable unless evidence binds the exact Git SHA, dependency lock state, CI workflow identity, tests, applicable SAST, secret scanning, dependency vulnerability scanning, SBOM digest, immutable build/image digest, and signature/attestation. Existing CI controls must be inventoried before adding redundant workflows; missing controls are added as separate governed increments.

## Engineering modification protocol

Every change should be a small, reviewable governed increment rather than an uncontrolled repository-wide rewrite.

1. Identify affected phase, trust boundary, and authority surface.
2. Define invariants and explicit non-goals before implementation.
3. Validate payloads with standards-compliant JSON Schema or strict typed models.
4. Enforce approved-root containment for filesystem paths crossing trust boundaries.
5. Minimize durable audit data; prefer hashes, identifiers, classifications, and protected evidence pointers over full sensitive payloads.
6. Use explicit module interfaces; avoid wildcard compatibility exports for security-sensitive public APIs.
7. Add negative tests for malformed, missing, expired, replayed, forged, oversized, and authority-expanding inputs.
8. Obtain exact-head CI on the final PR head before governed review or merge.
9. Do not represent staging, structural, or test evidence as production execution evidence.

## Production target architecture

`Untrusted Input → Normalize + Provenance → Injection Containment → Typed Contract → Intelligence Plane → Policy Decision Point → Human Authorization → Signed Authorization Envelope → Mission OS Kernel → Capability Lease → Isolated Connector → Provider → Read-Back Verification → Cryptographic Receipt → Evidence Ledger`

Cross-cutting planes:

- Secret Broker / managed identity;
- OpenTelemetry trace correlation;
- incident + quarantine handling;
- replay/idempotency state;
- KMS/HSM signing and attestation;
- CI provenance, SBOM, SAST, dependency and secret scanning.

## Prioritized implementation program

### Increment A — Contract integrity

Replace the custom subset validator with the installed standards-compliant `jsonschema` implementation. Enforce format checking and add negative tests for `const`, `pattern`, `additionalProperties`, `uniqueItems`, date-time, and length constraints.

### Increment B — Path-boundary inventory

Inventory all dynamic filesystem access. Introduce/reuse one canonical approved-root resolver and migrate trust-boundary reads/writes to it. Do not claim complete traversal protection until the inventory is closed.

### Increment C — Unified authorization envelope

Map Phase 5 authorization, approval tokens, Mission OS approval records, connector activation, and execution packets into one versioned authorization ontology without expanding authority.

### Increment D — Policy abstraction

Introduce a stable PDP interface with a local fail-closed reference evaluator first. Evaluate OPA/Rego or Cedar only behind that interface. External policy-engine failure is deny.

### Increment E — Trace/provenance propagation

Introduce immutable trace/run correlation fields across subprocess phase boundaries and propagate W3C TraceContext where applicable. Telemetry remains non-authoritative.

### Increment F — Ingestion quarantine and resilience

Create bounded ingestion adapters, deterministic retry classes, circuit breakers, and a quarantine/DLQ distinction. Security-invalid payloads go to quarantine/incident review, not blind retry.

### Increment G — Workload isolation

Define a deployment-neutral isolation contract first. Container/microVM implementation must enforce resource, filesystem, process, and network constraints and remain platform-specific.

### Increment H — Cryptographic production authority

Add KMS-backed asymmetric signing/verification interfaces and receipt key-version metadata in staging before production consideration.

### Increment I — Multi-node state only when required

Do not replace local SQLite/file coordination simply for architectural fashion. When multi-instance workers become a real requirement, migrate authoritative leases/idempotency to transactional/consensus-backed infrastructure with tested split-brain semantics.

### Increment J — Supply-chain completion

Inventory existing GitHub Actions and local hooks, then add only missing enforced gates for SBOM, SAST, history/current-tree secret scanning, dependency vulnerability scanning, provenance/attestation, and immutable artifact digests.

## Current increment

The first implementation under this protocol is intentionally narrow: standards-compliant contract validation plus regression coverage. It expands no connector or production authority.
