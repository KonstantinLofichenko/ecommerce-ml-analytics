# Validation reports and source evidence

The single current Dashboard V1.0 acceptance report is
[metabase-v1-synerise-refactor.md](metabase-v1-synerise-refactor.md).
Its aggregate baseline is [validation.json](../../analysis/catalog/metabase-v1/validation.json).
Use the [funnel contract](../funnel-data-contract.md) for definitions and
[operations guide](../dashboard-v1-operations.md) for rebuilds and memory guidance.

Retained reports with distinct scope:

- REES46 [behavior](phase-1.2-october-2019.md),
  [dataset build](phase-1.3a-october-2019-february-2020.md),
  [features](phase-2.3-features.md) and [baselines](phase-2.4-baselines.md)
  preserve the independent original analytics and ML project.
- [ClickHouse REES46 migration](phase-3.2-migration.md) preserves reconciliation
  and recovery evidence, including its stronger validation policy.
- [Synerise assessment](phase-3.3-synerise-assessment.md) and
  [provenance](phase-3.3-synerise-provenance.md) preserve unresolved source-version,
  clock and licensing assumptions. The assessment renderer keeps its original path.
- [Completed Synerise bulk load](phase-3.5-synerise-bulk-load.md) records the
  permanent dataset's count-only acceptance; it does not claim value reconciliation.

Superseded infrastructure, GA4 investigations, Synerise design/benchmark and partial
load reports are indexed in the [historical archive](../archive/README.md).
Those findings are retained, not discarded or promoted to current acceptance claims.
SQL execution audits are evidence and must not be replayed blindly. No original
research scripts, tests or unique validation data were deleted during organization.
