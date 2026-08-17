# RegenExcalibur AIGC ForgeRunner

ForgeRunner executes the AIGC validation suite on operator-owned compute without consuming a GitHub-hosted runner. It is a local exact-SHA evidence engine, not a persistent GitHub Actions agent and not merge authority.

**Business identity:** RegenExcalibur

**Employee attribution:** `1JGM`

## Security model

ForgeRunner deliberately has no pull-request webhook and cannot accept a branch name at execution time. An operator first creates a short-lived request bound to:

- a full target commit SHA and its exact tree SHA;
- a trusted ancestor;
- the current broker revision;
- the canonical runner-contract digest;
- an ordered stage set;
- a maximum two-hour validity window;
- zero external-action, provider-call, secret-access, deployment, and merge authority.

The request is consumed once. The commit is exported with `git archive` into a disposable directory with no `.git` metadata. Commands use argv arrays—never a shell—and run with a scrubbed environment, inert provider token, disabled package-index access, loopback-only proxy settings, an isolated home/temp directory, and no inherited credentials.

The process-level network guard is **not** kernel isolation. Run unfamiliar code only in a disposable OS account, VM, or container with an OS-enforced network deny rule. Do not install ForgeRunner as a persistent privileged service and never attach cloud or production secrets to its account.

## Requirements

- Python 3.12 or newer
- Git
- The repository's already-installed Python dependencies
- Optional local PostgreSQL at `127.0.0.1:5432/aigc_test`

No GitHub token, cloud credential, paid provider, or registration token is needed.
The dependency-integrity stage checks every exact pin in `requirements.txt` with
Python package metadata, so the runner does not depend on `pip` being installed
and never contacts a package index.

## Create a one-use exact-SHA request

Write requests and receipts outside the repository so the trusted broker worktree remains clean:

```bash
python scripts/run_operator_owned_ci.py plan \
  --repository-root . \
  --target-sha d6c5c584830b9e80bd5a6731ca837fad715fdc4f \
  --trusted-base-sha 451156970e511b2781e486a3e290edaa5c0f231b \
  --expires-minutes 30 \
  --output ../forge-request.json
```

The target commit must exist in the local object database. Fetch it read-only first when necessary.

## Execute once

```bash
python scripts/run_operator_owned_ci.py run \
  --repository-root . \
  --request ../forge-request.json \
  --output-root ../forge-receipt \
  --state-root ~/.regenexcalibur/aigc-forgerunner/state
```

Add `--local-postgres` only when a passwordless, loopback-only test database is already running. It sets the fixed test DSN `postgresql://postgres@127.0.0.1:5432/aigc_test`; it never starts or mutates an external database.

## Receipt interpretation

- `PASS`: every closed contract stage succeeded for the bound SHA/tree.
- `FAILED_SAFE`: a stage failed or timed out; later stages were not executed.
- `BLOCKED`: identity, ancestry, tree, approval, expiry, replay, worktree, or contract admission failed before execution.

Receipts contain stage and output hashes plus sanitized failure tails, but never full logs or inherited environment values. A local `PASS` does not claim GitHub-hosted CI, PostgreSQL coverage unless enabled, deployment readiness, merge authority, or production activation.

## Recommended operating topology

1. Use a dedicated non-admin OS account with no browser sessions or credentials.
2. Clone AIGC read-only into that account.
3. Install dependencies from reviewed lock or requirement files before execution.
4. Disconnect external networking or enforce an OS firewall deny rule.
5. Create the one-use request from the reviewed commit and trusted base.
6. Execute ForgeRunner and archive the receipt directory read-only.
7. Publish only the sanitized receipt after a separate repository-write approval.
8. Destroy the disposable workspace or VM.

This topology avoids GitHub-hosted runner billing while keeping code execution under explicit operator control.
