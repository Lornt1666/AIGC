# AIGC Quantum Onion Sentinel — Tailored Defense Blueprint

## Authority and Scope

Justice Gray Maciocha, Satoshi, Lornt — Quantum Onion Sentinel initialized.

This blueprint applies the Quantum Onion Sentinel doctrine to the specific `Lornt1666/AIGC` repository and its current local-operator architecture.

This document is defensive only. It does not define offensive exploitation, credential misuse, backdoor access, surveillance bypass, or uncontrolled external sharing.

## 1. Executive Summary — Bird's Eye View

AIGC is a local governed operator program with:

- a unified CLI;
- a local Streamlit cockpit;
- JSON-schema contract gates;
- local artifact receipts;
- work-acquisition and work-performance packets;
- approval-gated external action procedures;
- counterparty request intake;
- communication and observer-access packets;
- chat-log scoped observer hardening;
- secret-reference and redaction controls;
- emergency-stop and audit-ledger posture.

The Quantum Onion Sentinel converts this into a layered security program:

```text
Aegis Shield      -> abuse resistance, rate limits, redaction, safe boundaries
Excalibur Seals  -> identity, approval gates, least privilege, no self-approval
Quantum Maze     -> adaptive risk scoring, canaries, non-breaking parameter mutation
Medusa Chamber   -> containment, quarantine, emergency stop, forensic receipts
Ananta Core      -> minimal trusted base, schemas, secret references, immutable doctrine
```

The objective is not to make unverifiable claims of invincibility. The objective is professional defensive maturity: protect, validate, detect, contain, recover, and disclose evidence only through authorized, logged, minimum-necessary review.

## 2. Asset and Threat Inventory

### Core Assets

| Asset | Description | Sentinel priority |
|---|---|---|
| `src/aigc.py` | Unified CLI and operator entrypoint | Critical |
| `src/dashboard/operator_cockpit_app.py` | Local cockpit UI | High |
| `schemas/` | Contract-first validation boundary | Critical |
| `config/` | Governed runtime and policy inputs | High |
| `reports/artifacts/` | Generated receipts, packets, audits, observer exports | High |
| `memory/aigc_state.sqlite` | Local state and emergency-stop posture | Critical |
| `config/secret_manifest.json` | Secret references only, not raw secrets | Critical |
| `src/security/redaction_scanner.py` | Secret scanning and redaction gate | Critical |
| Work acquisition modules | Find/rank/prepare work packets | High |
| Counterparty intake modules | Prevent vague/random acceptance | Critical |
| Approval-gated action modules | Prepare popup/procedure packets | Critical |
| Communication observer modules | Prepare read-only counterparty visibility | Critical |
| Chat-log scoped observer modules | Prevent broad account/backend exposure | Critical |
| GitHub Actions workflow | CI security and validation gate | High |

### Threat Actors and Failure Modes

| Threat actor / failure mode | Risk | Sentinel response |
|---|---|---|
| Accidental over-sharing | Counterparty sees private repo internals or unrelated data | Scoped observer packets, redaction gate, selected artifacts only |
| Prompt injection | Counterparty text attempts to override operator controls | Counterparty intake, schema validation, approval-gated boundaries |
| Credential leakage | Secrets accidentally stored or logged | Secret references only, redaction scanner, no raw secret logging |
| Unauthorized automation | Submit/apply/pay/deploy without operator approval | Proceed button gate, external action default blocked |
| CI/CD drift | Unsafe changes enter `main` | PR workflow, tests, validation, branch discipline |
| Dependency/supply-chain risk | Malicious dependency or workflow compromise | SBOM, pinned dependencies, secret scanning, SLSA/OpenSSF roadmap |
| Observer crawl/indexing | Shared artifact discovered by crawlers or search engines | No-index policy, local packet first, no raw ChatGPT link sharing |
| Data retention overreach | Too much personal/counterparty data retained | Data minimization, artifact scoping, retention plan |
| False professional claims | AIGC fabricates credentials or completion state | Truthfulness gate, blocked fabricated credentials |
| Lawful disclosure mishandled | Overbroad or undocumented disclosure | Evidence export only, minimum necessary, jurisdiction review, audit receipt |

## 3. Quantum Onion and Mythic Layer Mapping

### Aegis Shield — Outer Wall

Concrete controls:

- deny-by-default external action posture;
- public/read-only source modes for work discovery;
- redaction scan before sharing or merging;
- rate-limit and throttling design for future connectors;
- bot/scraper resistance for future external endpoints;
- safe error messages without secret disclosure;
- observer packets marked no-index and local-first.

AIGC files and controls:

- `src/security/redaction_scanner.py`
- `config/work_domain_registry.json`
- `config/chatlog_scoped_observer_access.json`
- `config/communication_observer_access.json`

### Excalibur Seals — Inner Gates

Concrete controls:

- exact-phrase approval doctrine;
- operator popup with `Proceed` and `Cancel` states;
- no self-approval;
- counterparty request required before acceptance;
- platform terms review before external actions;
- least-privilege secret-reference policy;
- no credential use without reviewed integration.

AIGC files and controls:

- `src/core/approval_gated_external_actions.py`
- `src/core/external_action_procedures.py`
- `src/core/counterparty_request_intake.py`
- `src/security/approval_tokens.py`
- `src/security/secret_broker.py`

### Quantum Maze — Moving-Target Defense

Concrete controls:

- rotate canary identifiers in generated observer/action packets;
- mutate non-breaking risk thresholds by policy version, not by hidden behavior;
- change local artifact packet IDs and hashes per generation;
- decoy internal-only status items for suspicious observer requests;
- periodic health checks and integrity reports;
- deny sharing when packet hash or schema validation fails.

AIGC implementation stance:

- Mutation must be non-breaking.
- Mutation must not hide behavior from the operator.
- Mutation must not create deceptive external actions.
- Mutation must be auditable.

### Medusa Chamber — Petrification Zone

Concrete controls:

- emergency stop blocks runtime execution;
- suspicious external action requests become `blocked_pending_risk_review`;
- vague counterparty requests become `insufficient_information`;
- hard-blocked action requests receive disabled Proceed state;
- observer overreach requests produce a local report, not an invite;
- future connectors must isolate risky sessions into manual review.

AIGC files and controls:

- `src/core/state_store.py`
- `src/core/counterparty_request_intake.py`
- `src/core/approval_gated_external_actions.py`
- `src/core/chatlog_scoped_observer_access.py`

### Ananta Core — Heart of the Citadel

Concrete controls:

- schema-validated artifacts;
- minimal trusted CLI/cockpit surface;
- secret values never stored in repo;
- local artifact receipts;
- explicit safety boundaries in docs;
- production connector work deferred until each integration has a terms/API/security review.

AIGC files and controls:

- `schemas/`
- `src/core/contract_validator.py`
- `src/aigc.py`
- `src/core/program_health.py`
- `docs/AIGC_PROGRAM_RUNBOOK.md`

## 4. Detailed Defense Architecture

### Repository and Branch Controls

Required controls:

1. Keep `main` protected by PR workflow.
2. Require CI success before merge.
3. Require redaction scan before release.
4. Prefer signed commits where practical.
5. Add `CODEOWNERS` before multi-user collaboration.
6. Use branch names that describe the security scope.
7. Do not commit raw credentials, API keys, seed phrases, tokens, or OAuth secrets.
8. Treat generated artifacts as local evidence unless explicitly approved for sharing.

### CI/CD Controls

Required pipeline gates:

- unit tests;
- JSON-schema validation;
- redaction/secret scan;
- dependency vulnerability review;
- future SBOM generation;
- future provenance attestation;
- future workflow permission minimization;
- future scorecard-style repository posture check.

### Application Controls

Required implementation controls:

- no external action executes without procedure packet;
- no procedure packet proceeds without counterparty request when work/contract/action is involved;
- no acceptance is allowed when deliverables, terms, or acceptance criteria are missing;
- no observer packet shares hidden/system/developer/private content;
- no prompt-generated request can override hard blocks;
- no action packet may fabricate credentials or completion state.

### Data Controls

Required data controls:

- store only secret references in repo;
- minimize personal/counterparty data in routine logs;
- pseudonymize identifiers where possible;
- write audit receipts with event IDs, timestamps, and action states;
- redact before sharing;
- make exported evidence packets project-specific and revocable where supported.

## 5. Privacy, Logging, and Authorized Observability Design

AIGC supports three observability modes:

1. **Operator Observability** — full local view of project artifacts, receipts, status, risks, and blocked actions.
2. **Counterparty Observer Packet** — redacted, selected, project-specific view only.
3. **Authorized Evidence Export** — minimum-necessary evidence packet for lawful/process-bound review.

Hard requirements:

- no unrestricted backend access;
- no whole-account access;
- no raw ChatGPT link sharing by default;
- no hidden/system/developer/private content exposure;
- no unrelated client exposure;
- no silent sharing;
- all exports require audit receipts.

Authorized disclosure is not a backdoor. It is an evidence export workflow with scope review, operator review, redaction review, and audit logging.

## 6. Medusa-Style Intrusion Containment Plan

Containment states:

| State | Trigger | Result |
|---|---|---|
| `insufficient_information` | Missing work description, terms, deliverables, acceptance criteria | Ask for clarification |
| `blocked_pending_risk_review` | Risk flags, unclear terms, legal/financial/security concerns | Stop and request operator review |
| `hard_blocked` | Bypass, fabrication, secret misuse, self-approval | Proceed disabled |
| `observer_overreach_blocked` | Whole account/backend/raw chat access requested | Generate denial/evidence packet |
| `emergency_stop_active` | Operator triggers emergency stop | Runtime blocked |
| `petrification_zone` | Future connector detects boundary violation | Isolate, freeze, log, deny escalation |

## 7. Crypto-Agility and Post-Quantum Strategy

AIGC does not currently implement production network cryptography, but it must be designed to adopt crypto-agility when external services/connectors exist.

Required strategy:

- maintain a cryptographic inventory;
- abstract algorithms behind config/policy;
- avoid hard-coded algorithms and key sizes;
- prefer modern TLS from managed platforms for current integrations;
- plan hybrid classical + post-quantum key exchange when supported by the platform;
- track ML-KEM for key establishment and ML-DSA / SLH-DSA for signatures when mature platform support exists;
- rotate keys and certificates through documented lifecycle controls;
- never invent custom cryptography.

## 8. Abstract Security Code Art — Safe Pseudo-Code

```python
class AIGCQuantumOnionSentinel:
    def review_request(self, request):
        if self.emergency_stop_active():
            return self.medusa_block(request, "emergency_stop_active")

        if self.contains_hard_blocked_action(request):
            return self.medusa_block(request, "hard_blocked_action")

        if self.requires_counterparty_intake(request):
            intake = self.counterparty_intake(request)
            if not intake.ready_for_operator_popup:
                return self.medusa_block(request, intake.decision_state)

        packet = self.build_procedure_packet(request)
        packet = self.apply_redaction(packet)
        packet = self.attach_audit_receipt(packet)
        return self.operator_popup(packet)

    def operator_popup(self, packet):
        return {
            "title": "AIGC External Action Review",
            "exact_action": packet.action,
            "destination": packet.destination,
            "payload_hash": packet.payload_hash,
            "risk_class": packet.risk_class,
            "proceed_enabled": packet.redaction_passed and packet.policy_allowed,
            "external_action_performed": False,
        }

    def medusa_block(self, request, reason):
        receipt = self.write_forensic_receipt(request, reason)
        return {
            "decision": "blocked",
            "reason": reason,
            "receipt": receipt,
            "proceed_enabled": False,
            "external_action_performed": False,
        }
```

This is conceptual code art, not production connector code. It expresses control flow: validate, scope, redact, audit, then operator review.

## 9. Recommended Next Steps for AIGC Implementation

### Immediate

1. Keep PRs draft until CI passes.
2. Add the Sentinel blueprint to repo docs.
3. Run the Sentinel CLI locally after pulling main.
4. Review generated reports under `reports/artifacts/sentinel_security/`.
5. Keep all observer and communication packets local until approved.

### Next PRs

1. Add cockpit UI tab for Sentinel status.
2. Add cockpit UI tab for observer-packet review.
3. Add cockpit popup UI for approval-gated actions.
4. Add SBOM generation in CI.
5. Add `CODEOWNERS` and branch-protection documentation.
6. Add dependency update policy.
7. Add domain-specific read-only adapters one at a time.
8. Add connector-specific threat model before every official integration.

### Future Production Connector Gate

No live connector may be production-ready until it has:

- platform/API terms review;
- counterparty request visibility;
- secret-broker controls;
- least-privilege credential scope;
- explicit operator approval;
- audit receipt;
- rollback/correction plan;
- redaction review for all shareable artifacts;
- tests proving hard-blocked actions remain blocked.

## Final Sentinel Doctrine

AIGC is a governed operator system. The Sentinel does not make it invincible; it makes it disciplined.

The correct standard is:

```text
defensive only
schema-validated
approval-gated
redacted by default
specific-scope observer access
secret-reference only
CI-gated
lawful evidence export without backdoors
operator-controlled external threshold
```
