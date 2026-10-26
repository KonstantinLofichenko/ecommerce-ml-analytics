# Focused Synerise provenance and clock verification

See [findings](../../../docs/reports/phase-3.3-synerise-provenance.md) and
[unsent publisher inquiry](../../../docs/archive/synerise/phase-3.3-synerise-publisher-inquiry.md).
Earlier assessment and source files are preserved.

`verification.json` contains reverified archive/member/extracted hashes, archive
member metadata times, fresh Parquet counts and timestamp bounds, file metadata,
row-group signatures, hourly/date/second/minute/weekday aggregates and executed SQL
with hashes/timings. Raw identifiers are never exported. Original file names and
aggregate hash signatures are not customer-level exports.

`diagnostic-summary.json` summarizes interior-date activity, removing the two
partial boundary dates from hourly/weekday comparisons. `boundary-results.json`
counts purchases/clients within one hour on either side of existing snapshot and
label-end boundaries. These are proximity counts, not measured label changes or
inferred timezones. No source timestamps were shifted.

Official-source evidence saved on 21 October 2026: all 13 visible issues/PRs,
comments on the three entries with comments, repository metadata, empty release
and tag lists, archive HEAD response and Git README/split history summaries.
The issue API returned fewer than 100 entries; no further page was required.
`readme-count-history.json` extracts the reference table at each README revision.
The full 11-commit history was inspected in `/tmp/synerise-recsys2025`; no production
repository changes were made. Search output in `timezone-history-search.txt` is
empty because no matching historical code additions/removals were found, not
because historical timezone semantics have been proven absent everywhere.

## Reproduce local checks

```bash
.venv/bin/python analysis/synerise/provenance/verify.py
.venv/bin/python analysis/synerise/provenance/summarize.py
.venv/bin/python - <<'PY'
import json
import runpy
from pathlib import Path
import duckdb
module = runpy.run_path('analysis/synerise/provenance/verify.py')
with duckdb.connect() as connection:
    connection.execute("SET memory_limit='2GB'")
    connection.execute('SET threads=2')
    result = module['rows'](connection, Path(
        'analysis/synerise/provenance/boundaries.sql').read_text())
Path('analysis/synerise/provenance/boundary-results.json').write_text(
    json.dumps(result, indent=2, default=str) + '\n')
PY
.venv/bin/python -m pytest analysis/synerise/test_research.py -q
.venv/bin/ruff check analysis/synerise/provenance
.venv/bin/ruff format --check analysis/synerise/provenance
```

No second archive is downloaded and no extraction occurs. Verification opens
existing archive/Parquet only for reading and uses an ephemeral in-memory DuckDB
connection (2 GB/two threads). All source files are SHA-256 checked before and
after analysis. The archive's six members are streamed and hashed directly,
independently confirming that extracted files match the already downloaded archive.

Fixed 1,048,576-row Parquet groups are checked against metadata before computing
counts plus sum/XOR of DuckDB tuple hashes. No equal multiset signatures were found
within any file. This detects obvious whole-row-group repetitions, not arbitrary
partial overlap or copies with changed fields. Existing exact-duplicate rows remain
intact. Metadata date-range overlap across source types/row groups is expected and
is not itself duplicate data. The hash function is version-dependent; the diagnostic
is not a publisher-signed checksum or a formal collision-proof multiset proof.

A common-prefix diagnostic derives each reference count's crossing date from the
previously measured full-source daily aggregates, whose source hashes match now.
Different crossing dates rule out one shared earlier end cutoff *alone*. It does
not rule out combined time/customer filters or undocumented processing. Exact
row-level deduplication alone also leaves all five counts above their references.

Do not send the inquiry, create issues, change timezones or begin migration without
review and explicit authorization. HTTP headers, tar metadata, activity patterns
and generic Synerise platform timezone documentation do not establish the dataset's
source timezone or explain its count discrepancy.
