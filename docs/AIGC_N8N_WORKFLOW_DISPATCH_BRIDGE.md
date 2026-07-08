# AIGC n8n Workflow Dispatch Bridge

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Prime Thesis

The proper external trigger bridge is:

```text
Chat-log or desktop event
  -> n8n Webhook node
  -> trigger validation
  -> n8n HTTP Request node
  -> GitHub workflow_dispatch
  -> AIGC Narration Trigger workflow
  -> artifact bundle
  -> operator review
```

This avoids relying on GitHub issue-comment events created by automation, which may not reliably start a workflow from connector-created comments.

## Why n8n

n8n's Webhook node can start a workflow when it receives data from apps or services. It supports test and production URLs, and the production URL is registered when the workflow is published.

n8n's HTTP Request node can call REST APIs, which makes it the correct node for calling GitHub's workflow dispatch endpoint.

GitHub's workflow dispatch endpoint is designed to manually trigger a GitHub Actions workflow. It requires the workflow to support `workflow_dispatch`, a `ref`, and optional configured `inputs`.

## Required n8n Nodes

### 1. Webhook Intake

- Node: Webhook
- Method: POST
- Path: `aigc/run`
- Authentication: header auth required
- Purpose: receive chat-log or desktop trigger payload.

Expected payload:

```json
{
  "narration": "AIGC",
  "project_profile": "auto",
  "run_mode": "artifact_generation",
  "submission_decision": "review_only",
  "submission_phrase": ""
}
```

### 2. Validate Trigger

- Node: Code
- Purpose: require narration to contain `AIGC`.
- Default to review-only mode.
- Reject proceed unless phrase equals `PROCEED AIGC SUBMISSION`.

### 3. GitHub Workflow Dispatch

- Node: HTTP Request
- Method: POST
- URL:

```text
https://api.github.com/repos/Lornt1666/AIGC/actions/workflows/aigc_constellation_trigger.yml/dispatches
```

Headers:

```text
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2026-03-10
Authorization: Bearer <n8n GitHub credential>
```

Body:

```json
{
  "ref": "main",
  "inputs": {
    "narration": "AIGC",
    "project_profile": "auto",
    "run_mode": "artifact_generation",
    "submission_decision": "review_only",
    "submission_phrase": ""
  }
}
```

The GitHub credential must have Actions write permission for this private repository.

### 4. Audit Response

- Node: Respond to Webhook
- Purpose: return accepted dispatch metadata and no secret values.

Example response:

```json
{
  "accepted": true,
  "workflow": "AIGC Narration Trigger",
  "repo": "Lornt1666/AIGC",
  "ref": "main",
  "mode": "review_only",
  "secret_values_returned": false
}
```

## Required Secret Handling

n8n stores its GitHub credential internally. AIGC stores only references.

Allowed references:

```text
n8n_credential://GITHUB_ACTIONS_DISPATCH_CREDENTIAL
gcp_secret://AIGC_WORK_SOURCE_CONNECTOR_ALLOWLIST/latest
gcp_secret://AIGC_OPERATOR_GOOGLE_WORKSPACE_EMAIL/latest
```

Raw credential values must not be written to:

- AIGC repo;
- AIGC artifacts;
- GitHub workflow logs;
- reports;
- ChatGPT messages;
- Codex prompts.

## Failure Checks

If the bridge does not start a run, check:

1. n8n workflow is active.
2. Production webhook URL is used, not test URL.
3. GitHub credential has Actions write permission.
4. Workflow file name is exactly `aigc_constellation_trigger.yml`.
5. Branch ref is `main`.
6. Body includes `narration: AIGC`.
7. Submission mode is review-only unless exact proceed phrase is supplied.
8. GitHub Actions is enabled for the repository.

## Local GitHub CLI Fallback

```powershell
gh workflow run aigc_constellation_trigger.yml `
  -f narration="AIGC" `
  -f project_profile="auto" `
  -f run_mode="artifact_generation" `
  -f submission_decision="review_only"
```

Then inspect:

```powershell
gh run list --workflow "AIGC Narration Trigger" --limit 5
gh run view <RUN_ID> --log
```

## Short Form

```text
n8n receives AIGC.
n8n validates AIGC.
n8n dispatches GitHub Actions.
GitHub runs the pipeline.
AIGC emits artifacts.
The operator reviews before anything leaves.
```
