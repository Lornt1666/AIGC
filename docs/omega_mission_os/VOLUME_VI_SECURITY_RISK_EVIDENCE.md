# Volume VI — Security, Compliance, Risk, Incident, and Evidence Governance

## Security model

Mission OS is default-deny, least-privilege, revision-bound, and evidence-driven. Trust boundaries exist between users, agents, prompts, repositories, connectors, secrets, infrastructure, customers, and evidence stores.

## Mandatory controls

- durable emergency stop;
- role and capability separation;
- explicit read/write distinction;
- exact-action approvals with expiry;
- idempotency and replay protection;
- rate, budget, and model-call limits;
- secret-reference-only repository policy;
- input validation and output redaction;
- prompt-injection containment;
- immutable or append-only evidence records;
- incident classification and containment procedures.

## Risk register

Every material risk includes owner, category, likelihood, impact, exposure, controls, residual risk, trigger, review date, and disposition. Safety, legal, privacy, financial, security, reputational, operational, and model risks are tracked separately.

## Evidence taxonomy

- structural repository evidence;
- test and CI evidence;
- authorization evidence;
- execution receipts;
- staging operational evidence;
- production operational evidence;
- financial evidence;
- customer acceptance evidence;
- incident and recovery evidence.

Authorization evidence never substitutes for execution evidence. Simulations and projections are labeled and cannot promote production readiness.

## Incident lifecycle

`DETECTED -> TRIAGED -> CONTAINED -> INVESTIGATED -> REMEDIATED -> VERIFIED -> CLOSED -> LESSONS_ADMITTED`

Incidents may freeze affected missions and connector capabilities automatically, but external notification remains separately governed.

## Acceptance criteria

Implementation requires threat models, capability tests, adversarial prompt tests, secret scanning, evidence digest validation, incident drills, recovery evidence, and fail-closed behavior when canonical evidence is missing or contradictory.