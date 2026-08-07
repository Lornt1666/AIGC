from __future__ import annotations

from datetime import datetime, timezone
import unittest

from src.colosseum.compute_exchange import (
    ComputeAdmission,
    ComputeCandidate,
    ComputePerformanceObservation,
    ComputeRequirement,
    ExecutionPortfolio,
    PortfolioOutcome,
    PortfolioPrediction,
    ResourceType,
)
from src.colosseum.domain import (
    AgentCell,
    CapabilityEvidence,
    CapabilityVerdict,
    ConfidentialityClass,
    Deliverable,
    EmployerVault,
    Opportunity,
    Swarm,
    Verification,
    VerificationStatus,
    WorkLedger,
    WorkLedgerEntry,
)

NOW = datetime(2026, 8, 6, 20, tzinfo=timezone.utc)


class DomainContractTests(unittest.TestCase):
    def test_employer_vault_rejects_cross_employer_access(self) -> None:
        with self.assertRaises(ValueError):
            EmployerVault(
                vault_id="vault-a",
                employer_id="employer-a",
                confidentiality_class=ConfidentialityClass.CONFIDENTIAL,
                allowed_jurisdictions=("CA-QC",),
                retention_policy_id="retain-a",
                deletion_policy_id="delete-a",
                cross_employer_retrieval=True,
            )

    def test_remote_opportunity_cannot_require_physical_presence(self) -> None:
        with self.assertRaises(ValueError):
            Opportunity(
                opportunity_id="opp-1",
                source_id="source-1",
                employer_id="employer-1",
                title="Remote role",
                digitally_executable=True,
                physical_presence_required=True,
                legitimacy_status="LEGITIMATE_HIGH_CONFIDENCE",
                capability_requirements=(),
            )

    def test_swarm_agent_limits_must_fit_swarm_budget(self) -> None:
        cell = AgentCell(
            agent_cell_id="cell-1",
            role="Researcher",
            allowed_tools=("search",),
            allowed_data_scopes=("vault-a",),
            output_schema_id="schema-1",
            maximum_cost_cad=20,
            maximum_tokens=1000,
        )
        with self.assertRaises(ValueError):
            Swarm(
                swarm_id="swarm-1",
                engagement_id="eng-1",
                work_order_id="wo-1",
                objective="Research",
                agent_cells=(cell,),
                compute_budget_cad=10,
                token_budget=2000,
                confidentiality_class=ConfidentialityClass.CONFIDENTIAL,
                jurisdiction_policy_id="qc-only",
                verification_policy_id="verify-independent",
                emergency_stop_epoch=0,
            )

    def test_successful_verification_requires_evidence(self) -> None:
        with self.assertRaises(ValueError):
            Verification(
                verification_id="ver-1",
                deliverable_id="del-1",
                verifier_identity="verifier-1",
                status=VerificationStatus.PASS,
                checks=("criterion-1",),
                evidence_refs=(),
            )

    def test_verified_capability_requires_evidence(self) -> None:
        with self.assertRaises(ValueError):
            CapabilityEvidence(
                capability_evidence_id="cap-1",
                discipline="Software Engineering",
                skill="Python",
                verdict=CapabilityVerdict.VERIFIED_CAPABLE,
                benchmark_ids=("bench-1",),
                accepted_deliverable_ids=(),
                validated_attempts=1,
                successful_attempts=1,
                human_review_required=False,
                evidence_refs=(),
                last_verified_at=NOW,
            )

    def test_work_ledger_keeps_human_agent_compute_clocks_separate(self) -> None:
        entry = WorkLedgerEntry(
            event_id="event-1",
            work_order_id="wo-1",
            actor_id="agent-1",
            resource_id="cpu-1",
            started_at=NOW,
            ended_at=NOW,
            human_active_seconds=60,
            agent_active_seconds=120,
            compute_seconds=300,
        )
        totals = WorkLedger(work_order_id="wo-1", entries=(entry,)).totals
        self.assertEqual(totals["human_active_seconds"], 60)
        self.assertEqual(totals["agent_active_seconds"], 120)
        self.assertEqual(totals["compute_seconds"], 300)


class ComputeExchangeContractTests(unittest.TestCase):
    def requirement(self) -> ComputeRequirement:
        return ComputeRequirement(
            requirement_id="req-1",
            workload_class="research",
            minimum_quality=0.9,
            minimum_reliability=0.9,
            maximum_latency_ms=10_000,
            maximum_cost_cad=10.0,
            confidentiality_class=ConfidentialityClass.CONFIDENTIAL,
            allowed_jurisdictions=("CA-QC",),
            required_capabilities=("research",),
        )

    def candidate(self, **overrides: object) -> ComputeCandidate:
        values = dict(
            candidate_id="candidate-1",
            provider="provider-a",
            resource_type=ResourceType.AI_MODEL,
            model_or_runtime="model-a",
            region="northamerica-northeast1",
            jurisdiction="CA-QC",
            confidentiality_capability=ConfidentialityClass.CONFIDENTIAL,
            encryption="TLS+AER",
            estimated_cost_cad=3.0,
            estimated_latency_ms=2000,
            predicted_quality=0.95,
            predicted_reliability=0.96,
            availability=0.99,
            commercial_use_allowed=True,
            benchmark_evidence_refs=("bench-1",),
            capabilities=("research",),
            admission=ComputeAdmission.ADMISSIBLE,
            rejection_reasons=(),
        )
        values.update(overrides)
        return ComputeCandidate(**values)

    def test_cost_cannot_override_jurisdiction_gate(self) -> None:
        cheap_wrong_region = self.candidate(
            estimated_cost_cad=0.01,
            jurisdiction="US",
        )
        self.assertFalse(cheap_wrong_region.satisfies(self.requirement()))

    def test_cost_cannot_override_quality_floor(self) -> None:
        cheap_low_quality = self.candidate(
            estimated_cost_cad=0.01,
            predicted_quality=0.4,
        )
        self.assertFalse(cheap_low_quality.satisfies(self.requirement()))

    def test_cost_cannot_override_commercial_license(self) -> None:
        candidate = self.candidate(commercial_use_allowed=False)
        self.assertFalse(candidate.satisfies(self.requirement()))

    def test_admissible_candidate_can_satisfy_requirement(self) -> None:
        self.assertTrue(self.candidate().satisfies(self.requirement()))

    def test_not_admissible_requires_reasons(self) -> None:
        with self.assertRaises(ValueError):
            self.candidate(
                admission=ComputeAdmission.NOT_ADMISSIBLE,
                rejection_reasons=(),
            )

    def test_observed_measurement_requires_evidence(self) -> None:
        with self.assertRaises(ValueError):
            ComputePerformanceObservation(
                observation_id="obs-1",
                portfolio_id="portfolio-1",
                candidate_id="candidate-1",
                observed_at=NOW,
                actual_cost_cad=1.5,
                actual_latency_ms=None,
                actual_quality=None,
                actual_token_usage=None,
                actual_cpu_seconds=None,
                actual_gpu_seconds=None,
                verification_passed=None,
                jurisdiction_receipt_ref=None,
                evidence_refs=(),
            )

    def test_portfolio_prediction_and_outcome_remain_distinct(self) -> None:
        portfolio = ExecutionPortfolio(
            portfolio_id="portfolio-1",
            work_order_id="wo-1",
            requirement_ids=("req-1",),
            candidate_ids=("candidate-1",),
            stage_order=("research", "verify"),
            fallback_candidate_ids=(),
            employer_policy_id="policy-1",
            verification_route_id="verify-1",
            predicted_total_cost_cad=3.0,
            admitted=True,
        )
        prediction = PortfolioPrediction(
            prediction_id="prediction-1",
            portfolio_id=portfolio.portfolio_id,
            predicted_quality=0.95,
            predicted_acceptance_probability=0.9,
            predicted_completion_probability=0.95,
            predicted_verification_pass_probability=0.9,
            predicted_deadline_confidence=0.9,
            predicted_cost_cad=3.0,
            predicted_latency_ms=2000,
            predicted_token_usage=1000,
            predicted_cpu_seconds=60,
            predicted_gpu_seconds=None,
            assumptions=("benchmark current",),
        )
        outcome = PortfolioOutcome(
            outcome_id="outcome-1",
            portfolio_id=portfolio.portfolio_id,
            delivered=True,
            verification_passed=True,
            employer_accepted=None,
            revision_count=0,
            actual_total_cost_cad=2.5,
            deadline_met=True,
            observed_quality=0.97,
            security_incident=False,
            privacy_incident=False,
            confidentiality_incident=False,
            evidence_refs=("receipt-1",),
        )
        self.assertNotEqual(prediction.predicted_cost_cad, outcome.actual_total_cost_cad)


if __name__ == "__main__":
    unittest.main()
