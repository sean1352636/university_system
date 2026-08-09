"""Staff persistence: records, availability and derived workload."""

from __future__ import annotations

import sqlite3

from education_system.systems.fe_college.config import FULL_TIME_TEACHING_HOURS
from education_system.systems.fe_college.domain.staff.availability import Availability
from education_system.systems.fe_college.domain.staff.models import (
    Staff,
    next_staff_id,
)
from education_system.systems.fe_college.domain.staff.workload import Workload
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.infrastructure.persistence import (
    read_only,
    transaction,
)


# ── Staff records ───────────────────────────────────────────────────────────

def get(staff_id: str) -> Staff | None:
    with read_only() as conn:
        row = conn.execute("SELECT * FROM staff WHERE staff_id = ?", (staff_id,)).fetchone()
    return Staff.from_row(row) if row else None


def get_by_email(email: str) -> Staff | None:
    """Look a member of staff up by email — how a login is matched to a record."""
    with read_only() as conn:
        row = conn.execute(
            "SELECT * FROM staff WHERE lower(email) = lower(?)", (email.strip(),)
        ).fetchone()
    return Staff.from_row(row) if row else None


def list_staff(
    *,
    role: str | None = None,
    department: str | None = None,
    employment_status: str | None = None,
    active_only: bool = False,
    teaching_only: bool = False,
    query: str = "",
) -> list[Staff]:
    where: list[str] = []
    params: list = []
    if role:
        where.append("role = ?")
        params.append(role)
    if department:
        where.append("department = ?")
        params.append(department)
    if employment_status:
        where.append("employment_status = ?")
        params.append(employment_status)
    if active_only:
        where.append("employment_status <> 'Left'")
    if query:
        where.append(
            "(staff_id LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)"
        )
        like = f"%{query}%"
        params.extend([like] * 4)
    sql = "SELECT * FROM staff"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY last_name, first_name"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    staff = [Staff.from_row(r) for r in rows]
    # Teaching eligibility is a domain rule (role + employment status), so it
    # is applied through the model rather than duplicated as SQL.
    return [s for s in staff if s.can_teach] if teaching_only else staff


def create(member: Staff) -> Staff:
    if not member.staff_id.strip():
        member.staff_id = next_staff_id(all_staff_ids())
    member.validate()
    row = member.to_row()
    placeholders = ", ".join("?" for _ in row)
    try:
        with transaction() as conn:
            conn.execute(
                f"INSERT INTO staff ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
    except sqlite3.IntegrityError as exc:
        raise ValidationError(_integrity_message(exc, member)) from exc
    return member


def update(member: Staff) -> Staff:
    member.validate()
    row = member.to_row()
    assignments = ", ".join(f"{col} = ?" for col in row if col != "staff_id")
    values = [v for k, v in row.items() if k != "staff_id"]
    try:
        with transaction() as conn:
            cur = conn.execute(
                f"UPDATE staff SET {assignments}, updated_at = datetime('now') "
                "WHERE staff_id = ?",
                [*values, member.staff_id],
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No staff member with ID {member.staff_id}")
    except sqlite3.IntegrityError as exc:
        raise ValidationError(_integrity_message(exc, member)) from exc
    return member


def delete(staff_id: str) -> bool:
    """Delete a staff record.

    Courses, groups and sessions referencing them are set to NULL rather than
    deleted — a lecturer leaving must not take their timetable with them.
    """
    with transaction() as conn:
        cur = conn.execute("DELETE FROM staff WHERE staff_id = ?", (staff_id,))
        return cur.rowcount > 0


def all_staff_ids() -> list[str]:
    with read_only() as conn:
        return [r[0] for r in conn.execute("SELECT staff_id FROM staff").fetchall()]


def departments() -> list[str]:
    with read_only() as conn:
        rows = conn.execute(
            "SELECT DISTINCT department FROM staff "
            "WHERE department IS NOT NULL AND department <> '' ORDER BY department"
        ).fetchall()
    return [r[0] for r in rows]


def count_by_role() -> dict[str, int]:
    with read_only() as conn:
        rows = conn.execute(
            "SELECT role, COUNT(*) AS n FROM staff "
            "WHERE employment_status <> 'Left' GROUP BY role"
        ).fetchall()
    return {r["role"]: r["n"] for r in rows}


def _integrity_message(exc: sqlite3.IntegrityError, member: Staff) -> str:
    text = str(exc)
    if "staff.staff_id" in text or "PRIMARY KEY" in text:
        return f"A staff member with ID {member.staff_id} already exists"
    if "email" in text:
        return f"{member.email} is already used by another staff member"
    return f"Could not save staff member: {exc}"


# ── Availability ────────────────────────────────────────────────────────────

def get_availability(staff_id: str) -> Availability:
    with read_only() as conn:
        rows = conn.execute(
            "SELECT * FROM staff_unavailability WHERE staff_id = ?", (staff_id,)
        ).fetchall()
    return Availability.from_rows(staff_id, rows)


def save_availability(availability: Availability) -> None:
    """Replace a member of staff's blocked slots wholesale.

    Delete-then-insert inside one transaction: the GUI edits availability as a
    grid and sends back the whole picture, so a diff would be more code for the
    same result.
    """
    availability.validate()
    rows = availability.to_rows()
    with transaction() as conn:
        conn.execute(
            "DELETE FROM staff_unavailability WHERE staff_id = ?",
            (availability.staff_id,),
        )
        if rows:
            conn.executemany(
                "INSERT INTO staff_unavailability (staff_id, day, period, reason) "
                "VALUES (?, ?, ?, ?)",
                [(r["staff_id"], r["day"], r["period"], r["reason"]) for r in rows],
            )


# ── Workload ────────────────────────────────────────────────────────────────

def workloads(department: str | None = None) -> list[Workload]:
    """Assigned teaching hours per member of staff, from the timetable.

    One session is one hour, so the session count *is* the weekly hour count.
    Counted with a LEFT JOIN so staff with no timetable still appear — an
    unassigned lecturer is exactly who a curriculum manager is looking for.
    """
    sql = """
        SELECT s.staff_id,
               s.first_name || ' ' || s.last_name AS staff_name,
               s.contracted_hours,
               COUNT(t.session_id)                AS class_count,
               COUNT(DISTINCT t.course_id)        AS course_count
        FROM staff s
        LEFT JOIN sessions t ON t.teacher_id = s.staff_id
        WHERE s.employment_status <> 'Left'
    """
    params: list = []
    if department:
        sql += " AND s.department = ?"
        params.append(department)
    sql += " GROUP BY s.staff_id ORDER BY s.last_name, s.first_name"

    from education_system.systems.fe_college.domain.teaching.timetable import PERIOD_HOURS

    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        Workload(
            staff_id=r["staff_id"],
            staff_name=r["staff_name"],
            # An explicit 0 is meaningful — a sessional tutor holds no
            # contracted hours — so only a NULL falls back to the default.
            contracted_hours=float(
                r["contracted_hours"]
                if r["contracted_hours"] is not None
                else FULL_TIME_TEACHING_HOURS
            ),
            assigned_hours=round(r["class_count"] * PERIOD_HOURS, 2),
            class_count=r["class_count"],
            course_count=r["course_count"],
        )
        for r in rows
    ]


__all__ = [
    "all_staff_ids",
    "count_by_role",
    "create",
    "delete",
    "departments",
    "get",
    "get_availability",
    "get_by_email",
    "list_staff",
    "save_availability",
    "update",
    "workloads",
]
