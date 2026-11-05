"""Nondestructive checks against already-started e-commerce services only."""

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify() -> dict[str, str]:
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env").read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    secrets = [
        value.strip("\"'")
        for key, value in values.items()
        if any(word in key for word in ("PASSWORD", "KEY", "SECRET")) and value
    ]

    def run(*args: str, input_text: str | None = None) -> str:
        result = subprocess.run(
            ["docker", "compose", *args],
            cwd=ROOT,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr
        for secret in secrets:
            output = output.replace(secret, "[REDACTED]")
        if result.returncode:
            raise RuntimeError(output)
        return result.stdout.strip()

    run("--profile", "*", "config", "-q")
    run(
        "exec",
        "-T",
        "clickhouse",
        "bash",
        "-c",
        'clickhouse-client --user "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" '
        '--database "$CLICKHOUSE_DB" --query "SELECT 1"',
    )
    checks = {"compose": "valid", "clickhouse_sql": "SELECT 1 passed"}
    for user_key, database, password, forbidden in (
        ("METABASE_DB_USER", "metabase_metadata", "METABASE_DB_PASSWORD", "postgres"),
    ):
        user = values[user_key].strip("\"'")
        run(
            "exec",
            "-T",
            "-e",
            f"APP_USER={user}",
            "postgres",
            "bash",
            "-c",
            f'set -e; export PGPASSWORD="${password}"; '
            f'psql -h postgres -U "$APP_USER" -d {database} -Atc "SELECT 1"; '
            f'if psql -h postgres -U "$APP_USER" -d {forbidden} -c "SELECT 1" '
            "> /dev/null 2>&1; then exit 1; fi",
        )
        checks[user] = "Metabase database allowed; administrator database denied"
    health = run("exec", "-T", "metabase", "curl", "-fsS", "http://localhost:3000/api/health")
    if json.loads(health).get("status") != "ok":
        raise RuntimeError("Metabase is not ready")
    checks["metabase_health"] = "ready with PostgreSQL application storage"
    result = run(
        "exec",
        "-T",
        "metabase",
        "sh",
        "-c",
        'read -r user; read -r password; curl -fsS --user "$user:$password" '
        '--data-binary "SELECT 1" http://clickhouse:8123/',
        input_text=values["CLICKHOUSE_USER"].strip("\"'")
        + "\n"
        + values["CLICKHOUSE_PASSWORD"].strip("\"'")
        + "\n",
    )
    if result != "1":
        raise RuntimeError("Metabase-container ClickHouse SQL probe failed")
    checks["metabase_clickhouse_network_sql"] = "authenticated SELECT 1 via service DNS passed"
    properties = json.loads(
        run(
            "exec", "-T", "metabase", "curl", "-fsS", "http://localhost:3000/api/session/properties"
        )
    )
    if "clickhouse" not in properties.get("engines", {}):
        raise RuntimeError("ClickHouse engine not advertised by Metabase")
    checks["metabase_driver"] = "ClickHouse engine advertised; UI connection setup is manual"
    run("--profile", "tools", "run", "--rm", "dbt", "debug", "--log-level", "warn")
    checks["dbt_debug"] = "all checks passed"
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(verify(), indent=2))
