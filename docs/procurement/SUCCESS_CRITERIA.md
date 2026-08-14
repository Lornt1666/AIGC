# Procurement sandbox success criteria

This package is a local, synthetic design and validation environment. It does not procure hardware, contact suppliers, start auctions, sign contracts, move funds, or deploy infrastructure.

| Dimension | Sandbox success condition | Evidence | Production gate |
|---|---|---|---|
| Integrity | All committed JSON/YAML parses; catalog count is exactly 13 | Local validator receipt | Independent review |
| Determinism | Same seed and fixtures produce the same canonical receipt | Repeated test | Release digest binding |
| Safety | Every consequential scenario stops before egress | Adversarial scenario results | Authenticated, expiring permit |
| Supplier risk | Sanctions, KYC failure, identity mismatch and collusion block | Policy tests | Current authoritative data |
| Finance | Duplicate, over-ceiling and unapproved payments block | Policy tests | Two-party approval and reconciliation |
| Privacy | Unredacted PII cannot be stored or exported | Policy tests | Regional privacy review |
| Operations | All Kubernetes workloads remain at zero replicas | Manifest validation | Reviewed immutable images and deployment permit |
| Observability | Every simulated stage emits a trace ID and receipt hash | Validation receipt | Durable append-only audit store |

Economic, delivery, quality and latency numbers are evaluation targets—not verified claims—until measured against authorized, provenance-bearing data.
