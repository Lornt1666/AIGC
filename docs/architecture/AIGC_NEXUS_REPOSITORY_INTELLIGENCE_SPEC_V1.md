# AIGC Nexus Repository Intelligence — Measurement Contract V1

Status: ACTIVE_DISCOVERY

This measurement layer implements Stage 1 of the Evolutionary Convergence Law. It is observational and non-destructive.

## Purpose

Produce deterministic repository measurements before assigning removal ECS values or procuring replacement technology.

## Current metrics

- total/source/test/documentation/infrastructure/configuration/workflow file counts;
- text line counts by extension;
- test-to-source ratio;
- Python module/function/class counts;
- Python branch-point proxy;
- internal import-edge count;
- fan-in/fan-out coupling hotspots;
- syntax-error inventory;
- exact text-duplicate groups;
- repeated basename groups;
- canonical report SHA-256.

## Interpretation limits

- `branch_points_proxy` is not represented as formal cyclomatic complexity; it is an AST-derived hotspot proxy.
- exact duplicate detection is byte-equivalent normalized text detection, not semantic clone detection.
- repeated basenames are investigation candidates, not evidence of redundancy.
- file and line volume do not imply value or quality.
- a low test-to-source ratio does not prove inadequate coverage without coverage/runtime evidence.
- this analyzer grants no removal, migration, merge, deployment, procurement, or external-action authority.

## Next analytics layers

1. import-cycle and package-boundary analysis;
2. schema-semantic overlap analysis;
3. canonical-responsibility duplicate detection;
4. test-to-capability ownership mapping;
5. Git churn/staleness metrics;
6. dependency import/use and current-version/security analysis;
7. historical PR capability extraction;
8. ECS calculation from measured replacement/test/dependency/evidence dimensions.

## Output

Default generated report path:

`reports/nexus/repository-intelligence.json`

The report is generated evidence and is not required to be committed. CI or local analysis may retain it as an artifact after the exact repository revision is bound externally.
