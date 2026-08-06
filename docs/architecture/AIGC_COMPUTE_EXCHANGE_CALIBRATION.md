# AIGC Compute Exchange — Calibration and Outcome Learning

Status: CANONICAL ARCHITECTURE CONTRACT — RUNTIME IMPLEMENTATION DEFERRED

## Purpose

The Compute Exchange is not a cheapest-route selector. It is a governed procurement and learning system that selects the **BEST-FIT ADMISSIBLE EXECUTION PORTFOLIO FOR THE EMPLOYER'S OUTCOME**, observes what actually happened, and improves future portfolio predictions without weakening hard constraints.

## Hard admission before optimization

A candidate resource or portfolio is excluded before scoring when it fails any required capability, quality floor, confidentiality, security, privacy, jurisdiction/data-location, licensing, employer policy, deadline feasibility, availability, or budget-ceiling constraint. Optimization weights cannot purchase exceptions to these gates.

## Canonical feedback objects

### ComputeBenchmark
Evidence about a resource/model/tool on a bounded workload class. Fields should include benchmark_id, workload_class, resource identity/version, environment, jurisdiction, dataset/fixture digest, quality metric, verification result, latency distribution, resource usage, cost observation, timestamp, and evidence digest.

### ExecutionPortfolio
The selected heterogeneous set of resources for a task/work order, including ordered or parallel stages, fallbacks, budgets, employer policy binding, confidentiality class, jurisdiction policy, verification route, and immutable component identities where possible.

### PortfolioPrediction
The pre-execution forecast for an ExecutionPortfolio: predicted quality, acceptance probability, completion probability, latency, compute/tool/model usage, monetary cost, verification-pass probability, deadline confidence, reliability, and material risk assumptions.

### ComputePerformanceObservation
Observed stage-level measurements: actual resource/model/tool version, actual latency, actual usage, actual cost where evidenced, quality measurement, verifier result, failure/retry state, jurisdiction receipt where applicable, and evidence references.

### PortfolioOutcome
The post-execution aggregate outcome: delivered/not delivered, verification status, employer acceptance when available, revision count, actual total cost, deadline result, security/privacy/confidentiality incidents, observed quality, prediction error, and evidence digest.

## Prediction versus observation

For every material prediction retain the paired observation when measurable:

- predicted_quality ↔ observed_quality;
- predicted_cost ↔ actual_cost;
- predicted_latency ↔ actual_latency;
- predicted_completion_probability ↔ actual_result;
- predicted_token_usage ↔ actual_token_usage;
- predicted_cpu/gpu/runtime ↔ actual resource usage;
- predicted_verification_pass_probability ↔ actual_verification_result;
- predicted_deadline_confidence ↔ actual deadline result;
- predicted_acceptance_probability ↔ employer acceptance/revision outcome when available.

Unknown observations remain UNKNOWN. Never fabricate a measurement merely to close a feedback loop.

## Calibration

Maintain calibration/error statistics by workload class, resource/model/tool version, employer policy class, confidentiality class, and verification strategy where sample sizes are sufficient. Model/provider updates invalidate or age prior evidence according to explicit freshness policy.

A resource that is inexpensive but systematically underperforms required quality must lose selection probability. A resource that is expensive but materially improves accepted employer value may be preferred when the engagement policy supports it.

## Portfolio optimization

The Exchange should reason over Pareto-efficient portfolios rather than collapse all objectives into one universal scalar where practical. Engagement policy may prioritize quality, deadline, confidentiality, reliability, employer preference, resource efficiency, expected margin, or other lawful objectives after hard admission.

Cost is therefore contextual: minimize waste and protect sustainable margin, but do not minimize cost at the expense of the employer's required outcome.

## Verified Employer Value

A long-run decision metric may compare verified employer value against total economic, computational, and risk cost, but employer value must be evidence-backed rather than invented. Candidate signals include acceptance criteria passed, employer acceptance, revision burden, deadline performance, measurable deliverable quality, repeat engagement, and contract-defined outcome metrics.

No single formula is canonical until validated against real engagements. The canonical requirement is multi-objective, constraint-preserving, evidence-calibrated procurement.

## Confidentiality and learning boundary

Employer-specific observations remain inside the EmployerVault unless policy permits sanitized aggregation. Cross-employer learning must never expose proprietary content, secrets, identifiers, prompts, documents, embeddings, or deliverables. Aggregation must meet privacy/confidentiality policy before entering global benchmark evidence.

## Authority

This contract performs no provider procurement, cloud mutation, live model call, financial commitment, employer action, or autonomous external execution. Runtime implementation requires separate schemas, tests, exact-head CI, security review, and authority.