# PIBC-v1 Test Matrix

| Control | Evidence |
|---|---|
| Strict context schema | `tests/contracts/test_identity_boundary_schema.py` |
| Strict receipt schema | `tests/contracts/test_identity_boundary_schema.py` |
| Local permit | `tests/application/test_identity_boundary.py` |
| Local provider denied in production | application and API tests |
| Exact revision required | application tests |
| Role injection denied | application and adapter tests |
| Project membership required | application tests |
| Replay is deterministic | application tests |
| Changed-intent replay denied | application tests |
| Adapter remains IAL0/AAL0/FAL0 | adapter tests |
| Receipt restart persistence | persistence and API tests |
| Receipt update/delete prohibited | persistence tests |
| Raw secret material absent | adapter, persistence, and API tests |
| Multiple migrations remain idempotent | updated SQLite storage regression |

The full repository test suite and CI remain the authoritative verification gate.
