# AIGC Algorithmic Capability Fabric

## Purpose

The Algorithmic Capability Fabric gives every AIGC agent, phase, pipeline, and methodology layer an explicit governed capability contract.

It is not an authorization bypass. It does not grant credentials, platform access, contract authority, payment authority, deployment authority, or client-delivery authority.

## Capability Contract

Every capability must declare:

- capability id
- applicable phases and agent roles
- algorithm family
- methodology lenses
- ontology targets
- input contracts
- output contracts
- allowed uses
- forbidden uses
- risk controls
- required tests
- human review requirement
- external action default

The default external action value is always false.

## Methodology Lenses

AIGC applies capabilities through these lenses:

- ontology
- epistemology
- methodology
- praxeology
- axiology
- teleology
- semiotics
- cybernetics
- systems theory
- ethics
- legal review
- security review
- operations
- customer success

These lenses are used to make the system more explicit and inspectable. They are not a license to perform hidden actions.

## Current Capability Families

- opportunity ranking and fit scoring
- job ingestion and normalization
- best-practice synthesis
- deep work decomposition
- learning measures and outcome feedback
- governed agent-team design
- policy and risk gate
- uncertainty-aware quality kernel

## Agent Binding

Phase 19 sub-agent team members and Phase 24 business agents now include algorithmic capability metadata. This makes each agent's allowed internal reasoning methods visible in generated records.

Each agent capability remains bounded by:

- no hidden human impersonation
- no credential abuse
- no platform-rule bypass
- no automatic contract acceptance
- no automatic payment request
- no unchecked outward action
- no secret exfiltration

## Governance Boundary

Algorithmic capabilities may:

- rank internal opportunities
- extract requirements from approved sources
- synthesize best practices with source traceability
- decompose work into tasks and tests
- assign internal agent roles
- score quality and uncertainty
- recommend review, repair, deny, or handoff readiness

Algorithmic capabilities may not:

- contact clients
- submit work
- accept contracts
- request payment
- deploy services
- push code
- use credentials
- bypass platform policy
- claim hidden human identity

External action requires a separate approval path and exact scoped authorization.

## Test Expectations

Tests must prove:

- the manifest validates against `schemas/algorithmic_capability_manifest.schema.json`
- every capability requires human review
- every capability defaults external action to false
- every capability contains the full forbidden-use set
- generated agent records include capability metadata
- no generated capability grants self-approval

## File Map

- `src/core/algorithmic_capabilities.py`
- `schemas/algorithmic_capability_manifest.schema.json`
- `tests/test_algorithmic_capability_fabric.py`
- `src/phase19_subagent_forge.py`
- `src/phase24_autonomic_business_pipeline.py`
