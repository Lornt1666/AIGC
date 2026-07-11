# AIGC Review Authority and External Assurance Policy

## Status

Proposed policy for review through PR #41. This policy does not claim that an AI system is a human reviewer and does not create independent human approval where no distinct person exists.

## Purpose

Define truthful, risk-based review pathways for a solo-operated repository while preserving evidence integrity, operator accountability, security, confidentiality, and future separation of duties.

## Review authority classes

AIGC recognizes five distinct review events:

1. **Automated Verification** — deterministic tests, schemas, CI, security scans, and evidence checks.
2. **AI Advisory Review** — machine-generated analysis and recommendation bound to an exact revision.
3. **Operator Ratification** — explicit approval by the accountable repository owner/operator.
4. **Independent External Assurance Review** — review supplied by a separate provider, contractor, organization, or service under documented terms. This may be human-led, AI-assisted, or automated, but its actual nature must be disclosed.
5. **Independent Human Review** — reasoned review by a distinct real person using their own attributable identity.

These classes are never interchangeable in records or public claims.

## Prohibited representation

AIGC shall not:

- describe an AI agent as a human;
- describe author/operator approval as independent;
- describe a service-generated comment as a required human approval;
- purchase or solicit a predetermined approval;
- conceal the model, provider, operator, conflict, or limitations of an external assurance source;
- infer legal liability merely because a tool generated a recommendation.

## Solo-Operator Alternative Assurance Path

Where no eligible second human reviewer is reasonably available, a bounded change may proceed through the Solo-Operator Alternative Assurance Path only when all mandatory conditions are satisfied.

### Mandatory conditions

- exact base and head revision are recorded;
- required CI and negative tests pass on the exact head;
- an AI Advisory Review produces `RECOMMEND_APPROVE` or equivalent, with evidence and limitations;
- an independent analysis source distinct from the authoring session is used where technically and contractually available;
- all blocking findings are resolved or explicitly rejected with operator rationale;
- the operator signs an explicit risk acceptance and merge-ratification record;
- rollback is defined and practical;
- post-merge verification and observation are mandatory;
- no credentials, production deployment, irreversible data mutation, cross-tenant access, or external consequential action is introduced;
- the change is clearly labelled as using alternative assurance rather than independent human review.

### Ineligible changes

The alternative path cannot authorize:

- production deployment or release-critical changes;
- handling of real credentials or secret material;
- material privacy or regulated-data changes;
- real payment, contracting, legal filing, or external communication authority;
- destructive or irreversible migrations;
- disabling or weakening the Security & Privacy Wiring Gate;
- claims of certification, regulatory approval, or independent human assurance;
- any change whose governing policy explicitly requires a real independent human.

### Decision record

The merge record must state:

```text
Review path: SOLO_OPERATOR_ALTERNATIVE_ASSURANCE
Independent human review: NOT PERFORMED
AI advisory review: PERFORMED / NOT PERFORMED
External assurance provider: name or NONE
Operator risk acceptance: RECORDED
Exact head SHA: <sha>
Post-merge verification: REQUIRED
```

## Risk classification

### LOW

Documentation, formatting, non-executable metadata, and reversible internal-only changes. Required: CI where applicable, AI advisory review, operator ratification.

### MODERATE

Local executable changes with no credentials, external actions, production data, or irreversible effects. Required: full CI, negative tests, Review Packet, AI advisory review, operator ratification, post-merge verification. Independent human review is preferred.

### HIGH

Identity, authorization, security, privacy, persistence migrations, external connectors, consequential workflows, or architecture controls. Required: domain review plus independent human review unless a formally approved, scope-limited exception exists and the change remains non-production and reversible.

### RELEASE_CRITICAL

Production deployment, real users, regulated or sensitive data, credentials, payments, legal commitments, or irreversible operations. Independent human review and explicit operator authorization are mandatory. The solo-operator alternative path is prohibited.

## Independent External Assurance Provider

An external assurance provider may supply additional analysis but must not be misrepresented as a human reviewer unless a named human actually performs and signs the review.

### Provider due diligence

Before repository access or data transfer, record:

- legal entity and responsible contact;
- service description and whether review is human, AI-assisted, or automated;
- hosting and data-processing locations;
- retention, training-use, deletion, and subprocessors;
- security controls and incident notification;
- access scopes and technical isolation;
- ownership of inputs, outputs, findings, and derivative material;
- confidentiality and permitted-use terms;
- liability, indemnity, warranty, and limitation-of-liability terms;
- termination, deletion certification, and audit/evidence rights;
- conflict of interest and competitive-use restrictions.

### Contractual IP and confidentiality controls

AIGC should require, subject to legal review:

- a written NDA/confidentiality agreement;
- use solely for the defined review engagement;
- no model training, benchmarking, publication, resale, or reuse of private repository material without written permission;
- no disclosure to subprocessors except approved and equivalently bound parties;
- pre-existing IP remains with its original owner;
- AIGC architecture, frameworks, prompts, schemas, documentation, code, and undisclosed ideation remain the operator's confidential material;
- review findings and engagement deliverables are assigned or licensed to the operator on agreed terms;
- prompt return/deletion of repository copies and derived confidential material;
- incident notification and cooperation duties;
- appropriate indemnity for unauthorized disclosure, misuse, infringement, or security breach, subject to negotiated limits and applicable law;
- injunctive-relief language where appropriate;
- governing law, venue, dispute process, and survival clauses.

No policy can guarantee recovery. Enforceability, damages, and remedies depend on the contract, evidence, jurisdiction, provider assets, and applicable law. Legal counsel should review material engagements.

## Technical protection controls

Contractual terms supplement rather than replace technical controls:

- grant time-limited, least-privilege access;
- expose only the files needed for the review;
- use a review branch or sanitized export when possible;
- remove secrets and unrelated personal data;
- watermark or uniquely identify disclosure packages where practical;
- log access, downloads, reviews, and revocation;
- disable forking and unnecessary repository permissions where supported;
- revoke access immediately after the engagement;
- preserve evidence of exactly what was disclosed;
- avoid sharing patent-sensitive or trade-secret material beyond necessity.

## AI review tools

AI review tools may provide fast feedback and automated analysis. Their output is advisory evidence. Provider terms, privacy controls, retention, training use, security posture, and repository permissions must be evaluated before use.

An AI review service may be recorded as an `INDEPENDENT_EXTERNAL_ASSURANCE_SOURCE` when it is operated by a distinct provider and its analysis is independently generated. It is never recorded as `INDEPENDENT_HUMAN_REVIEW` unless a distinct named human actually reviews and signs the decision.

## PR #29 bootstrap treatment

PR #29 predates ratified AEC-001 and this policy. The operator may choose one of two truthful paths:

### Path A — Strict human independence

Obtain a distinct human review and then merge after all gates pass.

### Path B — Solo-Operator Alternative Assurance bootstrap

Record explicitly that independent human review was not performed; run the strongest available advisory review and exact-head CI; document findings, risk acceptance, rollback, and mandatory post-merge verification; then perform an operator-controlled merge using expected-head protection.

Path B changes the governance requirement. It does not retroactively create independent human approval.

## Required evidence for Path B

- exact PR #29 head SHA;
- passing CI bound to that SHA;
- Review Packet and AI advisory recommendation;
- zero unresolved blocking findings;
- operator risk acceptance statement;
- confirmation that PR #29 only measures readiness and does not deploy, use credentials, grant access, or perform external actions;
- expected-head protected merge;
- CI and readiness receipt on the resulting `main` revision;
- rollback procedure;
- issue record noting the governance bootstrap and future human-review target.

## Policy amendment rule

Future amendments require a dedicated reviewed PR, rationale, impact analysis, rollback, version update, and operator ratification. A policy amendment must never be used to conceal a failed control or falsify historical evidence.
