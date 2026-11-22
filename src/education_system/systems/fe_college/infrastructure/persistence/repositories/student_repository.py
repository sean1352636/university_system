"""Learner persistence: students, enrolments, support plans and targets.

Every method here is parameterised SQL over the connection helper. Repositories
return domain objects, never raw rows, so nothing above this layer has to know
the column names.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from education_system.systems.fe_college.domain.students.enrolment import Enrolment
from education_system.systems.fe_college.domain.students.models import (
    Student,
    ValidationError,
    next_student_id,
)
from education_system.systems.fe_college.domain.students.support import SupportPlan
from education_system.systems.fe_college.domain.students.targets import Target
from education_system.systems.fe_college.infrastructure.persistence import (
    read_only,
    transaction,
)

_STUDENT_COLUMNS = (
    "student_id, first_name, last_name, date_of_birth, uln, email, phone, address, "
    "postcode, learner_type, mode_of_study, status, tutor_group, personal_tutor, "
    "start_date, end_date, prior_attainment, has_ehcp, learning_support, "
    "emergency_contact_name, emergency_contact_phone, notes, middle_name, "
    "preferred_name, gender, address_line2, town, has_lldd, medical_notes, "
    "emergency_contact_relationship"
)


# ── Students ────────────────────────────────────────────────────────────────

def get(student_id: str) -> Student | None:
    with read_only() as conn:
        row = conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
    return Student.from_row(row) if row else None


def list_students(
    *,
    status: str | None = None,
    course_id: str | None = None,
    tutor_group: str | None = None,
    personal_tutor: str | None = None,
    learner_type: str | None = None,
    query: str = "",
    limit: int | None = None,
) -> list[Student]:
    """List learners, optionally filtered.

    ``course_id`` filters to learners with an *active* enrolment on that
    course, which is what every caller means by "students on this course".
    """
    sql = ["SELECT DISTINCT s.* FROM students s"]
    params: list = []
    if course_id:
        sql.append(
            "JOIN enrolments e ON e.student_id = s.student_id "
            "AND e.course_id = ? AND e.status = 'active'"
        )
        params.append(course_id)

    where: list[str] = []
    if status:
        where.append("s.status = ?")
        params.append(status)
    if tutor_group:
        where.append("s.tutor_group = ?")
        params.append(tutor_group)
    if personal_tutor:
        where.append("s.personal_tutor = ?")
        params.append(personal_tutor)
    if learner_type:
        where.append("s.learner_type = ?")
        params.append(learner_type)
    if query:
        where.append(
            "(s.student_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ? "
            "OR s.email LIKE ? OR s.uln LIKE ?)"
        )
        like = f"%{query}%"
        params.extend([like] * 5)
    if where:
        sql.append("WHERE " + " AND ".join(where))
    sql.append("ORDER BY s.last_name, s.first_name")
    if limit:
        sql.append("LIMIT ?")
        params.append(int(limit))

    with read_only() as conn:
        rows = conn.execute(" ".join(sql), params).fetchall()
    return [Student.from_row(r) for r in rows]


def create(student: Student) -> Student:
    """Insert a learner, allocating a student_id when one wasn't supplied."""
    if not student.student_id.strip():
        student.student_id = next_student_id(all_student_ids())
    student.validate()
    row = student.to_row()
    placeholders = ", ".join("?" for _ in row)
    try:
        with transaction() as conn:
            conn.execute(
                f"INSERT INTO students ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
    except sqlite3.IntegrityError as exc:
        raise ValidationError(_integrity_message(exc, student)) from exc
    return student


def find_possible_duplicates(student: Student) -> list[Student]:
    """Learners that look like the same person: same name and date of birth,
    or the same email address. Names and email ignore case."""
    clauses, params = [], []
    if student.date_of_birth:
        clauses.append("(LOWER(TRIM(first_name)) = LOWER(?) AND LOWER(TRIM(last_name)) = LOWER(?) "
                       "AND date_of_birth = ?)")
        params += [student.first_name.strip(), student.last_name.strip(),
                   student.date_of_birth.isoformat()]
    if student.email.strip():
        clauses.append("LOWER(TRIM(email)) = LOWER(?)")
        params.append(student.email.strip())
    if not clauses:
        return []
    sql = f"SELECT {_STUDENT_COLUMNS} FROM students WHERE ({' OR '.join(clauses)})"
    if student.student_id.strip():
        sql += " AND student_id <> ?"
        params.append(student.student_id.strip())
    with read_only() as conn:
        rows = conn.execute(sql + " ORDER BY student_id", params).fetchall()
    return [Student.from_row(r) for r in rows]


def update(student: Student) -> Student:
    student.validate()
    row = student.to_row()
    assignments = ", ".join(f"{col} = ?" for col in row if col != "student_id")
    values = [v for k, v in row.items() if k != "student_id"]
    try:
        with transaction() as conn:
            cur = conn.execute(
                f"UPDATE students SET {assignments}, updated_at = datetime('now') "
                "WHERE student_id = ?",
                [*values, student.student_id],
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No learner with ID {student.student_id}")
    except sqlite3.IntegrityError as exc:
        raise ValidationError(_integrity_message(exc, student)) from exc
    return student


def delete(student_id: str) -> bool:
    """Delete a learner and everything that cascades from them."""
    with transaction() as conn:
        cur = conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        return cur.rowcount > 0


def set_status(student_id: str, status: str, end_date: date | None = None) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE students SET status = ?, end_date = COALESCE(?, end_date), "
            "updated_at = datetime('now') WHERE student_id = ?",
            (status, end_date.isoformat() if end_date else None, student_id),
        )


def all_student_ids() -> list[str]:
    with read_only() as conn:
        return [r[0] for r in conn.execute("SELECT student_id FROM students").fetchall()]


def count_by_status() -> dict[str, int]:
    with read_only() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM students GROUP BY status"
        ).fetchall()
    return {r["status"]: r["n"] for r in rows}


def tutor_groups() -> list[str]:
    with read_only() as conn:
        rows = conn.execute(
            "SELECT DISTINCT tutor_group FROM students "
            "WHERE tutor_group IS NOT NULL AND tutor_group <> '' ORDER BY tutor_group"
        ).fetchall()
    return [r[0] for r in rows]


def _integrity_message(exc: sqlite3.IntegrityError, student: Student) -> str:
    """Turn a constraint violation into something a user can act on."""
    text = str(exc)
    if "students.student_id" in text or "PRIMARY KEY" in text:
        return f"A learner with ID {student.student_id} already exists"
    if "uln" in text:
        return f"ULN {student.uln} is already registered to another learner"
    if "FOREIGN KEY" in text:
        return f"Personal tutor '{student.personal_tutor}' is not a known staff member"
    return f"Could not save learner: {exc}"


# ── Enrolments ──────────────────────────────────────────────────────────────

def list_enrolments(
    *,
    student_id: str | None = None,
    course_id: str | None = None,
    academic_year: str | None = None,
    status: str | None = None,
) -> list[Enrolment]:
    where: list[str] = []
    params: list = []
    for column, value in (
        ("student_id", student_id),
        ("course_id", course_id),
        ("academic_year", academic_year),
        ("status", status),
    ):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    sql = "SELECT * FROM enrolments"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY academic_year DESC, is_main_aim DESC, course_id"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Enrolment.from_row(r) for r in rows]


def get_enrolment(enrolment_id: int) -> Enrolment | None:
    with read_only() as conn:
        row = conn.execute(
            "SELECT * FROM enrolments WHERE enrolment_id = ?", (enrolment_id,)
        ).fetchone()
    return Enrolment.from_row(row) if row else None


def add_enrolment(enrolment: Enrolment) -> Enrolment:
    enrolment.validate()
    row = enrolment.to_row()
    placeholders = ", ".join("?" for _ in row)
    try:
        with transaction() as conn:
            cur = conn.execute(
                f"INSERT INTO enrolments ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
            enrolment.enrolment_id = cur.lastrowid
    except sqlite3.IntegrityError as exc:
        text = str(exc)
        # SQLite names the violated *columns*, not the index, so match on the
        # column list rather than on ``idx_fe_enrolments_unique``.
        if "enrolments.student_id" in text or "enrolments.course_id" in text:
            raise ValidationError(
                f"{enrolment.student_id} is already enrolled on {enrolment.course_id} "
                f"for {enrolment.academic_year}"
            ) from exc
        if "FOREIGN KEY" in text:
            raise ValidationError(
                f"Unknown learner or course ({enrolment.student_id} / {enrolment.course_id})"
            ) from exc
        raise ValidationError(f"Could not enrol: {exc}") from exc
    return enrolment


def update_enrolment(enrolment: Enrolment) -> Enrolment:
    if enrolment.enrolment_id is None:
        raise ValidationError("Cannot update an enrolment without an ID")
    enrolment.validate()
    row = enrolment.to_row()
    assignments = ", ".join(f"{col} = ?" for col in row)
    with transaction() as conn:
        conn.execute(
            f"UPDATE enrolments SET {assignments} WHERE enrolment_id = ?",
            [*row.values(), enrolment.enrolment_id],
        )
    return enrolment


def withdraw_enrolment(enrolment_id: int, reason: str, on: date | None = None) -> None:
    if not reason.strip():
        raise ValidationError("A withdrawal must record a reason")
    with transaction() as conn:
        conn.execute(
            "UPDATE enrolments SET status = 'withdrawn', withdrawal_reason = ?, "
            "end_date = ? WHERE enrolment_id = ?",
            (reason.strip(), (on or date.today()).isoformat(), enrolment_id),
        )


def delete_enrolment(enrolment_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM enrolments WHERE enrolment_id = ?", (enrolment_id,)
        )
        return cur.rowcount > 0


# ── Support plans ───────────────────────────────────────────────────────────

def list_support_plans(student_id: str | None = None,
                       active_only: bool = False) -> list[SupportPlan]:
    sql = "SELECT * FROM support_plans"
    where, params = [], []
    if student_id:
        where.append("student_id = ?")
        params.append(student_id)
    if active_only:
        where.append("status IN ('active', 'under_review')")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY start_date DESC, plan_id DESC"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [SupportPlan.from_row(r) for r in rows]


def add_support_plan(plan: SupportPlan) -> SupportPlan:
    plan.validate()
    row = plan.to_row()
    placeholders = ", ".join("?" for _ in row)
    with transaction() as conn:
        cur = conn.execute(
            f"INSERT INTO support_plans ({', '.join(row)}) VALUES ({placeholders})",
            list(row.values()),
        )
        plan.plan_id = cur.lastrowid
    return plan


def update_support_plan(plan: SupportPlan) -> SupportPlan:
    if plan.plan_id is None:
        raise ValidationError("Cannot update a support plan without an ID")
    plan.validate()
    row = plan.to_row()
    assignments = ", ".join(f"{col} = ?" for col in row)
    with transaction() as conn:
        conn.execute(
            f"UPDATE support_plans SET {assignments} WHERE plan_id = ?",
            [*row.values(), plan.plan_id],
        )
    return plan


# ── Targets ─────────────────────────────────────────────────────────────────

def list_targets(student_id: str | None = None,
                 open_only: bool = False) -> list[Target]:
    sql = "SELECT * FROM targets"
    where, params = [], []
    if student_id:
        where.append("student_id = ?")
        params.append(student_id)
    if open_only:
        where.append("status IN ('set', 'in_progress')")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY due_date IS NULL, due_date, target_id DESC"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Target.from_row(r) for r in rows]


def add_target(target: Target) -> Target:
    target.validate()
    row = target.to_row()
    placeholders = ", ".join("?" for _ in row)
    with transaction() as conn:
        cur = conn.execute(
            f"INSERT INTO targets ({', '.join(row)}) VALUES ({placeholders})",
            list(row.values()),
        )
        target.target_id = cur.lastrowid
    return target


def update_target(target: Target) -> Target:
    if target.target_id is None:
        raise ValidationError("Cannot update a target without an ID")
    target.validate()
    row = target.to_row()
    assignments = ", ".join(f"{col} = ?" for col in row)
    with transaction() as conn:
        conn.execute(
            f"UPDATE targets SET {assignments} WHERE target_id = ?",
            [*row.values(), target.target_id],
        )
    return target


__all__ = [
    "add_enrolment",
    "add_support_plan",
    "add_target",
    "all_student_ids",
    "count_by_status",
    "create",
    "delete",
    "delete_enrolment",
    "get",
    "get_enrolment",
    "list_enrolments",
    "list_students",
    "list_support_plans",
    "list_targets",
    "set_status",
    "tutor_groups",
    "update",
    "update_enrolment",
    "update_support_plan",
    "update_target",
    "withdraw_enrolment",
]
