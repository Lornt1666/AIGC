# AIGC Devpost Gemini Workflow

## Evidence boundary

This implementation adds an end-to-end application path for a governed Gemini
assessment. Repository code and offline tests do not prove that Gemini, Google
Cloud, customers, revenue, or production operation exists. A production claim
requires an authorized deployment and retained runtime receipts.

## Workflow

1. An authenticated operator submits a permitted opportunity through the
   command center.
2. The application redacts common contact and secret-like strings before
   building the prompt.
3. The deployed application calls Gemini through Vertex AI using its Cloud Run
   service identity and Application Default Credentials. No API key is stored.
4. Gemini returns a Pydantic-constrained assessment with pointers to the exact
   supplied fields used as evidence.
5. Deterministic policy validates those pointers and evaluates AI permission,
   disclosure, injection signals, risk, score, and the mandatory human-review
   flag.
6. The application records a write-once-at-creation execution event with an
   integrity hash.
7. The operator records exactly one approve, deny, or revise decision.
8. Approval authorizes internal use only. It never performs an external
   business action.

## Required environment

| Variable | Requirement |
|---|---|
| `AIGC_COMMAND_CENTER_TOKEN` | Secret Manager reference used by the existing operator boundary |
| `AIGC_GEMINI_ENABLED` | Must be exactly enabled only after deployment approval |
| `GOOGLE_CLOUD_PROJECT` | Exact Google Cloud project ID |
| `GOOGLE_CLOUD_LOCATION` | Approved Vertex AI location compatible with the selected model |
| `AIGC_GEMINI_MODEL` | Exact deployed Gemini model name; no silent default |
| `AIGC_GEMINI_EVIDENCE_BACKEND` | `gcs` in production |
| `AIGC_GEMINI_EVIDENCE_BUCKET` | Dedicated evidence bucket |
| `AIGC_GEMINI_EVIDENCE_PREFIX` | Defaults to `product-evidence/gemini` |
| `AIGC_GEMINI_TIMEOUT_SECONDS` | Hard SDK request timeout; defaults to `30` |
| `AIGC_GEMINI_MAX_OUTPUT_TOKENS` | Bounded output budget; defaults to `1200` |
| `AIGC_GEMINI_MAX_ATTEMPTS` | Total attempts, including the first; maximum `3` |
| `AIGC_ENV` | `production` on Cloud Run |

Production refuses the JSONL evidence backend because Cloud Run's writable
filesystem is ephemeral.

## Service identity

Use a dedicated Cloud Run service account. Grant only the minimum Vertex AI
prediction permission and bucket-scoped permissions needed to create, list, and
read evidence objects. Do not create or commit a service-account key file.

The deployment script deliberately requires the project, service account,
regions, model, evidence bucket, Artifact Registry repository, and pinned
secret version as operator inputs. The registry repository, evidence bucket,
service account, IAM bindings, and secret version must already exist and must
be reviewed before use. Running the script is an external action and requires
explicit authorization.

The container runs as an unprivileged `aigc` user. The deploy command bounds
instances, concurrency, and request timeout; those values are conservative
starting limits, not proof of load capacity.

## API

- `GET /api/gemini/status`
- `POST /api/gemini/workflows`
- `GET /api/gemini/workflows/{run_id}`
- `POST /api/gemini/workflows/{run_id}/decision`

All routes inherit the existing command-center authentication dependency.

Example intake:

```json
{
  "title": "Permissioned opportunity",
  "description": "A real description with customer-private details removed.",
  "source_url": "https://example.com/opportunity",
  "constraints": ["No external business action", "Human review required"],
  "ai_assistance_permitted": true,
  "ai_disclosure_required": true
}
```

## Validation

```bash
python -m pytest tests/test_gemini_workflow.py tests/test_cloud_webapp.py
python scripts/run_gemini_workflow_smoke.py
```

The smoke script uses an explicit offline stub and writes a summary stating
separately that no model API call, deployment, or external business action
occurred.

## Production acceptance evidence

Do not update Devpost capability claims until all of the following are captured:

- successful Cloud Run revision and immutable image digest;
- exact Vertex AI model and region;
- successful live execution event with
  `model_api_call_performed: true` and `live_model_call: true`;
- model usage and latency metadata;
- deterministic policy result;
- human decision event;
- durable Cloud Storage evidence object identifiers;
- redacted screenshot or dashboard view;
- exact Git revision and passing CI;
- customer consent where a real customer input is used.

The generation-time `if_generation_match=0` precondition prevents accidental
overwrite of an existing event object. A production claim of retention,
tamper-resistance, or regulatory immutability additionally requires reviewed
bucket IAM, retention-policy, and audit-log evidence.
