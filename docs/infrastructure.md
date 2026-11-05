# Independent local infrastructure

The **`ecommerce-ml`** Docker Compose project provides ClickHouse analytics storage,
PostgreSQL-backed Metabase, and optional dbt/Python execution tools. Airflow was
removed on **5 November 2026**; it is not an available profile or runtime dependency.
JupyterLab and the offline ML pipeline remain host-side workflows managed by uv.
The independent AIS and airflow-intro projects are not used or modified.

[Current architecture](architecture.md) describes implemented analytics/ML.
[Historical infrastructure evidence](archive/infrastructure/phase-3.1-infrastructure.md)
retains the earlier Airflow design and measurements; its commands are historical,
not current setup instructions.

## Prerequisites and pinned versions

Use Docker Desktop with Compose v2.20+ and Linux containers. Images support native
Apple Silicon; no forced amd64 emulation or `latest` tag is configured. First builds
need access to their image registries. Allow host/Docker memory for the existing
**16 GiB ClickHouse container / 12 GiB server** plus other services and headroom.
The server limit remains in `infra/clickhouse/development.xml`; Compose sets
`mem_limit: 16g`. No memory settings changed during Airflow removal.

| Component | Image / configuration |
| --- | --- |
| ClickHouse | `clickhouse/clickhouse-server:25.8.33.6` |
| PostgreSQL | `ecommerce-ml-postgres:16.13`, built from `postgres:16.13-bookworm` |
| Metabase | `metabase/metabase:v0.58.33.1` |
| dbt | `ecommerce-ml-dbt:1.0.0`; direct versions in `infra/dbt/requirements.txt` |
| Optional Python tool | `ecommerce-ml-python:1.0.0`, existing project package/dev environment |

Other service limits remain 512 MiB PostgreSQL, 1536 MiB Metabase, 1 GiB dbt and
2 GiB Python tool. Image tags are explicit versions, not immutable digests.
The [ML reproduction guide](project-reproduction.md) distinguishes locked host
setup from historical ML pins; the optional Docker ML image is not claimed to
reproduce either notebook results or the full historical ML environment exactly.

## Configuration and credentials

For a new installation, copy `.env.example` and privately fill its required values,
or generate independent local credentials:

```bash
python3 scripts/init_infra_env.py
docker compose --profile '*' config -q
```

The generator creates a private mode-0600 `.env` and refuses to overwrite it.
It no longer generates any Airflow variables. Actual credentials must never enter
Git, rendered-config screenshots or command-line URLs. Use `config -q` instead of
printing resolved configuration. Do not regenerate `.env` for an existing volume.

| Variables | Purpose |
| --- | --- |
| `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD` | Existing ClickHouse application account |
| `CLICKHOUSE_INGEST_USER`, `CLICKHOUSE_INGEST_PASSWORD` | Restricted ingestion/publication account |
| `CLICKHOUSE_DBT_USER`, `CLICKHOUSE_DBT_PASSWORD` | Existing restricted REES46 dbt account |
| `CLICKHOUSE_BI_USER`, `CLICKHOUSE_BI_PASSWORD` | Read-only role described in migration operations |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | Metadata server administrator, not application login |
| `METABASE_DB_USER`, `METABASE_DB_PASSWORD` | Metabase PostgreSQL application account |
| `METABASE_ENCRYPTION_KEY` | Stable stored-connection encryption key; preserve across restarts |
| `CLICKHOUSE_HTTP_PORT`, `CLICKHOUSE_NATIVE_PORT`, `METABASE_PORT` | Loopback host ports |

The Metabase UI login is separate and remains the existing email/account.
Changing environment variables does not rotate initialized database credentials;
never solve a mismatch by deleting a volume. Existing non-Airflow credentials and
ports were preserved during removal. Airflow entries were removed from `.env` and
`.env.example`; dormant historical PostgreSQL metadata was not deleted.

## Services, networks and persistence

Do not override the Compose project name. Both bridge networks remain:

- `ecommerce-ml_ecommerce-analytics`: ClickHouse, Metabase, dbt and Python tools.
- `ecommerce-ml_ecommerce-metadata`: internal PostgreSQL/Metabase metadata network.

There was **no Airflow-only network**. PostgreSQL publishes no host port. Metabase
uses `postgres:5432` for application storage and `clickhouse:8123` for analytical
connections. Shared networks and Docker volumes are not external project resources.
No Docker socket is mounted.

Retained volumes: `ecommerce-ml_clickhouse-data`, `ecommerce-ml_clickhouse-logs`,
`ecommerce-ml_postgres-data`. These contain persistent ClickHouse/Metabase data.
The PostgreSQL volume still includes historical `airflow_metadata` and its role;
no database DROP, role deletion or shared-volume cleanup was performed.

| Host endpoint | Compose service |
| --- | --- |
| `http://127.0.0.1:18123` | ClickHouse HTTP (`CLICKHOUSE_HTTP_PORT`) |
| `127.0.0.1:19000` | ClickHouse native (`CLICKHOUSE_NATIVE_PORT`) |
| `http://127.0.0.1:13000` | Metabase (`METABASE_PORT`) |

All host ports bind to loopback. Container clients use service DNS and container
ports, not host loopback addresses. The former Airflow port 18080 is no longer
published by this project.

## Startup and checks

```bash
docker compose --profile '*' config -q
# Build/update only the PostgreSQL image when its fresh-volume bootstrap changes.
docker compose --profile bi build postgres
docker compose --profile bi up -d --wait
python3 scripts/verify_infrastructure.py
```

The verifier checks authenticated ClickHouse SQL, Metabase metadata access and
PostgreSQL-admin-database isolation, Metabase health, authenticated SQL from the
Metabase container to ClickHouse, its bundled driver, and dbt debug. It has no
Airflow option. No UI session extraction or dashboard writes are needed.

`infra/postgres/init-apps.sh` now provisions only Metabase on **fresh PGDATA**.
Existing data directories skip initialization. The image refresh during removal
updated that hook and cleared obsolete Airflow environment variables from the
PostgreSQL container; it reused the exact same persistent volume. ClickHouse and
Metabase containers were not rebuilt or recreated.

For a new Metabase connection, use the existing authorized ClickHouse account and
`clickhouse:8123`. Existing saved connections/dashboards require no edits. Bootstrap
role/grant changes are separate operations described in
[migration operations](clickhouse-migration.md); do not overwrite saved credentials
or assume restricted REES46 dbt grants cover all Synerise schemas.

## dbt, Python and JupyterLab

```bash
docker compose --profile tools build dbt
docker compose --profile tools run --rm dbt debug
# Optional existing Python import smoke check:
docker compose --profile ml build ml
docker compose --profile ml run --rm ml
```

The tools-profile dbt environment retains its restricted REES46 target. For the
implemented Synerise models and catalog profile, follow
[dashboard operations](dashboard-v1-operations.md) and
[feature/reproduction commands](project-reproduction.md). Do not run broad model
rebuilds merely to validate infrastructure.

The optional Python container keeps its data bind mount read-only and default
import smoke command. JupyterLab is not a Compose service; use
[the existing notebook/kernel setup](../notebooks/README.md). The ClickHouse → dbt
→ host Python ML → evaluation workflow and saved experiments are unchanged.

## Safe operations and retired resources

```bash
docker compose --profile '*' ps -a
docker compose logs --tail 100 clickhouse postgres metabase
docker compose --profile bi stop
```

Use explicit project-scoped operations. Avoid global prunes and destructive volume
resets. Airflow cleanup removed only the verified `ecommerce-ml-airflow-1` container,
its custom `ecommerce-ml-airflow:3.1.7` image and two Airflow-only named volumes
(`ecommerce-ml_airflow-logs`, `ecommerce-ml_airflow-state`). Shared networks, PostgreSQL
and all ClickHouse/Metabase persistent data remain. No AIS or airflow-intro resource
was removed. Shared/public base images and build caches were not globally pruned.

Historical files under `docs/archive/` intentionally retain Airflow references;
they are dated evidence, not runnable current setup instructions. No scheduler,
worker, triggerer, API or initialization service remains in the active Compose file.

## Removal validation — 5 November 2026

- Compose validation passed; services are `clickhouse`, `postgres`, `metabase`,
  `dbt` and `ml`. There are no Airflow profiles or runtime environment variables.
- ClickHouse, Metabase and the refreshed PostgreSQL container are healthy. The
  verifier passed PostgreSQL role isolation, Metabase health/driver checks,
  authenticated Metabase → ClickHouse SQL via service DNS, and `dbt debug`.
- Existing ClickHouse table UUIDs/counts and PostgreSQL database OIDs matched the
  pre-removal snapshot. REES46 retains **20,692,840 rows**; the ML feature table
  retains **547,914 customers / 74,781 positives**. Metabase retains **66 cards,
  2 dashboards and 68 dashboard-card entries**. No dashboard or connection was edited.
- All non-target containers, including other projects, retained their IDs,
  images, states and network membership. ClickHouse and Metabase container IDs
  stayed unchanged. PostgreSQL alone was recreated on its unchanged data volume.
  Both shared network IDs and all non-Airflow volume creation identities survived.
- Python checks: **83 passed, 3 opt-in skips**; 7 infrastructure tests passed.
  Four obsolete Airflow-secret parameter tests were removed with the feature.
  Existing pandas deprecation warnings remain unrelated. Ruff lint/format and
  PostgreSQL bootstrap shell-syntax checks passed.
- No global cleanup, volume reset, raw rebuild, training, commit or push occurred.
