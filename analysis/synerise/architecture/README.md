# Phase 3.4 architecture artifacts

[Architecture report](../../../docs/reports/phase-3.4-synerise-architecture.md).

- `proposed-ddl.sql`: six proposed raw tables; entirely commented, no automatic execution.
- `schema.py`: renderer shared with the isolated POC; not a migration runner.
- `workflow.md`: native/Python alternatives, recovery and release publication.
- `reconciliation.sql`: SELECT examples, explicitly parameterized Synerise database.
- `benchmark-plan.md`, `benchmark.py`: opt-in bounded POC, source/time/multiplicity checks.
- `benchmark-status.json`: attempts and reasons for safe rejection; no throughput invented.
- `benchmark-initial-schema-error.json`: failed initial DDL attempt and verified cleanup.
- `runtime-snapshot.json`: read-only live grants, memory and REES46 identity.
- `preservation.json`: local before/after preservation outcomes, no credential hashes.

The initial Docker-unavailable result was superseded after the user started Docker.
The first isolated DDL attempt failed a CHECK/ALIAS compatibility issue and was
cleaned up. Corrected benchmark retries stopped at memory checks before DDL/inserts.
At Phase 3.4 no successful ingestion measurement existed; do not interpret missing metrics
as zero-cost successful execution. Any later successful result must supersede this
status explicitly and preserve failure context.

No source mount, user/grant, Compose, production dbt or data changes are applied.
The temporary PyArrow environment is outside the project; no dependencies changed.

Phase 3.4.1 follow-up: [bounded benchmark](benchmark/README.md) records 65 successful
trials, a global tracker memory abort, verified cleanup and an INCONCLUSIVE decision.
It supersedes the old blocked status without deleting that historical evidence.
The renderer now uses the materialized tuple directly in partition/sort expressions.
