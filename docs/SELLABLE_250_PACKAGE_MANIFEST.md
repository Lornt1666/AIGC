# AIGC Sellable Package Manifest

Copyright (c) 2026 Justice Gray Maciocha. All Rights Reserved.

## Package positioning

Suggested product name:

**AIGC Governed Worker Command Center**

Suggested price point:

**USD 250 per folder/license**, subject to your final licensing terms, customer support model, and jurisdiction.

## What the buyer receives

- A local and cloud-launchable command center.
- Docker deployment support.
- Render, Fly.io, and Google Cloud Run launch paths.
- A governed business pipeline from opportunity discovery to handoff readiness.
- Human review packets with acceptance, denial, revision, and emergency stop controls.
- Phase 24 autonomic business pipeline records.
- Tests, CI workflow, deployment scripts, and documentation.
- A master prompt and architecture specification.

## Buyer requirements

The buyer needs:

- Python 3.12 or Docker;
- Git;
- optional cloud account for internet deployment;
- operator-owned command center token configured outside Git;
- their own API keys if they extend the system with model calls or third-party connectors;
- responsibility for platform terms, local laws, privacy requirements, and employer/client consent.

## Pre-sale checklist

Before distributing a copy:

- run `python -m pytest`;
- run `python src/aigc.py validate`;
- run the redaction scanner;
- verify there are no private credentials;
- verify the command center is not public without authentication;
- remove private generated data if needed;
- verify launch instructions on a clean machine;
- update the version number and release notes;
- zip the folder from a clean export, not from an active working directory containing secrets.

## Clean export command

```powershell
git archive --format zip --output AIGC-Governed-Worker-v0.1.0.zip HEAD
```

## Buyer warning label

This product is a governed automation and business-workflow framework. It does not guarantee jobs, contracts, income, approval, or acceptance by employers. Buyers must use it within platform rules, laws, privacy requirements, and disclosure obligations.

## Recommended support tiers

- **Folder only** — USD 250.
- **Folder + setup call** — higher price.
- **Folder + custom deployment** — higher price.
- **Enterprise customization** — quote separately.

## Release notes template

```text
Version:
Date:
Hash:
Included features:
Known limitations:
Deployment targets tested:
Security review completed:
```
