# Connect AIGC to ChatGPT, Codex, Skills, and a Custom App

**Repository:** `Lornt1666/AIGC`  
**Objective:** Make the repository available as live context in ChatGPT, writable through Codex, and operable through a private AIGC MCP app.

This document separates four capabilities that are often conflated:

```text
GitHub app in ChatGPT  = read/search/analyze/cite repository content
Codex environment      = inspect/edit/test/commit/push/prepare pull requests
ChatGPT Skill          = reusable AIGC operating procedure
Custom AIGC MCP app    = live runtime tools and interactive UI inside ChatGPT
```

None of these connections independently authorizes merge, deployment, Terraform apply, billing changes, job submission, employer communication, or production action.

---

## 1. Connect the GitHub repository to ChatGPT

In ChatGPT web:

```text
Settings
→ Apps
→ GitHub
→ Connect
```

GitHub will open an authorization flow. Select the account or installation and grant access to:

```text
Lornt1666/AIGC
```

Return to ChatGPT and, when offered, select AIGC for sync.

### If AIGC is not visible

1. Open `Settings → Apps → GitHub`.
2. Select **Choose repositories** or **Configure repositories on GitHub**.
3. Confirm the private repository is authorized.
4. Allow several minutes for availability.
5. If required, trigger GitHub search indexing using GitHub's repository search.

### Capability boundary

The GitHub app gives ChatGPT live repository-reading context. Use it to:

- inspect source;
- search concepts;
- review architecture;
- cite repository evidence;
- compare documentation with code.

Use Codex for code generation, editing, commits, and pull requests.

Official reference:

```text
https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt
```

---

## 2. Create a Codex environment for AIGC

In ChatGPT:

```text
Codex
→ Connect to GitHub
→ authorize GitHub if required
→ Environments
→ Manage Environments
→ Create Environment
→ select Lornt1666/AIGC
```

Recommended environment name:

```text
AIGC Engineering — Private
```

Recommended description:

```text
Evidence-bound engineering environment for Lornt1666/AIGC. Never write directly
 to main, never self-approve, and preserve exact revision, testing, evidence, and
 operator-review gates.
```

Start with basic environment configuration. Do not add broad secrets or unnecessary setup automation.

### First Codex task

Open Code mode and paste:

```text
Use docs/AIGC_OMEGA_PRIME_ENGINEERING_EXECUTION_DIRECTIVE.md as the governing
execution contract. Begin with the execution-mode declaration and a fresh
repository truth snapshot. Do not modify anything until that snapshot is complete.
```

### Codex authority boundary

Codex may, within an approved bounded task:

- inspect the repository;
- create a branch;
- edit files;
- run tests;
- commit changes;
- push its branch;
- prepare a draft pull request.

Codex may not independently:

- merge;
- deploy;
- apply Terraform;
- alter billing;
- use unapproved credentials;
- submit an application or deliverable;
- make contractual or employer commitments.

Official reference:

```text
https://help.openai.com/en/articles/11390924
```

---

## 3. Create the AIGC Ω-Prime Skill

Open:

```text
Plugins
→ Skills
→ Create
→ Create with editor
```

Create a Skill named:

```text
AIGC Ω-Prime Engineering
```

Suggested description:

```text
Use this Skill to inspect, diagnose, implement, review, release, and operate
Lornt1666/AIGC under its evidence-bound architecture, critical path, approval
boundaries, and exact-revision engineering process.
```

Include:

```text
SKILL.md
resources/AIGC_OMEGA_PRIME_ENGINEERING_EXECUTION_DIRECTIVE.md
resources/CHATGPT_CODEX_REPOSITORY_INTEGRATION.md
```

The Skill should activate for prompts such as:

```text
Use AIGC Ω-Prime Engineering. Inspect the current critical path.
Use AIGC Ω-Prime Engineering. Diagnose PR #123.
Use AIGC Ω-Prime Engineering. Prepare the next bounded implementation train.
Use AIGC Ω-Prime Engineering. Review the ChatGPT app tool surface.
```

It should not activate for unrelated repositories or generic programming questions.

### Skill rule

The Skill must refetch live GitHub state. It must never treat the revisions embedded in a resource as permanent truth.

OpenAI Skills are reusable workflows that can contain instructions, examples, supporting resources, and code. Skills can be uploaded or created in the Skills editor and are also supported in Codex.

Official reference:

```text
https://help.openai.com/en/articles/20001066
```

---

## 4. Build and connect the AIGC custom ChatGPT app

A Skill supplies procedure. The custom app supplies live tools, state, and interactive UI.

### Required architecture

```text
ChatGPT
→ AIGC MCP server over remote HTTPS
→ AIGC control plane
→ PostgreSQL, queue, agents, approvals, audit, evidence
→ approved adapters
```

### Required server endpoints

```text
GET  /health
GET  /readiness
POST /mcp or streamable MCP endpoint at /mcp
```

### Minimum first-release tools

```text
aigc_get_system_status
aigc_get_agent_fleet
aigc_list_opportunities
aigc_get_opportunity
aigc_list_active_quests
aigc_get_quest
aigc_list_approvals
aigc_get_approval_packet
aigc_get_evidence
aigc_get_readiness
aigc_analyze_opportunity
aigc_prepare_application
aigc_create_application_packet
aigc_create_work_order
aigc_plan_quest
aigc_delegate_internal_task
aigc_stop_all_agents
```

Do not expose job submission, employer messaging, contract acceptance, cloud mutation, or computer control in the first app release.

### Developer Mode connection

ChatGPT connects to remote MCP servers, not directly to a localhost-only endpoint.

Use either:

```text
reviewed remote HTTPS hosting
```

or:

```text
Secure MCP Tunnel for a private/local server
```

Then in ChatGPT web:

```text
Settings or Workspace Settings
→ Apps
→ Advanced Settings / Developer Mode
→ Apps
→ Create
→ enter MCP endpoint
→ choose authentication
→ Scan Tools
→ review tool names, schemas, annotations, and side effects
→ Create draft app
```

Test privately before publishing.

Official references:

```text
https://help.openai.com/en/articles/12515353-build-with-the-apps-sdk
https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt-beta
```

---

## 5. Required ChatGPT app evidence

Do not claim the app is installed or functional until all applicable evidence is observed:

```text
remote MCP endpoint reachable
TLS valid
health endpoint passes
authentication succeeds
Scan Tools completes
tool inventory captured
read tool succeeds
widget resource loads
Command Centre renders
Approval Inbox renders
error state renders
repeated read calls are idempotent
write tool confirmation appears where supported
app version recorded
```

Create:

```text
reports/chatgpt/developer_mode_smoke.json
reports/chatgpt/tool_inventory.json
reports/chatgpt/tool_annotation_review.json
reports/chatgpt/widget_accessibility_review.json
reports/chatgpt/csp_review.json
```

---

## 6. Plan and workspace limitations

Current product availability may vary by plan and workspace role.

- Custom MCP app development and full write/modify actions require supported workspace capabilities and Developer Mode.
- A local MCP server cannot be connected directly without a remote endpoint or Secure MCP Tunnel.
- The built-in GitHub app is repository-reading context; repository editing and PR work belong in Codex.
- Custom apps should be tested as drafts before workspace publication.

Always verify the current product UI and official documentation rather than relying on screenshots or historical wording.

---

## 7. End-to-end acceptance test

The integration is complete only after this operator journey succeeds:

```text
ChatGPT reads live AIGC repository context through GitHub
→ Codex opens AIGC environment
→ Codex reads the Ω-Prime directive
→ Codex creates a bounded branch and draft PR for an authorized task
→ AIGC MCP app is scanned in Developer Mode
→ Command Centre renders live backend state
→ operator opens Approval Inbox
→ an internal approval decision is recorded
→ audit evidence is retrievable
→ no unauthorized external action occurs
```

Expected authority state:

```text
operator_review_required=true
automatic_merge_allowed=false
self_approval_allowed=false
automatic_external_commitment_allowed=false
unreviewed_terraform_apply_allowed=false
external_action_performed=<observed value only>
```
