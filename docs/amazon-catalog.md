# Amazon metadata source and import contract

The local imported catalog uses Amazon Reviews 2023 **product metadata**, not review
events: `data/external/amazon/meta_All_Beauty.parquet` and
`data/external/amazon/meta_Electronics_00000.parquet`. Electronics is a selected
file, not a claim of full department coverage. Obtain these files from the authorized
upstream Amazon Reviews 2023 metadata distribution and review its terms before
use. No downloader, new download or additional dependency is introduced here.
Original local files remain ignored and immutable.

The existing `external_catalog.amazon_products` has 273,592 records. Its exact
schema, inspected during repository preparation, is:

```sql
CREATE TABLE external_catalog.amazon_products
(
    parent_asin String,
    title String,
    main_category String,
    categories Array(Nullable(String)),
    store Nullable(String),
    average_rating Nullable(Float64),
    rating_number Nullable(Int64),
    price Nullable(String),
    source_department String DEFAULT 'All_Beauty'
)
ENGINE = MergeTree
ORDER BY parent_asin;
```

For a fresh authorized import, expose the original Parquets to ClickHouse through
an explicitly configured read-only `user_files` path first. Inspect their schema
before inserting; do not assume that the Synerise-only mount exposes Amazon files.
Use explicit named projections, retaining category arrays and nullable values.
For example, with a read-only `amazon/` directory already accessible to `file()`:

```sql
-- Fresh empty destination only. Not idempotent: do not replay against existing data.
INSERT INTO external_catalog.amazon_products
(parent_asin, title, main_category, categories, store,
 average_rating, rating_number, price, source_department)
SELECT parent_asin, title, main_category, categories, store,
       average_rating, rating_number, price, 'All_Beauty'
FROM file('amazon/meta_All_Beauty.parquet', 'Parquet');

-- Repeat the explicit projection for meta_Electronics_00000.parquet,
-- using 'Electronics' as source_department; never use the Beauty default for it.
```

Validate count, identifier uniqueness, null compatibility and department membership
before accepting an import. Unexpected nulls in nonnullable columns must fail or
receive an explicitly reviewed policy, never silent coercion. Preserve a source
file checksum manifest for a new import. The original Amazon import was performed
outside the repository's checked-in ingestion scripts; an immutable upstream
release/checksum manifest is not supplied here. Repeating a download therefore
cannot be claimed to reproduce the original bytes solely from these filenames.
This is a documented reproducibility limitation, not a reason to overwrite the
validated existing table.

The dbt source declaration is `dbt/models/sources.yml`; staging is
`dbt/models/staging/amazon/stg_amazon_products.sql`. The deterministic display
mapping, exclusions, fallback policy and ML restrictions are documented in
[synthetic-catalog.md](synthetic-catalog.md). Current build commands and validation
are in the [Dashboard V1.0 report](reports/metabase-v1-synerise-refactor.md).
