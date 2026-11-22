"""Applying a Staff HR schema module.

The newer Staff HR schema modules (``staff_hr_access_schema``,
``staff_hr_absence_schema``, ``staff_hr_pay_schema``,
``staff_hr_hiring_schema``, ``staff_hr_compliance_schema``) each declare

* ``TABLES`` — ``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF NOT
  EXISTS`` statements, applied in order;
* ``ADDED_COLUMNS`` — ``(table, column, type)`` added to an existing table
  when it lacks the column;
* ``migrate_data(execute)`` — idempotent data changes (optional).

:func:`apply` runs one module with any ``execute`` that returns something
with ``fetchall()`` — ``sqlite3.Connection.execute`` at runtime, or
``op.get_bind().exec_driver_sql`` in the migration. Idempotent.
"""

from __future__ import annotations

import importlib

_PKG = "education_system.systems.university.domains.staff.infrastructure.database"

#: Every module, in the order they apply (a later one may refer to an
#: earlier one's tables).
MODULES = (
    "staff_hr_access_schema",
    "staff_hr_absence_schema",
    "staff_hr_pay_schema",
    "staff_hr_hiring_schema",
    "staff_hr_compliance_schema",
    "staff_hr_communication_schema",
)


def columns(execute, table: str) -> set:
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def table_exists(execute, table: str) -> bool:
    return bool(execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table,)).fetchall())


def apply_module(execute, module, data=True) -> None:
    for ddl in getattr(module, "TABLES", ()):
        execute(ddl)
    for table, column, kind in getattr(module, "ADDED_COLUMNS", ()):
        if table_exists(execute, table) and column not in columns(execute, table):
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {kind}')
    migrate = getattr(module, "migrate_data", None)
    if data and migrate is not None:
        migrate(execute)


def apply(execute, data=True) -> None:
    """Every module in :data:`MODULES` (``data``: run their data changes too —
    the migration does; the runtime only makes sure the tables exist)."""
    for name in MODULES:
        apply_module(execute, importlib.import_module(f"{_PKG}.{name}"), data)


_APPLIED: set = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file per process; commits unless the
    caller has a transaction open."""
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        return
    busy = conn.in_transaction
    apply(conn.execute, data=False)
    if busy:
        return
    conn.commit()
    if key:
        _APPLIED.add(key)


__all__ = ["MODULES", "apply", "apply_module", "apply_to_connection", "columns", "table_exists"]
