# Phase 3.1 — Independent Docker infrastructure verification

Verified locally on 20 October 2026, Europe/Moscow. Project: `ecommerce-ml`.
No event migration, production dbt transformation, dashboard, production DAG,
customer feature rebuild or production model training was performed.

## Architecture and versions

The agreed stack is Docker Compose + ClickHouse + dbt + Apache Airflow + Metabase
+ Python ML. DuckDB remains the validated reference. The older Kafka/MLflow
roadmap was replaced in current architecture documentation; neither is included.
AIS was inspected read-only for service/port patterns; no AIS resource was
modified or reused. No existing Docker implementation was present in this repo.

| Component | Verified version |
| --- | --- |
| Docker Engine / Compose | 29.9.1 / v5.6.0 |
| ClickHouse | 25.8.33.6 |
| PostgreSQL | 16.13-bookworm, custom initialization image |
| Metabase | v0.58.33.1 with bundled ClickHouse engine |
| dbt-core / dbt-clickhouse | 1.10.13 / 1.10.3 |
| Airflow | 3.1.7-python3.11, custom local startup/health wrappers |
| ML / dbt Python base | 3.11.14-slim-bookworm |

Images were built/pulled and run natively on Linux arm64 through Docker Desktop.
ClickHouse, Metabase and Airflow manifest checks include both arm64 and amd64.
No architecture override or emulation was required. Dependency environments are
separate; ML reuses the project package, dbt has pinned direct dependencies, and
Airflow retains its official image environment. Tags are explicit versions;
transitive ML dependencies follow existing pyproject ranges, not a full lockfile.

Two independent bridges were created: `ecommerce-ml_ecommerce-analytics` and the
internal `ecommerce-ml_ecommerce-metadata`. Only PostgreSQL, Metabase and Airflow
join metadata. ClickHouse/dbt/Metabase/Airflow/ML join analytics. Volumes use the
`ecommerce-ml_` prefix; none are external. No explicit container names, Docker
socket mounts, PostgreSQL host port, or AIS endpoints/credentials are used.

## Actual runtime results

| Check | Result |
| --- | --- |
| Compose config with all profiles | Passed; missing credential variables fail clearly |
| Custom images | PostgreSQL, dbt, Airflow and ML built successfully |
| ClickHouse | Healthy; authenticated SELECT 1 on dedicated ecommerce database |
| dbt debug | All checks passed, including git and ClickHouse connection |
| dbt run | Successful intentional no-op: zero production models |
| dbt test | Infrastructure connectivity singular test: 1 passed |
| PostgreSQL fresh initialization | Passed in disposable memory-backed container, without persistent-volume deletion |
| Metadata account isolation | Both own-database logins pass; cross-application database logins denied in both directions |
| PostgreSQL init replay | Create-if-missing hook reran without dropping/resetting data |
| Metabase | Healthy /api/health; PostgreSQL application schema initialized (135 public tables observed) |
| Metabase → ClickHouse | Authenticated SELECT 1 passed from Metabase container using clickhouse:8123 DNS |
| ClickHouse driver | ClickHouse engine advertised by Metabase session-properties API |
| Airflow | Healthy; PostgreSQL check passed; API reports metadata, scheduler, triggerer and DAG processor healthy |
| Airflow PostgreSQL schema | 50 public metadata tables observed |
| ML import | ecommerce_analytics import succeeds in isolated image |
| ML container tests | 56 passed, 9 intentionally skipped Docker-CLI-dependent tests |
| Local Python tests | 65 passed, no skips |
| Ruff lint / formatting | Passed |
| DuckDB reference | Read-only count checks match all prior values |

ClickHouse's `ecommerce` database contains **zero tables** after these checks.
The dbt test is SELECT-only. Default core services and the optional Airflow
service were actually started; dbt and ML ran as disposable one-shot containers.
ClickHouse, PostgreSQL, Metabase and Airflow were left running and healthy.

### Preserved DuckDB reference counts

| Relation | Rows |
| --- | --- |
| raw_events | 20,692,840 |
| sessions | 4,536,272 |
| customers | 1,639,358 |
| customer_snapshot_features | 243,162 |

The production reference was opened read-only for verification. It is neither
copied into image build contexts nor mounted writable in ML. Source CSV files
were not modified. No global Docker cleanup or volume reset was run.

## Startup corrections resolved during validation

A bind-mounted executable PostgreSQL initialization hook failed on macOS. The
final PostgreSQL image copies the hook with mode 0644, so the official entrypoint
sources it without an executable bind mount. First-time initialization was then
verified in a disposable tmpfs-backed container; the existing metadata volume
was recovered nondestructively through the idempotent hook.

Overly restrictive ClickHouse worker settings caused startup blockage and a
MergeTree pool consistency error. Final settings use a 1024-thread pool ceiling
and valid 16-worker background pool, with a 2 GB container / 1.5 GB server memory
budget. The dedicated database was created with IF NOT EXISTS after interrupted
first boot; no database was dropped. The final configuration is healthy.

Airflow's initial state volume ownership prevented writing its auth file. The
image now prepares the directory for the official airflow UID; only the new
e-commerce state volume's ownership was repaired. Its readiness probe checks all
standalone components, not merely an HTTP 200 response. dbt debug's missing git
executable was added to the dbt image and debug subsequently passed completely.

## Files created and modified

Created:

- `compose.yaml`, `.env.example`, `.dockerignore`.
- `infra/clickhouse/development.xml`.
- `infra/postgres/Dockerfile`, `infra/postgres/init-apps.sh`.
- `infra/dbt/Dockerfile`, `infra/dbt/requirements.txt`.
- `infra/airflow/Dockerfile`, `infra/airflow/start.py`, `infra/airflow/health.py`.
- `infra/ml/Dockerfile`.
- `dbt/dbt_project.yml`, `dbt/profiles.yml`, `dbt/tests/connectivity.sql`.
- `dbt/models/.gitkeep`, `dbt/macros/.gitkeep`, `dags/.gitkeep`.
- `scripts/init_infra_env.py`, `scripts/verify_infrastructure.py`.
- `tests/test_infrastructure.py`, `docs/infrastructure.md`, this report.

Modified: `.gitignore`, `README.md`, `docs/architecture.md`.
A private, ignored `.env` was generated for these local checks with independent
random credentials and mode 0600; its values are not part of the deliverables.
Generated dbt logs/targets are also ignored. No commits or pushes were made.

## Reproduction and remaining decisions

See [infrastructure instructions](../infrastructure.md) for configuration,
profiles, versions, ports, operations, safe reset and optional host dbt setup.
For a fresh checkout, first initialize developer credentials, then:

```bash
python3 scripts/init_infra_env.py
docker compose --profile '*' config -q
docker compose --profile bi --profile tools --profile ml --profile airflow build
docker compose --profile bi up -d --wait
docker compose --profile tools run --rm dbt debug
docker compose --profile tools run --rm dbt run
docker compose --profile tools run --rm dbt test
docker compose --profile airflow up -d --wait airflow
docker compose --profile ml run --rm ml
docker compose --profile ml run --rm ml pytest
python3 scripts/verify_infrastructure.py --include-airflow
```

Do not rerun the credential generator over an existing `.env`; it deliberately
refuses to overwrite it. To stop this project's services while preserving state:

```bash
docker compose --profile '*' down
```

Remaining manual step: visit `http://127.0.0.1:13000`, create the first Metabase
administrator, then add ClickHouse using `clickhouse`, port `8123`, database
`ecommerce`, user `ecommerce_app`, and the local password. The network/SQL path
and advertised driver were checked automatically, but a saved Metabase data
source and JDBC queries through that saved connection have **not** been tested.
No administrator account or dashboards were created on the user's behalf.

Airflow UI is `http://127.0.0.1:18080`, login `ecommerce_admin`; use the ignored
local `AIRFLOW_ADMIN_PASSWORD`. Its single-container standalone topology is
supported for local development, not a production orchestration deployment.
The initial ClickHouse development user is shared by dbt/manual BI setup; a
read-only BI role and ingestion-specific privileges should be designed when
analytical schemas are introduced. Data migration, dbt funnel/feature models,
production DAGs and dashboard work remain future phases.
