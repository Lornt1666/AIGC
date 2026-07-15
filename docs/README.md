# AIGC Documentation Index

## Architecture

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — canonical five-plane architecture, authority boundaries, plane ownership, and architectural invariants.
- [`REVIEW_EVIDENCE_PACKET_V1.md`](REVIEW_EVIDENCE_PACKET_V1.md) — review evidence and accountable human judgment.
- [`PRODUCTION_DEPLOYMENT_BASELINE_V1.md`](PRODUCTION_DEPLOYMENT_BASELINE_V1.md) — fail-closed deployment baseline.

## Staging preparation

- [`STAGING_BOOTSTRAP.md`](STAGING_BOOTSTRAP.md) — mock-only staging preparation runbook.
- [`governance/evolution/AIGC_PROVIDER_DISCOVERY_AUTOMATION_KIT_V1.md`](governance/evolution/AIGC_PROVIDER_DISCOVERY_AUTOMATION_KIT_V1.md) — provider-discovery command and simulation boundary.
- [`governance/evolution/AIGC_STAGING_PROCUREMENT_STATE_MACHINE_V1_1.md`](governance/evolution/AIGC_STAGING_PROCUREMENT_STATE_MACHINE_V1_1.md) — exact staging procurement state machine.

Run the current preparation surface with:

```bash
bash scripts/bootstrap-staging.sh
```

The command is revision-bound and mock-only. It stops before live provider discovery authorization and performs no external action.

## Runtime truth

The operator API endpoint:

```text
GET /api/v1/readiness
```

returns:

- current ledger-derived structural readiness;
- current production blockers;
- a separately labeled evidence-complete projection;
- delivery-judgment implementation status;
- the highest-impact next step.

Projected readiness never grants authority or changes the canonical production-ready state.
