# Volume III — Agent Fabric, Tool Bus, Connectors, and Memory

## Agent contract

Each specialist agent requires a unique identity, purpose, scope, allowed tools, prohibited actions, input and output schemas, quality criteria, budget, timeout, escalation conditions, and accountable owner.

Agents are bounded workers, not independent authorities. Generated sub-agent plans remain inert until admitted through existing governance.

## Initial agent set

- Mission Director
- Revenue Analyst
- Opportunity Qualifier
- Proposal Architect
- Engineering Director
- Research Analyst
- Finance Controller
- Compliance Reviewer
- Security and Risk Officer
- Evidence Curator
- Documentation Manager
- Quality Inspector

## Tool Bus

All connector use passes through a single policy enforcement interface that checks:

1. authenticated actor;
2. requested capability;
3. mission and operation ID;
4. approval and expiry;
5. data classification;
6. rate, cost, and scope limits;
7. emergency-stop state;
8. evidence and redaction requirements.

Read, draft, and write capabilities are separate. A read grant never implies write authority.

## Memory domains

- Constitutional memory
- Mission memory
- Project and Quest memory
- Conversation and working memory
- Research memory
- Business and customer memory
- Evidence memory
- Archived memory

Every record includes provenance, confidence, classification, retention policy, and supersession status. Accepted evidence is append-only. Derived summaries may be regenerated but must retain links to source records.

## Prompt and context controls

External content is untrusted data. It cannot redefine system policy, approval phrases, tool permissions, or evidence rules. Context assembly uses least privilege and includes only records needed for the current operation.

## Acceptance criteria

Implementation requires agent schemas, capability manifests, connector policy checks, prompt-injection defenses, memory provenance, retention controls, and tests proving read/write separation and denial of self-escalation.