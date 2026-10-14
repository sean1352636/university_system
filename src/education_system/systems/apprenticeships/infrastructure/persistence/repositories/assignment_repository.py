"""Assignments, the submissions made against them, and their moderations."""

from __future__ import annotations

import sqlite3
from typing import Any

from education_system.systems.apprenticeships.domain.progress.assignments import (
    Assignment,
    AssignmentModeration,
    AssignmentSubmission,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_bool,
    to_int,
)

_FIELDS = (
    "apprentice_id", "title", "brief", "assignment_type", "ksb_codes", "set_by",
    "due_date", "status", "attempt", "max_attempts", "grade", "feedback",
    "marked_by", "marked_at",
)

# The apprentice join carries the scope columns (employer, tutor) the
# service filters on, and the name every list shows. The moderation
# subquery answers "has the current attempt been second-marked?" without
# loading the children, which is what the moderation queue asks.
_SELECT = """
    SELECT x.*,
           (a.given_name || ' ' || a.family_name) AS apprentice_name,
           a.employer_id AS employer_id,
           a.tutor_id    AS tutor_id,
           EXISTS (SELECT 1 FROM assignment_moderations m
                    WHERE m.assignment_id = x.assignment_id
                      AND m.attempt = x.attempt) AS current_moderated
      FROM assignments x
      JOIN apprentices a ON a.apprentice_id = x.apprentice_id
"""

_WITH_APPRENTICE = ("Set", "Referred")


def _map(row: Any) -> Assignment:
    return Assignment(
        assignment_id=row["assignment_id"],
        apprentice_id=row["apprentice_id"],
        title=row["title"],
        assignment_type=col(row, "assignment_type", ""),
        brief=col(row, "brief"),
        ksb_codes=col(row, "ksb_codes"),
        set_by=col(row, "set_by"),
        set_at=col(row, "set_at", ""),
        due_date=col(row, "due_date"),
        status=col(row, "status", "Set"),
        attempt=to_int(col(row, "attempt"), 1),
        max_attempts=to_int(col(row, "max_attempts"), 1),
        grade=col(row, "grade"),
        feedback=col(row, "feedback"),
        marked_by=col(row, "marked_by"),
        marked_at=col(row, "marked_at"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
        apprentice_name=col(row, "apprentice_name", "") or "",
        employer_id=col(row, "employer_id"),
        tutor_id=col(row, "tutor_id"),
        current_moderated=to_bool(col(row, "current_moderated")),
    )


def _map_submission(row: Any) -> AssignmentSubmission:
    return AssignmentSubmission(
        submission_id=row["submission_id"],
        assignment_id=row["assignment_id"],
        attempt=to_int(row["attempt"], 1),
        submitted_by=row["submitted_by"],
        body=col(row, "body"),
        evidence_id=col(row, "evidence_id"),
        submitted_at=col(row, "submitted_at", ""),
        is_late=to_bool(col(row, "is_late")),
        grade=col(row, "grade"),
        feedback=col(row, "feedback"),
        marked_by=col(row, "marked_by"),
        marked_at=col(row, "marked_at"),
        evidence_title=col(row, "evidence_title"),
    )


def _map_moderation(row: Any) -> AssignmentModeration:
    return AssignmentModeration(
        moderation_id=row["moderation_id"],
        assignment_id=row["assignment_id"],
        attempt=to_int(row["attempt"], 1),
        moderator=row["moderator"],
        outcome=row["outcome"],
        original_grade=col(row, "original_grade"),
        adjusted_grade=col(row, "adjusted_grade"),
        notes=col(row, "notes"),
        moderated_at=col(row, "moderated_at", ""),
    )


def _attach_children(conn: sqlite3.Connection, items: list[Assignment]) -> None:
    """Submissions and moderations for a whole page, in one query each."""
    if not items:
        return
    ids = [i.assignment_id for i in items]
    placeholders = ", ".join("?" for _ in ids)
    by_id = {i.assignment_id: i for i in items}
    for row in conn.execute(
        f"""SELECT s.*, e.title AS evidence_title
              FROM assignment_submissions s
              LEFT JOIN portfolio_evidence e ON e.evidence_id = s.evidence_id
             WHERE s.assignment_id IN ({placeholders})
             ORDER BY s.attempt""",
        ids,
    ).fetchall():
        by_id[row["assignment_id"]].submissions.append(_map_submission(row))
    for row in conn.execute(
        f"""SELECT * FROM assignment_moderations
             WHERE assignment_id IN ({placeholders}) ORDER BY attempt""",
        ids,
    ).fetchall():
        by_id[row["assignment_id"]].moderations.append(_map_moderation(row))


# ── Reads ───────────────────────────────────────────────────────────

def get(assignment_id: int, *, with_children: bool = True) -> Assignment | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"{_SELECT} WHERE x.assignment_id = ?", (assignment_id,)
        ).fetchone()
        if row is None:
            return None
        item = _map(row)
        if with_children:
            _attach_children(conn, [item])
    return item


def _filters(
    *,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    tutor_id: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    assignment_type: str | None = None,
    set_by: str | None = None,
    marked_by: str | None = None,
    not_marked_by: str | None = None,
    awaiting_moderation: bool = False,
    open_only: bool = False,
    overdue_on: str | None = None,
    due_from: str | None = None,
    due_before: str | None = None,
) -> QueryBuilder:
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "x.apprentice_id = ?", apprentice_id)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(status, "x.status = ?", status)
    qb.add_in("x.status", statuses)
    qb.add_if(assignment_type, "x.assignment_type = ?", assignment_type)
    qb.add_if(set_by, "LOWER(x.set_by) = LOWER(?)", set_by)
    qb.add_if(marked_by, "LOWER(x.marked_by) = LOWER(?)", marked_by)
    qb.add_if(
        not_marked_by, "LOWER(COALESCE(x.marked_by, '')) != LOWER(?)", not_marked_by
    )
    if awaiting_moderation:
        qb.add(
            "x.status IN ('Marked', 'Referred') AND x.marked_by IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM assignment_moderations m "
            "WHERE m.assignment_id = x.assignment_id AND m.attempt = x.attempt)"
        )
    if open_only:
        qb.add_in("x.status", list(_WITH_APPRENTICE))
    # Overdue is judged against a date the caller passes (the local date
    # the domain uses), not SQLite's UTC date('now').
    if overdue_on:
        qb.add_in("x.status", list(_WITH_APPRENTICE))
        qb.add("x.due_date IS NOT NULL AND x.due_date < ?", overdue_on)
    qb.add_if(due_from, "x.due_date >= ?", due_from)
    qb.add_if(due_before, "x.due_date <= ?", due_before)
    return qb


def list_assignments(
    *,
    with_children: bool = False,
    limit: int | None = None,
    **filters: Any,
) -> list[Assignment]:
    """Assignments matching the filters, soonest due first.

    Filters: ``apprentice_id`` / ``employer_id`` / ``tutor_id`` (the scope
    ``access.apprentice_filters()`` yields), ``status`` / ``statuses``,
    ``assignment_type``, ``set_by`` / ``marked_by`` / ``not_marked_by``
    (usernames), ``awaiting_moderation``, ``open_only`` (still with the
    apprentice), ``overdue_on`` (with the apprentice and past due as of
    that ISO date), and ``due_from`` / ``due_before``.
    """
    init_db()
    qb = _filters(**filters)
    sql = (
        f"{_SELECT} {qb.where} "
        "ORDER BY COALESCE(x.due_date, '9999'), x.assignment_id"
    )
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        items = [_map(r) for r in conn.execute(sql, args).fetchall()]
        if with_children:
            _attach_children(conn, items)
    return items


def count_assignments(**filters: Any) -> int:
    """How many assignments match — the same filters as :func:`list_assignments`."""
    init_db()
    qb = _filters(**filters)
    with connect() as conn:
        row = conn.execute(
            f"""SELECT COUNT(*) AS n FROM assignments x
                  JOIN apprentices a ON a.apprentice_id = x.apprentice_id
                  {qb.where}""",
            qb.args,
        ).fetchone()
    return to_int(col(row, "n"))


# ── Writes ──────────────────────────────────────────────────────────

def create(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO assignments ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update(assignment_id: int, payload: dict[str, Any]) -> None:
    """Update the supplied fields only; anything absent is untouched."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE assignments SET {assignments}, updated_at = datetime('now') "
            "WHERE assignment_id = ?",
            [*(payload[c] for c in columns), assignment_id],
        )


def add_submission(
    assignment_id: int,
    *,
    attempt: int,
    body: str | None,
    evidence_id: int | None,
    submitted_by: str,
    is_late: bool,
) -> int:
    """Record an attempt and hand the assignment to the markers, together.

    The assignment row describes the current attempt, so a resubmission
    clears the previous attempt's grade from it — that grade stays on its
    own submission row.
    """
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO assignment_submissions
                   (assignment_id, attempt, body, evidence_id, submitted_by, is_late)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (assignment_id, attempt, body, evidence_id, submitted_by, 1 if is_late else 0),
        )
        conn.execute(
            """UPDATE assignments
                  SET status = 'Submitted', attempt = ?, grade = NULL, feedback = NULL,
                      marked_by = NULL, marked_at = NULL, updated_at = datetime('now')
                WHERE assignment_id = ?""",
            (attempt, assignment_id),
        )
        return int(cur.lastrowid)


def record_mark(
    assignment_id: int,
    *,
    attempt: int,
    grade: str,
    feedback: str | None,
    marked_by: str,
    marked_at: str,
    status: str,
    due_date: str | None = None,
) -> None:
    """Grade an attempt: on its submission row and on the assignment, together.

    *due_date*, when given, replaces the assignment's due date — the
    marker setting a resubmission deadline for referred work.
    """
    init_db()
    with connect() as conn:
        conn.execute(
            """UPDATE assignment_submissions
                  SET grade = ?, feedback = ?, marked_by = ?, marked_at = ?
                WHERE assignment_id = ? AND attempt = ?""",
            (grade, feedback, marked_by, marked_at, assignment_id, attempt),
        )
        sets = ["status = ?", "grade = ?", "feedback = ?", "marked_by = ?", "marked_at = ?"]
        values: list[Any] = [status, grade, feedback, marked_by, marked_at]
        if due_date is not None:
            sets.append("due_date = ?")
            values.append(due_date)
        conn.execute(
            f"UPDATE assignments SET {', '.join(sets)}, updated_at = datetime('now') "
            "WHERE assignment_id = ?",
            [*values, assignment_id],
        )


def add_moderation(
    assignment_id: int,
    *,
    attempt: int,
    moderator: str,
    outcome: str,
    original_grade: str | None,
    adjusted_grade: str | None,
    notes: str | None,
    status: str,
    grade: str | None,
) -> int:
    """Record a moderation and apply its result to the assignment, together."""
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO assignment_moderations
                   (assignment_id, attempt, moderator, outcome, original_grade,
                    adjusted_grade, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (assignment_id, attempt, moderator, outcome, original_grade, adjusted_grade, notes),
        )
        conn.execute(
            """UPDATE assignments SET status = ?, grade = ?, updated_at = datetime('now')
                WHERE assignment_id = ?""",
            (status, grade, assignment_id),
        )
        return int(cur.lastrowid)
