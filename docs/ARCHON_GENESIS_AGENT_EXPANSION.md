# ARCHON-GENESIS — AIGC Agent Expansion

**Status:** Design-time compiler and proposed agent portfolio; not production activated.  
**Version:** archon-genesis/1.0  
**Decision authority:** Release Assurance Agent remains the sole canonical release authority.

## Mission

ARCHON-GENESIS turns an approved AIGC brief into a deterministic architecture proposal: minimal agent roster, responsibility boundaries, interface contracts, dependency topology, failure-mode analysis (FMEA), epistemic ledger, and an implementation runbook. It is a compiler for agent designs, not a super-agent with unrestricted execution authority.

## Why these agents

The repository already contains governance and phase-based agent concepts, a Governor policy layer, CI validation roles, an exact-head acceptance gate, and constellation/security-governance components. The new portfolio is deliberately complementary rather than duplicating the Governor or Release Assurance Agent.

| Agent | Responsibility | Primary outputs |
|---|---|---|
| Context & Evidence Curator | Consolidates project context, source claims, prior decisions, and unknowns | Evidence map, decision register, unknowns |
| Architecture & Contract Engineer | Converts requirements into topology, typed inputs/outputs, invariants, acceptance criteria | Architecture proposal, interface contracts |
| Dependency & Change Sentinel | Maps affected modules and invalidates evidence after changes | Dependency graph, change-impact report |
| Red Team Assurance Agent | Adversarially challenges assumptions, prompt-injection surfaces, privilege boundaries, and failure modes | Findings, negative-test catalogue |
| Blue Team Controls Engineer | Specifies least privilege, identity boundaries, audit controls, secrets handling, recovery | Control matrix, identity contract |
| Validation & Evidence Engineer | Defines exact-SHA/tree/run/artifact binding and deterministic acceptance tests | Test plan, evidence contract |
| Observability & Incident Steward | Defines audit events, drift detection, alerting, pause, incident response, and recovery | Telemetry contract, incident runbook |
| Independent Contract & Completeness Verifier | Checks consistency and completeness without authoring the design it reviews | Verification report, blockers, human-review packet |

## Executive, holding-company, and board-level agent house

The compiler's default portfolio now contains 25 proposed roles: eight technical/assurance roles and 17 executive or enterprise stewardship roles. These are bounded advisory agents, not a replacement for accountable human executives or the existing Governor.

| Agent | Executive mandate | Boundary |
|---|---|---|
| CEO Strategy & Enterprise Steward | Strategy, priorities, trade-offs, executive scorecard | Cannot override Governor, human approval, or Release Assurance |
| Chief of Staff & Executive Coordination | Cross-functional coordination, decisions, dependencies, escalation | Cannot collapse independent reviews |
| COO Delivery & Operations | Operating plans, service measures, capacity and recovery | No unapproved side effects |
| CFO Finance & Capital Steward | Cost, budget, cash exposure, scenario analysis | Cannot spend or commit funds |
| CTO Engineering & Technology Architecture | Engineering standards, technical roadmap, reliability trade-offs | Cannot bypass security or release gates |
| CIO Platform & Information Systems | Platform, integration, identity, continuity and data-flow mapping | No broad access grants |
| CISO Security & Privacy | Security/privacy controls, identity boundaries, incident escalation | Security veto recommendations require the designated human/governance process |
| Chief AI & Model Governance | Model inventory, evaluations, oversight and drift | Cannot self-certify model fitness |
| Chief Risk & Compliance | Risk taxonomy, controls, compliance mapping and escalation | Cannot approve its own exceptions |
| Chief Legal & Regulatory Review | Legal/regulatory issue spotting and counsel routing | Not a substitute for qualified legal advice |
| Chief Data & Provenance | Data lineage, quality, retention, provenance | Cannot fabricate provenance or alter audit history |
| Chief Product & Customer Outcomes | User needs, product metrics, acceptance criteria | Cannot redefine accepted scope without approval |
| Chief Investment & Portfolio Strategy | Portfolio fit, synergies, concentration and capital scenarios | No transactions or investment execution |
| Corporate Development & Strategic Partnerships | Partnership/M&A research and due-diligence preparation | No outreach, negotiation or transactions |
| Board & Governance Secretariat | Board packets, governance calendar, reserved-matter routing | Drafts only; no board decision impersonation |
| Internal Audit & Independent Assurance | Independent control sampling and remediation validation | Must remain independent of control ownership |
| People, Talent & Organizational Capability | Competency, training, staffing and oversight-capacity analysis | No autonomous employment decisions |

The existing Governor remains responsible for policy eligibility and escalation. The CEO agent prioritizes within approved strategy; the Chief of Staff coordinates; specialist executives provide bounded recommendations; independent audit verifies controls; the human owner remains accountable. Release Assurance remains the single canonical software-release decision authority.

## Ordered workflow

1. Chief of Staff records the task, scope, owner, constraints, and acceptance criteria.
2. ARCHON-GENESIS compiles the approved brief deterministically.
3. Independent contract gate checks schema, uniqueness, dependencies, cycles, and authority boundaries.
4. AER evaluates trustworthiness, evidence quality, and risk proportionality.
5. Red Team produces adversarial challenges.
6. Blue Team maps mitigations and least-privilege controls; Red and Blue must not collapse into a single self-review.
7. Green Team may propose bounded remediation, but changes require the normal approval and change-control process.
8. Independent verifier reviews the final candidate and evidence.
9. Authorized human records explicit acceptance.
10. Release Assurance evaluates release evidence and makes the only canonical release decision.

## Contracts and invariants

- Inputs and outputs are named and versioned.
- Every agent has a stable ID, a single primary mission, declared dependencies, and explicit capabilities.
- Unknown, inferred, observed, and proposed information remain distinct.
- Retrieved content is untrusted data, not instructions.
- Missing, stale, contradictory, mismatched, or unauthenticated evidence blocks acceptance.
- No agent can grant itself authority, authenticate its own identity, approve its own material exception, or rewrite accepted audit history.
- Use read-only/draft-only permissions by default. Side effects require external authorization and human confirmation appropriate to risk.
- Credentials, signing private keys, and trust-root private material must never be stored in the repository.
- Logs and evidence must be retained outside the control of the agent being monitored.
- Every workflow must support pause, revocation, budget limits, and recoverability.

## Implementation

The compiler is pure Python and deterministic. It performs no network calls, model calls, repository writes, or agent execution. Run it from the repository root:

    PYTHONPATH=src python -c "import json; from pathlib import Path; from archon_genesis import compile_architecture, render_report; b=json.loads(Path('config/archon_genesis_aigc_brief.json').read_text()); r=compile_architecture(b); Path('reports/ARCHON_GENESIS_PROPOSAL.json').write_text(json.dumps(r, indent=2)+'\\n'); Path('reports/ARCHON_GENESIS_PROPOSAL.md').write_text(render_report(r))"

Run its tests:

    PYTHONPATH=src python -m unittest discover -s tests -p 'test_archon_genesis.py' -v

## FMEA

| Failure mode | Risk | Required control |
|---|---|---|
| Prompt injection in retrieved material | High | Treat source as data, provenance, adversarial tests, no instruction inheritance |
| Role collision or privilege escalation | Critical | Capability allowlists, independent identities, external authorization, no self-approval |
| Stale/mismatched evidence | High | Bind to exact SHA, tree, run, artifact digest, and expiry |
| Runaway loop or cost | High | Step/time/token/tool budgets, circuit breaker, operator pause |
| Audit alteration | High | Append-only externally retained logs and independent access |
| Approval fatigue | Medium | Risk-tiered approvals, concise diffs, escalation, sampled audits |

## Acceptance gate

The output is a proposal, not proof of readiness. Before activation: tests must pass on the exact proposed commit; interfaces must be reviewed; the threat model and controls must be accepted; independent verification must complete; human acceptance must be recorded; and canonical Release Assurance must evaluate the evidence. This compiler cannot mark a release ready.
