# AIGC One-Click Operator Cockpit

## Start

On Windows, double-click:

```text
INITIALIZE_AIGC.bat
```

The launcher runs the safe local initialization sequence and opens the Streamlit cockpit only when required initialization steps complete.

Existing users may also double-click:

```text
RUN_AIGC_COCKPIT.bat
```

which opens the composed cockpit directly.

## Initialization sequence

The Initialize button performs only:

1. local SQLite state initialization;
2. repository contract validation;
3. local program-health evaluation;
4. structural readiness evaluation;
5. read-only work-acquisition packet preparation;
6. cockpit smoke validation;
7. mock-only, no-network provider discovery.

It does not install packages, log in, use credentials, contact job platforms, submit applications, send messages, schedule interviews, accept contracts, run Terraform apply, create cloud resources, deploy, or deliver work.

## Jobs & Interviews

The Jobs & Interviews tab supports two governed intake paths.

### Read-only opportunity radar

The operator may click:

```text
Refresh read-only opportunities
```

This runs AIGC Phase 2 against the currently approved public API/RSS sources. It collects, normalizes, classifies, scores, and queues opportunities. It does not log in, use credentials, apply, message an employer, submit a proposal, or make an external commitment.

Eligible job records may then be selected from the Phase 2 queue and converted into internal review packets. Rejected records and non-job/open-source records are not imported into the job-application queue.

Each imported packet retains:

- source platform and official URL;
- radar score and decision;
- platform-policy status;
- risk and forbidden flags;
- approval requirements;
- source-attribution requirements.

### Manual posting entry

The operator may alternatively record an official posting URL and enter the role, organization, requirements, and verified qualifications directly.

### Review and acceptance

For either intake path, the operator may:

- enter verified qualifications;
- prepare or edit an application draft;
- prepare interview notes;
- review the complete packet and radar evidence;
- type an exact acceptance phrase;
- approve the packet for **manual operator submission only**;
- open the official posting and submit manually;
- record an interview invitation internally;
- download application, interview, and audit packets.

## What acceptance means

```text
APPROVED_FOR_MANUAL_OPERATOR_SUBMISSION
```

means the reviewed draft may be manually copied or submitted by the accountable operator on the official platform.

It does not mean:

- the application was submitted;
- a message was sent;
- credentials were used;
- a form was filled automatically;
- an interview was scheduled;
- an external contract or offer was accepted.

## Existing governed controls preserved

The composed cockpit retains:

- Run;
- New Work Order;
- Paycheque Pipeline;
- Review & Accept;
- Audit / Transparency;
- exact-phrase acceptance;
- Deny and Revise outcomes;
- emergency stop;
- external-action false receipts.

## Future live connectors

A future approved connector may prepare a separately reviewable outward-action packet. Any actual application submission, message, scheduling change, contract acceptance, cloud apply, or delivery must remain separately authorized, exact-action scoped, platform compliant, auditable, and revocable.
