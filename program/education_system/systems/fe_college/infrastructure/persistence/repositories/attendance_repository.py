"""Attendance persistence — register marks and the aggregates over them.

Aggregation is done in SQL (``GROUP BY mark``) rather than by pulling every
mark into Python: a year of marks for a full college is hundreds of thousands
of rows, and the dashboards only ever want the counts.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.fe_college.config import ATTENDANCE_MARKS
from education_system.systems.fe_college.domain.students.attendance import (
    AttendanceRecord,
    AttendanceSummary,
    summary_from_counts,
)
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.infrastructure.persistence import (
    read_only,
    transaction,
)


# ── Marks ───────────────────────────────────────────────────────────────────

def list_marks(
    *,
    student_id: str | None = None,
    course_id: str | None = None,
    session_date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    period: str | None = None,
    limit: int | None = None,
) -> list[AttendanceRecord]:
    where: list[str] = []
    params: list = []
    if student_id:
        where.append("student_id = ?")
        params.append(student_id)
    if course_id:
        where.append("course_id = ?")
        params.append(course_id)
    if session_date:
        where.append("session_date = ?")
        params.append(session_date.isoformat())
    if date_from:
        where.append("session_date >= ?")
        params.append(date_from.isoformat())
    if date_to:
        where.append("session_date <= ?")
        params.append(date_to.isoformat())
    if period:
        where.append("period = ?")
        params.append(period)

    sql = "SELECT * FROM attendance"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY session_date DESC, period, student_id"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [AttendanceRecord.from_row(r) for r in rows]


def save_mark(record: AttendanceRecord) -> AttendanceRecord:
    """Insert or overwrite one mark.

    UPSERT on the (student, course, date, period) key so re-submitting a
    register corrects it rather than duplicating it.
    """
    record.validate()
    row = record.to_row()
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    updates = ", ".join(
        f"{c} = excluded.{c}"
        for c in row
        if c not in ("student_id", "course_id", "session_date", "period")
    )
    with transaction() as conn:
        conn.execute(
            f"INSERT INTO attendance ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(student_id, course_id, session_date, period) "
            f"DO UPDATE SET {updates}",
            list(row.values()),
        )
    return record


def save_register(records: list[AttendanceRecord]) -> int:
    """Save a whole register in one transaction.

    All-or-nothing: if one mark is invalid the register is rejected, so a
    lecturer never ends up with half a register saved and no indication which
    half. Returns the number of marks written.
    """
    if not records:
        return 0
    for r in records:
        r.validate()

    rows = [r.to_row() for r in records]
    columns = ", ".join(rows[0])
    placeholders = ", ".join("?" for _ in rows[0])
    updates = ", ".join(
        f"{c} = excluded.{c}"
        for c in rows[0]
        if c not in ("student_id", "course_id", "session_date", "period")
    )
    with transaction() as conn:
        conn.executemany(
            f"INSERT INTO attendance ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(student_id, course_id, session_date, period) "
            f"DO UPDATE SET {updates}",
            [list(r.values()) for r in rows],
        )
    return len(rows)


def delete_mark(record_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute("DELETE FROM attendance WHERE record_id = ?", (record_id,))
        return cur.rowcount > 0


def register_dates(course_id: str, limit: int = 30) -> list[str]:
    """Dates a register has been taken for a course, most recent first."""
    with read_only() as conn:
        rows = conn.execute(
            "SELECT DISTINCT session_date FROM attendance WHERE course_id = ? "
            "ORDER BY session_date DESC LIMIT ?",
            (course_id, int(limit)),
        ).fetchall()
    return [r[0] for r in rows]


def has_register(course_id: str, session_date: date, period: str = "") -> bool:
    with read_only() as conn:
        row = conn.execute(
            "SELECT 1 FROM attendance WHERE course_id = ? AND session_date = ? "
            "AND period = ? LIMIT 1",
            (course_id, session_date.isoformat(), period),
        ).fetchone()
    return row is not None


# ── Aggregates ──────────────────────────────────────────────────────────────

def _counts(where: list[str], params: list) -> dict[str, int]:
    sql = "SELECT mark, COUNT(*) AS n FROM attendance"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY mark"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {r["mark"]: r["n"] for r in rows}


def summary_for_student(student_id: str, *, course_id: str | None = None,
                        date_from: date | None = None) -> AttendanceSummary:
    where, params = ["student_id = ?"], [student_id]
    if course_id:
        where.append("course_id = ?")
        params.append(course_id)
    if date_from:
        where.append("session_date >= ?")
        params.append(date_from.isoformat())
    return summary_from_counts(_counts(where, params))


def summary_for_course(course_id: str, *, date_from: date | None = None) -> AttendanceSummary:
    where, params = ["course_id = ?"], [course_id]
    if date_from:
        where.append("session_date >= ?")
        params.append(date_from.isoformat())
    return summary_from_counts(_counts(where, params))


def college_summary(date_from: date | None = None) -> AttendanceSummary:
    where, params = [], []
    if date_from:
        where.append("session_date >= ?")
        params.append(date_from.isoformat())
    return summary_from_counts(_counts(where, params))


def summaries_by_student(
    *,
    course_id: str | None = None,
    date_from: date | None = None,
) -> dict[str, AttendanceSummary]:
    """Per-learner summaries in one query — for the at-risk report."""
    sql = "SELECT student_id, mark, COUNT(*) AS n FROM attendance"
    where, params = [], []
    if course_id:
        where.append("course_id = ?")
        params.append(course_id)
    if date_from:
        where.append("session_date >= ?")
        params.append(date_from.isoformat())
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY student_id, mark"

    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()

    per_student: dict[str, dict[str, int]] = {}
    for r in rows:
        per_student.setdefault(r["student_id"], dict.fromkeys(ATTENDANCE_MARKS, 0))
        per_student[r["student_id"]][r["mark"]] = r["n"]
    return {sid: summary_from_counts(counts) for sid, counts in per_student.items()}


def summaries_by_course(date_from: date | None = None) -> dict[str, AttendanceSummary]:
    """Per-course summaries in one query — for the admin dashboard."""
    sql = "SELECT course_id, mark, COUNT(*) AS n FROM attendance"
    params: list = []
    if date_from:
        sql += " WHERE session_date >= ?"
        params.append(date_from.isoformat())
    sql += " GROUP BY course_id, mark"

    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()

    per_course: dict[str, dict[str, int]] = {}
    for r in rows:
        per_course.setdefault(r["course_id"], dict.fromkeys(ATTENDANCE_MARKS, 0))
        per_course[r["course_id"]][r["mark"]] = r["n"]
    return {cid: summary_from_counts(counts) for cid, counts in per_course.items()}


def recent_absences(days: int = 7, unauthorised_only: bool = True) -> list[AttendanceRecord]:
    """Absences in the last ``days`` — the pastoral team's daily list."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    marks = ("unauthorised",) if unauthorised_only else ("unauthorised", "authorised")
    placeholders = ", ".join("?" for _ in marks)
    with read_only() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance WHERE session_date >= ? "
            f"AND mark IN ({placeholders}) ORDER BY session_date DESC",
            (cutoff, *marks),
        ).fetchall()
    return [AttendanceRecord.from_row(r) for r in rows]


__all__ = [
    "college_summary",
    "delete_mark",
    "has_register",
    "list_marks",
    "recent_absences",
    "register_dates",
    "save_mark",
    "save_register",
    "summaries_by_course",
    "summaries_by_student",
    "summary_for_course",
    "summary_for_student",
]
