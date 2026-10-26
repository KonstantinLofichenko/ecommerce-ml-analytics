"""Supported single-container development startup; not a production scheduler."""

import json
import os
from pathlib import Path
from urllib.parse import quote

user = quote(os.environ["AIRFLOW_DB_USER"], safe="")
password = quote(os.environ["AIRFLOW_DB_PASSWORD"], safe="")
os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"] = (
    f"postgresql+psycopg2://{user}:{password}@postgres:5432/airflow_metadata"
)
state = Path("/opt/airflow/state")
state.mkdir(parents=True, exist_ok=True)
password_file = state / "passwords.json"
# Supplied local credential; avoid standalone's generated password appearing in logs.
password_file.write_text(
    json.dumps({os.environ["AIRFLOW_ADMIN_USER"]: os.environ["AIRFLOW_ADMIN_PASSWORD"]})
)
password_file.chmod(0o600)
os.execvp("airflow", ["airflow", "standalone"])
