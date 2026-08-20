# AIGC Project State — 2026-08-20

This document is the recovery handoff for the RegenExcalibur AIGC Coordinator.
It separates live GitHub state, recovered local state, and production claims so
that the next change does not invalidate the strongest evidence already
available.

## Executive state

- **Integrated release candidate:** draft PR
  [`#231`](https://github.com/Lornt1666/AIGC/pull/231), head commit
  `a5148855321770940afe7d13a9e4d14e3de0c77f`, tree
  `1ad6bea6cf4c1b728d557aed7299b5fdc8aba20c`.
- **Parent integration:** draft PR
  [`#220`](https://github.com/Lornt1666/AIGC/pull/220), head commit
  `451156970e511b2781e486a3e290edaa5c0f231b`.
- **Separate current slice:** draft PR
  [`#232`](https://github.com/Lornt1666/AIGC/pull/232), head commit
  `fb2f984accbedd8127d9bd06cb30bfd09255af66`; it is an Opera bridge slice
  against `main`, not a replacement for the integrated release chain.
- **Expired-contest cleanup:** draft PR
  [`#234`](https://github.com/Lornt1666/AIGC/pull/234), based exactly on PR
  #231 head, removes the expired contest from active product scope and adds
  this operational handoff plus its machine-readable receipt.
- **First unmet release gate:** G4, exact-head hosted CI for PR #231.
- **Product readiness:** `12/34` checks pass (`35.2941%`); the local core is
  healthy, but release evidence, authenticated hosting, durable state, web
  completion, connector certification, and production authorization remain
  incomplete.
- **Production state:** not deployed and not production-proven. The current
  frontend and API are governed local planning/diagnostic surfaces.

## What exists now

The PR #231 tree includes the following operator surfaces inherited through
PR #220:

| Surface | Current capability | Boundary |
| --- | --- | --- |
| `src/dashboard/nexus_app.py` | Streamlit control-room projection for run graph, artifacts, verification, governance, connectors, memory, and evidence | Local deterministic dry-run; approval controls are presentation-only |
| `src/webapp/nexus_dashboard.py` | Read-only dashboard projection | Production activation is disabled |
| `src/webapp/regenexcalibur_api.py` | FastAPI health, coordinator planning, diagnostics, coordination engineering, and autodesign iteration endpoints | No external execution and no production authentication layer |
| `src/integrations/mcp/server.py` | Streamable HTTP MCP host with 11 governed tools at loopback `/mcp` | Local-only; public host validation and authentication are not complete |

The current API contract exposes:

- `GET /health`
- `POST /v1/coordinator/plan`
- `POST /v1/diagnostics/run`
- `POST /v1/coordination/engineer`
- `POST /v1/autodesign/iterate`

These endpoints establish the development control plane. They do **not** prove
a public production endpoint, external worker execution, provider activation,
billing readiness, or authorization to act for an employer.

## Evidence ledger

| Evidence | Result | Classification |
| --- | --- | --- |
| PR #231 author-reported local suite | `1317 passed, 5 skipped, 0 failed` | Strong local evidence for exact PR head; not independently rerun in this recovered workspace |
| PR #231 focused ForgeRunner suite | `19 passed` | Local focused evidence reported in the PR |
| Hosted workflow run `31999900601`, job `95298121085` | Failed before checkout; zero steps and zero artifacts | Admission/billing failure, not a code-test result |
| PR #220 hosted workflow run `31793754157`, job `94746177824` | Failed before checkout; zero steps | Admission/billing failure, not a code-test result |
| Recovered 2026-08-14 source archive | `501 passed, 4 skipped` locally on 2026-08-20 | Independent regression result for the recovered snapshot only; not PR #231 verification |
| Product-focused bridge and employer-sandbox suites | `16 passed` locally on 2026-08-20 | Current recovered snapshot only |
| Post-cleanup affected suites | `44 passed` locally on 2026-08-20 | Cloud authorization, MCP HTTP, bridge, and employer-sandbox coverage |
| Post-cleanup full recovered suite | `501 passed, 4 skipped` locally on 2026-08-20 | Confirms the cleanup did not regress the recovered snapshot; still not exact PR #231 evidence |
| Zero-egress employer sandbox | `PASS`; receipt `SBX-4F88AB73D87044790709ABBF`; SHA-256 `4f88ab73d87044790709abbfe25f4dd62455a21bd6e53ab713316697a041369e`; zero actions and zero provider calls | Safe local operational evidence |
| Live loopback MCP HTTP probe | Protocol `2025-06-18`; server `aigc-nexus 1.29.0`; 11 tools; all advertised read-only | Real local socket validation; not public deployment evidence |

The recovered workspace came from
`RegenExcalibur_AIGC_Coordinator_source.zip`. Its files differ from PR #231,
and its `.git` directory is not a usable Git checkout. It must not be presented
as the current release candidate or used to overwrite PR #231.

## Release sequence

1. Preserve PR #231 at exact head
   `a5148855321770940afe7d13a9e4d14e3de0c77f` until G4 is resolved.
2. Recover or clone the exact PR #231 source into a valid Git checkout and
   create a product-operations branch from that exact source identity.
3. Remove expired contest-only assets from that branch without altering
   product code or append-only evidence needed for release provenance.
4. Owner confirms the GitHub Actions billing/spending condition has changed.
5. With explicit digest-bound authorization, rerun exact-head hosted CI once.
6. Require checkout, dependency installation, tests, security validation, and
   retained artifacts to complete on that exact SHA.
7. Review and approve the merge chain: PR #231 into the PR #220 branch, then
   the integrated release candidate into its approved base. Merge authority is
   distinct from CI authority.
8. Patch the production control plane:
   authentication, authorization, tenant isolation, durable state, rate limits,
   secrets integration, audit retention, and environment separation.
9. Run cloud preflight and deployment under separate Phase 5 production
   permits. Deployment, traffic, provider activation, billing changes, and live
   worker actions each require their own explicit scope.

Do not repeatedly retry the unchanged hosted admission failure. A retry without
evidence that the billing condition changed adds noise and consumes budget
without advancing G4.

## Team operating lanes

An actual delivery team should assign one accountable human to each lane:

| Lane | Accountable output |
| --- | --- |
| Release captain | Exact SHA, merge order, authorization receipts, stop conditions |
| Platform/API | Authenticated FastAPI control plane and environment-safe execution adapters |
| Frontend/product | Operator workflows, state transitions, error recovery, and accessibility |
| Security/governance | Threat model, secrets boundary, tenant isolation, permit enforcement |
| Verification | Exact-head CI, artifact retention, end-to-end and failure-path evidence |
| Cloud operations | Development/staging/production projects, observability, rollback, budgets |
| Employer/compliance | Employer-specific policy, data handling, and human approval boundaries |

Agent archetypes may assist these lanes, but mythic names and agent outputs do
not grant authority. A named human remains accountable for every external
mutation and production decision.

## Exact next action

The cleanup branch and PR now exist. The next useful action is **not** a code
push from this recovered snapshot. Obtain an authorized valid checkout of PR
#234, verify that its base is exact PR #231 head
`a5148855321770940afe7d13a9e4d14e3de0c77f`, and run its complete suite. The
first implementation slice after that verification is authenticated
development hosting for `/mcp`, backed by durable state and a retained
host-validation receipt. After that slice passes local and hosted CI, stage it
behind zero public traffic. Provider calls, public traffic, billing changes,
and employer actions remain separately authorized operations.

## Constitutional invariants

- Human authority is sovereign.
- No external execution occurs without an action-specific permit.
- Evidence is append-only and tied to exact source identity.
- UI controls do not imply provider or production authority.
- A planning result is not an execution receipt.
- A pre-checkout workflow failure is not a failing test suite.
- Local success is not production deployment evidence.
