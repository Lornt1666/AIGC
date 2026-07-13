# AIGC Quest Candidate Intake v1

Status: bounded local implementation for draft review.

## Purpose

Quest Candidate Intake converts a manually supplied opportunity record or an output from an already governed read-only adapter into a persistent, schema-valid candidate on the local Quest Board.

A candidate is not:

- a Quest;
- an application;
- a proposal submission;
- a bid;
- a contract;
- permission to contact a person;
- permission to use account credentials;
- permission to perform any external action.

The candidate boundary is:

```text
manual entry or governed read-only adapter
→ source-catalog policy check
→ candidate normalization
→ JSON Schema validation
→ atomic SQLite candidate + audit write
→ Quest Board
→ accountable-operator qualification
→ eligible for separate canonical Quest creation
```

## API surface

### `GET /api/v1/quests/sources`

Returns the combined base work-source gate catalog and ChatGPT-log addendum.

Catalog inclusion is informational and policy-bearing. It does not enable a connector or authorize scraping, applying, bidding, messaging, purchasing, publishing, security testing, payment activity, or another external action.

### `POST /api/v1/quests/candidates/ingest`

Records and normalizes supplied candidate data.

The route does not retrieve the supplied URL. Network retrieval remains inside separately reviewed read-only adapters.

Example:

```json
{
  "candidate_id": "cand_upwork_react_001",
  "source_id": "upwork",
  "source_url": "https://www.upwork.com/jobs/example",
  "title": "Build a React dashboard with Tailwind",
  "description": "Create a typed dashboard with a responsive Tailwind interface.",
  "proposed_quest_title": "React Dashboard Development",
  "domain": "software_development",
  "required_skills": ["react", "tailwind", "typescript"],
  "budget_range": {
    "min": 800,
    "max": 1500,
    "currency": "USD"
  },
  "deadline_days": 14,
  "remote_status": "remote",
  "risk_class": "low",
  "rights_status": "public_posting",
  "ingestion_channel": "manual"
}
```

### `GET /api/v1/quests/candidates`

Lists persistent candidates.

Optional status filter:

```text
GET /api/v1/quests/candidates?status=DISCOVERED
GET /api/v1/quests/candidates?status=QUALIFIED
```

### `POST /api/v1/quests/candidates/{candidate_id}/qualify`

Records the accountable operator's decision that a candidate may proceed to canonical Quest creation.

Example:

```json
{
  "expected_revision": 1,
  "decision": "QUALIFY",
  "operator_role": "ACCOUNTABLE_OPERATOR",
  "reason": "Scope is sufficiently clear for governed quest drafting."
}
```

Qualification sets:

```text
status = QUALIFIED
quest_creation_authorized = true
quest_created = false
next_step = CREATE_QUEST_UNDER_CANONICAL_LIFECYCLE
```

This endpoint intentionally does not create the Quest aggregate. Quest creation remains a separate implementation step so the candidate train does not silently resolve or bypass the canonical lifecycle decision gate.

## Persistence

Quest Candidate Intake uses the existing SQLite substrate:

- `records` with collection `quest_candidates`;
- optimistic revision checks;
- idempotency records;
- append-only audit events;
- one transaction for candidate mutation and audit evidence;
- restart-safe retrieval.

## Ingestion channels

| Channel | Meaning |
|---|---|
| `manual` | The operator or another internal component supplies the posting data. No remote retrieval occurs. |
| `existing_read_only_adapter` | One of the currently implemented Phase 2 read-only adapters supplies the data. |
| `approved_read_only_adapter` | Reserved for a future adapter explicitly promoted to `read_only_enabled`. |

The current existing adapter allowlist is:

- RemoteOK;
- Remotive;
- We Work Remotely;
- GitHub Issues.

All other sources default to manual entry until their terms, interface, connector, tests, rate limits, privacy boundary, and evidence have been separately reviewed.

## Work-source coverage

The combined catalog family contains every work-related website example previously discussed for AIGC, organized as:

- remote and curated job boards;
- general employment boards;
- government employment systems;
- freelance marketplaces;
- developer work and open-source issues;
- coding bounties;
- authorized security programs;
- government and RFP procurement;
- local services, communities, and classifieds;
- company-direct applicant-tracking job boards;
- professional outreach and prospecting tools;
- self-employment commerce channels.

Examples include RemoteOK, Remotive, We Work Remotely, Wellfound, FlexJobs, Jobicy, SolidGigs, freelancermap, Indeed, LinkedIn Jobs, Glassdoor, ZipRecruiter, Adzuna, The Muse, USAJOBS, Canada Job Bank, Upwork, Freelancer.com, Guru, PeoplePerHour, Contra, Toptal, Fiverr, GitHub Issues, GitLab Issues, IssueHunt, Topcoder, Gitcoin, HackerOne, Bugcrowd, CanadaBuys, MERX, Alberta Purchasing Connection, SAM.gov, Kijiji, Craigslist, Facebook Groups, Facebook Marketplace, Reddit work communities, Nextdoor, Greenhouse, Lever, Workday, Ashby, SmartRecruiters, X/Twitter, Apollo.io, Hunter.io, Shopify, Etsy, and Redbubble.

## Safety boundary

The implementation performs no external action.

Specifically, it does not:

- crawl or scrape a source;
- authenticate to a source;
- use credentials;
- apply to a job;
- submit a proposal;
- bid;
- send a message;
- accept legal terms;
- upload a deliverable;
- purchase anything;
- initiate payment;
- post content;
- perform security testing;
- create a production identity;
- deploy a public service.

Every candidate and audit event records:

```json
{
  "external_action_performed": false
}
```

## Validation

Run:

```powershell
python -m pytest tests/api/test_quest_candidates_api.py tests/contracts/test_quest_candidate_schema.py
python -m pytest
```

The focused test suite covers:

- ingestion;
- normalization;
- source-policy failure;
- source catalog coverage;
- idempotency;
- persistent restart recovery;
- qualification;
- optimistic revision conflicts;
- contract rejection of unknown fields;
- prohibition on recording external action as true.
