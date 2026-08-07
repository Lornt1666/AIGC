# AIGC Governed Orchestration Bundle

Status: orchestration-kernel V1 admission contract; planning only.

## Purpose

A green scheduler result is not execution authority. Before any future executor may consume a `SwarmPlan`, the plan must be enclosed in a `GovernedOrchestrationBundle` that binds the exact policy, Definitions of Done, Task DAG, plan, capability evidence, human qualification evidence, professional credential evidence, role-specific qualification requirements, evaluation time and false-authority state.

That bundle must then be enclosed in an `OrchestrationAdmissionEnvelope` containing the exact authorized `WorkOrder`. The envelope independently proves the engagement binding and that every task Definition of Done covers every WorkOrder requirement and acceptance criterion.

## Semantic evidence binding

Evidence identifiers alone are insufficient. The bundle rejects:

- capability references that do not resolve to the same skill and verdict;
- specialist assignments without an active role-bound human qualification;
- regulated assignments without an active role-bound professional credential;
- credentials whose profession or credential class does not match the selected role;
- qualifications or credentials bound to a different human identity;
- evidence outside an effective-policy jurisdiction;
- expired, revoked or unverified evidence;
- human or licensed review without the applicable role-bound evidence;
- dangling evidence references;
- altered canonical records or authority escalation.

The final admission envelope additionally rejects an unauthorized WorkOrder, a different engagement, a different work-order identity, or incomplete Definition-of-Done coverage.

## Persistence and evidence

The governed bundle and final admission envelope are deterministic, SHA-256 bound and round-trip reconstructable. Component contracts remain separately validated against their strict schemas, while the composition schemas validate capability evidence, qualification evidence, role requirements, the complete WorkOrder and the false-authority envelopes.

## Resource ceilings

Compute, cost, token, latency, privacy, security, confidentiality, jurisdiction, provider, model, tool and licensing controls remain hard admission constraints. A zero compute-time ceiling means zero permitted compute; it is never interpreted as an unlimited allowance.

The exact-head CI contract validates:

1. dependency consistency;
2. Python compilation;
3. repository contracts;
4. orchestration schemas, including the governed bundle and WorkOrder admission envelope;
5. orchestration round trips, including both evidence envelopes;
6. repository redaction;
7. release-surface secret scanning;
8. offline procurement smoke;
9. mock provider discovery;
10. inert Terraform;
11. focused Colosseum tests and the complete repository suite;
12. false-authority invariants against the final envelope;
13. readiness.

## Authority

This contract grants no execution, external action, job application, employer communication, contract acceptance, provider/model call, cloud mutation, invoice transmission, payment, merge, deployment, financial action or App Store action.
