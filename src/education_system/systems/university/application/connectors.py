"""Supported institutional connector contracts and replay-safe execution."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from education_system.systems.university.infrastructure import connector_adapters
from education_system.systems.university.infrastructure.connector_adapters import adapter_for
from education_system.systems.university.infrastructure.database.db import transaction

SUPPORTED_CONNECTORS = frozenset(
    {
        "ucas", "hesa_jisc", "slc", "ukvi_cas", "payments", "library",
        "vle", "idp", "timetable", "degree_verification",
    }
)


def configure(name: str, config: Mapping[str, Any], *, enabled: bool = True) -> None:
    if name not in SUPPORTED_CONNECTORS:
        raise ValueError(f"Unsupported connector {name!r}")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO connector_configurations
                 (connector_name, enabled, config_json, status)
               VALUES (?, ?, ?, 'configured')
               ON CONFLICT(connector_name) DO UPDATE SET
                 enabled=excluded.enabled, config_json=excluded.config_json,
                 status='configured', last_error=NULL""",
            (name, int(enabled), json.dumps(dict(config), sort_keys=True)),
        )


def deliver(
    name: str, idempotency_key: str, payload: Mapping[str, Any],
    adapter: Callable[[Mapping[str, Any]], str | None],
) -> bool:
    if name not in SUPPORTED_CONNECTORS:
        raise ValueError(f"Unsupported connector {name!r}")
    with transaction() as conn:
        existing = conn.execute(
            "SELECT 1 FROM connector_receipts "
            "WHERE connector_name=? AND idempotency_key=?",
            (name, idempotency_key),
        ).fetchone()
        if existing:
            return False
        configured = conn.execute(
            "SELECT enabled FROM connector_configurations WHERE connector_name=?",
            (name,),
        ).fetchone()
        if configured is None or not configured["enabled"]:
            raise RuntimeError(f"Connector {name} is not enabled")
        reference = adapter(payload)
        conn.execute(
            """INSERT INTO connector_receipts
                 (connector_name, idempotency_key, external_reference, outcome)
               VALUES (?, ?, ?, 'delivered')""",
            (name, idempotency_key, reference),
        )
        conn.execute(
            "UPDATE connector_configurations SET status='healthy', "
            "last_checked_at=CURRENT_TIMESTAMP WHERE connector_name=?",
            (name,),
        )
    return True


def enabled_config(name: str) -> dict[str, Any] | None:
    """The configuration of an enabled connector, or ``None``."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT enabled, config_json FROM connector_configurations WHERE connector_name=?",
            (name,),
        ).fetchone()
    if row is None or not row["enabled"]:
        return None
    return json.loads(row["config_json"] or "{}")


def send(name: str, idempotency_key: str, payload: Mapping[str, Any]) -> bool | None:
    """Deliver through the connector's configured transport. ``None`` when
    the connector is not enabled (nothing is recorded, nothing is sent)."""
    config = enabled_config(name)
    if config is None:
        return None
    record = {"idempotency_key": idempotency_key, **dict(payload)}
    try:
        return deliver(name, idempotency_key, record, adapter_for(name, config))
    except Exception as exc:
        with transaction() as conn:
            conn.execute(
                "UPDATE connector_configurations SET status='failing', last_error=?, "
                "last_checked_at=CURRENT_TIMESTAMP WHERE connector_name=?",
                (str(exc)[:500], name),
            )
        raise


def configuration(name: str) -> dict[str, Any]:
    """The stored configuration whether or not the connector is enabled."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT config_json FROM connector_configurations WHERE connector_name=?", (name,),
        ).fetchone()
    return json.loads(row["config_json"] or "{}") if row else {}


def write_batch(name: str, batch_id: str, filename: str, content: str | bytes) -> str:
    """Write a whole batch file (a statutory return, a decisions file) into
    the connector's file folder for staff to upload to the external portal,
    and record it as a receipt (``outcome='file_written'``). Nothing is sent:
    the HESA, SLC, UCAS and Home Office portals take uploads by hand.
    Returns the file path."""
    if name not in SUPPORTED_CONNECTORS:
        raise ValueError(f"Unsupported connector {name!r}")
    path = connector_adapters.write_batch_file(name, configuration(name), filename, content)
    with transaction() as conn:
        conn.execute(
            """INSERT INTO connector_receipts
                 (connector_name, idempotency_key, external_reference, outcome)
               VALUES (?, ?, ?, 'file_written')
               ON CONFLICT(connector_name, idempotency_key) DO NOTHING""",
            (name, f"batch:{batch_id}", str(path)),
        )
    return str(path)


def overview() -> list[dict[str, Any]]:
    """Every supported connector with its configuration and receipt count."""
    with transaction() as conn:
        rows = {r["connector_name"]: dict(r) for r in conn.execute(
            "SELECT * FROM connector_configurations")}
        counts = dict(conn.execute(
            "SELECT connector_name, COUNT(*) FROM connector_receipts GROUP BY connector_name"
        ).fetchall())
    out = []
    for name in sorted(SUPPORTED_CONNECTORS):
        row = rows.get(name, {})
        out.append({
            "connector_name": name,
            "enabled": bool(row.get("enabled")),
            "config": json.loads(row.get("config_json") or "{}"),
            "status": row.get("status") or "unconfigured",
            "last_checked_at": row.get("last_checked_at"),
            "last_error": row.get("last_error"),
            "receipts": int(counts.get(name, 0)),
        })
    return out


def receipts(name: str, limit: int = 100) -> list[dict[str, Any]]:
    with transaction() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM connector_receipts WHERE connector_name=? "
            "ORDER BY processed_at DESC LIMIT ?", (name, limit))]


__all__ = [
    "SUPPORTED_CONNECTORS", "configuration", "configure", "deliver", "enabled_config",
    "overview", "receipts", "send", "write_batch",
]
