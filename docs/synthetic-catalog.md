# Synthetic Synerise catalog enrichment

Implemented and validated **23 October 2026**. Both dimensions are in
`synerise_analytics`:

| Model | Rows | Meaning |
| --- | ---: | --- |
| `dim_synerise_categories` | 6,912 | Every original Synerise category ID, with a synthetic display taxonomy |
| `dim_synerise_products` | 1,534,050 | Every original SKU, unchanged category/price bucket, synthetic Amazon title |

**Labels and title associations are synthetic display enrichment, not recovered
Synerise names or verified entity matches. Do not use them as ML predictors.**
Both models carry `is_synthetic_enrichment=1`, `mapping_version=amazon_catalog_v1`
and dbt metadata `exclude_from_ml: true`. Existing feature pipelines are unchanged.

## Mapping algorithm

1. Reuse `stg_amazon_products` for ASINs/titles and join the existing raw metadata
   by ASIN to recover its full category hierarchy. The staging model is unchanged.
2. Prefer a complete, trimmed hierarchy whose root matches the source department.
   Recognized Electronics roots are `Electronics` and `Car & Vehicle Electronics`;
   Beauty roots are `Beauty & Personal Care`, `All Beauty`, and `Premium Beauty`.
   A compatible hierarchy wins over conflicting `main_category`, with a quality flag.
3. When the hierarchy is absent or has missing child labels, use a recognized
   department/main-category fallback. A conflicting hierarchy root, unknown source
   department or unclassifiable record is excluded rather than relabeled silently.
   The recognized-main lists and classification logic are in the shared macro.
4. Define a taxonomy key as JSON `(source_department, selected full path)`. Rank
   eligible donors by unique `parent_asin`; rank donors within each taxonomy key
   by that same ID. All ordering has an explicit unique tie-breaker.
5. A version-seeded hash of each Synerise category ID selects one anchor donor's
   global rank. That donor defines the category's path and `Synthetic: ...` label.
   This samples paths in proportion to their eligible donor counts rather than
   giving every rare leaf category equal weight.
6. A different version-seeded hash of each SKU selects a donor rank **within its
   category's chosen taxonomy only**. Copy that donor's exact staged title and ASIN.
   Preserve the original SKU, `category_id`, and `price_bucket` without modification.

The SQL uses stable ClickHouse `cityHash64`, ordered window ranks and modulo counts;
there is no randomness, Python ETL, external AI call or new download. A numeric
internal taxonomy join key reduces memory; an exact collision guard checks it
against the full JSON taxonomy key. Long titles and paths are attached after
narrow assignment joins, rather than carried through window sorting.

Source: [classification/ranking macro](../dbt/macros/amazon_synthetic_catalog.sql),
[category model](../dbt/models/marts/catalog/dim_synerise_categories.sql),
[product model](../dbt/models/marts/catalog/dim_synerise_products.sql),
[YAML documentation](../dbt/models/marts/catalog/models.yml).

## Validation results

The final local dbt build completed **2 models and 41 data tests**, with zero errors
or skips. Tests cover exact identifier uniqueness, non-nullness, relationships,
complete source coverage, unchanged category/price values, category/title membership,
exact donor title equality, both assignment formulas, taxonomy-key collisions,
nonempty eligible catalog, and nine adversarial classification fixtures.
Uniqueness uses exact `uniqExact` comparison instead of a group for every SKU.

Fixed-input rebuild checks matched row counts and all-original-output-column MD5
sum fingerprints across implementations/rebuilds. This supplements the direct
formula and membership tests; fingerprints are probabilistic evidence. Source
catalog edits can change ordinal/modulo mappings: this is deterministic for fixed
inputs, not append-stable. Freeze catalog inputs and bump the mapping version for
an intentional new mapping policy or catalog refresh.

Amazon quality audit:

| Candidate classification | Products |
| --- | ---: |
| Compatible full hierarchy | 127,307 |
| Preferred hierarchy with conflicting main category | 19,542 |
| Hierarchy with missing main category | 1,638 |
| Beauty main-category fallback, missing hierarchy | 112,578 |
| Electronics main-category fallback, missing hierarchy | 12,474 |
| Excluded conflicting hierarchy root | 34 |
| Excluded unclassifiable metadata | 7 |

The source has 273,592 records. Existing staging removes 12 empty-title records,
leaving 273,580 candidates; the explicit classification policy excludes another 41,
leaving **273,539 eligible donors**. All Beauty candidates lack detailed hierarchies,
so their fallback is intentionally broad; no narrower beauty taxonomy is invented.

Existing table UUIDs, schemas and metadata counts were unchanged for REES46,
Synerise raw, Amazon raw, staging and funnel relations. The funnel's three result
rows and existing staging/funnel SQL files also matched their before-build baseline.
No existing reporting table, dbt funnel logic, raw record, credential or grant was
modified. Only the two new dimensions were built/rebuilt. Aggregate validation is
saved locally at `data/processed/synthetic-catalog/validation.json` (Git-ignored).
The read-only audit analysis is `dbt/analyses/synthetic_catalog_profile.sql`.

## Rebuild

Use the existing local `.venv-dbt` and the new isolated `catalog` target. The normal
`dev` target is unchanged. Export an existing authorized ClickHouse account through
your usual private credential mechanism; no secrets belong in commands or Git.
The existing restricted `ecommerce_dbt` role lacks Synerise permissions, so validation
used the existing authorized administrator via process environment, without grants.

```bash
export CLICKHOUSE_DATABASE=synerise_analytics
export CLICKHOUSE_HOST=127.0.0.1
export CLICKHOUSE_PORT=18123
# CLICKHOUSE_USER and CLICKHOUSE_PASSWORD must already be exported privately.
.venv-dbt/bin/dbt build --project-dir dbt --profiles-dir dbt \
  --target catalog --select tag:synthetic_catalog
```

Do not add `+` to the selector: upstream staging relations already exist, and the
selector builds only the dimensions and their associated tests. The final verified
runtime was dbt 1.12.6, dbt-clickhouse 1.10.3 and ClickHouse 25.8.33.6.

The catalog target uses one thread, bounded query memory/blocks, and query-local
direct I/O. Models and larger tests also bound sorting/join memory. Server/container
limits and service configurations were unchanged. Earlier containerized attempts
and a redundant profiling query hit the server's known global memory-limit issue;
the final bounded local build passed all required checks. Docker-based rebuilds
were not established as reliable under that existing memory pressure.

## Limitations

Titles and labels can repeat across SKUs/categories; identifiers, not labels, are
unique. Price buckets do not correspond to Amazon prices. Compatibility follows
Amazon's provided classification and cannot guarantee the metadata itself is
semantically correct. Broad fallback labels and hierarchy/main conflicts are exposed
as quality fields, not hidden. This is a synthetic portfolio/display catalog;
no ML feature, dashboard or funnel dependency was switched to it.

## Metabase V1 hierarchy update — 26 October 2026

The canonical dimensions and product/category funnel facts now expose five
forward-filled scalar category levels, full depth and actual leaf, while keeping
full arrays and all prior assignments unchanged. Exact uniqueness tests now use
in-order aggregation over sorted IDs to avoid large exact-distinct hash sets.
See the [refactor validation and rebuild instructions](reports/metabase-v1-synerise-refactor.md)
for the current 91-test result, narrow metric intermediates, memory observations
and manual card updates. The earlier validation numbers above describe the original
catalog implementation, before this reporting-layer extension.
