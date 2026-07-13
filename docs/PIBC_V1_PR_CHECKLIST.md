# PIBC-v1 Draft PR Checklist

- [x] Separate branch from exact main revision.
- [x] Contract-first JSON Schema Draft 2020-12.
- [x] Unknown properties fail closed.
- [x] Raw assertions, tokens, credentials, provider claims, and nonce values excluded from normalized contracts and receipts.
- [x] Caller-supplied roles and authority fields rejected.
- [x] Local adapter fixed to IAL0/AAL0/FAL0, EA1, and LOCAL_SIMULATION.
- [x] Production mode rejects local identity and unbound revisions.
- [x] Membership, tenant, project, session, assurance, expiry, and replay controls implemented.
- [x] Additive append-only SQLite receipt migration.
- [x] Internal local preflight API.
- [x] PIBC-focused schema, application, adapter, persistence, and API tests.
- [x] Production-readiness ledger unchanged.
- [ ] Full GitHub Actions CI passed at exact head revision.
- [ ] Accountable operator reviewed exact diff.
- [ ] Merge explicitly authorized.

No checklist item authorizes live identity-provider configuration, credential use, deployment, connector activation, contract acceptance, messaging, payment, delivery, or another external action.
