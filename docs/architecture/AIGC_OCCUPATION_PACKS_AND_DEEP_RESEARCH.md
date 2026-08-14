# AIGC Occupation Packs and Deep Research Procurement

Status: `LOCAL CONTRACTS VERIFIED — EMPLOYER CERTIFICATION AND PROVIDER DISPATCH BLOCKED`

## Executive result

AIGC now has thirteen machine-readable occupation packs and a provider-neutral
Deep Research procurement boundary. Each pack defines allowed local outputs,
prohibited actions, human supervision, quantitative admission gates, an autonomy
ceiling, a recertification interval, and a dated occupational-classification
mapping. Every pack remains `DRAFT` and `LOCAL_DRAFT_ONLY`; none grants execution
authority or establishes employer-accepted competence.

The research boundary produces a deterministic plan through:

```text
DEFINE -> SOURCE -> RETRIEVE -> SCREEN -> EXTRACT
       -> TRIANGULATE -> CHALLENGE -> SYNTHESIZE -> VERIFY -> PACKAGE
```

Only `DEFINE` is locally ready. `SOURCE` is visibly blocked until an approved
retrieval surface or request-bound provider permit exists. Downstream stages wait
for admitted evidence. The plan does not browse, call a model, access credentials,
spend money, or publish.

## Occupational evidence baseline

The catalogue uses current official classification surfaces as mapping references:

- [O*NET Web Services](https://services.onetcenter.org/about) provides a REST API
  over the current O*NET database, occupation reports, tasks, skills, knowledge,
  and crosswalk services. Access requires registration and attribution.
- [ESCO](https://esco.ec.europa.eu/en/about-esco/what-esco) is the European
  Commission's multilingual classification of occupations and skills; exact ESCO
  concept identifiers must be resolved before claiming a crosswalk.
- [Canada's NOC matrix](https://noc.esdc.gc.ca/Structure/Matrix) organizes NOC 2021
  occupations by broad occupational category and TEER. Exact NOC mappings remain a
  later research task rather than inferred from title similarity.

An O*NET code in a pack is an occupational mapping, not a competency credential.
Composite AIGC roles are labeled `RELATED`; only directly named roles use `EXACT`.
Mappings must be re-reviewed when the classification changes.

## Catalogue

| Pack | Local scope | Hard guardrail |
|---|---|---|
| Software and Research Assistant | code analysis and bounded local patches | no push, release, credential use, or production change |
| Administrative Coordinator | correspondence and scheduling drafts | no send, invite, signature, purchase, or contract acceptance |
| Data Analysis and Reporting Specialist | data quality and reproducible reporting | no source mutation, re-identification, or regulated determination |
| Deep Research Analyst | source plans and provenance-linked synthesis | no invented citations, provider dispatch, or publication |
| Technical Writer | product-grounded technical documentation | no unverified behavior claims or publication |
| Software QA Analyst | local/sandbox test design and execution | no unapproved production or destructive testing |
| Customer Support Knowledge Assistant | support triage and response drafts | no send, refund, account change, or legal admission |
| Project Coordinator | plans, risks, dependencies, and status drafts | no budget, staffing, scope, or external schedule commitment |
| Bookkeeping Workpaper Assistant | reconciliation and classification proposals | no ledger post, payment, filing, or assurance opinion |
| Defensive Cybersecurity Analyst | supplied-evidence review and local fix validation | no unapproved target interaction, exploitation, or secret extraction |
| Procurement Research Analyst | supplier research and comparison drafts | no contact, purchase, negotiation, terms acceptance, or budget commitment |
| Executive Operations Assistant | decision briefs and coordination drafts | no executive decision, external send, or restricted-data disclosure |
| Editorial and Content Assistant | editing and source-grounded content drafts | no publication, plagiarism, rights clearance, or authorship misrepresentation |

The first KPI layer is intentionally small: each pack uses one or more task-value
metrics and at least one guardrail. Targets are provisional admission thresholds;
employer evaluation data must recalibrate them. Optimizing output volume is not a
success metric.

## Deep Research contract

The official [OpenAI Deep Research guide](https://developers.openai.com/api/docs/guides/deep-research)
documents Deep Research through the Responses API and requires at least one source
surface such as web search, remote MCP, or file search. Model availability and
deprecation state can change, so the policy stores
`REVALIDATE_CURRENT_SUPPORTED_MODEL` rather than freezing a stale model ID.

Before any provider run, AIGC must resolve:

1. the exact research question, intended decision, jurisdictions, source ceiling,
   and cost ceiling;
2. a current supported model and tool contract from official documentation;
3. an approved source boundary and prompt-injection screening policy;
4. a secret reference through the governed broker, never a raw credential;
5. one request-bound, unexpired permit covering model, tools, maximum spend, and
   provider-call count;
6. a reconciliation rule for timeout or indeterminate provider outcome.

Research evidence cannot authorize an application, message, purchase, deployment,
or employer action. Those remain separate connector and execution-permit gates.

## Verification

```bash
.venv/bin/python scripts/validate_aigc_occupation_packs.py
.venv/bin/python scripts/validate_aigc_deep_research_policy.py
.venv/bin/python scripts/validate_aigc_universal_integration.py
.venv/bin/python -m pytest -q tests/test_nexus_occupation_packs.py \
  tests/test_nexus_deep_research_procurement.py \
  tests/test_nexus_mcp_contract.py
```

The truthful terminal distinction is:

- local pack and research-plan contracts: `PASS` after fresh validation;
- employer competence certification: `BLOCKED` pending qualified evaluation;
- external research source retrieval or provider call: `BLOCKED` pending exact
  source, billing, credential-broker, and execution-permit evidence;
- publication or employer action: `BLOCKED` pending separate authorization.
