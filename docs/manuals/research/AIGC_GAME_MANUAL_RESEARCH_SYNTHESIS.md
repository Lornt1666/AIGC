# AIGC Game-Manual Research Synthesis

> **Repository snapshot:** `Lornt1666/AIGC` at current `main` head `293de53489fe7212fad272c01c698c0ffe2da610`, inspected 2026-07-11 (America/Edmonton). Open draft PRs are identified separately. This document does not authorize public deployment, live connector execution, employment promises, payment custody, or external action.


## Decision

The correct model for AIGC is a **hybrid living manual system**:

1. **An old-school mythic field manual** that gives the system identity, maps, roles, rituals, and strategic context.
2. **A searchable modular web/manual index** organized by operator state, career path, feature, and troubleshooting need.
3. **Study-sim technical volumes** for high-risk domains such as identity, authorization, connectors, payments, disputes, security, and recovery.
4. **Walkthrough missions** that teach by executing safe scenarios in a disposable environment.
5. **Contextual help** linked to actual phase/job states so the user sees the relevant page when a decision is required.
6. **Patch-aware versioning** that binds every manual to an exact repository revision and never presents future design as current runtime.

## What was studied

| Reference | Manual pattern | AIGC adaptation |
| --- | --- | --- |
| Final Fantasy XIV Play Guide | Modular living guide | Separate getting-started, controls/UI, classes/jobs, features, services, and patch-aware content; pair static documentation with contextual help. |
| EVE Academy | Career-path onboarding | Organize learning by the path a participant wants to pursue rather than forcing one linear manual. |
| OpenTTD Manual | Layered wiki/reference system | Start with install/tutorial/interface, then branch into systems, mechanics, settings, economy, multiplayer, hotkeys, and troubleshooting. |
| DCS Documentation | Module-specific study manuals | Complex systems need dedicated technical volumes, procedural checklists, terminology, and localized/revisioned editions. |
| HighFleet / Tunic / The Banished Vault | Manual as world artifact | Lore, visual identity, maps, and discovery can deepen engagement, but operational truth must remain explicit. |
| Manual-generation research | State and mechanic grounding | Useful manuals map rules to actions, visualize moves, explain strategy, and surface the section relevant to the current state. |

## The manual architecture selected for AIGC

### Layer A - One-page field card
Status, current revision, emergency stop, validate, run, review, accept, stop.

### Layer B - Book 0 quickstart
A guided first expedition through the current local/internal system.

### Layer C - Career paths
Worker, client, operator, architect, reviewer, trust-and-safety, finance, and SRE paths.

### Layer D - Module manuals
Each bounded context receives a dedicated book with commands, contracts, diagrams, failure modes, and tests.

### Layer E - Walkthrough missions
Synthetic discovery, qualification, technical-document production, bounded code change, rework, delivery simulation, incident, and restore.

### Layer F - Reference codex
Glossary, schemas, state transitions, approval classes, reason codes, CLI/API reference, data dictionary, and troubleshooting.

### Layer G - Live contextual help
Each UI state links to the book/runlevel that explains the current decision, required evidence, and consequences.

## Design rules

- **Mythic outside, exact inside.** Lore may name the realm; tables, commands, states, money, legal terms, and approvals use literal language.
- **Progressive disclosure.** A beginner sees the next safe action; an expert can drill into contracts and evidence.
- **State-indexed help.** Documentation is keyed to job state and capability maturity.
- **Role-indexed navigation.** Participants can follow the path relevant to their duties.
- **Version truth.** Implemented, draft, procured target, and blocked future are visually and semantically distinct.
- **Rehearsal before consequence.** Every high-impact workflow has a synthetic or sandbox walkthrough.
- **Patch resilience.** Procedure pages are generated from registries/contracts where possible and checked for drift in CI.

## Research sources

- **FINAL FANTASY XIV Play Guide.** Official modular guide covering controls, UI, classes/jobs, features, services, and patch-aware updates. https://na.finalfantasyxiv.com/lodestone/playguide/
- **EVE Academy.** Official role/career-path onboarding model. https://www.eveonline.com/eve-academy
- **OpenTTD Manual.** Official layered manual and wiki with tutorials, interface, systems, mechanics, settings, and troubleshooting. https://wiki.openttd.org/en/Manual/
- **DCS World Documentation.** Official module-specific technical-manual library. https://www.digitalcombatsimulator.com/en/downloads/documentation/
- **The revenge of the video game manual.** Reporting on immersive modern manuals for HighFleet, Tunic, Tren, and The Banished Vault. https://www.theguardian.com/games/2024/jan/17/the-revenge-of-the-video-game-manual-tunic-the-banished-vault
- **Automatic Generation of Board Game Manuals.** Research on rules translation, move visualization, strategy explanation, and full-manual assembly. https://arxiv.org/abs/2109.09507
- **Learning to Win by Reading Manuals in a Monte-Carlo Framework.** Research supporting state-relevant manual retrieval for complex tasks. https://arxiv.org/abs/1401.5390
- **NIST AI Risk Management Framework.** Voluntary trustworthiness and AI risk management reference; AI RMF 1.0 is under revision as of 2026. https://www.nist.gov/itl/ai-risk%2Dmanagement-framework
- **NIST SP 800-218 SSDF 1.1.** High-level secure software development practices integrated into the SDLC. https://csrc.nist.gov/pubs/sp/800/218/final
- **WCAG 2.2.** Current W3C Recommendation for accessible web content. https://www.w3.org/TR/WCAG22/
- **CRA RC4110 Employee or Self-employed.** Canadian worker-status factors; facts of the relationship control classification. https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/rc4110/employee-self-employed.html
