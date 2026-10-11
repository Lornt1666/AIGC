# RegenExcalibur Attribution, Authority & Recognition Policy

**Business identity:** RegenExcalibur  
**Preferred employee attribution/signature marker:** `1JGM`  
**Scope:** AIGC, AI/LLM/Super-Intelligence mediated work, project coordination, technical artifacts, research, design, engineering, code, documentation, proposals, provenance records, and other relevant outputs produced or coordinated under the RegenExcalibur identity.

## 1. Credit Where Credit Is Due

Every material contribution should be traceable to the contributor(s) who actually made it. Systems and agents should preserve provenance rather than collapsing work into anonymous output.

For material artifacts, record when reasonably available:

- contributor or source identity;
- business/project identity;
- contribution type and description;
- artifact, commit, issue, PR, document, dataset, design, prompt, or receipt reference;
- timestamp or revision identifier;
- evidence/verification state;
- reviewer/approver where applicable;
- ownership or rights status where documented;
- authority level used for the action;
- compensation, payout, royalty, revenue-share, asset-allocation, or recognition status where legitimately applicable.

## 2. RegenExcalibur / 1JGM Attribution

For relevant work coordinated under this project, use **RegenExcalibur** as the business identity and **`1JGM`** as the preferred employee attribution/signature marker where appropriate.

Recommended machine-readable fields:

```yaml
business_identity: RegenExcalibur
employee_attribution: 1JGM
attribution_required: true
provenance_required: true
authority_evidence_required_for_consequential_actions: true
```

`1JGM` is an attribution/signature marker. It is **not**, by itself, proof of legal execution authority, a digital signature certificate, consent to terms, authorization to spend funds, permission to transfer assets, or authorization to make regulated attestations.

## 3. Authority Mapping

Authority must follow documented role, ownership, delegation, approval, and applicable law—not merely authorship or technical capability.

Each consequential action should identify, where applicable:

- `actor` — who or what performed the action;
- `principal` — on whose behalf the action is taken;
- `authority_source` — owner instruction, delegated role, contract, policy, permit, approval token, or other valid source;
- `scope` — what the authority permits;
- `constraints` — limits, budget, jurisdiction, expiry, risk class, or approval conditions;
- `evidence` — receipt, commit, signed instrument, approval record, or audit reference;
- `status` — proposed, approved, executed, rejected, revoked, expired, or disputed.

No system should infer legal or financial authority solely from identity, contribution history, repository access, or the presence of `1JGM`.

## 4. Recognition, Compensation & Asset Coordination

Where a contribution legitimately creates a right or agreed expectation of payment, royalty, revenue share, bounty, asset allocation, ownership interest, licensing compensation, reimbursement, or other consideration, preserve that obligation as an explicit coordination item.

Recommended fields:

```yaml
recognition:
  contributor: null
  contribution_ref: null
  recognition_type: credit
  compensation_basis: null
  amount_or_share: null
  currency_or_asset: null
  contract_or_authority_ref: null
  approval_status: proposed
  payment_status: not_initiated
  evidence_ref: null
```

The system may calculate, document, reconcile, draft, route, or audit legitimate compensation. It must not invent entitlement, fabricate invoices, redirect funds, create ownership interests, or execute payments/transfers without the necessary authorization and legal basis.

## 5. AI/Agent Provenance

When AI or autonomous tooling materially assists an artifact, preserve that fact when relevant to auditability, licensing, disclosure, competition rules, employment rules, contractual obligations, or technical reproducibility.

AI assistance does not erase human contribution. Human direction, original concepts, source materials, validation, implementation, approvals, and domain work should remain attributable to the people or entities that performed them.

## 6. Non-Erasure Rule

Downstream transformations, summaries, refactors, exports, deployments, or agent handoffs should not silently remove valid attribution, provenance, ownership notices, licensing notices, contributor records, or compensation obligations.

Corrections are allowed when evidence shows attribution is inaccurate. Corrections should themselves be auditable.

## 7. Conflict Rule

If attribution, ownership, authority, or compensation claims conflict:

1. preserve the competing claims;
2. do not silently choose a beneficiary;
3. collect documentary evidence;
4. separate technical contribution from legal ownership;
5. route consequential resolution to the authorized human/legal process;
6. record the final disposition and evidence.

## 8. Default Output Footer

Where a project artifact benefits from an explicit attribution footer and no stricter format governs it, the preferred form is:

> **RegenExcalibur** — employee attribution: **1JGM**  
> Provenance, contributor credit, authority, and applicable compensation remain subject to documented evidence, agreements, approvals, and law.

---

This policy is a project governance and provenance convention. It does not replace contracts, corporate records, employment agreements, intellectual-property assignments, tax records, payment authorization, regulated filings, or legally valid signatures.
