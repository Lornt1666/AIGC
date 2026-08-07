# REGENEXCALIBUR :: OMNI-FORGE-Ω∞

## Status

**GOVERNED EXECUTION SUBSTRATE — DRAFT — NO EXTERNAL EXECUTION AUTHORITY**

AIGC's Digital Work Colosseum is the canonical product and domain ontology.
OMNI-FORGE is the deterministic engineering and execution substrate used
through the canonical AIGC planes. It is not a competing constitutional model
for Employer, EmployerVault, Engagement, WorkOrder, Task, AgentCell, Swarm,
Deliverable, Verification, CapabilityEvidence or ComputeRequirement.

OMNI-FORGE's mythology is an interface; repository evidence is the law. It is
not omniscient and does not automatically produce production-ready software.
An artifact may be classified as a production candidate only after
compilation, adversarial testing, security review, exact-head hosted CI,
immutable deployment receipts, recovery evidence and explicit human
authorization.

## Canonical compatibility boundary

`src/omni_forge/colosseum_compat.py` provides the smallest current-main
compatibility surface:

- canonical Colosseum typed contracts remain owned by `src/colosseum`;
- Employer and Task are identifier anchors until canonical typed contracts are
  introduced there;
- exact object relationships, employer isolation, authorization scopes,
  classifications, jurisdictions, tools and budgets are verified fail-closed;
- repository commit SHA, tested tree SHA, schema digest and idempotency digest
  remain bound to one repository-only authorization packet;
- OMNI-FORGE does not duplicate or redefine the canonical product ontology.

## Preserved implementation

This increment retains:

- typed agent-invocation boundaries;
- deterministic execution lifecycle transitions;
- graph validation for cycles, schemas, authorization and idempotency;
- bounded token, cost and three-attempt repair budgets;
- exact commit/tree-bound authorization packets;
- immutable hash-chained evidence receipts;
- JSON schemas and adversarial regression tests;
- a dedicated pull-request-triggered exact-head CI gate.

It does not add:

- an iOS application or Swift package;
- App Attest, signing, archive or TestFlight evidence;
- Cloud Run deployment or Google Cloud resource creation;
- live Gemini or other live-model calls;
- production activation or public access;
- employer communication or Gmail sending;
- GitHub merge or automatic-merge authority;
- App Store upload, publication or submission authority;
- financial authority.

## Invariants

1. No unvalidated transition produces an external effect.
2. Every external operation requires exact authorization.
3. Every artifact binds to commit SHA, tree SHA, schema version and digest.
4. Every external retry is idempotent or classified as uncertain.
5. Every secret reference is purpose-bound and version-pinned.
6. Every agent output crosses a typed schema boundary.
7. Every canonical execution binds one Employer, EmployerVault, Engagement,
   WorkOrder, Task, AgentCell, Swarm, Deliverable, Verification,
   CapabilityEvidence and ComputeRequirement context.
8. EmployerVault confidentiality and jurisdiction policy cannot be weakened by
   an invocation, Swarm or ComputeRequirement.
9. Every future deployment must use an immutable image digest.
10. Every production claim requires runtime evidence.
11. No jurisdiction claim exceeds provider receipts.
12. No repair bypasses testing, review or authorization.
13. Evidence receipts cannot grant authority.
14. Synthetic pull-request merge refs cannot satisfy exact-head admission.

## Authority state

```text
repository_analysis=true
architecture_generation=true
code_generation=true
test_generation=true
pull_request_creation=true

cloud_resource_creation=false
deployment=false
production_activation=false
public_access=false
live_model_calls=false
financial_actions=false
automatic_merge=false
merge=false
app_store_submission=false
```

## Admission rule

Keep the pull request draft and unmerged. Require a complete governed diff
review and a fresh pull-request-triggered exact-head hosted CI receipt for the
post-convergence head.

Admission evidence must retain:

- requested pull-request head SHA;
- observed checkout SHA;
- tested tree SHA;
- focused OMNI-FORGE and complete repository test results;
- schema, dependency, compilation and redaction results;
- canonical exact-SHA validation results;
- comprehensive false-authority receipt;
- exact-head-scoped artifact ID, size and SHA-256 digest.

CI success authorizes governed review only. It grants no merge, deployment,
cloud, model, publication, financial or App Store authority.
