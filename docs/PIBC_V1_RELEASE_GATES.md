# PIBC-v1 Release Gates

1. Exact-head GitHub Actions passes.
2. No unresolved review findings remain.
3. Migration is verified against empty and existing databases.
4. Redaction and secret scans pass.
5. Production-readiness remains false unless separately evidenced.
6. Operator gives an explicit merge decision.
7. Any live provider, credential, or deployment work is isolated in a later reviewed PR.
