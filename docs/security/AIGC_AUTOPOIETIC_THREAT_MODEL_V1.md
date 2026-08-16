# AIGC Autopoietic Ecosystem Threat Model V1

## Security objective

Permit bounded local improvement without allowing the improving system to manufacture authority, conceal effects, corrupt evidence, exfiltrate data, escape resource limits or rewrite the constitution that governs it.

## Protected assets

- operator authority and revocations;
- constitutional policy;
- exact repository lineage;
- objective and acceptance contracts;
- secrets and credential references;
- canonical state and memory;
- evidence and receipt chains;
- model, dataset and adapter provenance;
- financial and compute budgets;
- external accounts and communication channels;
- availability of kill switch and rollback paths.

## Trust boundaries

1. **Operator boundary:** only a verified human/operator process may issue consequential authority.
2. **Candidate boundary:** synthesized code/configuration is untrusted until independently verified.
3. **Verifier boundary:** verifier outputs are evidence, never execution permits.
4. **Adapter boundary:** every external capability is denied unless an exact adapter and permit are present.
5. **Telemetry boundary:** observations require source lineage and freshness.
6. **Synthetic-data boundary:** self-generated information is quarantined from independent evidence.
7. **Canonical-state boundary:** local shadow state cannot silently become authoritative state.

## Principal threats and controls

| Threat | Control | Residual risk |
|---|---|---|
| Self-issued authority | Policy literals disable self-authority; consequential effects return `AWAITING_OPERATOR` | A future adapter could be implemented incorrectly; must be separately certified |
| Approval replay | Exact request/revision binding, expiry in existing Nexus permits, idempotency ledger | Distributed persistence is not yet implemented in this slice |
| Stale state or telemetry | Exact state and repository hash checks | Source authenticity beyond local evidence requires authenticated telemetry adapters |
| Receipt tampering | Canonical SHA-256 receipt and exact predecessor chain | Hashes do not prove identity without later signing |
| Producer self-verification | Producer/verifier identity inequality and hard gate | Colluding models may share failure modes; diversity evidence is required later |
| Prompt/config injection | Strict closed contracts, unknown-property rejection, effect classification | Semantic attacks inside permitted text still need modality-specific defenses |
| Raw secret ingestion | Sensitive-key and credential-pattern rejection | Pattern detection is not a complete secret scanner |
| Network exfiltration | Reference kernel contains no network adapter and reports zero calls | Future model/tool adapters create a new egress boundary |
| Subprocess or sandbox escape | Reference executor is pure in-memory logic | Container/WASM isolation is future work |
| Resource exhaustion | Sealed operation, compute, memory, output and cycle budgets | Python host resource enforcement is logical, not OS-level cgroup enforcement |
| Infinite recursion/loop | Every cycle terminates; candidate operation graph must be acyclic | External agent runtimes need their own time and recursion limits |
| Synthetic-data collapse | Synthetic evidence cannot count as independent evidence | Dataset-level contamination analysis is future work |
| Metric gaming | Multiple weighted metrics, hard security gate, independent verification | Fitness design can still be incomplete or miss real-world harms |
| Optimizer-induced safety regression | Effect gate, rollback, minimum fitness delta and immutable policy | Unmeasured properties may regress; expand test oracles before promotion |
| Supply-chain compromise | Planned lockfiles, SBOM, provenance, signatures and exact-head CI | Not completed by this slice |
| Adapter substitution | Adapter manifests, capability/effect gates and evidence refs | Cryptographic adapter identity and signed manifests are future work |
| Split-brain state | Exact parent hash and receipt predecessor | Durable compare-and-swap backend is future work |
| Kill-switch bypass | Evaluated before deficit formulation and execution | Distributed propagation is future work |
| Hidden external effect | Local reference has no external ports and fixed zero counters | Future adapters must reconcile actual provider receipts, not self-reported counters |
| Rollback failure | Automatic eligibility requires rollback-supported reversible operations | True external rollback may be compensating rather than restoring |
| Financial escalation | Financial effect is operator-required and absent from local executor | Financial integrations remain high risk and separately governed |
| Unlawful autonomous governance | Constitution remains human governed and non-self-amendable | Legal/compliance review remains jurisdiction-specific |

## Abuse cases explicitly denied

- bypassing authentication, MFA or CAPTCHA;
- harvesting or exposing credentials;
- modifying payment methods or spending without exact authorization;
- autonomous employer contact or job application submission;
- accepting contracts, terms, privacy consent or legal attestations;
- publishing, merging, deploying or enabling public traffic without fresh authority;
- weaponization, offensive intrusion or destructive infrastructure changes;
- silently training on private or restricted data;
- claiming independent verification from a common self-generated evidence chain.

## Security acceptance gates before any external adapter

1. Adapter manifest and source reviewed.
2. Exact effect class and resource scope sealed.
3. Egress allowlist and DNS/redirect protections tested.
4. Raw-secret redaction and metadata-only receipts verified.
5. One-use permit consumption atomic and replay-tested.
6. Indeterminate outcome reconciliation implemented.
7. Rollback or compensating action tested.
8. Tenant and principal isolation tested.
9. Audit receipts independently resolvable.
10. Kill switch demonstrated at the execution boundary.
11. Security scanner, dependency scan and SBOM pass.
12. Fresh operator approval binds the exact revision and action.

## Current security disposition

The local V1 kernel demonstrates policy and logic controls, not production isolation. It performs zero external effects and is therefore intentionally safer than a partially connected “autonomous” runtime. Networked adapters, distributed persistence, OS sandboxing, signatures and production deployment remain unproven.
