"""Supported institutional connector contracts and replay-safe execution."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

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


__all__ = ["SUPPORTED_CONNECTORS", "configure", "deliver"]
