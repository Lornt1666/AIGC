# OS Architecture Blueprint

## Layers

1. **Identity:** canonical universe name, coordinator, seeder, watermark, and schema version.
2. **Coordination:** deterministic stage order and immutable role catalogue.
3. **Design:** ontology and architecture artifacts derived from a validated seed.
4. **Engineering:** typed models, closed APIs, JSON Schemas, and reusable receipts.
5. **Governance:** LIFE constraints, external-effect classification, human approval, and bounded recursion.
6. **Delivery:** MCP transport, fixed JSON bridge, CI, observability, and rollback evidence.

## Trust boundaries

- The Universe Gate accepts data, never authority.
- The Agent Forge returns descriptors, not independent operating-system processes.
- Provider calls, secrets, network access, spending, public writes, and production changes lie outside the Genesis trust boundary.
- The receipt hash covers normalized seed identity, stage identity, role identity, the evolution decision, and zero-egress assertion.

## Compatibility

The structured tool result is the primary interface. Widgets are optional. MCP clients can render the same result without AIGC-specific UI, and local callers can use the fixed stdin/stdout JSON bridge.
