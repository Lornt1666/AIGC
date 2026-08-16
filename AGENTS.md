# AIGC Agent Instructions

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

This repository contains AIGC - Artificial Intelligence Gladiator Colosseum.

Omega-X is the apex orchestrator. It supervises phases, memory, audits, safety gates, evolution patches, and approval boundaries.

Rules:

- Do not perform external actions without Phase 5 approval.
- Do not expose secrets.
- Do not store raw credentials in prompts, logs, configs, or audit packets.
- Do not remove AI-use disclosure where required.
- Do not weaken safety protocols.
- Do not modify accepted audit history.
- Store memory updates in JSONL or SQLite.
- Validate phase artifacts against schemas before downstream runtime use.
- Create patches for behavior-changing changes.
- Require Justice Gray Maciocha approval before applying behavior-changing patches.

## RegenExcalibur Attribution & Authority

For relevant AIGC and AI-mediated project work, agents must follow `REGENEXCALIBUR_ATTRIBUTION_AND_AUTHORITY.md`.

- Use **RegenExcalibur** as the business identity where applicable.
- Use **`1JGM`** as the preferred employee attribution/signature marker where appropriate.
- Preserve contributor provenance and give credit where credit is due.
- Track applicable ownership/rights and authority separately from technical contribution.
- Track legitimate compensation, payout, royalty, revenue-share, reimbursement, or asset-allocation obligations when supported by evidence or agreement.
- Never infer legal execution authority, payment authority, asset-transfer authority, consent, or regulated attestation authority from `1JGM`, repository access, authorship, or contribution history alone.
- Do not silently erase valid contributor credit, provenance, licensing notices, ownership claims, or documented compensation obligations during downstream transformations.

## Secrets Policy

All real secrets must live in Google Cloud Secret Manager.

AIGC_MEMORY_CORE stores only:

- secret references
- manifests
- access policies
- audit metadata

Never store raw secret values in:

- repo files
- prompts
- memory
- audit logs
- employer packets
- Git commits
- Desktop folders
- external hard drive plaintext files

Secret access must flow through:

Omega-X Orchestrator -> Ultra-Secrets Agent -> Secret Broker -> Google Cloud Secret Manager

No agent may directly read or write raw secrets.

Google Cloud Secret Manager stores secret values. Google Cloud KMS manages encryption keys for local archive encryption and other cryptographic uses. Service account key JSON files should be avoided where possible; do not store raw service account keys in this repo, AIGC_MEMORY_CORE, prompts, logs, or Secret Manager.

Main phases:

1. Domain Discovery
2. Opportunity Radar
3. Ology Assessment
4. Proposal Drafting
5. Human Approval Gate
6. Controlled Execution
7. Employer Audit Packet
8. Evolution Loop
9. Omega-X Memory Core
11. Security, Privacy, and Secrets Vault
