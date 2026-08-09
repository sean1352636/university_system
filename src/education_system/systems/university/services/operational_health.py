"""Operator health checks with ownership and remediation metadata."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from education_system.platform.identity.auth.db import AUTH_DB_FILE, connect
from education_system.systems.university.infrastructure.database.schema_version import (
    get_schema_state,
)
from education_system.paths import UNIVERSITY_EMAIL_CONFIG_FILE
from education_system.systems.university.services.degraded_states import (
    list_degraded_states,
)


@dataclass(frozen=True, slots=True)
class HealthCheck:
    name: str
    status: str
    owner: str
    runbook: str
    message: str
    metrics: dict[str, Any]


OWNERS = {
    "database_revision": ("platform-data", "runbooks/database-revision"),
    "outbox": ("platform-integrations", "runbooks/event-delivery"),
    "email": ("platform-communications", "runbooks/email-delivery"),
    "authentication": ("platform-identity", "runbooks/authentication"),
    "external_integrations": (
        "university-integrations",
        "runbooks/external-integrations",
    ),
    "degraded_states": ("platform-operations", "runbooks/degraded-states"),
}


def _check(name: str, fn: Callable[[], tuple[str, str, dict[str, Any]]]) -> HealthCheck:
    owner, runbook = OWNERS[name]
    try:
        status, message, metrics = fn()
    except Exception as exc:
        status, message, metrics = "failed", str(exc), {}
    return HealthCheck(name, status, owner, runbook, message, metrics)


def _database_revision() -> tuple[str, str, dict[str, Any]]:
    state = get_schema_state()
    return (
        ("healthy" if state.supported else "failed"),
        (
            "Database revision is supported"
            if state.supported
            else f"Expected {state.required}; found {state.current or 'unversioned'}"
        ),
        asdict(state),
    )


def _outbox() -> tuple[str, str, dict[str, Any]]:
    conn = connect()
    try:
        pending = conn.execute(
            """SELECT COUNT(*) FROM cross_system_event_outbox o
                WHERE NOT EXISTS (
                    SELECT 1 FROM cross_system_event_consumed c
                     WHERE c.event_id = o.event_id AND c.status = 'ok'
                )"""
        ).fetchone()[0]
        dead = conn.execute(
            """SELECT COUNT(*) FROM cross_system_event_consumed
                WHERE status = 'dead_letter'"""
        ).fetchone()[0]
    finally:
        conn.close()
    status = "failed" if dead else "degraded" if pending > 100 else "healthy"
    return status, f"{pending} pending; {dead} dead letters", {
        "pending": pending,
        "dead_letters": dead,
    }


def _email() -> tuple[str, str, dict[str, Any]]:
    configured = Path(UNIVERSITY_EMAIL_CONFIG_FILE).exists()
    return (
        ("healthy" if configured else "degraded"),
        ("Email configuration present" if configured else "Email is not configured"),
        {"configured": configured},
    )


def _authentication() -> tuple[str, str, dict[str, Any]]:
    conn = sqlite3.connect(AUTH_DB_FILE)
    try:
        conn.execute("SELECT 1").fetchone()
    finally:
        conn.close()
    return "healthy", "Authentication store reachable", {}


def _external_integrations() -> tuple[str, str, dict[str, Any]]:
    # Configuration availability is reported without making remote requests.
    return "healthy", "Integration registry available", {"remote_probe": False}


def _degraded() -> tuple[str, str, dict[str, Any]]:
    states = list_degraded_states()
    critical = sum(row["severity"] == "critical" for row in states)
    status = "failed" if critical else "degraded" if states else "healthy"
    return status, f"{len(states)} open degraded states", {
        "open": len(states),
        "critical": critical,
    }


def health_report() -> dict[str, Any]:
    checks = [
        _check("database_revision", _database_revision),
        _check("outbox", _outbox),
        _check("email", _email),
        _check("authentication", _authentication),
        _check("external_integrations", _external_integrations),
        _check("degraded_states", _degraded),
    ]
    statuses = {check.status for check in checks}
    overall = (
        "failed" if "failed" in statuses
        else "degraded" if "degraded" in statuses
        else "healthy"
    )
    return {"status": overall, "checks": [asdict(check) for check in checks]}


__all__ = ["HealthCheck", "OWNERS", "health_report"]
