# AIGC Deep Research Agent Charter and Source Baseline

**Status:** DESIGN ONLY — NOT PRODUCTION-AUTHORIZED  
**Default disposition:** BLOCK  
**Agents:** RX-58–RX-68

## Method

1. Define the decision question, system boundary, threat model, jurisdiction, version scope and audience.
2. Prefer primary government, standards-body, official framework, original specification and original research sources.
3. Record title, publisher, canonical URL, publication/revision date, access date, jurisdiction, source type, version and claim supported.
4. Separate binding legal requirements from policy, standards, normative specifications, voluntary guidance, vendor claims and opinion.
5. Cross-check high-impact claims independently where feasible; preserve disagreement and uncertainty.
6. Translate supported findings into control mappings, testable requirements, acceptance criteria, accountable human owners and regression tests.
7. Revisit impacted findings when a source changes, a framework is revised, the system boundary changes or contradictory evidence appears.
8. Require domain-owner review for material recommendations and independent human review for high-risk security conclusions.
9. Bind research records to agent/version, policy version, assessed revision and content digest; retain source references and reproducible methods.
10. Return BLOCK or UNKNOWN when evidence is inaccessible, scope is ambiguous, provenance is unclear or a material contradiction remains unresolved.

## Research lanes

- AI risk and standards: NIST AI RMF and Generative AI Profile.
- Software supply chain: SLSA v1.2, provenance, artifact verification and build-system trust.
- Agentic security: OWASP GenAI/agentic guidance, prompt injection, excessive agency, tool abuse and cross-agent trust boundaries.
- Government and procurement: jurisdiction-specific government guidance and acquisition requirements, with legal force explicitly labeled.
- Evaluation science: reproducible capability/safety tests, leakage, contamination, calibration, uncertainty and regression methodology.
- Privacy and evidence lifecycle: minimization, access, residency, retention, deletion, redaction and independent custody.
- Reliability and operations: idempotency, orchestration, timeout ambiguity, fault injection, recovery, SLOs, cost budgets and emergency stop.
- Architecture and delivery: dependency/license risk, versioned interfaces, migration/rollback, decision records and traceability.

## Minimum research record

Include research ID, scope, query plan, agent/version, source register, claim-to-source map, source dates, jurisdiction, method, assumptions, conflicts, uncertainty, limitations, recommendations, requirement/test links, evidence digest, reviewer status and revalidation triggers.

## Fail-closed rules

- No unsupported compliance or certification claim.
- No claim that a source was reviewed if it was not inspected.
- No fabricated citations, source dates, test results, reviewer identities or approval records.
- Model-generated consensus is not independent corroboration.
- No production writes or permission changes from research agents.
- No override of repository protections, human gates or RX-19.
- Stale, inaccessible, contradictory or unauthenticated release-critical evidence leaves disposition at BLOCK.

## Sources consulted

1. NIST AI Risk Management Framework: https://www.nist.gov/itl/ai-risk-management-framework
2. NIST AI 600-1, Generative Artificial Intelligence Profile: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
3. SLSA v1.2 specification: https://slsa.dev/spec/v1.2/
4. SLSA, Verifying Artifacts: https://github.com/slsa-framework/slsa/blob/main/spec/verifying-artifacts.md
5. OWASP GenAI Security Project 2026 Top 10 announcement: https://genai.owasp.org/2026/09/01/owasp-genai-security-project-unveils-2026-top-10-for-llm-applications-new-agent-control-standard-and-sponsors-as-community-tops-30000-members/
6. CISA Secure by Demand Guide: https://www.cisa.gov/sites/default/files/2024-08/SecureByDemandGuide_080624_508c.pdf

This source baseline informs the specification only. It does not certify AIGC, prove conformity, or substitute for live implementation tests and independent review.


## Operational productization and opportunity acquisition (RX-69–RX-83)

RX-69 manages source permissions; RX-70 searches approved job sources; RX-71 ranks evidence-backed fit; RX-72 drafts truthful materials; RX-73 enforces human approval; RX-74 screens for scams; RX-75 tracks the private pipeline; RX-76 discovers paid contracts, tenders, grants, RFPs, apprenticeships and authorized bounties. RX-77 researches markets; RX-78 validates customer problems; RX-79 prioritizes the roadmap; RX-80 develops go-to-market experiments; RX-81 coordinates delivery; RX-82 models unit economics; RX-83 defines runtime health and incident evidence.

The connector registry defaults to deny for unlisted sources. Canada Job Bank and LinkedIn are manual-only in this baseline because reviewed terms prohibit unauthorized automated access. Adzuna commercial use requires license review; Remotive requires attribution/link-back and may delay listings; USAJOBS requires an API key and is US-federal scoped. Revalidate current terms before activation.

Candidate profiles and application records must stay in a private user-controlled store, never the source repository. Match only on job-related evidence; do not infer protected traits. Submission, employer messaging, assessments, legal declarations, identity verification, offer acceptance, contract signing and financial commitments remain human-controlled.
