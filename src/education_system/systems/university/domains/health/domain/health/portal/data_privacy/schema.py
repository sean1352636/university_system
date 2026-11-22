"""Schema entry points for the health portal's integration and security
tables. The tables themselves are declared once, in
``infrastructure/health/health_schema`` (migration ``a0d2f4b6c8e1``).
"""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3
from education_system.systems.university.domains.health.domain.health.services import get_connection

def ensure_integration_schema():
    """The integration tables (``integration_logs``, insurance / lab events,
    ``sync_queue``) with their alias columns and indexes — declared once in
    ``infrastructure/health/health_schema`` and applied once per database
    file. Safe to call repeatedly."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        health_schema,
    )
    health_schema.ensure()


def ensure_security_schema():
    """The privacy / security tables (``data_privacy_settings``,
    ``encryption_keys``, RBAC, security incidents) with their alias columns
    (backfilled when added) — see ``health_schema``. Safe to call repeatedly."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        health_schema,
    )
    health_schema.ensure()


def _first_existing_column(conn: sqlite3.Connection, table: str, candidates: list[str]) -> str | None:
    from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
    validate_identifier(table, "table")
    cur = conn.cursor()
    cur.execute("PRAGMA table_info([" + table + "])")
    cols = {row[1] for row in cur.fetchall()}
    for col in candidates:
        if col in cols:
            return col
    return None
