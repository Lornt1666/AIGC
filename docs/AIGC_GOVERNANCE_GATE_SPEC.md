# AIGC Governance Gate Specification

## Purpose

The governance gate converts work-order intent into a visible decision record before any downstream movement.

The gate is implemented in:

- `src/core/work_order.py`
- `schemas/governance_decision.schema.json`
- `tests/test_governance_router.py`

## Decision Fields

A governance decision records:

- `decision_id`
- `work_order_id`
- `correlation_id`
- `classification`
- `risk_class`
- `allowed_operations`
- `blocked_operations`
- `required_approvals`
- `assigned_agents`
- `risk_findings`
- `external_action_allowed`
- `approval_required_before_external_action`
- `self_approval_allowed`
- `symbolic_layers_grant_authority`
- `status`

## Classification Values

The router classifies work into one of these operating classes:

- `internal-only`
- `documentation-only`
- `code-generation`
- `research-packet`
- `customer-facing-draft`
- `external-action-proposed`
- `blocked/high-risk`
- `requires-permit`

## Allowed Operations

The gate allows internal preparation only:

- schema validation
- risk classification
- governance routing
- artifact generation
- manifest generation
- approval packet generation
- redaction review instruction
- operator review preparation
- audit record preparation

## Blocked Operations

The gate blocks:

- job application submission
- bid submission
- outreach messaging
- invoice dispatch
- contract acceptance
- purchase or payment
- account changes
- social posting
- website action
- credential use
- external API side effects
- file movement outside the workspace
- production deployment
- secret access or logging

## Human Authority

The gate always records:

```json
{
  "external_action_allowed": false,
  "approval_required_before_external_action": true,
  "self_approval_allowed": false,
  "symbolic_layers_grant_authority": false
}
```

## Symbolic Layer Rule

Symbolic layers may improve language, UX, categorization, or reasoning organization.

They do not authorize execution.

Authority comes only from explicit contracts, tests, and human approval gates.

## Evidence

Regression tests prove:

- external intent requires a permit;
- external action remains blocked;
- high-risk outward movement is classified as blocked/high-risk;
- symbolic layers grant no execution authority.
