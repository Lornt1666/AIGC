# Automated Canadian Grant System

ACGS is an isolated, local draft-only grant-application workspace. It provides deterministic opportunity matching, narrative templates, CAD budget checks, and red-team findings for operator review.

It does not fetch grant portals, use credentials, determine eligibility, submit applications, or represent the supplied business profile as verified. All four configured portals are references only until their terms, source format, and a scoped Phase 5 approval have been reviewed.

## Run locally

From `/home/runner/work/AIGC/AIGC`:

```bash
python -m uvicorn automated_canadian_grant_system.frontend.app:app --host 127.0.0.1 --port 8000
```

Or, from `/home/runner/work/AIGC/AIGC/automated_canadian_grant_system`:

```bash
python frontend/app.py
```

Open `http://127.0.0.1:8000`. The portal only generates internal drafts and always returns a blocked manual-handoff state for submission.

## Local draft templates

Read-only templates are available at:

```text
GET /api/draft-payloads/alberta_innovates
GET /api/draft-payloads/nrc_irap
```

They are local source-attribution templates, not fetched program data. Each template identifies its official portal, declares that the source was not fetched or verified, and requires an operator to supply current program-specific information. NRC IRAP is a federal reference; its presence does not configure a live connector or determine eligibility.

## Tests

```bash
python -m pytest automated_canadian_grant_system/tests
```

## Portal activation

Alberta Innovates is listed first because the working profile is Alberta-based. That ordering is not a finding of eligibility or evidence of an active program. Before any live read-only connector can be added, review the official source and platform terms, record scoped Phase 5 approval, preserve source attribution, and keep the submission path manually controlled.
