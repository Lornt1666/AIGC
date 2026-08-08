# AIGC Nexus V1 Full-System Convergence Review

Status: `ACTIVE RELEASE CONVERGENCE — EXTERNAL RUNTIME EVIDENCE STILL REQUIRED`

## Reviewed baseline

- Repository: `Lornt1666/AIGC`
- Release train: `release/aigc-nexus-v1`
- Pull request: `#181`
- Current-main convergence: completed through an explicit two-parent merge with main `60297f4c6ac1c0feecb5ab913991cf3220247f27`.
- Live-provider/durable-control implementation admission: exact head `20385f1e5fab01d78579afd6af25348065be4481`, AIGC CI #2674, artifact `9016695906`, digest `sha256:bee233ee2f6cb6904cb8ace31dff42dbf70050a193acd1bd40b44c4a3f4bed53`.

This review is evidence, not authority. It does not authorize a provider call, cloud mutation, financial spend, deployment, merge, or production activation.

## Gate status

### 1. Private GitHub READ_FILE canary

`TRANSPORT_PROVEN / CANONICAL_ADMISSION_FAILED / NO RETRY`

The one-shot GitHub Actions canary reached its governed read step with the GitHub Actions installation token under `Contents: read` and `Metadata: read`. The canary transport boundary consumes authority immediately before dispatch and converts HTTP, URL, timeout, malformed JSON, and malformed base64 failures to `RepositoryTransportError`. The observed failure instead reached the executor's generic post-execution branch after the pre-dispatch authority/credential checks. Therefore the real private GitHub request path was exercised and returned past the transport-specific failure boundary, but the resulting observation was not admitted into canonical `RepositoryContext` evidence. The credential was one-shot and the workflow was relocked. No automatic retry is permitted.

The canary must not be represented as a fully successful canonical read receipt.

### 2. GitHub App / credential boundary

`IMPLEMENTED + CI ADMITTED / LIVE INSTALLATION NOT YET PROVISIONED`

`GitHubAppInstallationReadBoundary` keeps the App private key and installation token inside infrastructure, restricts the token request to one repository and read-only contents permission, validates expiry/permissions, returns only opaque `RepositoryCredentialCapability`, and clears the installation token after the read attempt.

### 3–4. Gemini and OpenAI provider adapters

`IMPLEMENTED + CI ADMITTED / LIVE CREDENTIAL PRECONDITIONS MISSING`

Both adapters are provider-neutral `ProviderAdapter` implementations behind `GovernedLiveNexusProviderRuntime`. They are exact-model, TEXT-only, trusted as `READ_EXTERNAL`, require explicit live/network/credential policy, a real bound `ExecutionPermit`, and durable control-store health. OpenAI uses Responses with `store=False`; Gemini uses Vertex mode / ADC. Neither supplies tools.

### 5. Durable runtime controls

`IMPLEMENTED + POSTGRES INTEGRATION CI ADMITTED`

PostgreSQL 16 integration covers cross-instance terminal-result replay, atomic idempotency conflict, emergency-stop epoch activation/clear, persistent permit invocation ceilings, principal/global request limits, usage reservations, and canonical terminal result persistence.

### 6. Controlled live multi-model canary

`BLOCKED BY EXTERNAL PRECONDITIONS`

Repository code is ready for a bounded canary, but no verified AIGC Google Cloud project/workload identity or injectable OpenAI project credential is currently available to this release train, and no provider spend receipt exists. A live canary must not be fabricated from mocks or from ChatGPT responses.

### 7. Immutable-digest staging deployment

`BLOCKED BY EXTERNAL PRECONDITIONS`

Montréal (`northamerica-northeast1`) remains the intended Canadian staging region, but a concrete AIGC project ID/project number/billing account, exact regional secret versions, Artifact Registry, Cloud SQL, Cloud Run service identities, evidence bucket, and approved spend configuration are not proven by this release train. No cloud resource may be invented.

### 8. Deployed load/failure/security/reconciliation validation

`BLOCKED UNTIL STAGING EXISTS`

The repository has deterministic/adversarial and real ephemeral-Postgres validation, but deployed latency, concurrency, failure injection, restart recovery, egress/security, and reconciliation measurements require the immutable staging revision from Gate 7.

### 9. Full-system convergence findings

#### Resolved in this convergence increment

1. **Reducer semantics:** canonical `ArtifactState` may advance only after `execution_status=succeeded`. `not_started`, `failed`, `cancelled`, and `timed_out` leave state unchanged. `partially_applied` and `indeterminate` stop at `ReconciliationRequired` until a reconciliation ChangeSet produces confirmed evidence.
2. **Dashboard stale projection:** the UI no longer claims persistent memory is a future workstream. It reports SQLite memory/evidence, the read-only repository gateway, governed live provider foundation, and PostgreSQL runtime controls as available but not auto-connected.
3. **Mutable evidence revision:** the visible dry-run UI no longer defaults an “exact revision” field to a branch name. It accepts only 40/64-character hexadecimal revisions and may obtain an exact release revision from `AIGC_RELEASE_REVISION`.
4. **Direct dependency drift:** direct Python requirements are pinned to the exact versions admitted by CI #2674. A cryptographic transitive lock with package hashes remains a future supply-chain hardening item.

#### Remaining convergence debt

1. Resource-specific state reducers remain intentionally absent; the generic reducer cannot infer external resource semantics.
2. The dashboard remains an inspection projection; it is not wired to production Postgres/provider/repository health and cannot grant authority.
3. Live provider cost accounting depends on externally reviewed CAD token pricing; pricing must not be hard-coded from stale memory.
4. The failed private-GitHub canary did not retain the inner failure receipt, so future external canaries must persist terminal receipts even when the top-level command exits non-zero.
5. Historical branches remain numerous and must not be deleted solely because Nexus supersedes their runtime role; retirement still requires dependency/reference/evidence coverage.
6. A fully hash-locked transitive Python dependency artifact has not yet been generated.

### 10. Release evidence / ready / merge

`BLOCKED`

PR #181 must remain draft until Gates 6–8 have real external evidence and a final exact-head convergence CI/evidence packet passes. CI success for implementation code is not a substitute for staging/live-runtime evidence.

## Release invariant

`Capability may evolve autonomously. Authority may not.`
