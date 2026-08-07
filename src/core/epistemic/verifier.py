from __future__ import annotations

from hashlib import sha256
import json

from src.core.epistemic.canonicalization import canonical_json_bytes, canonical_sha256
from src.domain.epistemic.models import ArtifactState, Claim
from src.domain.epistemic.verification import (
    UtilityScore,
    UtilityWeights,
    VerifierFinding,
    VerifierReport,
)


class DeterministicEpistemicVerifier:
    """Pure read-only verifier for epistemic state transitions.

    No model calls, embeddings, network calls, file writes, tool calls, or artifact
    modification occur here. Every reported metric is deterministic from the supplied
    baseline and target states.
    """

    def __init__(self, *, weights: UtilityWeights, utility_threshold: float = 0.0) -> None:
        if not -1.0 <= utility_threshold <= 1.0:
            raise ValueError("utility_threshold must be between -1.0 and 1.0")
        self.weights = weights
        self.utility_threshold = float(utility_threshold)

    def evaluate(self, baseline: ArtifactState, target: ArtifactState) -> VerifierReport:
        baseline_hash = canonical_sha256(baseline)
        target_hash = canonical_sha256(target)
        active_claims = self._active_claims(target.claims)

        findings = list(self._audit_fidelity(baseline, target))
        findings.extend(self._audit_claims(active_claims))
        findings.extend(self._audit_redundancy(target))

        f = self._fidelity_score(baseline, target)
        e = self._evidence_coverage(active_claims)
        c = self._structural_completeness(target)
        r = self._redundancy_score(target)
        x = self._unsupported_claim_score(active_claims)
        total = (
            self.weights.fidelity * f
            + self.weights.evidence * e
            + self.weights.completeness * c
            - self.weights.redundancy * r
            - self.weights.unsupported * x
        )
        total = max(-1.0, min(1.0, total))

        falsified = sum(1 for claim in active_claims if claim.verification_state == "falsified")
        unverified = sum(1 for claim in active_claims if claim.verification_state == "unverified")
        hard_failure = any(finding.severity in {"error", "critical"} for finding in findings)
        passing = not hard_failure and unverified == 0 and total >= self.utility_threshold

        score = UtilityScore(
            total_score=total,
            semantic_fidelity_f=f,
            evidence_coverage_e=e,
            structural_completeness_c=c,
            redundancy_r=r,
            unsupported_claims_x=x,
        )
        report_payload = {
            "verifier_id": "deterministic_epistemic_verifier_v2",
            "baseline_state_hash": baseline_hash,
            "target_state_hash": target_hash,
            "active_claim_ids": [claim.id for claim in active_claims],
            "findings": [finding.model_dump(mode="json") for finding in findings],
            "utility_score": score.model_dump(mode="json"),
            "utility_threshold": self.utility_threshold,
            "hard_failure": hard_failure,
            "unverified_claims": unverified,
            "is_passing": passing,
        }
        report_id = "VRF-" + sha256(
            json.dumps(
                report_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()[:24].upper()

        return VerifierReport(
            baseline_state_hash=baseline_hash,
            target_state_hash=target_hash,
            report_id=report_id,
            total_claims_audited=len(target.claims),
            unverified_claims=unverified,
            falsified_claims=falsified,
            findings=tuple(findings),
            utility_score=score,
            utility_threshold=self.utility_threshold,
            hard_failure=hard_failure,
            is_passing=passing,
        )

    @staticmethod
    def _active_claims(claims: tuple[Claim, ...]) -> tuple[Claim, ...]:
        superseded_ids = {claim.supersedes for claim in claims if claim.supersedes is not None}
        return tuple(claim for claim in claims if claim.id not in superseded_ids)

    @staticmethod
    def _objects_by_id(items: tuple) -> dict[str, object]:
        return {item.id: item for item in items}

    def _audit_fidelity(
        self,
        baseline: ArtifactState,
        target: ArtifactState,
    ) -> tuple[VerifierFinding, ...]:
        findings: list[VerifierFinding] = []
        for kind, before_items, after_items in (
            ("ENTITY", baseline.entities, target.entities),
            ("CLAIM", baseline.claims, target.claims),
            ("RELATION", baseline.relations, target.relations),
        ):
            before = self._objects_by_id(before_items)
            after = self._objects_by_id(after_items)
            for identifier, original in before.items():
                replacement = after.get(identifier)
                if replacement is None:
                    findings.append(
                        VerifierFinding(
                            code=f"{kind}_DROPPED",
                            severity="critical",
                            message=f"Baseline {kind.lower()} {identifier} is absent from target state.",
                            claim_ids=(identifier,) if kind == "CLAIM" else (),
                            entity_ids=(identifier,) if kind == "ENTITY" else (),
                        )
                    )
                elif canonical_json_bytes(original) != canonical_json_bytes(replacement):
                    findings.append(
                        VerifierFinding(
                            code=f"{kind}_MUTATED_IN_PLACE",
                            severity="critical",
                            message=f"Baseline {kind.lower()} {identifier} changed while retaining its identifier.",
                            claim_ids=(identifier,) if kind == "CLAIM" else (),
                            entity_ids=(identifier,) if kind == "ENTITY" else (),
                        )
                    )
        return tuple(findings)

    @staticmethod
    def _audit_claims(claims: tuple[Claim, ...]) -> tuple[VerifierFinding, ...]:
        findings: list[VerifierFinding] = []
        for claim in claims:
            if claim.verification_state == "falsified":
                findings.append(
                    VerifierFinding(
                        code="FALSIFIED_CLAIM_PRESENT",
                        severity="critical",
                        message=f"Claim {claim.id} is explicitly falsified.",
                        claim_ids=(claim.id,),
                        evidence_refs=claim.falsification_evidence_refs,
                    )
                )
            if claim.verification_state == "unverified":
                findings.append(
                    VerifierFinding(
                        code="UNVERIFIED_ACTIVE_CLAIM",
                        severity="warning",
                        message=f"Active claim {claim.id} remains unverified.",
                        claim_ids=(claim.id,),
                    )
                )
            if claim.basis in {"observation", "simulation"} and not claim.evidence_refs:
                findings.append(
                    VerifierFinding(
                        code="EMPIRICAL_CLAIM_WITHOUT_EVIDENCE",
                        severity="warning",
                        message=f"Active empirical claim {claim.id} has no evidence reference.",
                        claim_ids=(claim.id,),
                    )
                )
        return tuple(findings)

    @staticmethod
    def _audit_redundancy(artifact: ArtifactState) -> tuple[VerifierFinding, ...]:
        findings: list[VerifierFinding] = []
        normalized_names: dict[str, list[str]] = {}
        for entity in artifact.entities:
            normalized_names.setdefault(" ".join(entity.name.lower().split()), []).append(entity.id)
        for name, identifiers in normalized_names.items():
            if name and len(identifiers) > 1:
                findings.append(
                    VerifierFinding(
                        code="DUPLICATE_ENTITY_SEMANTICS",
                        severity="warning",
                        message="Multiple entities use the same normalized name.",
                        entity_ids=tuple(sorted(identifiers)),
                    )
                )
        normalized_claims: dict[str, list[str]] = {}
        for claim in artifact.claims:
            normalized_claims.setdefault(" ".join(claim.statement.lower().split()), []).append(claim.id)
        for statement, identifiers in normalized_claims.items():
            if statement and len(identifiers) > 1:
                findings.append(
                    VerifierFinding(
                        code="DUPLICATE_CLAIM_SEMANTICS",
                        severity="warning",
                        message="Multiple claims use the same normalized statement.",
                        claim_ids=tuple(sorted(identifiers)),
                    )
                )
        return tuple(findings)

    @staticmethod
    def _fidelity_score(baseline: ArtifactState, target: ArtifactState) -> float:
        baseline_objects = tuple(baseline.entities) + tuple(baseline.claims) + tuple(baseline.relations)
        if not baseline_objects:
            return 1.0
        target_maps = {
            **{item.id: item for item in target.entities},
            **{item.id: item for item in target.claims},
            **{item.id: item for item in target.relations},
        }
        preserved = 0
        for original in baseline_objects:
            replacement = target_maps.get(original.id)
            if replacement is not None and canonical_json_bytes(original) == canonical_json_bytes(replacement):
                preserved += 1
        return preserved / len(baseline_objects)

    @staticmethod
    def _evidence_coverage(claims: tuple[Claim, ...]) -> float:
        evidence_requiring = [
            claim
            for claim in claims
            if claim.basis in {"observation", "simulation"}
            or claim.verification_state in {"verified", "corroborated", "falsified"}
        ]
        if not evidence_requiring:
            return 1.0
        supported = 0
        for claim in evidence_requiring:
            refs = (
                claim.falsification_evidence_refs
                if claim.verification_state == "falsified"
                else claim.evidence_refs
            )
            if refs:
                supported += 1
        return supported / len(evidence_requiring)

    @staticmethod
    def _structural_completeness(artifact: ArtifactState) -> float:
        # ArtifactState construction already enforces identifiers, relation targets,
        # derivation lineage, duplicate IDs, and acyclic claim derivation.
        return 1.0

    @staticmethod
    def _redundancy_score(artifact: ArtifactState) -> float:
        denominator = len(artifact.entities) + len(artifact.claims)
        if denominator == 0:
            return 0.0
        duplicate_count = 0
        entity_names = [" ".join(item.name.lower().split()) for item in artifact.entities]
        claim_statements = [" ".join(item.statement.lower().split()) for item in artifact.claims]
        duplicate_count += len(entity_names) - len(set(entity_names))
        duplicate_count += len(claim_statements) - len(set(claim_statements))
        return min(1.0, duplicate_count / denominator)

    @staticmethod
    def _unsupported_claim_score(claims: tuple[Claim, ...]) -> float:
        empirical = [claim for claim in claims if claim.basis in {"observation", "simulation"}]
        if not empirical:
            return 0.0
        unsupported = sum(1 for claim in empirical if not claim.evidence_refs)
        return unsupported / len(empirical)
