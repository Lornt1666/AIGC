# AIGC Independent Reviewer Recruitment and Onboarding Packet

## Purpose

This packet supports the lawful, attributable, least-privilege recruitment and onboarding of an independent reviewer for significant AIGC pull requests, beginning with PR #29.

It does not purchase approval, guarantee a favourable decision, grant authority by possession of a link, or allow the author/operator identity to satisfy an independence requirement.

## Immediate review target

- Repository: `Lornt1666/AIGC` (private)
- Pull request: PR #29 — Production Readiness Ledger
- Required reviewed head: `dc6b38204f3087eda7beb676ad53beecf1d8e1e2`
- Current automated evidence: CI previously successful on the exact head
- Required independent outcome: `APPROVE`, `REQUEST_CHANGES`, `COMMENT`, or decline
- Expected scope: bounded review of readiness-ledger evidence, schemas, tests, claims, and governance boundaries

## Candidate profile

A candidate should:

- use their own GitHub identity;
- be distinct from the PR author/operator;
- understand Python, tests, schemas, or software review sufficiently for the assigned scope;
- disclose conflicts of interest;
- accept private-repository confidentiality and minimum-data handling;
- review only within their competence;
- make a reasoned decision rather than a courtesy approval.

## Sourcing channels

Use the following order:

1. trusted developer, IT professional, instructor, classmate, or technical colleague;
2. Alberta or Canadian software/cybersecurity community;
3. recognized professional or local technology meetup;
4. reputable freelance reviewer for a bounded paid assessment;
5. experienced open-source maintainer willing to review private evidence.

Compensation, when used, pays for time and analysis—not for approval.

## Initial outreach template

> Hello,
>
> I am seeking an independent review of one bounded pull request in a private GitHub repository for the AIGC project. The pull request implements a production-readiness ledger and already has automated CI evidence plus a structured review checklist.
>
> I am asking for an honest technical decision: approve, request changes, comment, or decline. There is no expectation of a favourable result.
>
> Scope: PR #29 at exact head `dc6b38204f3087eda7beb676ad53beecf1d8e1e2`.
>
> The review focuses on evidence semantics, schemas, tests, unsupported production claims, release-gate behaviour, and governance boundaries. Repository access can be limited and revoked after the review.
>
> Please reply with your GitHub username, relevant experience, any conflict of interest, and whether you are willing to preserve the repository's confidentiality.

## Candidate screening checklist

- [ ] Candidate uses a distinct real GitHub identity.
- [ ] Candidate confirms willingness to provide an honest decision.
- [ ] Candidate states relevant competence.
- [ ] Candidate discloses conflicts or confirms none known.
- [ ] Candidate accepts confidentiality and acceptable-use expectations.
- [ ] Candidate agrees not to copy private repository material outside approved channels.
- [ ] Candidate agrees to inspect the exact head SHA.
- [ ] Candidate understands access may expire or be revoked after review.

## Least-privilege onboarding

1. Record candidate consent and GitHub username.
2. Grant only the repository permission required to review.
3. Request the reviewer on PR #29.
4. Provide the exact-head review packet and checklist.
5. Do not provide secrets, shared credentials, or unnecessary personal information.
6. Set a review target date and escalation contact.
7. Revoke access when the review relationship ends unless continued access is explicitly approved.

## PR #29 reviewer checklist

The reviewer shall:

1. Confirm the head is exactly `dc6b38204f3087eda7beb676ad53beecf1d8e1e2`.
2. Inspect the readiness scoring model for unsupported or misleading completion claims.
3. Verify structural evidence is not represented as runtime or production proof.
4. Verify schema strictness, revision binding, unknown-field handling, and evidence downgrade behaviour.
5. Verify `readiness --require-production-ready` fails while production blockers remain.
6. Inspect tests for malformed ledgers, missing evidence, unbound revisions, blockers, and release-gate failure.
7. Confirm no credentials, deployment, external actions, self-approval, or governance bypass were introduced.
8. Review rollback scope and known limitations.
9. Submit `APPROVE`, `REQUEST_CHANGES`, or `COMMENT` against the exact final head.

## Staleness rule

Any head change after packet generation or approval invalidates the prior exact-head review evidence. CI and independent review must be revalidated against the new head.

## Merge gate

PR #29 may proceed to operator-controlled merge only when:

- required CI is successful on the final head;
- one eligible independent reviewer has approved the final head;
- no unresolved mandatory review threads remain;
- operator merge authorization remains current.

## Post-review steps

- Record the reviewer identity, reviewed head, decision, and date.
- Resolve requested changes.
- Re-run CI after any change.
- Obtain renewed review if the head changes.
- Merge with expected-head protection only after all gates pass.
- Verify CI and readiness evidence on the resulting `main` revision.
- Revoke or retain reviewer access according to the agreed scope.
- Capture reviewer feedback to improve the Review Packet Generator and Engineering Review Council.

## Current status

At the time this packet was prepared, no distinct independent reviewer had submitted an approval for PR #29. The only submitted reviews were author/operator comments and do not satisfy separation of duties.
