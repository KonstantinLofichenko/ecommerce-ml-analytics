"""Small authenticated HTTP client; no automatic retries of writes."""

import base64
import gzip
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


class MigrationError(ValueError):
    """A migration cannot safely proceed."""


class TransportError(MigrationError):
    """A request may have committed despite an unavailable acknowledgement."""


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise MigrationError(f"Unsafe SQL identifier: {value!r}")
    return f"`{value}`"


def environment(path: Path = Path(".env")) -> dict[str, str]:
    """Simple .env reader for generated literal values; shell exports take precedence."""
    values = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    return {**values, **os.environ}


@dataclass
class ClickHouse:
    url: str
    user: str
    password: str = field(repr=False)
    timeout: int = 300
    read_attempts: int = 3

    def __post_init__(self) -> None:
        parsed = urlparse(self.url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise MigrationError("Use an HTTP(S) URL without embedded credentials.")

    def _request(
        self, sql: str, data: bytes | None = None, parameters: dict[str, str] | None = None
    ) -> bytes:
        options = {
            "query": sql,
            "wait_end_of_query": "1",
            "max_threads": "2",
            "max_memory_usage": "536870912",
            "max_bytes_before_external_group_by": "134217728",
            "max_bytes_before_external_sort": "134217728",
            "date_time_input_format": "best_effort",
            "input_format_null_as_default": "0",
            **(parameters or {}),
        }
        headers = {
            "Authorization": "Basic "
            + base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        }
        if data is not None:
            headers["Content-Encoding"] = "gzip"
            body = gzip.compress(data, compresslevel=1)
        else:
            body = b""
        request = Request(
            self.url.rstrip("/") + "/?" + urlencode(options),
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as exc:
            # Do not echo SQL, query parameters, payloads or credentials into logs.
            text = exc.read().decode(errors="replace")
            code = re.search(r"Code: (\d+)", text)
            message = f"ClickHouse HTTP {exc.code}; server code {code[1] if code else 'unknown'}"
            if exc.code in (429, 500, 502, 503, 504):
                raise TransportError(message) from None
            raise MigrationError(message) from None
        except (URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise TransportError(f"ClickHouse transport failure: {type(exc).__name__}") from None

    def query(self, sql: str) -> list[dict]:
        for attempt in range(self.read_attempts):
            try:
                return json.loads(self._request(sql + " FORMAT JSON").decode())["data"]
            except TransportError:
                if attempt + 1 == self.read_attempts:
                    raise
                time.sleep(min(2**attempt, 4))
        raise AssertionError("unreachable")

    def command(self, sql: str, parameters: dict[str, str] | None = None) -> None:
        self._request(sql, parameters=parameters)

    def insert(self, qualified_table: str, payload: bytes) -> None:
        self._request(
            f"INSERT INTO {qualified_table} FORMAT JSONEachRow",
            payload,
            {"insert_deduplicate": "0", "async_insert": "0"},
        )


def configured_client(
    values: dict[str, str], role: str = "INGEST", url: str | None = None
) -> ClickHouse:
    prefix = "CLICKHOUSE" if role == "ADMIN" else f"CLICKHOUSE_{role}"
    user, password = values.get(prefix + "_USER"), values.get(prefix + "_PASSWORD")
    if not user or not password:
        raise MigrationError(f"Set {prefix}_USER and {prefix}_PASSWORD.")
    return ClickHouse(
        url
        or values.get("CLICKHOUSE_MIGRATION_URL")
        or f"http://127.0.0.1:{values.get('CLICKHOUSE_HTTP_PORT', '18123')}",
        user,
        password,
    )
