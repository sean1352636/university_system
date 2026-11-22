"""one attendance store: fold ``attendance`` into ``attendance_records``

Revision ID: e9b2d4f6a8c1
Revises: c6e8a1d3f5b7
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/attendance_schema.py`` for why.

1. ``attendance_records`` is rebuilt so ``status`` is ``COLLATE NOCASE``
   (and gains ``reason`` / ``departure_time``). Rows in tables that reference
   it (appeals, calendar links) are kept across the rebuild.
2. Rows in the old ``attendance`` table are copied in — skipping any the
   absence tracker had already mirrored (same student, module and date) —
   and the table is replaced by a view of the same name with INSTEAD OF
   triggers, so code that uses the old name reads and writes the same rows.
3. Existing statuses are lower-cased; absences covered by an approved
   absence request become 'excused'.
4. The attendance office tables, settings and triggers are added.

Idempotent: each step checks the current state first.
"""
import re
from typing import Sequence, Union

from alembic import op


revision: str = 'e9b2d4f6a8c1'
down_revision: Union[str, Sequence[str], None] = 'c6e8a1d3f5b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _q(bind, sql, params=()):
    return bind.exec_driver_sql(sql, params) if params else bind.exec_driver_sql(sql)


def _object(bind, name):
    row = _q(bind, "SELECT type, sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()
    return (row[0], row[1] or "") if row else (None, "")


def _columns(bind, table):
    return [r[1] for r in _q(bind, f'PRAGMA table_info("{table}")')]


def _children(bind):
    """Tables with a foreign key to attendance_records."""
    return [r[0] for r in _q(bind, "SELECT name FROM sqlite_master WHERE type = 'table' "
                                   "AND sql LIKE '%REFERENCES attendance_records%'")]


def _rebuild_records(bind, schema):
    kind, sql = _object(bind, "attendance_records")
    if kind is None:
        op.execute(schema.create_records_sql())
        return
    if re.search(r"\bstatus\s+TEXT\s+COLLATE\s+NOCASE", sql, re.IGNORECASE):
        return  # already rebuilt
    # PRAGMA foreign_keys is a no-op inside alembic's transaction, so dropping
    # the parent could cascade into (or be blocked by) child rows: park them.
    parked = []
    for child in _children(bind):
        op.execute(f'DROP TABLE IF EXISTS "{child}__keep"')
        op.execute(f'CREATE TABLE "{child}__keep" AS SELECT * FROM "{child}"')
        op.execute(f'DELETE FROM "{child}"')
        parked.append(child)
    old = set(_columns(bind, "attendance_records"))
    shared = [n for n, _ in schema.RECORD_COLUMNS if n in old]
    cols = ", ".join(shared)
    op.execute("DROP TABLE IF EXISTS attendance_records__new")
    op.execute(schema.create_records_sql("attendance_records__new"))
    op.execute(f"INSERT INTO attendance_records__new ({cols}) SELECT {cols} FROM attendance_records")
    op.execute("DROP TABLE attendance_records")
    op.execute("ALTER TABLE attendance_records__new RENAME TO attendance_records")
    for child in parked:
        keep_cols = ", ".join(f'"{c}"' for c in _columns(bind, f"{child}__keep"))
        op.execute(f'INSERT INTO "{child}" ({keep_cols}) SELECT {keep_cols} FROM "{child}__keep"')
        op.execute(f'DROP TABLE "{child}__keep"')


def _fold_old_table(bind):
    kind, _sql = _object(bind, "attendance")
    if kind != "table":
        return
    old = set(_columns(bind, "attendance"))

    def col(name, fallback="NULL"):
        return f"a.{name}" if name in old else fallback

    op.execute(
        "INSERT INTO attendance_records (student_id, module_code, date, status, reason, notes, "
        "recorded_by, recorded_at, check_in_time, departure_time, check_in_method) "
        f"SELECT a.student_id, a.module_code, COALESCE(a.date, {col('class_date')}), LOWER(a.status), "
        f"{col('reason')}, {col('notes')}, COALESCE({col('recorded_by')}, 'register'), "
        f"COALESCE({col('created_at')}, datetime('now')), {col('arrival_time')}, {col('departure_time')}, "
        "'register' FROM attendance a "
        "WHERE NOT EXISTS (SELECT 1 FROM attendance_records r WHERE r.student_id = a.student_id "
        "                  AND r.module_code = a.module_code "
        f"                  AND r.date = COALESCE(a.date, {col('class_date')}))")
    op.execute("DROP TABLE attendance")  # its triggers go with it


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        attendance_schema as schema,
    )
    bind = op.get_bind()

    _rebuild_records(bind, schema)
    _fold_old_table(bind)
    if _object(bind, "attendance")[0] is None:
        op.execute(schema.COMPAT_VIEW)
        for ddl in schema.COMPAT_TRIGGERS:
            op.execute(ddl)

    op.execute("UPDATE attendance_records SET status = LOWER(status) "
               "WHERE status IS NOT NULL AND status <> LOWER(status) COLLATE BINARY")

    def columns(table):
        return set(_columns(bind, table))

    schema.apply(bind.exec_driver_sql, columns)

    if columns("parent_student_relationships") and columns("parent_preferences"):
        op.execute(schema.PARENT_TRIGGER)

    if columns("absence_requests"):
        # ``date_end`` is otherwise added at runtime by the absence-enhancements
        # schema; on a database built from scratch this migration runs first,
        # so add it here (same ALTER) before the backfill reads it.
        if "date_end" not in columns("absence_requests"):
            op.execute("ALTER TABLE absence_requests ADD COLUMN date_end TEXT")
        op.execute(
            "UPDATE attendance_records SET status = 'excused', "
            f"reason = '{schema.EXCUSE_MARK}' || (SELECT r.id FROM absence_requests r "
            f"   WHERE {schema._COVERS.format(rec='attendance_records')} LIMIT 1) || ')' "
            "WHERE LOWER(status) = 'absent' AND EXISTS (SELECT 1 FROM absence_requests r "
            f"   WHERE {schema._COVERS.format(rec='attendance_records')})")


def downgrade() -> None:
    # The old table's rows now live in attendance_records; nothing to split back.
    pass
