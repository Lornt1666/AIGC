# AIGC Work Source Gate Procurement

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

Every work source gets its own gate packet before automation access is considered.

```text
source
  -> terms review
  -> access mode classification
  -> robots/API policy check
  -> connector allowlist
  -> secret reference manifest
  -> approval phrase
  -> dry-run receipt
  -> idempotency key
  -> rate-limit policy
  -> redaction scan
  -> audit receipt
  -> rollback/manual handoff path
```

## Covered Sources

The catalog covers RemoteOK, Remotive, WeWorkRemotely, Wellfound, FlexJobs, Indeed, LinkedIn Jobs, Glassdoor, ZipRecruiter, Upwork, Freelancer, Guru, PeoplePerHour, Contra, Toptal, GitHub Issues, GitLab Issues, IssueHunt, CanadaBuys, MERX, Alberta Purchasing Connection, SAM.gov, Kijiji, Craigslist, Facebook Groups, local classifieds, Greenhouse, Lever, Workday, Ashby, and SmartRecruiters.

## What Each Source Receives

Each source record includes:

- source terms review;
- source access mode classification;
- robots/API policy check when applicable;
- connector allowlist state;
- Google Secret Manager reference manifest;
- approval token or exact phrase requirement;
- dry-run receipt requirement;
- idempotency key requirement;
- rate-limit policy;
- redaction scan;
- audit receipt;
- rollback or manual handoff path.

## Live Use Boundary

The catalog does not grant live scraping, live submission, messaging, bidding, or account automation.

It prepares the source-by-source control map. Live access requires the Submission Approval Cockpit, connector allowlisting, source-policy review, secret references, and audit receipts.

## Local Run

```powershell
python .\src\work_source_gate_procurement.py --project-root . --config config\aigc_work_source_gate_catalog.json
```

## Outputs

- `data/work_source_gates/aigc_work_source_gate_procurement_packet.json`
- `reports/work_source_gate_procurement_report.md`
- `data/audit/aigc_work_source_gate_procurement_audit.jsonl`

## Short Form

```text
Every source gets a gate.
Every gate gets an audit.
Every action waits for approval.
```
