"""Create restricted service users without rotating existing credentials."""

import hashlib
import secrets
from pathlib import Path

from ecommerce_analytics.ingestion.clickhouse import ClickHouse, MigrationError, identifier

ROLES = {"INGEST": "ecommerce_ingest", "DBT": "ecommerce_dbt", "BI": "ecommerce_bi"}


def ensure_role_environment(path: Path) -> None:
    lines = path.read_text().splitlines()
    original_lines = list(lines)
    existing = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in lines
        if "=" in line and not line.lstrip().startswith("#")
    }
    additions = []
    for role, default in ROLES.items():
        section = []
        for key, value in (
            (f"CLICKHOUSE_{role}_USER", default),
            (f"CLICKHOUSE_{role}_PASSWORD", secrets.token_hex(32)),
        ):
            if key not in existing:
                section.append(f"{key}={value}")
            elif not existing[key].strip():
                lines = [f"{key}={value}" if line.startswith(key + "=") else line for line in lines]
        if section:
            additions += [f"# ClickHouse {role.lower()} account — restricted credentials", *section]
    if additions or lines != original_lines:
        path.write_text("\n".join(lines + ([""] + additions if additions else [])) + "\n")


def provision(client: ClickHouse, values: dict[str, str]) -> None:
    names = [values.get(f"CLICKHOUSE_{role}_USER", "") for role in ROLES]
    if len(set(names + [client.user])) != 4:
        raise MigrationError("Ingestion, dbt, BI and administrator users must be distinct.")
    for role in ROLES:
        user = identifier(values[f"CLICKHOUSE_{role}_USER"])
        password = values.get(f"CLICKHOUSE_{role}_PASSWORD")
        if not password:
            raise MigrationError(f"Set CLICKHOUSE_{role}_PASSWORD.")
        digest = hashlib.sha256(password.encode()).hexdigest()
        client.command(
            f"CREATE USER IF NOT EXISTS {user} IDENTIFIED WITH sha256_hash BY {{digest:String}}",
            {"param_digest": digest},
        )
    ingest, dbt, bi = (identifier(values[f"CLICKHOUSE_{r}_USER"]) for r in ROLES)
    client.command("CREATE DATABASE IF NOT EXISTS ecommerce_analytics ENGINE=Atomic")
    client.command(
        f"GRANT SELECT, INSERT, CREATE TABLE, DROP TABLE, ALTER TABLE, TRUNCATE "
        f"ON ecommerce.* TO {ingest}"
    )
    client.command(f"GRANT SELECT ON ecommerce.raw_events TO {dbt}")
    client.command(
        f"GRANT SELECT, INSERT, CREATE TABLE, CREATE VIEW, DROP TABLE, DROP VIEW, "
        f"ALTER TABLE, ALTER VIEW, TRUNCATE ON ecommerce_analytics.* TO {dbt}"
    )
    client.command(f"GRANT SELECT ON ecommerce.raw_events TO {bi}")
    # Existing ecommerce_app remains unchanged so a saved Metabase connection keeps working.
