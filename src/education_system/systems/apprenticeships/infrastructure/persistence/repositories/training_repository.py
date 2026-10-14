"""Training sessions, registers, training plans and off-the-job hours."""

from __future__ import annotations

from typing import Any

from collections.abc import Iterable

from education_system.systems.apprenticeships.domain.training import attendance as attendance_rules
from education_system.systems.apprenticeships.domain.training.attendance import AttendanceSummary
from education_system.systems.apprenticeships.domain.training.off_the_job_hours import OTJEntry
from education_system.systems.apprenticeships.domain.training.sessions import (
    SessionAttendance,
    TrainingPlanItem,
    TrainingSession,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_float,
    to_int,
)

# Selected by every session query. Kept as one string so the column list
# and the mapper below cannot drift apart.
_SESSION_SELECT = """
    SELECT s.*,
           p.title       AS programme_title,
           t.full_name   AS trainer_name,
           (SELECT COUNT(*) FROM session_attendance sa
             WHERE sa.session_id = s.session_id)
                         AS attendee_count
      FROM training_sessions s
      LEFT JOIN programmes p ON p.programme_id = s.programme_id
      LEFT JOIN staff      t ON t.staff_id     = s.trainer_id
"""

_ATTENDANCE_SELECT = """
    SELECT sa.*,
           a.given_name || ' ' || a.family_name AS apprentice_name
      FROM session_attendance sa
      JOIN apprentices a ON a.apprentice_id = sa.apprentice_id
"""

# The apprentice join is unconditional: the foreign key is NOT NULL and
# cascades, so it can never drop a row, and one SQL shape beats two.
_ENTRY_SELECT = """
    SELECT o.*
      FROM otj_entries o
      JOIN apprentices a ON a.apprentice_id = o.apprentice_id
"""

_SESSION_FIELDS = (
    "programme_id", "title", "session_date", "start_time", "end_time",
    "delivery_mode", "location", "trainer_id", "capacity", "otj_hours",
    "ksb_codes", "notes", "status",
)

_PLAN_FIELDS = (
    "apprentice_id", "title", "description", "planned_start", "planned_end",
    "planned_hours", "ksb_codes", "delivery_mode", "status", "objective_id",
)

_ENTRY_FIELDS = (
    "apprentice_id", "activity_date", "hours", "activity_type", "description",
    "ksb_codes", "status", "session_id", "submitted_at", "approved_by",
    "approved_at", "decision_note",
)


def _map_session(row: Any) -> TrainingSession:
    return TrainingSession(
        session_id=row["session_id"],
        title=row["title"],
        session_date=row["session_date"],
        programme_id=col(row, "programme_id"),
        start_time=col(row, "start_time"),
        end_time=col(row, "end_time"),
        delivery_mode=col(row, "delivery_mode", "Classroom"),
        location=col(row, "location"),
        trainer_id=col(row, "trainer_id"),
        capacity=col(row, "capacity"),
        otj_hours=to_float(col(row, "otj_hours")),
        ksb_codes=col(row, "ksb_codes"),
        notes=col(row, "notes"),
        status=col(row, "status", "Scheduled"),
        created_at=col(row, "created_at", ""),
        programme_title=col(row, "programme_title"),
        trainer_name=col(row, "trainer_name"),
        attendee_count=to_int(col(row, "attendee_count")),
    )


def _map_attendance(row: Any) -> SessionAttendance:
    return SessionAttendance(
        attendance_id=row["attendance_id"],
        session_id=row["session_id"],
        apprentice_id=row["apprentice_id"],
        status=col(row, "status", "Present"),
        otj_hours=to_float(col(row, "otj_hours")),
        notes=col(row, "notes"),
        absence_reason=col(row, "absence_reason"),
        recorded_at=col(row, "recorded_at", ""),
        apprentice_name=col(row, "apprentice_name", ""),
    )


def _map_plan_item(row: Any) -> TrainingPlanItem:
    return TrainingPlanItem(
        item_id=row["item_id"],
        apprentice_id=row["apprentice_id"],
        title=row["title"],
        description=col(row, "description"),
        planned_start=col(row, "planned_start"),
        planned_end=col(row, "planned_end"),
        planned_hours=to_float(col(row, "planned_hours")),
        ksb_codes=col(row, "ksb_codes"),
        delivery_mode=col(row, "delivery_mode"),
        status=col(row, "status", "Planned"),
        objective_id=col(row, "objective_id"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def _map_entry(row: Any) -> OTJEntry:
    return OTJEntry(
        entry_id=row["entry_id"],
        apprentice_id=row["apprentice_id"],
        activity_date=row["activity_date"],
        hours=to_float(col(row, "hours")),
        activity_type=col(row, "activity_type", ""),
        description=col(row, "description", ""),
        ksb_codes=col(row, "ksb_codes"),
        status=col(row, "status", "Draft"),
        session_id=col(row, "session_id"),
        submitted_at=col(row, "submitted_at"),
        approved_by=col(row, "approved_by"),
        approved_at=col(row, "approved_at"),
        decision_note=col(row, "decision_note"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


# ── Sessions ────────────────────────────────────────────────────────

def get_session(session_id: int) -> TrainingSession | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"{_SESSION_SELECT} WHERE s.session_id = ?", (session_id,)
        ).fetchone()
    return _map_session(row) if row else None


def list_sessions(
    *,
    programme_id: int | None = None,
    trainer_id: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    upcoming_only: bool = False,
) -> list[TrainingSession]:
    """Timetable list with the labels and headcount the screens need."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(programme_id, "s.programme_id = ?", programme_id)
    qb.add_if(trainer_id, "s.trainer_id = ?", trainer_id)
    qb.add_if(status, "s.status = ?", status)
    qb.add_if(date_from, "s.session_date >= ?", date_from)
    qb.add_if(date_to, "s.session_date <= ?", date_to)
    if upcoming_only:
        qb.add("s.session_date >= date('now')")
        qb.add("s.status <> 'Cancelled'")
    # Upcoming reads forwards — the next session first; every other view
    # is a history, which reads backwards.
    direction = "ASC" if upcoming_only else "DESC"
    sql = (
        f"{_SESSION_SELECT} {qb.where} "
        f"ORDER BY s.session_date {direction}, s.start_time {direction}"
    )
    with connect() as conn:
        rows = conn.execute(sql, qb.args).fetchall()
    return [_map_session(r) for r in rows]


def create_session(payload: dict[str, Any]) -> int:
    """Insert a session and return the new id."""
    init_db()
    columns = [f for f in _SESSION_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO training_sessions ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def update_session(session_id: int, payload: dict[str, Any]) -> None:
    """Update the supplied fields only; anything absent is untouched."""
    init_db()
    columns = [f for f in _SESSION_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        conn.execute(
            f"UPDATE training_sessions SET {assignments} WHERE session_id = ?",
            [*values, session_id],
        )


def delete_session(session_id: int) -> None:
    """Remove a session and its register.

    The off-the-job entries the register generated survive: the hours
    were genuinely trained, and the entry's ``session_id`` is nulled by
    the foreign key rather than cascaded away.
    """
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM training_sessions WHERE session_id = ?", (session_id,))


# ── Attendance ──────────────────────────────────────────────────────

def list_attendance(session_id: int) -> list[SessionAttendance]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            f"{_ATTENDANCE_SELECT} WHERE sa.session_id = ? "
            "ORDER BY a.family_name, a.given_name",
            (session_id,),
        ).fetchall()
    return [_map_attendance(r) for r in rows]


def get_attendance(session_id: int, apprentice_id: int) -> SessionAttendance | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"{_ATTENDANCE_SELECT} WHERE sa.session_id = ? AND sa.apprentice_id = ?",
            (session_id, apprentice_id),
        ).fetchone()
    return _map_attendance(row) if row else None


def upsert_attendance(
    session_id: int,
    apprentice_id: int,
    *,
    status: str,
    otj_hours: float,
    notes: str | None = None,
    absence_reason: str | None = None,
) -> int:
    """Mark the register for one apprentice, replacing any earlier mark.

    A register gets re-marked routinely — someone turns up late, or the
    tutor corrects a mistake — so this leans on the ``(session_id,
    apprentice_id)`` unique constraint rather than making callers check
    first and race each other.
    """
    init_db()
    with connect() as conn:
        conn.execute(
            """INSERT INTO session_attendance
                   (session_id, apprentice_id, status, otj_hours, notes, absence_reason)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id, apprentice_id) DO UPDATE SET
                   status         = excluded.status,
                   otj_hours      = excluded.otj_hours,
                   notes          = excluded.notes,
                   absence_reason = excluded.absence_reason,
                   recorded_at    = datetime('now')""",
            (session_id, apprentice_id, status, otj_hours, notes, absence_reason),
        )
        # lastrowid is only meaningful when the INSERT branch ran, so the
        # id is read back rather than assumed.
        row = conn.execute(
            "SELECT attendance_id FROM session_attendance "
            "WHERE session_id = ? AND apprentice_id = ?",
            (session_id, apprentice_id),
        ).fetchone()
    return int(row["attendance_id"])


def delete_attendance(attendance_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            "DELETE FROM session_attendance WHERE attendance_id = ?", (attendance_id,)
        )


def list_attendance_for_apprentice(apprentice_id: int) -> list[SessionAttendance]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            f"""{_ATTENDANCE_SELECT}
                  JOIN training_sessions ts ON ts.session_id = sa.session_id
                 WHERE sa.apprentice_id = ?
                 ORDER BY ts.session_date DESC, sa.attendance_id DESC""",
            (apprentice_id,),
        ).fetchall()
    return [_map_attendance(r) for r in rows]


def attendance_by_apprentice(
    apprentice_ids: Iterable[int],
) -> dict[int, list[SessionAttendance]]:
    """Every mark for each apprentice, newest first — one query for a cohort.

    An apprentice with no marks still gets an empty list, so a caller can
    tell "never marked" from "not asked about".
    """
    ids = sorted(set(apprentice_ids))
    if not ids:
        return {}
    init_db()
    qb = QueryBuilder()
    qb.add_in("sa.apprentice_id", ids)
    with connect() as conn:
        rows = conn.execute(
            f"""{_ATTENDANCE_SELECT}
                  JOIN training_sessions ts ON ts.session_id = sa.session_id
                  {qb.where}
                 ORDER BY ts.session_date DESC, sa.attendance_id DESC""",
            qb.args,
        ).fetchall()
    grouped: dict[int, list[SessionAttendance]] = {i: [] for i in ids}
    for row in rows:
        grouped[row["apprentice_id"]].append(_map_attendance(row))
    return grouped


def attendance_summary(apprentice_id: int) -> AttendanceSummary:
    """Counts per mark plus the marks themselves."""
    return attendance_rules.summarise(
        apprentice_id, list_attendance_for_apprentice(apprentice_id)
    )


# ── Training plan ───────────────────────────────────────────────────

def list_plan_items(apprentice_id: int, *, status: str | None = None) -> list[TrainingPlanItem]:
    init_db()
    qb = QueryBuilder()
    qb.add("apprentice_id = ?", apprentice_id)
    qb.add_if(status, "status = ?", status)
    with connect() as conn:
        rows = conn.execute(
            # Undated items sort to the end rather than the top, which is
            # where NULLs would otherwise land in an ascending SQLite sort.
            f"""SELECT * FROM training_plan_items {qb.where}
                 ORDER BY COALESCE(planned_start, '9999-12-31'), item_id""",
            qb.args,
        ).fetchall()
    return [_map_plan_item(r) for r in rows]


def get_plan_item(item_id: int) -> TrainingPlanItem | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM training_plan_items WHERE item_id = ?", (item_id,)
        ).fetchone()
    return _map_plan_item(row) if row else None


def create_plan_item(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _PLAN_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO training_plan_items ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def update_plan_item(item_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _PLAN_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        conn.execute(
            f"UPDATE training_plan_items SET {assignments}, updated_at = datetime('now') "
            "WHERE item_id = ?",
            [*values, item_id],
        )


def delete_plan_item(item_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM training_plan_items WHERE item_id = ?", (item_id,))


# ── Off-the-job entries ─────────────────────────────────────────────

def get_entry(entry_id: int) -> OTJEntry | None:
    init_db()
    with connect() as conn:
        row = conn.execute(f"{_ENTRY_SELECT} WHERE o.entry_id = ?", (entry_id,)).fetchone()
    return _map_entry(row) if row else None


def list_entries(
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    employer_id: int | None = None,
    tutor_id: int | None = None,
    limit: int | None = None,
) -> list[OTJEntry]:
    """Logged hours, filtered as the log, employer queue and tutor queue need.

    ``employer_id`` and ``tutor_id`` scope through the apprentice rather
    than the entry: an approver's queue is defined by whose hours they
    are, and an apprentice moving employer moves their whole log with
    them.
    """
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "o.apprentice_id = ?", apprentice_id)
    qb.add_if(status, "o.status = ?", status)
    qb.add_in("o.status", statuses)
    qb.add_if(date_from, "o.activity_date >= ?", date_from)
    qb.add_if(date_to, "o.activity_date <= ?", date_to)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    sql = f"{_ENTRY_SELECT} {qb.where} ORDER BY o.activity_date DESC, o.entry_id DESC"
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_map_entry(r) for r in rows]


def get_entry_by_session(session_id: int, apprentice_id: int) -> OTJEntry | None:
    """The entry a register mark generated, if it did.

    Lets a corrected register update the hours it already logged instead
    of adding a second entry for the same session.
    """
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"{_ENTRY_SELECT} WHERE o.session_id = ? AND o.apprentice_id = ?",
            (session_id, apprentice_id),
        ).fetchone()
    return _map_entry(row) if row else None


def create_entry(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _ENTRY_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO otj_entries ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def update_entry(entry_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _ENTRY_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        conn.execute(
            f"UPDATE otj_entries SET {assignments}, updated_at = datetime('now') "
            "WHERE entry_id = ?",
            [*values, entry_id],
        )


def delete_entry(entry_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM otj_entries WHERE entry_id = ?", (entry_id,))


def set_entry_status(
    entry_id: int,
    status: str,
    *,
    approved_by: str | None = None,
    approved_at: str | None = None,
    decision_note: str | None = None,
    submitted_at: str | None = None,
) -> None:
    """Move an entry's status, writing only the stamps supplied.

    Omitted stamps keep their existing value, so re-approving an entry
    that was rejected does not wipe the date it was first submitted.
    """
    init_db()
    assignments = ["status = ?"]
    values: list[Any] = [status]
    for column, value in (
        ("submitted_at", submitted_at),
        ("approved_by", approved_by),
        ("approved_at", approved_at),
        ("decision_note", decision_note),
    ):
        if value is not None:
            assignments.append(f"{column} = ?")
            values.append(value)
    with connect() as conn:
        conn.execute(
            f"UPDATE otj_entries SET {', '.join(assignments)}, "
            "updated_at = datetime('now') WHERE entry_id = ?",
            [*values, entry_id],
        )


def hour_totals(apprentice_id: int) -> dict[str, float]:
    """Approved, pending and draft hours plus the entry count, in one pass.

    The OTJ summary needs all four together on every dashboard row, and
    ``off_the_job_hours.build_summary`` takes them as arguments precisely
    so the aggregation can happen here in SQL.
    """
    init_db()
    with connect() as conn:
        row = conn.execute(
            """SELECT
                   COALESCE(SUM(CASE WHEN status = 'Approved'  THEN hours END), 0) AS approved,
                   COALESCE(SUM(CASE WHEN status = 'Submitted' THEN hours END), 0) AS pending,
                   COALESCE(SUM(CASE WHEN status = 'Draft'     THEN hours END), 0) AS draft,
                   COUNT(*) AS n
                 FROM otj_entries
                WHERE apprentice_id = ?""",
            (apprentice_id,),
        ).fetchone()
    return {
        "approved": to_float(col(row, "approved")),
        "pending": to_float(col(row, "pending")),
        "draft": to_float(col(row, "draft")),
        "count": to_int(col(row, "n")),
    }


def pending_count(*, employer_id: int | None = None, tutor_id: int | None = None) -> int:
    """How many entries are waiting on an approver, for the queue badges."""
    init_db()
    qb = QueryBuilder()
    qb.add("o.status = 'Submitted'")
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    with connect() as conn:
        row = conn.execute(
            f"""SELECT COUNT(*) AS n
                  FROM otj_entries o
                  JOIN apprentices a ON a.apprentice_id = o.apprentice_id
                  {qb.where}""",
            qb.args,
        ).fetchone()
    return to_int(col(row, "n"))
