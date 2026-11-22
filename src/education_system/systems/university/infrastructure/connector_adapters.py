"""Transports for the institutional connectors (``application/connectors``).

Each enabled connector names a transport in its configuration
(``connector_configurations.config_json``):

* ``file`` (the default) - one JSON line per record in
  ``var/data/university/exports/connectors/<connector>/<YYYY-MM-DD>.jsonl``.
  UCAS, HESA Data Futures, the SLC portal and the Home Office sponsor system
  take batch uploads, so staff collect the day's file and upload it; the
  file is the record of what was sent.
* ``http`` - a JSON ``POST`` to ``endpoint`` with a bearer token read from
  the environment variable named by ``token_env`` or from ``token_file``
  (a file under ``var/secrets``). Never from the configuration itself.
  ``timeout`` is in seconds (default 20). A non-2xx answer raises, so the
  event is retried.

The adapter returns the external reference stored on the connector receipt.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from education_system import paths

OUTBOUND_DIR: Path = paths.UNIVERSITY_EXPORTS_DIR / "connectors"
TRANSPORTS = ("file", "http")
_FILE_LOCK = threading.Lock()

Adapter = Callable[[Mapping[str, Any]], str | None]


def connector_directory(connector: str, config: Mapping[str, Any] | None = None) -> Path:
    """The folder a connector's files go to: its configured ``directory``,
    else ``exports/connectors/<connector>``."""
    return Path((config or {}).get("directory") or OUTBOUND_DIR / connector)


def write_batch_file(connector: str, config: Mapping[str, Any] | None, filename: str,
                     content: str | bytes) -> Path:
    """Write one whole batch file (XML, CSV) into ``<connector folder>/batches``.
    Refuses to overwrite: every batch gets its own name."""
    name = Path(filename).name
    if not name or name != filename:
        raise ValueError("A batch file name cannot contain a folder")
    target = connector_directory(connector, config) / "batches" / name
    with _FILE_LOCK:
        target.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode("utf-8") if isinstance(content, str) else content
        with target.open("xb") as handle:
            handle.write(data)
    return target


def file_adapter(connector: str, config: Mapping[str, Any]) -> Adapter:
    folder = connector_directory(connector, config)

    def send(record: Mapping[str, Any]) -> str:
        now = datetime.now(UTC)
        target = folder / f"{now.date().isoformat()}.jsonl"
        line = json.dumps({"connector": connector, "written_at": now.isoformat(),
                           **dict(record)}, default=str, sort_keys=True)
        with _FILE_LOCK:
            folder.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return f"file:{target.name}"

    return send


def _token(config: Mapping[str, Any]) -> str | None:
    if config.get("token_env"):
        return os.environ.get(str(config["token_env"])) or None
    if config.get("token_file"):
        path = Path(str(config["token_file"]))
        if not path.is_absolute():
            path = paths.PLATFORM_SECRETS_DIR / path
        try:
            return path.read_text(encoding="utf-8").strip() or None
        except OSError as exc:
            raise RuntimeError(f"Connector token file {path} cannot be read") from exc
    return None


def http_adapter(connector: str, config: Mapping[str, Any]) -> Adapter:
    endpoint = str(config.get("endpoint") or "").strip()
    if not endpoint.lower().startswith("https://"):
        raise RuntimeError(f"Connector {connector} needs an https:// endpoint")
    timeout = float(config.get("timeout") or 20)

    def send(record: Mapping[str, Any]) -> str | None:
        headers = {"Content-Type": "application/json",
                   "Idempotency-Key": str(record.get("idempotency_key") or "")}
        token = _token(config)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = json.dumps(dict(record), default=str).encode("utf-8")
        req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 - https only
                raw = resp.read().decode("utf-8", "replace")
                status = resp.status
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{connector} answered HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{connector} unreachable: {exc.reason}") from exc
        try:
            answer = json.loads(raw) if raw else {}
        except ValueError:
            answer = {}
        if isinstance(answer, dict):
            for key in ("reference", "id", "transaction_id"):
                if answer.get(key):
                    return str(answer[key])
        return f"http:{status}"

    return send


def adapter_for(connector: str, config: Mapping[str, Any]) -> Adapter:
    transport = str(config.get("transport") or "file").lower()
    if transport == "http":
        return http_adapter(connector, config)
    if transport == "file":
        return file_adapter(connector, config)
    raise RuntimeError(f"Connector {connector} has unknown transport {transport!r}")


__all__ = ["OUTBOUND_DIR", "TRANSPORTS", "adapter_for", "connector_directory", "file_adapter",
           "http_adapter", "write_batch_file"]
