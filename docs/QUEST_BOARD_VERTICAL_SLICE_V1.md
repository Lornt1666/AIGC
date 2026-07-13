# AIGC Quest Board Vertical Slice v1

Status: draft, local-only, operator-controlled.

## Implemented loop

```text
manual entry or governed read-only adapter
→ persistent Quest Candidate DISCOVERED
→ accountable-operator qualification
→ Candidate QUALIFIED
→ atomic candidate-to-Quest conversion
→ Quest PROPOSED
→ visible local Quest Board
```

The loop does not include work acceptance or external execution.

## Ratified lifecycle semantics

Issue #66 records the accountable-operator decision that:

- `WORK_ACCEPTED` means bounded internal work has been explicitly authorized;
- `ACCEPTED_FOR_DELIVERY` means completed reviewed work has been accepted for a separate delivery action;
- generic canonical `ACCEPTED` is prohibited;
- `REWORK_REQUIRED` is an explicit canonical state;
- PR #64 is classified as a bounded internal execution/review sub-lifecycle requiring a compatibility adapter.

Candidate conversion therefore creates a Quest in `PROPOSED`, never `WORK_ACCEPTED`.

## Application composition

PR #77 reconciles the intended PR #63 application composition into one container:

```text
FastAPI route
→ ApplicationContainer
   ├── AuthorizationApplicationService
   │   └── SQLiteAuthorizationReceiptRepository
   ├── QuestCandidateApplicationService
   │   └── SQLiteQuestCandidateRepository
   └── QuestApplicationService
       └── SQLiteQuestRepository
→ one SQLite database and migration boundary
```

Authorization receipts, candidate records, Quest records, idempotency records, and append-only audit events survive process restart.

## API

### Candidate intake

- `GET /api/v1/quests/sources`
- `POST /api/v1/quests/candidates/ingest`
- `GET /api/v1/quests/candidates`
- `POST /api/v1/quests/candidates/{candidate_id}/qualify`

### Quest creation and queries

- `POST /api/v1/quests/candidates/{candidate_id}/create-quest`
- `GET /api/v1/quests`
- `GET /api/v1/quests/{quest_id}`

### Operator UI

- `GET /`
- `GET /quest-board`

The UI supports:

- manual candidate entry;
- source selection from the governed catalog;
- candidate inspection;
- qualification;
- creation of a proposed Quest;
- display of persistent Quest state.

## Atomic conversion

Quest creation performs one SQLite transaction that:

1. verifies the candidate exists;
2. verifies exact candidate revision;
3. verifies `QUALIFIED` and Quest-creation authorization;
4. verifies the initial Quest state is `PROPOSED`;
5. creates the Quest record;
6. updates candidate conversion evidence;
7. appends the immutable audit event;
8. stores the idempotent response.

Any failure rolls back the complete transaction.

## Quest creation defaults

Defaults are bounded and do not fabricate authority:

- owner and authority are the role `ACCOUNTABLE_OPERATOR`, not a hard-coded personal name;
- budget remains `null` unless supplied by the candidate or operator;
- deadline remains `null` unless supplied or derivable from the posting observation plus `deadline_days`;
- scope is internal production for operator review;
- non-scope expressly blocks applications, bidding, messaging, contract acceptance, payments, delivery, deployment, credential use, and external action;
- acceptance criteria include reviewability and the external-action prohibition.

## Local run

```powershell
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/quest-board
```

Optional database location:

```powershell
$env:AIGC_LOCAL_DATABASE_PATH = "C:\path\to\local_operator.sqlite3"
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

## Validation targets

```powershell
python -m pytest tests/api/test_local_operator_api.py
python -m pytest tests/api/test_persistent_authorization_receipts.py
python -m pytest tests/api/test_quest_candidates_api.py
python -m pytest tests/api/test_quest_creation_api.py
python -m pytest tests/contracts/test_quest_candidate_schema.py
python -m pytest tests/contracts/test_quest_schema.py
python -m pytest
```

## Governance boundary

This vertical slice does not:

- retrieve arbitrary URLs;
- scrape websites;
- authenticate to work platforms;
- apply, bid, message, contact, post, purchase, pay, or deliver;
- accept the work commitment;
- use production identity;
- expose secrets;
- invoke live write connectors;
- deploy publicly.

`external_action_performed` remains `false` throughout the candidate and Quest creation paths.
