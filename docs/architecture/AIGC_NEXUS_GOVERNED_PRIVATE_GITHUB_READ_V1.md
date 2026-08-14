# AIGC Nexus Governed Private GitHub Read V1

Status: `IMPLEMENTATION_ONLY — LIVE PRIVATE GITHUB READ NOT AUTHORIZED`

## Constitutional invariant

`Reasoning != Verification != Authority != Execution != Evidence`

Repository content, repository context, ToolBroker decisions, credentials, and GitHub adapter outputs are never authority.

## Admitted implementation topology

```text
RepositoryReadRequest
        ↓
GovernanceDecision
        ↓
ExecutionPermit
        ↓
EpistemicToolBroker policy admission
        ↓
GovernedRepositoryReadExecutor
        ↓
RepositoryCredentialResolver
        ↓
GitHubRepositoryReadPort
        ↓
NexusRepositoryGateway
        ↓
GovernedGitHubKernelAdapter
        ↓
DeterministicGitHubReadProvider [IMPLEMENTATION GATE ONLY]
        ↓
RepositoryReadObservation
        ↓
exact-revision verification + raw hash verification + redaction
        ↓
RepositoryContext
        ↓
ExecutionReceipt
```

`EpistemicToolBroker` remains a policy/admission boundary and does not dispatch tools. The executor requires both a canonical approved `GovernanceDecision` and an actual canonical `ExecutionPermit`; it does not create either authority object.

## Request binding

The repository permit request digest binds:

- repository;
- exact revision;
- semantic operation;
- path/query;
- sensitivity;
- principal;
- canonical gateway-policy hash;
- maximum response bytes.

The permit must also bind the exact repository, revision, and path in `resource_scope` and must match the executor's pre-bound ChangeSet hash.

## Exact revision

Repository reads require a 40- or 64-character hexadecimal revision. Floating names such as `HEAD`, `main`, `latest`, `current`, or a branch name are not admitted as runtime evidence revisions.

## Credential boundary

This implementation introduces only an opaque repository credential-capability abstraction.

Available implementations:

- `DeterministicCredentialResolver` — test-only, creates no real credential and records `credentials_used = 0`;
- `UnavailableCredentialResolver` — fail-closed placeholder.

`GitHubRepositoryReadPort` rejects live credential capabilities and rejects `live_external_reads_enabled=true` in this release gate.

No token, private key, Authorization header, PAT, GitHub App installation token, or other secret is represented in Nexus domain contracts, permits, repository contexts, provider prompts, articulation messages, or receipts.

Future production target:

```text
GitHub App
    ↓
repository-scoped installation
    ↓
short-lived installation token
    ↓
credential boundary
    ↓
GitHubRepositoryReadPort
```

Target permissions are `Metadata: Read` and `Contents: Read`; write permissions are outside this architecture.

## Existing GitHub adapter reuse

The implementation reuses `GovernedGitHubKernelAdapter` and preserves its sole capability:

`READ_REPOSITORY_STATE`

The adapter continues to reject mutation requests and reports `write_capability_present=false` and `production_activation_authorized=false`.

No unrestricted REST/GraphQL request primitive is introduced.

## Semantic operation surface

This implementation executes only:

`READ_FILE`

Other modeled repository operations remain fail-closed until separately implemented and validated.

## Gateway enforcement

`NexusRepositoryGateway` remains non-authoritative and enforces:

- explicit repository allowlist;
- explicit operation allowlist;
- explicit path-prefix allowlist;
- allowed sensitivity classes;
- exact hexadecimal revision;
- maximum response bytes;
- observation/request binding;
- raw-content SHA-256 verification;
- deterministic redaction;
- projected-content SHA-256;
- immutable `RepositoryContext` identity;
- `write_capability_present=false`.

The canonical gateway-policy hash is shared with the executor's permit-request digest calculation.

## Execution evidence

Mock successful reads produce the existing canonical `ExecutionReceipt` with:

- the actual `permit_id`;
- pre-bound `change_set_id` and `parent_state_hash`;
- `execution_status=succeeded`;
- the resulting `RepositoryContext` hash and context ID as evidence;
- `external_action_performed=false`.

That last field is intentionally false because the deterministic implementation does not issue a real network request.

A future live read must report `external_action_performed=true` after actual dispatch.

## Failure semantics

- missing/invalid authority → `not_started` or fail closed before transport;
- ToolBroker denial/emergency stop → `not_started`, provider call count remains zero;
- unavailable credential capability → deterministic `failed`, no network;
- unsupported operation → deterministic `failed`, no network;
- invalid observation/hash/revision/size → deterministic `failed`;
- future uncertain post-dispatch transport failure → must become `indeterminate`, require reconciliation, and prohibit blind automatic retry.

No live uncertain transport occurs in this implementation gate.

## Security invariants

Credential-like provider exceptions are redacted at the port boundary and the raw exception chain is suppressed before propagation.

Repository content remains `UNTRUSTED_REPOSITORY_CONTENT`, including source comments, README instructions, fake system messages, fake permits, and self-authorization language.

## Explicitly not authorized or implemented

- live GitHub network calls;
- real GitHub credential resolution/use;
- GitHub App private-key use;
- installation-token issuance;
- PAT use;
- repository mutation;
- generic GitHub API access;
- live Gemini/OpenAI calls;
- cloud mutation;
- production activation;
- external communication;
- financial spend.

## Side-effect target for this gate

```text
live_private_github_reads = 0
network_calls = 0
real_github_calls = 0
credentials_used = 0
repository_writes = 0
external_action_performed = false
incremental_spend_cad = 0.00
```

## Next release gate

After fresh exact-head CI admits this implementation, the only eligible external-read step is a separately authorized:

`RELEASE_GATE_ONE_LIVE_PRIVATE_GITHUB_READ_CANARY`

That canary must bind one exact CI-verified revision, one harmless allowlisted file, one repository, one read request, one short-lived repository-scoped GitHub App credential, zero write capability, and CAD 0.00 financial authority.
