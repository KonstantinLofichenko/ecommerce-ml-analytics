"""Require all standalone components to report healthy, not just HTTP status 200."""

import json
from urllib.request import urlopen

with urlopen("http://localhost:8080/api/v2/monitor/health", timeout=10) as response:
    health = json.load(response)
if any(
    health.get(component, {}).get("status") != "healthy"
    for component in ("metadatabase", "scheduler", "triggerer", "dag_processor")
):
    raise SystemExit(1)
