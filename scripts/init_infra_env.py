"""Create independent ignored development secrets; never overwrite an existing .env."""

import base64
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def initialize(path: Path = ROOT / ".env") -> None:
    keys = [
        "CLICKHOUSE_PASSWORD",
        "CLICKHOUSE_INGEST_PASSWORD",
        "CLICKHOUSE_DBT_PASSWORD",
        "CLICKHOUSE_BI_PASSWORD",
        "POSTGRES_PASSWORD",
        "AIRFLOW_DB_PASSWORD",
        "METABASE_DB_PASSWORD",
        "METABASE_ENCRYPTION_KEY",
        "AIRFLOW_JWT_SECRET",
        "AIRFLOW_ADMIN_PASSWORD",
    ]
    values = {key: secrets.token_hex(32) for key in keys}
    values["AIRFLOW_FERNET_KEY"] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    values.update(
        CLICKHOUSE_USER="ecommerce_app",
        CLICKHOUSE_INGEST_USER="ecommerce_ingest",
        CLICKHOUSE_DBT_USER="ecommerce_dbt",
        CLICKHOUSE_BI_USER="ecommerce_bi",
        POSTGRES_USER="ecommerce_metadata_admin",
        AIRFLOW_DB_USER="ecommerce_airflow",
        METABASE_DB_USER="ecommerce_metabase",
        AIRFLOW_ADMIN_USER="ecommerce_admin",
        CLICKHOUSE_HTTP_PORT="18123",
        CLICKHOUSE_NATIVE_PORT="19000",
        METABASE_PORT="13000",
        AIRFLOW_PORT="18080",
    )
    # Exclusive create and private permissions: actual values never enter stdout or Git.
    import os

    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as file:
        file.writelines(f"{key}={value}\n" for key, value in values.items())


if __name__ == "__main__":
    initialize()
    print("Created private .env with unique local development credentials.")
