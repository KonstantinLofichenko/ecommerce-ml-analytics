# Reports and retained evidence

The current Dashboard V1.0 report is [metabase-v1-synerise-refactor.md](metabase-v1-synerise-refactor.md).
It is the single final dashboard validation/rebuild report. Supporting aggregate
baselines remain in `analysis/catalog/metabase-v1/validation.json`.

Other reports are historical milestones, not alternate dashboard acceptance reports:

- Phase 1–2 reports preserve REES46 ingestion, feature definitions and baseline evaluation.
- Phase 3.1–3.2 preserve infrastructure, permissions, migration and reconciliation evidence.
- GA4 assessments preserve executed versus unexecuted research and generator limitations.
- Synerise assessment/provenance preserve unresolved archive counts, licensing and clock semantics.
- Architecture/benchmark/native-ingestion reports preserve distinct memory failures,
  checksum policies and partial private releases; the later bulk-load report describes
  the completed count-only permanent load. Earlier policies are not current acceptance gates.
- The publisher inquiry is an unsent draft, not evidence of external contact.

No report was deleted or relocated: these documents contain unique technical decisions
or validation evidence, and their existing reproduction links remain valid. Historical
SQL audits under `analysis/` are evidence, not safe scripts to replay blindly. Generated
runtime logs and temporary validation outputs are excluded from Git; source scripts,
small aggregate evidence and fixtures are retained.
