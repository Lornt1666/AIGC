# Agent Forge Contract

The Forge contains eight named roles from the Genesis specification. In RX-0 a role is a typed descriptor—not a background process, person, legal principal, model account, or bearer of authority.

All roles share these invariants:

- effect ceiling: `LOCAL_DETERMINISTIC_PLAN`;
- no provider calls;
- no process spawning;
- no external mutation;
- no secret access;
- no ability to approve their own work;
- artifacts must pass LIFE and verification gates.

An adapter that later invokes an LLM or another worker must preserve these constraints, record exact model/provider identity, treat output as untrusted, and stop before any consequential action.
