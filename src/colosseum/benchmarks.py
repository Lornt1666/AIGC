from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .domain import _require_nonnegative, _require_text


@dataclass(frozen=True)
class ComputeBenchmark:
    benchmark_id: str
    workload_class: str
    provider: str
    resource_identity: str
    resource_version: str
    environment_id: str
    jurisdiction: str
    fixture_digest: str
    measured_quality: float
    verification_passed: bool
    latency_ms_p50: int
    latency_ms_p95: int
    observed_cost_cad: float | None
    sample_count: int
    measured_at: datetime
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "benchmark_id",
            "workload_class",
            "provider",
            "resource_identity",
            "resource_version",
            "environment_id",
            "jurisdiction",
            "fixture_digest",
        ):
            _require_text(name, getattr(self, name))
        if not 0 <= self.measured_quality <= 1:
            raise ValueError("measured_quality must be between 0 and 1")
        _require_nonnegative("latency_ms_p50", self.latency_ms_p50)
        _require_nonnegative("latency_ms_p95", self.latency_ms_p95)
        if self.latency_ms_p95 < self.latency_ms_p50:
            raise ValueError("latency_ms_p95 cannot be lower than latency_ms_p50")
        if self.observed_cost_cad is not None:
            _require_nonnegative("observed_cost_cad", self.observed_cost_cad)
        if self.sample_count <= 0:
            raise ValueError("sample_count must be greater than zero")
        if self.measured_at.tzinfo is None:
            raise ValueError("measured_at must be timezone-aware")
        if not self.evidence_refs:
            raise ValueError("benchmark measurements require evidence")
