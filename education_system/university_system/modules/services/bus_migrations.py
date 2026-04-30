"""Centralised idempotent schema bootstrap for cross-domain bus tables.

Each bus module (``finance_bus``, ``student_union_bus``,
``loyalty_bus``, ``housing_finance``) lazily creates its tables on
first call. That works at runtime but is invisible to test fixtures
that hand bus modules a fresh DB without invoking the relevant entry
point first.

This module aggregates every bus's idempotent setup into one
``ensure_all_bus_schemas()`` call. Tests that need a populated schema
can call it once in their setUp; production code does not need to —
the per-module first-call bootstraps remain in place.

The function is safe to call repeatedly: every CREATE / ALTER is
``IF NOT EXISTS`` or wrapped to ignore duplicate-column errors.
"""

from __future__ import annotations

import logging

from education_system.university_system.infrastructure.database.db import (
    get_connection,
)

logger = logging.getLogger(__name__)


# Mirrored from the individual bus modules. Kept in sync deliberately —
# the per-module copies are still authoritative for runtime first-call;
# this list is the single place tests can rely on.

_FINANCE_HOLDS = """
CREATE TABLE IF NOT EXISTS finance_holds (
    hold_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    amount       REAL NOT NULL DEFAULT 0,
    reason       TEXT NOT NULL,
    source       TEXT NOT NULL,
    reference_id TEXT,
    is_active    INTEGER NOT NULL DEFAULT 1,
    placed_at    TEXT NOT NULL,
    released_at  TEXT,
    placed_by    TEXT,
    released_by  TEXT
);
CREATE INDEX IF NOT EXISTS idx_finance_holds_student
    ON finance_holds(student_id, is_active);
"""

_SU_ADVOCACY = """
CREATE TABLE IF NOT EXISTS su_advocacy_requests (
    request_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    case_id      INTEGER NOT NULL,
    case_kind    TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    su_rep_id    TEXT,
    requested_at TEXT NOT NULL,
    claimed_at   TEXT,
    notes        TEXT
);
CREATE INDEX IF NOT EXISTS idx_su_advocacy_student
    ON su_advocacy_requests(student_id, status);
CREATE INDEX IF NOT EXISTS idx_su_advocacy_case
    ON su_advocacy_requests(case_id, case_kind);
"""

_LOYALTY_LEDGER = """
CREATE TABLE IF NOT EXISTS loyalty_ledger (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    source       TEXT NOT NULL,
    points       INTEGER NOT NULL,
    reference_id TEXT,
    description  TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_student
    ON loyalty_ledger(student_id);
"""

_GYM_DAY_PASSES = """
CREATE TABLE IF NOT EXISTS gym_day_passes (
    pass_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    used_at    TEXT,
    reason     TEXT
);
"""


# Idempotent ALTER specs: (table, column, type)
_COLUMN_ADDITIONS: tuple[tuple[str, str, str], ...] = (
    ("student_union_clubs", "hall_id", "TEXT"),
    ("restaurant_customers", "student_id", "TEXT"),
    ("risks", "reference_id",     "TEXT"),
    ("risks", "next_review_date", "TEXT"),
    ("risks", "expires_at",       "TEXT"),
    ("risks", "closed_at",        "TEXT"),
)


def _add_column_if_missing(conn, table: str,
                           column: str, ddl_type: str) -> None:
    try:
        cols = {r[1] for r in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()}
    except Exception:
        return
    if not cols or column in cols:
        return
    try:
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"
        )
    except Exception as exc:
        logger.debug("ALTER %s.%s failed: %s", table, column, exc)


def ensure_all_bus_schemas() -> None:
    """Create every cross-domain bus table + idempotent column add.

    Safe to call multiple times. Best-effort — individual statements
    that fail are logged at debug, never raised, so a missing parent
    table doesn't break unrelated bootstraps.
    """
    try:
        with get_connection() as conn:
            for script in (_FINANCE_HOLDS, _SU_ADVOCACY,
                           _LOYALTY_LEDGER, _GYM_DAY_PASSES):
                try:
                    conn.executescript(script)
                except Exception as exc:
                    logger.debug("schema script failed: %s", exc)
            for table, col, typ in _COLUMN_ADDITIONS:
                _add_column_if_missing(conn, table, col, typ)
            conn.commit()
    except Exception as exc:
        logger.warning("ensure_all_bus_schemas failed: %s", exc)


def bootstrap_all_bus_subscribers() -> None:
    """Eagerly import every bus module so any self-registering
    subscribers (e.g. ``email_bus.register_subscribers``) wire up
    at startup rather than the first lazy reference.

    Called by the unified launcher; safe to call multiple times —
    each bus's registration is idempotent.
    """
    bus_names = (
        "academic_state",
        "attendance_bus", "careers_bus", "cases_bus", "cert_bus",
        "commerce_bus", "document_bus", "email_bus", "finance_bus",
        "housing_finance", "loyalty_bus", "parking_bus",
        "restaurant_bus", "risk_bus", "staff_hr_bus",
        "student_union_bus", "trip_bus",
    )
    for name in bus_names:
        try:
            __import__(
                f"education_system.university_system.modules.services.{name}"
            )
        except Exception as exc:
            logger.debug("bus import %s failed: %s", name, exc)


__all__ = ["ensure_all_bus_schemas", "bootstrap_all_bus_subscribers"]
