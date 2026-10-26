# Independent local infrastructure — Phase 3.1

This stack is for local infrastructure development. DuckDB remains the validated
reference implementation. ClickHouse is the target analytical database, initially
empty at Phase 3.1. Phase 3.2 adds validated raw history; see the
[migration guide](clickhouse-migration.md). Infrastructure startup itself creates
no events, features, models, dashboards or production DAGs. The independent AIS repository was inspected only as a reference;
its files, containers, networks, volumes and credentials are not used or modified.

## Prerequisites and versions

Use Docker Desktop with Compose v2.20+ (validated with Compose v5.6.0), Linux
containers, and sufficient free disk for images and persistent volumes. All base
images have explicit versions and support native Apple Silicon arm64; no forced
amd64 emulation is configured. First builds require Internet access. Allow about
8 GB Docker memory for the core BI stack; 12 GB is a practical starting budget
when enabling Airflow and concurrent tools. These are development budgets, not
benchmarks. Service memory limits are 2 GB ClickHouse, 512 MB PostgreSQL, 1.5 GB
Metabase, 3 GB Airflow, 1 GB dbt and 2 GB ML. Optional tools run only when requested.

| Component | Pinned base/version |
| --- | --- |
| ClickHouse | `clickhouse/clickhouse-server:25.8.33.6` |
| PostgreSQL | custom `ecommerce-ml-postgres:16.13`, from `postgres:16.13-bookworm` |
| Metabase | `metabase/metabase:v0.58.33.1` |
| dbt | custom `ecommerce-ml-dbt:1.0.0`, Python `3.11.14-slim-bookworm` |
| dbt packages | `dbt-core==1.10.13`, `dbt-clickhouse==1.10.3` |
| Airflow | custom `ecommerce-ml-airflow:3.1.7`, from `apache/airflow:3.1.7-python3.11` |
| ML Python | custom `ecommerce-ml-python:1.0.0`, Python `3.11.14-slim-bookworm` |

Top-level dbt requirements are pinned separately in `infra/dbt/requirements.txt`.
ML reuses `pyproject.toml`, including its dependency ranges; it does not claim a
fully locked transitive dependency graph. Airflow uses the official image's
Python/provider environment without installing dbt or ML into it. Never use
`latest`. Image tags are version-pinned, not immutable digests; review future
upgrades deliberately. The AIS reference uses different images/ports and a much
larger stack; only the service separation pattern is reused.

## Configuration and credentials

From the repository root, either copy `.env.example` to `.env` and supply strong,
independent developer credentials, or generate unique local development values:

```bash
python3 scripts/init_infra_env.py
docker compose --profile '*' config -q
```

The generator creates `.env` with mode 0600 and refuses to overwrite an existing
file. Actual values are never printed. `.env` and Docker build contexts exclude
secrets. Do not commit `.env`, copy AIS credentials, or paste rendered Compose
configuration/logs containing secrets into tickets. Use `config -q` for validation.
All credential variables are mandatory, even when optional profiles are disabled,
so an incomplete environment fails before a container starts.

| Variables | Meaning |
| --- | --- |
| `CLICKHOUSE_USER`, `POSTGRES_USER` | ClickHouse application and PostgreSQL administrator usernames |
| `AIRFLOW_DB_USER`, `METABASE_DB_USER` | Separate metadata database usernames |
| `AIRFLOW_ADMIN_USER` | Airflow UI login username |
| `CLICKHOUSE_PASSWORD` | `ecommerce_app` user on database `ecommerce` |
| `POSTGRES_PASSWORD` | dedicated local metadata-superuser password |
| `AIRFLOW_DB_PASSWORD` | `ecommerce_airflow` metadata login |
| `METABASE_DB_PASSWORD` | `ecommerce_metabase` metadata login |
| `METABASE_ENCRYPTION_KEY` | stable Metabase stored-credential encryption key |
| `AIRFLOW_FERNET_KEY` | valid URL-safe base64 32-byte Fernet key |
| `AIRFLOW_JWT_SECRET` | independent Airflow API authentication secret |
| `AIRFLOW_ADMIN_PASSWORD` | `ecommerce_admin` local Simple Auth Manager UI password |

Metabase UI administrators use an email chosen during first-run setup; that login
is separate from `METABASE_DB_USER` and is not provisioned by an environment variable.
Usernames default to the existing project accounts. Changing a database username
on an initialized volume is not an account migration; coordinate any such change
with explicit database administration.

Generated passwords/keys are 32 random bytes encoded as hex, except the Fernet
key. For manual configuration, prefer URL-safe random values and follow Compose
.env quoting rules. Keep encryption keys stable across restarts and back them up
securely. Changing the PostgreSQL password variables does **not** rotate existing
roles; initialization is create-if-missing and deliberately does not reset users
or drop databases. Rotate existing passwords with an explicit database admin
procedure and update the corresponding environment together. Never solve a
credential mismatch by deleting a persistent volume.

## Architecture and isolation

Compose project name is `ecommerce-ml`; no explicit container names or external
networks/volumes are used. Do not override the project name when following these
instructions. Actual network names are project-scoped:

- `ecommerce-ml_ecommerce-analytics`: ClickHouse, dbt, Metabase, Airflow and ML.
- `ecommerce-ml_ecommerce-metadata`: internal bridge for PostgreSQL, Metabase and
  Airflow. PostgreSQL publishes no host ports. Its only role is application metadata.

All inter-container connections use `clickhouse`, `postgres` or `airflow` DNS.
`localhost` in readiness probes refers only to the probed container itself.
Metabase/Airflow have analytics-network access for outbound connections. Named
volumes (`clickhouse-data`, `clickhouse-logs`, `postgres-data`, `airflow-logs`,
`airflow-state`) are prefixed `ecommerce-ml_`. No Docker socket is mounted.

| Host URL/port | Variable | Container target |
| --- | --- | --- |
| `http://127.0.0.1:18123` | `CLICKHOUSE_HTTP_PORT` | `clickhouse:8123` |
| `127.0.0.1:19000` native | `CLICKHOUSE_NATIVE_PORT` | `clickhouse:9000` |
| `http://127.0.0.1:13000` | `METABASE_PORT` | `metabase:3000` |
| `http://127.0.0.1:18080` | `AIRFLOW_PORT` | `airflow:8080` |

These avoid the AIS defaults 8123, 9000, 3000 and 8080. All published ports bind
only to 127.0.0.1. Edit the port variables if another local application uses them.
Container clients continue to use the original container ports, not host ports.

## ClickHouse and dbt

```bash
docker compose up -d --wait clickhouse
docker compose --profile tools build dbt
docker compose --profile tools run --rm dbt debug
docker compose --profile tools run --rm dbt run
docker compose --profile tools run --rm dbt test
```

The ClickHouse health check authenticates and executes SELECT 1 against
`ecommerce`; data/log volumes survive restarts. Resource settings retain a valid
MergeTree worker-pool configuration. After Phase 3.2 bootstrap, dbt uses CLICKHOUSE_DBT_USER / PASSWORD and writes
only ecommerce_analytics while reading the declared ecommerce.raw_events source.
The dbt runtime includes git required by
`dbt debug`. It sets `DBT_PROFILES_DIR=/workspace/dbt` and uses environment-based
credentials. `dbt run` intentionally has no models yet; `dbt test` executes the connectivity test and, after Phase 3.2, the raw source
and historical row-count tests. Bootstrap/migrate before testing that source. No funnel
transformations or production tables exist.

Optional host-only dbt environment (separate from the project's ML environment):

```bash
python3.11 -m venv .venv-dbt
.venv-dbt/bin/pip install -r infra/dbt/requirements.txt
```

Supply `CLICKHOUSE_PASSWORD` set to your restricted dbt password,
`CLICKHOUSE_USER=ecommerce_dbt`, `CLICKHOUSE_DATABASE=ecommerce_analytics`, `CLICKHOUSE_HOST=127.0.0.1`,
`CLICKHOUSE_PORT=18123` (or the configured host port), and
`DBT_PROFILES_DIR=$PWD/dbt` in your shell. Run `.venv-dbt/bin/dbt --project-dir dbt
debug`. Do not commit credentials or install this environment inside a container.

## PostgreSQL and Metabase

```bash
docker compose --profile bi up -d --build --wait
```

PostgreSQL creates `airflow_metadata` owned by `ecommerce_airflow` and
`metabase_metadata` owned by `ecommerce_metabase`. PUBLIC database access is
revoked; neither application role can connect to the other's database. The
superuser is only for initialization/administration, never application login.
The image copies its idempotent initialization hook with non-executable mode;
this avoids macOS executable-bind-mount failures. Hooks run on a fresh volume
only. To repair an interrupted first-time initialization without deleting data:

```bash
docker compose exec postgres bash /docker-entrypoint-initdb.d/10-apps.sh
```

Open Metabase at its host URL and complete its first-run administrator setup.
Then Admin settings → Databases → Add database → ClickHouse:

- Host `clickhouse`, port `8123`, database `ecommerce`.
- Username `ecommerce_app`, password from your local `CLICKHOUSE_PASSWORD`.
- SSL off for this isolated local development connection.

The selected Metabase includes the supported ClickHouse driver; do not download
legacy driver JARs or invent plugin environment settings. PostgreSQL stores
Metabase configuration/dashboards, so no H2 database or separate Metabase data
volume is used. Keep `METABASE_ENCRYPTION_KEY` stable. No dashboards are created.
A read-only ClickHouse BI role can be added when real analytical schemas arrive;
the initial shared development user is not a production permissions design.

## Optional Airflow

```bash
docker compose --profile airflow up -d --build --wait airflow
```

Uses the supported `airflow standalone` local-development command, which runs
metadata migrations and the scheduler/API/DAG processor components. Metadata is
PostgreSQL, not SQLite. `infra/airflow/start.py` supplies the PostgreSQL URI with
URL-encoded credentials and a private Simple Auth Manager password file before
starting standalone. UI login: `ecommerce_admin`, password from
`AIRFLOW_ADMIN_PASSWORD`. Examples are disabled; `dags/` is mounted read-only
and intentionally empty. Logs and local auth state use named volumes. API and
metadata health are checked. This is a single-container development arrangement,
not production HA or a distributed executor deployment. No ingestion/ML DAGs and
no Docker socket are included. Stop it when not needed:

```bash
docker compose --profile airflow stop airflow
```

## Optional Python execution

```bash
docker compose --profile ml build ml
docker compose --profile ml run --rm ml
docker compose --profile ml run --rm ml python -c 'import duckdb, ecommerce_analytics'
docker compose --profile ml run --rm ml pytest
```

The image installs the existing package and dev dependencies, with no nested
virtual environment. `data/` is mounted read-only to protect DuckDB/raw files;
write-producing feature commands are intentionally not run during this phase.
Default command only imports the project. Tests create synthetic data in /tmp;
the production dataset is not migrated or modeled. Docker-CLI-dependent static
tests skip inside this image because it intentionally has no Docker client/socket.

## Operations, persistence and reset

```bash
docker compose --profile '*' ps -a
docker compose logs --tail 100 clickhouse postgres metabase
docker compose --profile airflow logs --tail 100 airflow
docker compose restart clickhouse
docker compose --profile '*' stop
docker compose --profile '*' down
```

`stop` and `down` preserve named volumes. `down` removes this project's containers
and networks only. Avoid global prune commands, AIS paths and other project
names. For a deliberate **destructive reset of e-commerce only**, first back up
needed ClickHouse/metadata volumes, verify the project is `ecommerce-ml`, then run:

```bash
docker compose --profile '*' down --volumes
```

That deletes this project's database/log/auth volumes, not the bind-mounted
DuckDB/raw data, and was **not** run during verification. Recreate credentials
only if intentionally rotating the entire local environment. See the
[verification report](reports/phase-3.1-infrastructure.md) for actual checks and
outstanding first-run steps.

## Primary references

- [Metabase ClickHouse connection](https://www.metabase.com/docs/latest/databases/connections/clickhouse)
- [Bundled driver history](https://github.com/ClickHouse/metabase-clickhouse-driver)
- [Airflow 3.1.7 standalone](https://airflow.apache.org/docs/apache-airflow/3.1.7/start.html)
- [PostgreSQL image initialization](https://hub.docker.com/_/postgres)
- [dbt-clickhouse](https://pypi.org/project/dbt-clickhouse/1.10.3/)
