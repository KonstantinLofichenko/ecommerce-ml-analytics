"""Isolation, secret validation and resource safeguards in rendered Compose config."""

import json
import os
import runpy
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "CLICKHOUSE_PASSWORD",
    "CLICKHOUSE_DBT_PASSWORD",
    "POSTGRES_PASSWORD",
    "AIRFLOW_DB_PASSWORD",
    "METABASE_DB_PASSWORD",
    "METABASE_ENCRYPTION_KEY",
    "AIRFLOW_FERNET_KEY",
    "AIRFLOW_JWT_SECRET",
    "AIRFLOW_ADMIN_PASSWORD",
)


def render(missing: str | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update({key: "test-only-not-a-real-secret" for key in REQUIRED})
    if missing:
        env[missing] = ""
    return subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            ".env.example",
            "--profile",
            "*",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker CLI is not installed")
def test_compose_isolation_and_topology() -> None:
    result = render()
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    assert config["name"] == "ecommerce-ml"
    services = config["services"]
    assert set(services) == {"clickhouse", "postgres", "dbt", "metabase", "airflow", "ml"}
    for service in services.values():
        assert "container_name" not in service
        assert not service["image"].endswith(":latest")
        for port in service.get("ports", []):
            assert port["host_ip"] == "127.0.0.1"
            assert str(port["published"]) not in {"8123", "9000", "8080", "3000"}
        assert all("docker.sock" not in v.get("source", "") for v in service.get("volumes", []))
    assert services["postgres"].get("ports", []) == []
    assert config["networks"]["ecommerce-metadata"]["internal"]
    for name in ("postgres", "metabase", "airflow"):
        assert "ecommerce-metadata" in services[name]["networks"]
    for name in ("clickhouse", "dbt", "metabase", "airflow", "ml"):
        assert "ecommerce-analytics" in services[name]["networks"]
    for obj in (*config["networks"].values(), *config["volumes"].values()):
        assert obj["name"].startswith("ecommerce-ml_")
        assert not obj.get("external", False)
    assert all(v.get("read_only") for v in services["ml"]["volumes"])
    assert services["dbt"]["environment"]["CLICKHOUSE_HOST"] == "clickhouse"
    assert services["metabase"]["environment"]["MB_DB_HOST"] == "postgres"


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker CLI is not installed")
@pytest.mark.parametrize("key", REQUIRED)
def test_missing_secret_fails_clearly(key: str) -> None:
    result = render(key)
    assert result.returncode != 0
    assert key in result.stderr


def test_private_unique_credentials_and_no_overwrite(tmp_path: Path) -> None:
    initialize = runpy.run_path(str(ROOT / "scripts" / "init_infra_env.py"))["initialize"]
    path = tmp_path / ".env"
    initialize(path)
    assert path.stat().st_mode & 0o777 == 0o600
    values = dict(line.split("=", 1) for line in path.read_text().splitlines())
    assert len({values[k] for k in REQUIRED}) == len(REQUIRED)
    assert all(len(values[k]) >= 32 for k in REQUIRED)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        initialize(path)
    assert path.read_bytes() == before
