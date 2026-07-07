# AIGC Public Research Procurement Matrix

## Purpose

This matrix records the public research basis for missing AIGC architecture layers before those layers are procured into implementation.

Procurement here means architecture contracts, schemas, tests, and controlled implementation plans. It does not mean purchasing services, configuring accounts, installing external systems, reading credentials, or executing live actions.

## Research Boundary

The research scan used publicly available, authoritative sources:

- NIST AI Risk Management Framework
- NIST Secure Software Development Framework
- OWASP Top 10 for LLMs and Gen AI Apps
- OpenAI Agents SDK documentation
- LangGraph interrupt documentation
- Temporal workflow execution documentation
- Prefect workflow orchestration documentation
- SLSA software supply-chain requirements
- NIST post-quantum cryptography standards

## Source Matrix

| Source ID | Source | Type | Safe Borrow | Avoid |
|---|---|---|---|---|
| `src_nist_ai_rmf` | NIST AI Risk Management Framework | official standard | Govern, Map, Measure, Manage risk lifecycle | treating the framework as a one-time checklist |
| `src_nist_ssdf` | NIST SSDF SP 800-218 | official standard | secure development practices and vulnerability response | shipping without security requirements or review |
| `src_owasp_llm_top10` | OWASP LLM / GenAI Top 10 2025 | official security project | prompt-injection, sensitive-information, and excessive-agency controls | relying on prompt text as the only security boundary |
| `src_openai_agents_sdk` | OpenAI Agents SDK docs | official product docs | guardrails, handoffs, sessions, tracing, resumable approvals | tool execution without tool guardrails |
| `src_langgraph_interrupts` | LangGraph interrupts docs | official product docs | pause/resume state and human-in-the-loop checkpoints | resuming external action without permit revalidation |
| `src_temporal_workflow_execution` | Temporal workflow execution docs | official product docs | durable execution, event history, retries, signals, timers | retrying unapproved external actions |
| `src_prefect_docs` | Prefect docs | official product docs | flow monitoring, task retries, state tracking | treating observability as approval |
| `src_slsa_requirements` | SLSA requirements | official supply-chain framework | provenance, attestation, authenticity | releasing without verifiable provenance |
| `src_nist_pqc` | NIST post-quantum cryptography standards | official cryptographic standard | ML-KEM, ML-DSA, SLH-DSA migration targets | inventing custom cryptography |

## Missing Layers Identified

| Layer | Priority | Current Status | Procurement Action |
|---|---:|---|---|
| Public research provenance matrix | P0 | procured as catalog | instantiate source-ranked catalog before future layer work |
| AI RMF Govern/Map/Measure/Manage control plane | P0 | procured as local contract | add AI risk-control mappings and tests |
| Input/tool/output guardrail mesh | P0 | procured as local contract | define tool guardrail policies for every function/tool invocation |
| Human interrupt and resumable approval state | P0 | procured as local contract | add interrupt records and permit revalidation on resume |
| Durable workflow execution readiness | P1 | procured as local contract | design Temporal-ready event-history records |
| Data workflow and evidence observability | P1 | procured as local contract | design Prefect-ready evidence refresh records |
| Supply-chain provenance and release attestation | P0 | procured as local contract | add release provenance, SBOM guidance, and signing plan |
| Prompt-injection and excessive-agency red-team harness | P0 | procured as local contract | add adversarial fixtures that attack the approval boundary |
| Privacy, retention, and data-classification layer | P0 | procured as local contract | add retention classes and data-boundary contracts |
| Cost, rate-limit, and unbounded-consumption guard | P1 | procured as local contract | add budgets, max steps, token ceilings, and tripwires |
| Vetted post-quantum crypto provider integration plan | P1 | procured as provider-selection contract | keep envelope plan; require vetted provider before real crypto claims |
| Buyer tenant isolation and workspace boundary | P1 | procured as local contract | add tenant IDs, storage partitions, and export filters |

## Non-Negotiable Procurement Blocks

The catalog blocks procurement of:

- hidden human impersonation
- credential abuse
- platform-rule bypass
- automatic contract acceptance
- automatic payment request
- unchecked outward action

These remain hazards to detect, block, and audit. They are not build targets.

## Files

- `src/core/public_research_procurement.py`
- `schemas/public_research_procurement_catalog.schema.json`
- `tests/test_public_research_procurement.py`
