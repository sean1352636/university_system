"""university: one home each for safeguarding and health data

* **Safeguarding** — the safeguarding service keeps its cases in the
  classified database ``var/data/university/safeguarding/
  safeguarding_records.db`` (``ClassifiedStorage().database_path(
  "safeguarding")``), but eleven ``safeguarding_*`` tables also existed in
  ``student_records.db``. The chat "report and escalate" path wrote there,
  where no safeguarding screen looks (fixed in code). Their rows are copied
  into the classified database — submission ids kept where free, otherwise
  remapped with the children following — each move recorded in the
  classified audit log (``moved_from_main_db``), checked, and only then are
  the main-database copies dropped. ``university_event_outbox`` is not a
  safeguarding table: each database keeps its own transactional outbox.
* **Health** — health code reads and writes ``student_records.db`` (through
  ``pastoral/infrastructure/health/storage``); ``health_records.db`` is the
  abandoned store. Its stranded rows (``first_aid_incidents``,
  ``first_aid_training_registrations``, ``security_settings``) are copied in,
  skipping exact duplicates (and settings whose name is already set). The file is left in
  place for the user to delete.
* **medical_conditions** — rows whose student is not on record (two, for
  student 9248626, imported from a sixth-form record) are moved into
  ``orphaned_health_records`` with the reason, for review, instead of
  pointing at a student who does not exist.

Revision ID: 3c5e7a9b1d4f
Revises: 2b4d6f8a0c3e
Create Date: 2026-10-18 12:00:00.000000

Idempotent: re-running finds nothing left to move.
"""
import json
import sqlite3
from datetime import datetime
from typing import Sequence, Union

from alembic import op


revision: str = '3c5e7a9b1d4f'
down_revision: Union[str, Sequence[str], None] = '2b4d6f8a0c3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Parents first, so children can follow a remapped submission id.
SAFEGUARDING_TABLES = (
    "safeguarding_submissions", "safeguarding_assignments", "safeguarding_action_items",
    "safeguarding_case_notes", "safeguarding_case_referrals", "safeguarding_notifications",
    "safeguarding_audit_log", "safeguarding_dsl_oncall", "safeguarding_training",
    "safeguarding_webhooks", "safeguarding_webhook_deliveries",
)
# (table, key columns; None = a row is a duplicate only when every column
# but the id matches — test runs left many exact copies, and rows differing
# only in severity or status are different records)
HEALTH_TABLES = (
    ("first_aid_incidents", None),
    ("first_aid_training_registrations", None),
    ("security_settings", ("setting_name",)),
)


def _tables(execute) -> set[str]:
    return {r[0] for r in execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            .fetchall()}


def _columns(execute, table) -> list[str]:
    return [r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()]


def _same(conn, table, cols, row) -> bool:
    """Is a row with these values (id aside) already in ``table``?"""
    where = " AND ".join(f'"{c}" IS ?' for c in cols)
    return conn.execute(f'SELECT 1 FROM "{table}" WHERE {where} LIMIT 1',  # nosec B608
                        [row[c] for c in cols]).fetchone() is not None


# ── safeguarding ────────────────────────────────────────────────────────


def _classified_path():
    from education_system.platform.kernel.adapters import ClassifiedStorage
    return ClassifiedStorage().database_path("safeguarding")


def _move_safeguarding(execute) -> None:
    present = [t for t in SAFEGUARDING_TABLES if t in _tables(execute)]
    if not present:
        return
    # Make sure the classified database has the safeguarding schema.
    from education_system.systems.university.domains.safeguarding.infrastructure.db import (
        init_db,
    )
    init_db()
    target = sqlite3.connect(str(_classified_path()))
    target.row_factory = sqlite3.Row
    there = {r[0] for r in target.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    id_map: dict[int, int] = {}
    moved: dict[str, int] = {}
    try:
        for table in present:
            if table not in there:
                raise RuntimeError(f"The safeguarding database has no table {table}")
            source_cols = _columns(execute, table)
            cols = [c for c in source_cols if c in _columns(target.execute, table) and c != "id"]
            for values in execute(f'SELECT * FROM "{table}"').fetchall():  # nosec B608
                row = dict(zip(source_cols, values))
                if table != "safeguarding_submissions" and row.get("case_id") in id_map:
                    row["case_id"] = id_map[row["case_id"]]
                if _same(target, table, cols, row):
                    if table == "safeguarding_submissions":
                        found = target.execute(
                            f'SELECT id FROM "{table}" WHERE '  # nosec B608
                            + " AND ".join(f'"{c}" IS ?' for c in cols),
                            [row[c] for c in cols]).fetchone()
                        id_map[row["id"]] = found[0]
                    continue
                keep_id = "id" in row and target.execute(
                    f'SELECT 1 FROM "{table}" WHERE id = ?', (row["id"],)).fetchone() is None  # nosec B608
                insert_cols = (["id"] if keep_id else []) + cols
                cur = target.execute(
                    f'INSERT INTO "{table}" ({", ".join(chr(34) + c + chr(34) for c in insert_cols)}) '  # nosec B608
                    f'VALUES ({", ".join("?" * len(insert_cols))})',
                    [row[c] for c in insert_cols])
                if table == "safeguarding_submissions":
                    id_map[row["id"]] = row["id"] if keep_id else cur.lastrowid
                moved[table] = moved.get(table, 0) + 1
        if moved:
            target.execute(
                "INSERT INTO safeguarding_audit_log (ts, actor, actor_role, action, case_id, "
                "details) VALUES (?, 'migration 3c5e7a9b1d4f', 'system', 'moved_from_main_db', "
                "NULL, ?)",
                (datetime.now().isoformat(),
                 json.dumps({"rows": moved, "submission_ids": id_map}, sort_keys=True)))
        target.commit()
        # Check every main row now has its copy before dropping anything.
        for table in present:
            source_cols = _columns(execute, table)
            cols = [c for c in source_cols if c in _columns(target.execute, table) and c != "id"]
            for values in execute(f'SELECT * FROM "{table}"').fetchall():  # nosec B608
                row = dict(zip(source_cols, values))
                if table != "safeguarding_submissions" and row.get("case_id") in id_map:
                    row["case_id"] = id_map[row["case_id"]]
                if not _same(target, table, cols, row):
                    raise RuntimeError(f"{table}: a row did not reach the safeguarding database; "
                                       "nothing was dropped")
    finally:
        target.close()
    for table in reversed(present):
        execute(f'DROP TABLE IF EXISTS "{table}"')


# ── health ──────────────────────────────────────────────────────────────


def _move_health(execute) -> None:
    from education_system.paths import UNIVERSITY_HEALTH_DB_PATH
    if not UNIVERSITY_HEALTH_DB_PATH.exists():
        return
    source = sqlite3.connect(f"file:{UNIVERSITY_HEALTH_DB_PATH}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        source_tables = {r[0] for r in source.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        main_tables = _tables(execute)
        for table, key_cols in HEALTH_TABLES:
            if table not in source_tables:
                continue
            if table not in main_tables:
                ddl = source.execute("SELECT sql FROM sqlite_master WHERE name = ?",
                                     (table,)).fetchone()[0]
                execute(ddl.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS", 1))
            main_cols = set(_columns(execute, table))
            for row in source.execute(f'SELECT * FROM "{table}"'):  # nosec B608
                row = dict(row)
                key = key_cols or [c for c in row if c != "id" and c in main_cols]
                where = " AND ".join(f'"{c}" IS ?' for c in key)
                if execute(f'SELECT 1 FROM "{table}" WHERE {where} LIMIT 1',  # nosec B608
                           tuple(row[c] for c in key)).fetchone():
                    continue
                cols = [c for c in row if c != "id" and c in main_cols]
                execute(f'INSERT INTO "{table}" ({", ".join(chr(34) + c + chr(34) for c in cols)}) '  # nosec B608
                        f'VALUES ({", ".join("?" * len(cols))})', tuple(row[c] for c in cols))
    finally:
        source.close()


def _quarantine_orphan_conditions(execute) -> None:
    tables = _tables(execute)
    if not {"medical_conditions", "students"} <= tables:
        return
    execute("""CREATE TABLE IF NOT EXISTS orphaned_health_records (
        orphan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_table TEXT NOT NULL,
        source_id INTEGER,
        student_id TEXT,
        reason TEXT NOT NULL,
        original_json TEXT NOT NULL,
        quarantined_at TEXT NOT NULL DEFAULT (datetime('now')),
        resolved_at TEXT,
        resolution TEXT
    )""")
    cols = _columns(execute, "medical_conditions")
    rows = execute("SELECT * FROM medical_conditions WHERE student_id IS NOT NULL AND "
                   "student_id NOT IN (SELECT student_id FROM students)").fetchall()
    for values in rows:
        row = dict(zip(cols, values))
        execute("INSERT INTO orphaned_health_records (source_table, source_id, student_id, "
                "reason, original_json) VALUES ('medical_conditions', ?, ?, ?, ?)",
                (row.get("id"), row.get("student_id"),
                 "The student is not on record (imported without a student record)",
                 json.dumps(row, default=str, sort_keys=True)))
        execute("DELETE FROM medical_conditions WHERE id = ?", (row.get("id"),))


def upgrade() -> None:
    execute = op.get_bind().exec_driver_sql
    _move_safeguarding(execute)
    _move_health(execute)
    _quarantine_orphan_conditions(execute)


def downgrade() -> None:
    # The classified safeguarding database is the home of those rows, and
    # health_records.db is retired; nothing is moved back.
    pass
