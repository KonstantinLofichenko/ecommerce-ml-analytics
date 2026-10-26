# Historical investigations and proposals

These documents preserve dated evidence, not current deployment instructions.
Use the [funnel data contract](../funnel-data-contract.md),
[architecture](../architecture.md), [operations guide](../dashboard-v1-operations.md)
and [V1.0 acceptance report](../reports/metabase-v1-synerise-refactor.md) for current work.

| Area | Archived documents | Why retained |
| --- | --- | --- |
| Infrastructure | [Phase 3.1 verification](infrastructure/phase-3.1-infrastructure.md) | Original startup corrections and initial resource limits; later limits supersede them. |
| GA4 | [Public-data assessment](ga4/phase-3.3-ga4-assessment.md), [generator assessment](ga4/phase-3.3-ga4-generator-assessment.md) | Distinct unexecuted-access and executed-generator findings; neither is current dashboard acceptance evidence. |
| Synerise design | [Architecture proposal](synerise/phase-3.4-synerise-architecture.md), [benchmark protocol](synerise/benchmark-plan.md), [workflow](synerise/workflow.md) | Proposed schemas, transport alternatives and recovery decisions, superseded in part by the simpler bulk load. |
| Synerise execution | [Benchmark](synerise/phase-3.4.1-synerise-ingestion-benchmark.md), [partial native ingestion](synerise/phase-3.5-synerise-native-ingestion.md) | Unique memory failures, partial private-release state and stronger checks that must not be confused with final count-only acceptance. |
| Unsent draft | [Publisher inquiry](synerise/phase-3.3-synerise-publisher-inquiry.md) | Unique unresolved provenance/clock questions. This is not evidence of publisher contact. |

Executable research scripts, tests, original aggregate JSON, source manifests,
commented DDL and SQL audits retain their paths under `analysis/` to preserve
reproduction and script-relative fixtures. They are historical research tools,
not automatic current-production workflows. The older failed-run package remains
under `analysis/synerise/ingestion/history/2026-10-21-failed/`.

The source assessment and provenance report remain in `docs/reports/`: their
unresolved findings still qualify current usage, and the assessment renderer
retains its original output path. REES46 and ML milestone reports are also retained.

Only `analysis/synerise/ingestion/counts.md` and `performance.md` were removed:
they contain generated tables duplicated in the archived native-ingestion report
and reproducible from retained JSON through the unchanged `report.py` script.
Their regenerated paths are explicitly ignored. No unique validation evidence
or original dataset was removed.

For new experiments use ignored `scratch/`, `analysis/scratch/`, `analysis/output/`
or `docs/scratch/`; generated production artifacts continue to use ignored
`data/processed/`. Promote only reviewed methodology, scripts, fixtures and compact
evidence to tracked locations. Markdown, JSON and SQL are not globally ignored.
