"""university trips: one trip store, the new trip columns and tables

1. **Status CHECKs.** ``trips.status`` now allows proposed, planning (the
   legacy spelling of proposed), approved, open, full, closed, in_progress,
   cancelled, completed and archived; ``trip_participants.status`` allows
   registered, waitlisted, offered, confirmed, cancelled, attended, no_show
   and removed. A table whose CHECK differs is rebuilt from its own stored
   definition with only the CHECK (and the trips status default) changed,
   legacy values mapped ('active' -> 'open', 'planned' -> 'planning',
   'waitlist' -> 'waitlisted', ...). Child rows are parked and restored
   around the rebuild, indexes and triggers recreated, the AUTOINCREMENT
   sequence kept. An unknown status value stops the migration rather than
   being guessed.
2. **Schema.** ``trip_management/database.apply`` — the one trip DDL —
   adds the new columns to trips / trip_participants / trip_staff and
   creates trip_history, trip_approvals, trip_risk_assessments,
   trip_risk_items, trip_incidents, trip_rollcalls, trip_rollcall_entries,
   trip_instalments, trip_evaluations and trip_reconciliations.
3. **One store.** ``trip_registrations`` rows become ``trip_participants``
   rows; ``union_trips`` become ``trips`` (``source`` 'su',
   ``organising_club`` from ``student_clubs``) and their
   ``union_trip_registrations`` become participants. Each legacy table is
   dropped only when every row was copied (a row whose person or trip
   cannot be resolved, or with notes there is no column for, keeps its
   table). A copied union trip is marked in ``trip_history`` so a re-run
   never copies it twice.
4. ``trip_calendar_events`` is dropped if it exists and is empty (nothing
   reads it; trip events live in ``unified_events``).
5. Instructors are granted ``create_trips`` (they lead trips already).

Idempotent: every step checks what exists first.

Revision ID: c4146c91ede9
Revises: d8f0a2c4e6b9
Create Date: 2026-10-18 21:00:00.000000
"""
import logging
import re
from datetime import datetime
from typing import Sequence, Union

from alembic import op


revision: str = 'c4146c91ede9'
down_revision: Union[str, Sequence[str], None] = 'd8f0a2c4e6b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)

_STATUS_CHECK = re.compile(r"CHECK\s*\(\s*status\s+IN\s*\(([^)]*)\)\s*\)", re.IGNORECASE)
_MERGE_MARK = "union_trips:"

UNION_TRIP_STATUS = {'upcoming': 'open', 'full': 'full', 'cancelled': 'cancelled',
                     'completed': 'completed'}
REGISTRATION_STATUS = {'pending': 'registered', 'registered': 'registered',
                       'approved': 'registered', 'confirmed': 'confirmed',
                       'cancelled': 'cancelled', 'waitlist': 'waitlisted',
                       'waitlisted': 'waitlisted', 'attended': 'attended'}


def _x():
    return op.get_bind().exec_driver_sql


def _table(name) -> bool:
    return _x()("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (name,)).fetchone() is not None


def _cols(table) -> list:
    return [r[1] for r in _x()(f'PRAGMA table_info("{table}")').fetchall()]


def _count(table) -> int:
    return _x()(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]  # nosec B608


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _children(table) -> list:
    """Tables with a foreign key to ``table``."""
    pattern = re.compile(r'REFERENCES\s+"?%s"?\s*\(' % re.escape(table), re.IGNORECASE)
    return [name for name, sql in _x()("SELECT name, sql FROM sqlite_master WHERE type = 'table' "
                                       "AND name <> ?", (table,)).fetchall()
            if sql and pattern.search(sql)]


# ── 1. status CHECKs ────────────────────────────────────────────────────


def _rebuild_status_check(table, allowed, legacy, default_from=None, default_to=None) -> None:
    execute = _x()
    row = execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                  (table,)).fetchone()
    if not row:
        return
    sql = row[0]
    match = _STATUS_CHECK.search(sql)
    if not match:
        return  # no CHECK: every value is already accepted
    current = {v.strip().strip("'\"") for v in match.group(1).split(',') if v.strip()}
    if current == set(allowed):
        return  # already rebuilt

    # Values the new CHECK would refuse stop the migration: guessing a
    # status would silently change what a trip or a booking means.
    case = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in legacy.items())
    mapped = f"CASE status {case} ELSE status END" if legacy else "status"
    marks = ", ".join(f"'{v}'" for v in allowed)
    bad = execute(f'SELECT DISTINCT status FROM "{table}" WHERE status IS NOT NULL '  # nosec B608
                  f'AND ({mapped}) NOT IN ({marks})').fetchall()
    if bad:
        raise RuntimeError(f"{table}: status values with no mapping: "
                           f"{', '.join(str(r[0]) for r in bad)}")

    new_sql = sql[:match.start()] + f"CHECK (status IN ({marks}))" + sql[match.end():]
    if default_from:
        new_sql = re.sub(r"(status\s+TEXT\s+DEFAULT\s+)'%s'" % re.escape(default_from),
                         r"\1'%s'" % default_to, new_sql, count=1, flags=re.IGNORECASE)
    temp = f"{table}__rebuild"
    new_sql, renamed = re.subn(r'^\s*CREATE\s+TABLE\s+"?%s"?' % re.escape(table),
                               f'CREATE TABLE "{temp}"', new_sql, count=1, flags=re.IGNORECASE)
    if not renamed:
        raise RuntimeError(f"{table}: could not read its CREATE TABLE statement")

    columns = _cols(table)
    seq_row = execute("SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)).fetchone() \
        if _table("sqlite_sequence") else None
    extras = [r[0] for r in execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name = ? AND type IN ('index', 'trigger') "
        "AND sql IS NOT NULL", (table,)).fetchall()]
    before = _count(table)

    # PRAGMA foreign_keys is a no-op inside alembic's transaction, so dropping
    # the parent could cascade into (or be blocked by) child rows: park them.
    parked = []
    for child in _children(table):
        execute(f'DROP TABLE IF EXISTS "{child}__keep"')
        execute(f'CREATE TABLE "{child}__keep" AS SELECT * FROM "{child}"')
        execute(f'DELETE FROM "{child}"')
        parked.append(child)

    execute(f'DROP TABLE IF EXISTS "{temp}"')
    execute(new_sql)
    cols = ", ".join(f'"{c}"' for c in columns)
    select = ", ".join(mapped if c == 'status' else f'"{c}"' for c in columns)
    execute(f'INSERT INTO "{temp}" ({cols}) SELECT {select} FROM "{table}"')  # nosec B608
    if _count(temp) != before:
        raise RuntimeError(f"{table}: row count changed during the rebuild")
    execute(f'DROP TABLE "{table}"')
    execute(f'ALTER TABLE "{temp}" RENAME TO "{table}"')
    for ddl in extras:
        execute(ddl)
    if seq_row is not None:
        # Keep AUTOINCREMENT from reusing ids of deleted rows.
        if execute("SELECT 1 FROM sqlite_sequence WHERE name = ?", (table,)).fetchone():
            execute("UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = ?",
                    (seq_row[0], table))
        else:
            execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (table, seq_row[0]))

    for child in parked:
        keep_cols = ", ".join(f'"{c}"' for c in _cols(f"{child}__keep"))
        execute(f'INSERT INTO "{child}" ({keep_cols}) SELECT {keep_cols} FROM "{child}__keep"')  # nosec B608
        execute(f'DROP TABLE "{child}__keep"')
    logger.info("Rebuilt %s with the new status CHECK (%s rows)", table, before)


# ── 3. one store ────────────────────────────────────────────────────────


def _student_of(user_id):
    """users.student_id for a users.id, when that student exists."""
    execute = _x()
    row = execute("SELECT student_id FROM users WHERE id = ?", (user_id,)).fetchone()
    sid = row[0] if row else None
    if sid and _table("students") and not execute(
            "SELECT 1 FROM students WHERE student_id = ?", (sid,)).fetchone():
        return None  # trip_participants.student_id is FK -> students
    return sid


def _person(value):
    """``(users.id, student_id)`` for a stored username / student number, or None.

    A bare number is not read as users.id: the SU screen stored the signed-in
    user's id, which may be the shared auth.db id.
    """
    execute = _x()
    text = str(value or "").strip()
    if not text:
        return None
    row = execute("SELECT id, student_id FROM users WHERE username = ? COLLATE NOCASE",
                  (text,)).fetchone()
    if row is None:
        row = execute("SELECT id, student_id FROM users WHERE student_id = ?", (text,)).fetchone()
    if row is None:
        return None
    return row[0], _student_of(row[0])


def _place_exists(trip_id, user_id, student_id) -> bool:
    execute = _x()
    if student_id:
        return execute("SELECT 1 FROM trip_participants WHERE trip_id = ? AND student_id = ?",
                       (trip_id, student_id)).fetchone() is not None
    return execute("SELECT 1 FROM trip_participants WHERE trip_id = ? AND user_id = ?",
                   (trip_id, user_id)).fetchone() is not None


def _merge_trip_registrations() -> None:
    execute = _x()
    if not _table("trip_registrations"):
        return
    cols = set(_cols("trip_registrations"))
    notes = "notes" if "notes" in cols else "NULL"
    rows = execute(f"SELECT id, trip_id, user_id, registration_date, status, {notes} "  # nosec B608
                   "FROM trip_registrations").fetchall()
    copied = 0
    for _rid, trip_id, user_id, registered, status, note in rows:
        if note and str(note).strip():
            continue  # trip_participants has no column for it: keep the row
        if not execute("SELECT 1 FROM trips WHERE id = ?", (trip_id,)).fetchone():
            continue
        if not execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
            continue
        student_id = _student_of(user_id)
        if not _place_exists(trip_id, user_id, student_id):
            execute("INSERT INTO trip_participants (trip_id, student_id, user_id, registration_date, "
                    "status, payment_status, source) VALUES (?, ?, ?, ?, ?, 'pending', 'operations')",
                    (trip_id, student_id, user_id, registered or _now(),
                     REGISTRATION_STATUS.get(str(status or '').lower(), 'registered')))
        copied += 1
    if copied == len(rows):
        execute("DROP TABLE trip_registrations")
    else:
        logger.warning("trip_registrations kept: %s of %s rows could not be copied",
                       len(rows) - copied, len(rows))


def _merged_trip_ids() -> dict:
    """union_trips.trip_id -> trips.id for union trips already copied."""
    rows = _x()("SELECT trip_id, new_value FROM trip_history WHERE action = 'merged' "
                "AND new_value LIKE ?", (_MERGE_MARK + '%',)).fetchall()
    return {int(value[len(_MERGE_MARK):]): trip_id for trip_id, value in rows}


def _merge_union_trips() -> None:
    execute = _x()
    if not _table("union_trips"):
        return
    clubs = {}
    if _table("student_clubs") and {"club_id", "club_name"} <= set(_cols("student_clubs")):
        clubs = dict(execute("SELECT club_id, club_name FROM student_clubs").fetchall())
    done = _merged_trip_ids()
    rows = execute("SELECT trip_id, trip_name, destination, trip_date, return_date, description, "
                   "max_participants, estimated_cost, organizer_club_id, created_by, created_at, "
                   "status FROM union_trips").fetchall()
    for (old_id, name, destination, day, return_day, description, cap, cost, club_id,
         created_by, created_at, status) in rows:
        if old_id in done:
            continue
        person = _person(created_by)
        stamp = created_at or _now()
        cur = execute(
            "INSERT INTO trips (trip_name, description, destination, start_date, end_date, "
            "max_participants, cost, status, created_by, created_at, updated_at, trip_type, "
            "source, organising_club, version, updated_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'su_social', 'su', ?, 1, ?)",
            (name, description, destination, day, return_day or day, cap or 30, cost or 0.0,
             UNION_TRIP_STATUS.get(str(status or '').lower(), 'proposed'),
             person[0] if person else None, stamp, stamp, clubs.get(club_id),
             str(created_by) if created_by is not None else None))
        new_id = cur.lastrowid
        execute("INSERT INTO trip_history (trip_id, version, changed_by, changed_at, action, "
                "field, old_value, new_value) VALUES (?, 1, 'migration', ?, 'merged', NULL, NULL, ?)",
                (new_id, _now(), f"{_MERGE_MARK}{old_id}"))
        done[old_id] = new_id

    regs_left = 0
    if _table("union_trip_registrations"):
        regs = execute("SELECT trip_id, user_id, registered_at FROM union_trip_registrations").fetchall()
        copied = 0
        for old_trip, user, registered in regs:
            new_trip = done.get(old_trip)
            person = _person(user)
            if new_trip is None or person is None:
                continue
            user_id, student_id = person
            if not _place_exists(new_trip, user_id, student_id):
                execute("INSERT INTO trip_participants (trip_id, student_id, user_id, "
                        "registration_date, status, payment_status, source) "
                        "VALUES (?, ?, ?, ?, 'registered', 'pending', 'su')",
                        (new_trip, student_id, user_id, registered or _now()))
            copied += 1
        if copied == len(regs):
            execute("DROP TABLE union_trip_registrations")
        else:
            regs_left = len(regs) - copied
            logger.warning("union_trip_registrations kept: %s of %s rows could not be copied",
                           regs_left, len(regs))
    if not regs_left and all(r[0] in done for r in rows):
        execute("DROP TABLE union_trips")


def _drop_trip_calendar_events() -> None:
    if _table("trip_calendar_events") and _count("trip_calendar_events") == 0:
        _x()('DROP TABLE "trip_calendar_events"')


def _grant_instructor_create_trips() -> None:
    execute = _x()
    if not all(_table(t) for t in ("roles", "permissions", "role_permissions")):
        return
    role = execute("SELECT id FROM roles WHERE role_name = 'instructor'").fetchone()
    perm = execute("SELECT id FROM permissions WHERE permission_name = 'create_trips'").fetchone()
    if not role or not perm:
        return
    if not execute("SELECT 1 FROM role_permissions WHERE role_id = ? AND permission_id = ?",
                   (role[0], perm[0])).fetchone():
        execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (role[0], perm[0]))


def upgrade() -> None:
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (
        database as schema,
    )
    # Participants first: rebuilding trips parks and restores them.
    _rebuild_status_check('trip_participants', schema.PARTICIPANT_STATUSES,
                          schema.LEGACY_PARTICIPANT_STATUSES)
    _rebuild_status_check('trips', schema.TRIP_STATUSES, schema.LEGACY_TRIP_STATUSES,
                          default_from='planning', default_to='proposed')
    schema.apply(_x())
    _merge_trip_registrations()
    _merge_union_trips()
    _drop_trip_calendar_events()
    _grant_instructor_create_trips()


# Columns this revision added (cancellation_date / cancellation_reason /
# payment_method / payment_reference predate it on live databases).
_PREEXISTING = {'trip_participants': {'payment_method', 'payment_reference',
                                      'cancellation_date', 'cancellation_reason'}}


def downgrade() -> None:
    # Drops what holds nothing: the new tables while empty, then the added
    # columns while every value is NULL or the column default. The wider
    # status CHECKs stay (they accept every older value) and merged rows
    # stay in trips / trip_participants — splitting them back out would
    # recreate the duplicate stores.
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import (
        database as schema,
    )
    execute = _x()
    for ddl in schema.INDEXES_SQL:
        name = ddl.split(" IF NOT EXISTS ")[1].split()[0]
        execute(f'DROP INDEX IF EXISTS "{name}"')
    for table in reversed(schema.NEW_TABLES):
        if _table(table) and _count(table) == 0:
            execute(f'DROP TABLE "{table}"')
    for table, columns in schema.ADDED_COLUMNS.items():
        if not _table(table):
            continue
        present = set(_cols(table))
        for name, decl in columns:
            if name not in present or name in _PREEXISTING.get(table, ()):
                continue
            default = re.search(r"DEFAULT\s+('[^']*'|[-\d.]+)", decl)
            keep_if = f'"{name}" IS NOT NULL'
            if default:
                keep_if += f' AND "{name}" <> {default.group(1)}'
            if execute(f'SELECT 1 FROM "{table}" WHERE {keep_if} LIMIT 1').fetchone():  # nosec B608
                continue
            try:
                execute(f'ALTER TABLE "{table}" DROP COLUMN "{name}"')
            except Exception:
                # Still used by an index, trigger or view: leave it.
                logger.info("Kept %s.%s on downgrade", table, name)
