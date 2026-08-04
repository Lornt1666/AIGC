# Ω Mission OS Increment 11.2 — Issue-Driven Exact-SHA Dispatch Bridge

## Status

Concept implementation under governed review. Production activation remains false. No external provider action is authorized.

## Purpose

Increment 11.2 removes the final manual `workflow_dispatch` dependency from the Exact-SHA CI Receipt Broker. An authorized repository operator can create a structured GitHub Issue through the connected GitHub interface. A workflow definition loaded from the default branch validates that issue and executes the existing canonical validation runner against the exact requested commit.

## Trust architecture

```text
Authorized issue author
        |
        v
Closed issue request + exact label
        |
        v
Default-branch issues workflow
        |
        +--> immutable github.workflow_sha checkout
        +--> issue/actor/replay validation
        +--> target existence and main reachability
        +--> exact commit and tree checkout
        +--> shared canonical AIGC CI runner
        +--> runner-isolated atomic evidence
        +--> exact receipt and upload inventory
        +--> terminal issue revalidation
        +--> bounded success comment and issue closure
```

The issue branch cannot provide executable code. The workflow, parser, contract, canonical runner, and receipt builder are loaded from the immutable workflow revision on the default branch.

## Request contract

The request accepts only:

- schema version;
- constrained request ID;
- fixed repository and `main` branch;
- full target SHA;
- full broker revision;
- the complete canonical seven-stage check set;
- `production_activation_authorized=false`;
- `external_action_authorized=false`.

Arbitrary commands, workflow names, paths, environment variables, credentials, provider actions, deployments, and repository mutations are not accepted.

## Authorization and replay resistance

The workflow requires:

- label `exact-sha-ci-request`;
- issue state `open`;
- author association `OWNER`, `MEMBER`, or `COLLABORATOR`;
- event actor identity equal to issue-author identity;
- exact authority confirmations;
- no recognized secret material;
- no prior completion marker for the same issue request;
- no other issue containing the same request ID;
- unchanged issue body, timestamps, author, state, and label before evidence finalization and before terminal mutation.

The immutable execution binding covers issue number, node ID, creation and update timestamps, body digest, actor login and numeric ID, request ID, target SHA, broker revision, and request digest.

## Permission boundary

```yaml
permissions:
  contents: read
  issues: write
```

Issue write permission is used only for bounded result comments and closing a successfully completed request issue. The workflow grants no contents write, pull-request write, actions write, OIDC, secrets, deployment, Terraform apply, Gmail, or external-provider authority.

## Evidence

Every successful run produces:

- exact target and tested-tree binding;
- canonical stage records in runner-controlled temporary storage;
- atomic stage publication;
- individual command exit-code and output digests;
- issue execution envelope;
- artifact manifest;
- phase-one receipt;
- completion manifest;
- exact terminal upload inventory.

The receipt records broker validation success while leaving GitHub's eventual workflow conclusion as `pending`, because a running workflow cannot truthfully attest its future terminal state.

## Terminal behavior

Success:

1. revalidate the unchanged issue;
2. upload the verified receipt bundle;
3. revalidate the issue again;
4. append a bounded completion comment;
5. close the issue as completed.

Failure:

1. fail closed;
2. append a bounded non-secret failure classification when possible;
3. leave the issue open;
4. preserve production and external-action authorization as false.
