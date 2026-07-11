# AIGC Principal Authority Binding Forge v1.1

Status: **procured / not implemented**  
Scope: **AIGC only**  
Base revision: `7acef921a39f76fb56f9df883d7597fa2b720d5f`  
External action performed: `false`

## 1. Evolution Diagnosis v+1

### Verified defect basis

The v1 kernel compares `request.tenant_id` with `request.resource.tenant_id` and performs the equivalent comparison for project scope. It does not establish that the actor belongs to that tenant or project. The actor's optional `tenant_id` is not used as an authority source. A policy is not bound to a principal, tenant, project, resource, role, membership, purpose, or revision. The session is not bound to a principal, membership, tenant, or project. Approval revision is not compared with the request revision. Revocation depends on a request-selected identifier. Purpose and context are absent. `int(...)` casts can raise rather than return a deterministic denial.

Architectural consequences:

- **Actor tenant ignored:** a principal from tenant B can submit a self-consistent tenant A request/resource pair.
- **Membership unresolved:** tenant/project authority is inferred from strings rather than an active grant.
- **Session unbound:** possession of a session identifier is not tied to a principal or membership.
- **Policy subject undefined:** any caller can present any policy object that grants the requested action.
- **Approval revision unmatched:** approval evidence may be replayed across changed requests or commits.
- **Revocation request-selected:** omission or substitution of a revocation identifier can bypass unrelated revoked authority.
- **Purpose/context absent:** policy cannot constrain why, where, or under which operational conditions an action occurs.
- **Malformed assurance conversion:** invalid values can produce exceptions rather than a fail-closed decision receipt.

A collection of matching strings is not an authority chain. Authority must be derived through resolvable, current, revision-bound relationships.

### Ontology health

Required first-class entities:

`Principal`, `PrincipalStatus`, `TenantMembership`, `ProjectMembership`, `RoleBinding`, `AuthorityGrant`, `PolicySubject`, `SessionBinding`, `Purpose`, `DecisionContext`, `ApprovalObligation`, `RevocationTarget`, `RequestDigest`, `PolicyRevision`.

Required relationship:

`principal -> active membership -> subject-bound session -> applicable policy -> tenant/project/resource/action/purpose/context -> obligations -> decision -> receipt`.

### Taxonomy refinements

Decision states: `PERMIT`, `DENY`, `REVIEW_REQUIRED`, `NOT_APPLICABLE`, `INDETERMINATE`.

Principal states: `PENDING`, `ACTIVE`, `SUSPENDED`, `REVOKED`, `EXPIRED`, `TERMINATED`, `COMPROMISED`, `INVALID`.

Session states: `PENDING`, `ACTIVE`, `STEP_UP_REQUIRED`, `IDLE_EXPIRED`, `ABSOLUTE_EXPIRED`, `REVOKED`, `TERMINATED`, `COMPROMISED`, `INVALID`.

Membership states: `PENDING`, `ACTIVE`, `EXPIRED`, `REVOKED`, `SUSPENDED`, `INVALID`.

Assurance axes: `IAL0-IAL3`, `AAL0-AAL3`, `FAL0-FAL3`, and evidence maturity `EA0_CLAIMED-EA5_PRODUCTION_OBSERVED`.

### Methodology correction

`contract-first design -> schema validation -> principal resolution -> membership resolution -> session binding -> policy applicability -> tenant/project/resource checks -> purpose/context checks -> assurance checks -> approval obligations -> revocation checks -> security/privacy hooks -> decision -> redacted receipt -> CI evidence`.

### Architecture integrity

The existing kernel remains a governed local simulator. v1.1 must introduce repository interfaces without introducing persistence or live identity:

- `PrincipalRepository`
- `MembershipRepository`
- `SessionRepository`
- `PolicyRepository`
- `RevocationRepository`
- `ApprovalRepository`
- `SecurityPrivacyAdapter`
- `ObserverAuthorityAdapter`

### Production readiness

This procurement does not change production readiness. The merged kernel remains local simulation. Production authentication, durable sessions, tenant administration, staging, recovery, and operational evidence remain absent. No numerical readiness increase is claimed until implementation, exact-head CI, reviewed merge, and exact-main verification exist.

### Dead logic, redundancy, and fragility

No executable module is proven dead. Fragile structures are self-asserted tenant/project scope, request-selected revocation, unbound sessions, unscoped policies, replayable approvals, and exception-producing malformed input. Redundant authority concepts should be consolidated behind one repository interface rather than deleted.

## 2. Contender Arena v+1

1. **Principal Authority Binding Guard** — bind principal, membership, session, policy, and approval. Highest direct security value and bounded scope.
2. **Full Kernel v1.1** — add purpose, context, obligations, assurance axes, and richer decision states. Stronger completeness but larger review surface.
3. **Shared Contract Enforcement Repair** — standards-complete schemas and discriminated payloads. Essential substrate, but does not alone fix tenant authority.
4. **Transactional Identity Spine** — SQLite-backed state. Durable but unsafe before authority semantics are stable.
5. **Security/Observer Adapter Bridge** — connect existing governance controls. Valuable successor after principal binding.
6. **Readiness Ledger Reconciliation** — measurable progress only after behavioral evidence exists.
7. **Production Identity Provider** — deferred; authenticating a person does not fix unbound authorization semantics.

Winning synthesis: principal binding + contract validation + exact-revision approvals + deterministic revocation + mutation tests + later persistence.

## 3. Auto-Design Output v+1

### Principal

A stable subject record with `principal_id`, `actor_reference`, `principal_status`, assurance axes, authority source, evidence references, validity interval, and revocation version.

### TenantMembership

Binds one principal to one tenant with status, roles, scopes, validity, policy revision, grants, evidence, and revocation state.

### ProjectMembership

Binds one tenant membership to explicit projects with project-local roles, scopes, validity, and evidence.

### RoleBinding

Maps role identifiers to scopes and policy selectors; roles never directly imply unrestricted authority.

### AuthorityGrant

Represents an explicit, scoped, revision-bound grant with issuer, subject, tenant, project, resource selector, actions, purposes, validity, and revocation target.

### PolicySubject

Defines which principals, roles, memberships, tenants, and projects a policy may govern.

### SessionBinding

Binds a session to principal, membership, tenant, active project, assurance, lifecycle state, and revocation version.

### Purpose

Controlled purpose identifier plus description and permitted data/action categories.

### DecisionContext

Bounded environmental context: channel, device class, network class, jurisdiction, time, risk signals, and operator mode. No raw credentials or unnecessary personal data.

### ApprovalObligation

Defines approval class, eligible actor types, independence rule, exact request digest, exact revision, expiry, and evidence requirements.

### RevocationTarget

Typed target: `principal`, `membership`, `session`, `grant`, `approval`, or `policy`.

### RequestDigest

SHA-256 of canonical authorization-request JSON excluding mutable receipt fields.

### PolicyRevision

Strong revision reference with kind, value, observed time, and compatibility state.

## 4. Auto-Engineer Output v+1

### Evaluation pipeline

1. Validate request, principal, membership, session, policy, approval, and revocation contracts.
2. Resolve principal and require `ACTIVE` state.
3. Resolve active tenant membership.
4. Resolve required project membership.
5. Bind session to principal and membership.
6. Select only policies whose subject selectors match.
7. Compare tenant, project, resource, action, scope, purpose, and context.
8. Evaluate assurance cross-product: identity, authentication, federation, evidence maturity.
9. Resolve approval obligations and exact request/revision binding.
10. Resolve revocations independently of request-selected identifiers.
11. Call Security & Privacy Wiring pre-decision hook for sensitive/external paths.
12. Call Observer Authority adapter when observer access is implicated.
13. Produce `PERMIT`, `DENY`, `REVIEW_REQUIRED`, `NOT_APPLICABLE`, or `INDETERMINATE`.
14. Redact and persist only minimum-necessary receipt metadata.

### Evidence maturity scoring

`EA0`: claimed only; `EA1`: schema-valid; `EA2`: semantic tests; `EA3`: CI-executed; `EA4`: staging observed; `EA5`: production observed. A permit cannot claim maturity above the least mature mandatory evidence input.

### Denial and hold reason catalogue

`UNKNOWN_PRINCIPAL`, `PRINCIPAL_NOT_ACTIVE`, `TENANT_MEMBERSHIP_MISSING`, `TENANT_MEMBERSHIP_INACTIVE`, `PROJECT_MEMBERSHIP_MISSING`, `SESSION_PRINCIPAL_MISMATCH`, `SESSION_MEMBERSHIP_MISMATCH`, `SESSION_TENANT_MISMATCH`, `SESSION_PROJECT_MISMATCH`, `SESSION_NOT_ACTIVE`, `POLICY_SUBJECT_MISMATCH`, `POLICY_TENANT_MISMATCH`, `POLICY_PROJECT_MISMATCH`, `POLICY_REVISION_MISMATCH`, `RESOURCE_TENANT_MISMATCH`, `RESOURCE_PROJECT_MISMATCH`, `ACTION_NOT_ALLOWED`, `SCOPE_NOT_GRANTED`, `PURPOSE_NOT_ALLOWED`, `CONTEXT_NOT_ALLOWED`, `INSUFFICIENT_IAL`, `INSUFFICIENT_AAL`, `INSUFFICIENT_FAL`, `INSUFFICIENT_EVIDENCE_MATURITY`, `APPROVAL_MISSING`, `APPROVAL_CLASS_MISMATCH`, `APPROVAL_REVISION_MISMATCH`, `APPROVAL_REQUEST_DIGEST_MISMATCH`, `APPROVAL_EXPIRED`, `APPROVAL_REVOKED`, `SELF_APPROVAL_NOT_INDEPENDENT`, `PRINCIPAL_REVOKED`, `MEMBERSHIP_REVOKED`, `SESSION_REVOKED`, `GRANT_REVOKED`, `POLICY_REVOKED`, `SECURITY_PRIVACY_REVIEW_REQUIRED`, `OBSERVER_AUTHORITY_REQUIRED`, `MALFORMED_REQUEST`, `INDETERMINATE_AUTHORITY`.

## 5. Auto-Architect Output v+1

`Authorization Request Validator -> Principal Resolver -> Membership Resolver -> Session Binding Gate -> Policy Applicability Engine -> Authorization Decision Kernel -> Security/Privacy Adapter -> Observer Authority Adapter -> Redacted Receipt`.

Adapter interfaces:

- `resolve_principal(principal_id) -> PrincipalRecord | None`
- `resolve_memberships(principal_id, tenant_id) -> list[MembershipBinding]`
- `resolve_session(session_id) -> SessionBinding | None`
- `select_policies(subject, resource, action) -> list[AccessPolicy]`
- `resolve_revocations(targets) -> list[RevocationRecord]`
- `evaluate_security_privacy(context) -> AdapterDecision`
- `evaluate_observer_authority(context) -> AdapterDecision`

Future SQLite migration must implement repository interfaces without changing kernel semantics. Future identity-provider adapters may establish authenticated subjects, but may not create tenant/project authority without membership evidence.

Threat-model hooks must cover confused deputy, tenant substitution, project substitution, session theft, policy injection, approval replay, stale membership, revocation bypass, and receipt leakage.

Future UI must target WCAG 2.2 AA: keyboard operation, visible focus, semantic statuses, non-color-only decisions, understandable denial reasons, accessible authentication, and confirmation before consequential actions.

## 6. Cognitive Review v+1

The defect is an authority-model flaw, not merely a missing comparison. Request consistency cannot establish principal entitlement. Authentication, when later added, would prove who the caller is; it would still not prove what tenant, project, policy, or purpose the caller may use. The v1.1 boundary must therefore stabilize authorization semantics before persistence or live authentication.

## 7. Societal Logic Integration v+1

Principal, membership, session, approval, and receipt records must minimize personal information, identify purpose, support correction and revocation, and preserve accountable human oversight for consequential work or employment workflows. Authorization success grants a bounded system action; it does not authorize employment, financial, legal, or other consequential outcomes. Accessible denial and review interfaces remain mandatory.

## 8. Final Synthesis v+1

Implement a subject-bound local authorization simulator in which a permit requires a resolvable active principal, membership, session, policy, purpose/context match, valid assurance, current approvals, and no applicable revocation. Preserve IAL0/AAL0/FAL0 and local-simulation labels until real identity and operational evidence exist.

## 9. Next Implementation Step v+1

Implement **Principal Authority Binding Guard v1.1** as a separate reviewed PR. No persistence, credentials, live identity, deployment, or external action is in scope.

## 10. Procurement Success Packet v+1

### Evidence paths

- `governance/schemas/identity/*.schema.json`
- `governance/identity/local_identity_simulation.json`
- `governance/identity/local_access_policy_registry.json`
- `src/core/identity/*.py`
- `tests/test_principal_authority_binding.py`
- `artifacts/identity/principal_authority_binding_receipt.json`
- exact-head CI run and exact-main post-merge receipt

### Synthetic fixture sets

- tenant A principal with project A membership;
- tenant B principal with tenant B membership;
- suspended, expired, revoked, and compromised principals;
- active and inactive memberships;
- active, expired, revoked, wrong-principal, wrong-tenant, and wrong-project sessions;
- subject-bound and mismatched policies;
- valid, expired, revoked, replayed, and self-issued approvals;
- typed revocations for principal, membership, session, grant, approval, and policy.

### CI gates

Schema meta-validation; fixture validation; principal/membership/session binding tests; policy applicability tests; approval replay tests; revocation tests; purpose/context tests; malformed-input fail-closed tests; adapter regression tests; full repository tests; AEC-001 validation; redaction scan; readiness evaluation; receipt upload.

### Readiness-ledger constraint

No readiness mutation occurs on branch creation or documentation. After reviewed merge and exact-main behavioral evidence, `production_identity_access` may move from `unimplemented` to `partial`, while the production blocker remains active. CI must calculate the score; no hand-authored score is authoritative.

### Operator review checklist

- exact base and head revisions recorded;
- no credentials or real personal identities;
- principal-to-membership binding proven;
- session ownership proven;
- policy subject and revision proven;
- approval request digest and revision proven;
- request-selected revocation bypass impossible;
- malformed inputs deny without exception;
- adapters preserve existing hard blocks;
- rollback is one bounded revert;
- independent reviewer is distinct from implementer where required.

## 11. Workflow Procurement Procedure v+1

`intake -> evidence verification -> scope lock -> contract-first design -> implementation plan -> security/privacy wiring -> mutation tests -> CI -> operator review -> independent review -> merge decision -> exact-main verification -> readiness-ledger update`.

## 12. Engine Evolution v+1

Add **Subject-Binding Mutation Preflight**. The evolution engine must mutate actor, tenant, project, membership, session, policy, approval, purpose, context, and revocation identifiers and prove every unauthorized substitution is rejected by the evidence-producing pathway.

## 13. Next-Run Directive v+1

Inspect only this train:

1. Verify current `main` and branch base.
2. Verify operator authorized the implementation scope.
3. Verify all six contract schemas exist and meta-validate.
4. Verify synthetic fixtures contain no personal data or secrets.
5. Verify principal-to-tenant membership binding.
6. Verify project membership binding.
7. Verify session principal/membership/tenant/project binding.
8. Verify policy subject, tenant, project, purpose, context, and revision binding.
9. Verify approval class, revision, request digest, expiry, revocation, and independence.
10. Verify revocation is resolved independently of request-selected IDs.
11. Verify malformed input returns deterministic denial.
12. Verify Security & Privacy and Observer Authority adapter boundaries.
13. Verify mutation matrix coverage and artifacts.
14. Verify exact-head CI and retain artifacts according to repository policy.
15. Require a distinct qualified identity/security reviewer for ready-for-review transition.
16. Require operator merge approval with expected-head protection.
17. Preserve rollback by one squash-revert and superseding receipts.
18. Update readiness only after exact-main evidence; retain production blocker.

Decision rule:

If principal, membership, session, policy, approval, purpose/context, and revocation bindings are enforced; all mutation tests reject unauthorized substitutions; CI passes; and qualified review exists, advance to operator merge decision. Otherwise keep the PR draft and do not add persistence, live identity, or production access.