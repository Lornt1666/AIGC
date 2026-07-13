# AIGC Quest Candidate Intake v1

Status: bounded local implementation for draft review.

## Purpose

Quest Candidate Intake converts a manually supplied opportunity record or output from an already governed read-only adapter into a persistent, schema-valid candidate on the local Quest Board.

A candidate is not:

- a Quest;
- an application or bid;
- a contract;
- permission to contact a person;
- permission to use credentials;
- permission to perform an external action.

The complete bounded intake path is:

```text
manual entry or governed read-only adapter
→ source-catalog policy check
→ candidate normalization and schema validation
→ Candidate DISCOVERED
→ accountable-operator qualification
→ Candidate QUALIFIED
→ separate atomic Quest creation command
→ Quest PROPOSED
```

Qualification and Quest creation do not authorize `WORK_ACCEPTED`.

## API surface

### `GET /api/v1/quests/sources`

Returns the combined base work-source gate catalog and ChatGPT-log addendum.

Catalog inclusion is informational and policy-bearing. It does not enable a connector or authorize scraping, applying, bidding, messaging, purchasing, publishing, security testing, payment activity, or another external action.

### `POST /api/v1/quests/candidates/ingest`

Records and normalizes supplied candidate data. The route does not retrieve the supplied URL.

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
  "rights_status": "manual_operator_entry",
  "ingestion_channel": "manual"
}
```

### `GET /api/v1/quests/candidates`

Lists persistent candidates. Optional filters:

```text
GET /api/v1/quests/candidates?status=DISCOVERED
GET /api/v1/quests/candidates?status=QUALIFIED
```

### `POST /api/v1/quests/candidates/{candidate_id}/qualify`

Records the accountable operator's decision that the candidate may proceed to Quest proposal creation.

```json
{
  "expected_revision": 1,
  "decision": "QUALIFY",
  "operator_role": "ACCOUNTABLE_OPERATOR",
  "reason": "Scope is sufficiently clear for governed Quest drafting."
}
```

Qualification records:

```text
status = QUALIFIED
quest_creation_authorized = true
quest_created = false
next_step = CREATE_QUEST_UNDER_CANONICAL_LIFECYCLE
```

### `POST /api/v1/quests/candidates/{candidate_id}/create-quest`

Creates a canonical Quest from a qualified candidate.

```json
{
  "expected_candidate_revision": 2,
  "operator_role": "ACCOUNTABLE_OPERATOR"
}
```

The conversion transaction:

1. verifies the exact candidate revision;
2. verifies `QUALIFIED` and Quest-creation authorization;
3. creates the Quest in `PROPOSED`;
4. updates the candidate with the Quest identifier and conversion digest;
5. appends audit evidence;
6. stores the idempotent result.

After conversion:

```text
candidate.qualification.quest_created = true
candidate.qualification.next_step = REQUEST_WORK_ACCEPTANCE
quest.lifecycle_state = PROPOSED
work_accepted = false
external_action_performed = false
```

## Ingestion channels

| Channel | Meaning |
|---|---|
| `manual` | The operator or another internal component supplies the posting data. No remote retrieval occurs. |
| `existing_read_only_adapter` | An implemented Phase 2 read-only adapter supplies the data. |
| `approved_read_only_adapter` | Reserved for an adapter separately promoted to `read_only_enabled`. |

The current existing adapter allowlist is:

- RemoteOK;
- Remotive;
- We Work Remotely;
- GitHub Issues.

All other sources default to manual entry until their terms, interface, connector, tests, rate limits, privacy boundary, and evidence have been separately reviewed.

## Work-source coverage

The combined catalog contains 52 work-related platforms and channels across remote jobs, general employment, government employment, freelance marketplaces, developer work, bounties, authorized security programs, procurement, classifieds, applicant-tracking systems, outreach tools, and commerce channels.

Catalog inclusion never grants access or external-action authority.

## Persistence

The implementation uses the shared local SQLite substrate for:

- candidate records;
- Quest records;
- authorization receipts;
- optimistic revisions;
- idempotency records;
- append-only audit events;
- restart-safe retrieval.

## Safety boundary

The implementation does not:

- crawl or scrape a source;
- authenticate to a work platform;
- apply or bid;
- send a message;
- accept legal terms or work;
- upload a deliverable;
- purchase or pay;
- post content;
- perform security testing;
- use production identity;
- invoke a live write connector;
- deploy publicly.

Every candidate, Quest, and conversion receipt preserves:

```json
{
  "external_action_performed": false
}
```

## Validation

```powershell
python -m pytest tests/api/test_quest_candidates_api.py
python -m pytest tests/api/test_quest_creation_api.py
python -m pytest tests/contracts/test_quest_candidate_schema.py
python -m pytest tests/contracts/test_quest_schema.py
python -m pytest
```
