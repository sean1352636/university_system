"""Quizzes as assignments, backed by the exam portal.

A quiz used to be its own thing in the LMS tab: ``lms_quizzes`` plus a
question table that never got used, entirely separate from the assignment
list where the rest of a module's assessed work lives, and separate again
from ``exam_portal_*``, which is the platform's actual quiz engine —
questions, timed attempts, per-answer marking, integrity flags, exam
accommodations and grade writeback.

So a quiz is now both:

* a row in ``assignments`` with ``assignment_type='quiz'``, so it appears in
  the Assignment GUI beside every other piece of assessed work and inherits
  the listing, filtering and due-date handling already built there; and
* a row in ``exam_portal_exams`` linked back to it, which holds the questions
  and the sitting.

``exam_portal_exams.assignment_id`` is the link. It is added on demand the
same way ``exam_service`` adds its own late columns, so an existing database
picks it up without a migration step.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any, Optional

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

#: The assignments.assignment_type value that marks a row as a quiz.
QUIZ_TYPE = "quiz"


def ensure_link_column(conn=None) -> bool:
    """Add ``exam_portal_exams.assignment_id`` if it is not there yet.

    Idempotent, and mirrors ``ExamService._ensure_tables``: this codebase adds
    late columns with a guarded ALTER rather than a migration, so a database
    that predates the link still works.
    """
    own = conn is None
    conn = conn or get_connection()
    try:
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(exam_portal_exams)").fetchall()}
        if "assignment_id" in cols:
            return True
        conn.execute("ALTER TABLE exam_portal_exams ADD COLUMN assignment_id INTEGER")
        conn.commit()
        return True
    except sqlite3.OperationalError:
        logger.debug("could not add exam_portal_exams.assignment_id", exc_info=True)
        return False
    finally:
        if own:
            conn.close()


def resolve_creator(created_by, conn) -> Optional[int]:
    """Map *created_by* to a ``users.id``, or None when it names nobody.

    ``assignments.created_by`` is a foreign key onto ``users.id`` — an integer,
    not the username the LMS screens passed around. Handing it a username
    fails the constraint outright (foreign keys are enforced platform-wide),
    so a caller may pass either and this resolves it.
    """
    if created_by in (None, ""):
        return None
    try:
        return int(created_by)
    except (TypeError, ValueError):
        pass
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (str(created_by),)
        ).fetchone()
    except sqlite3.Error:
        logger.debug("could not resolve creator %r", created_by, exc_info=True)
        return None
    return row[0] if row else None


def create_quiz(
    *,
    module_code: str,
    title: str,
    created_by: str,
    description: str = "",
    instructions: str = "",
    due_date: Optional[str] = None,
    duration_minutes: int = 60,
    total_marks: float = 100.0,
    pass_mark: float = 50.0,
    max_attempts: int = 1,
    shuffle_questions: bool = False,
    conn=None,
) -> tuple[int, int]:
    """Create a quiz. Returns ``(assignment_id, exam_id)``.

    Both rows are written in one transaction: a quiz that exists in the
    assignment list but has no exam behind it cannot be sat, and an exam with
    no assignment row is invisible where people look for it.

    ``created_by`` may be a ``users.id`` or a username; the assignment row
    needs the id (it is a foreign key), while the exam row keeps whatever was
    passed, since it has no such constraint and reads better as a name.
    """
    own = conn is None
    conn = conn or get_connection()
    try:
        ensure_link_column(conn)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        creator_id = resolve_creator(created_by, conn)

        cursor = conn.execute(
            """INSERT INTO assignments
                   (module_code, title, description, instructions, due_date,
                    max_marks, assignment_type, is_active, created_by,
                    created_at, status, duration_minutes, max_score, time_limit)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 'active', ?, ?, ?)""",
            (module_code, title, description, instructions, due_date,
             total_marks, QUIZ_TYPE, creator_id, now,
             duration_minutes, total_marks, duration_minutes),
        )
        assignment_id = cursor.lastrowid

        cursor = conn.execute(
            """INSERT INTO exam_portal_exams
                   (title, description, module_code, created_by, status,
                    duration_minutes, pass_mark, total_marks, max_attempts,
                    shuffle_questions, instructions, end_time, assignment_id)
               VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, module_code, created_by,
             duration_minutes, pass_mark, total_marks, max_attempts,
             1 if shuffle_questions else 0, instructions, due_date,
             assignment_id),
        )
        exam_id = cursor.lastrowid

        conn.commit()
        return assignment_id, exam_id
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        if own:
            conn.close()


def exam_id_for_assignment(assignment_id: int, conn=None) -> Optional[int]:
    """The exam backing a quiz assignment, or None when it has none."""
    own = conn is None
    conn = conn or get_connection()
    try:
        ensure_link_column(conn)
        row = conn.execute(
            "SELECT id FROM exam_portal_exams WHERE assignment_id = ? "
            "ORDER BY id LIMIT 1",
            (assignment_id,),
        ).fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        logger.debug("exam lookup failed for assignment %s", assignment_id, exc_info=True)
        return None
    finally:
        if own:
            conn.close()


def list_quizzes(module_code: Optional[str] = None, conn=None) -> list[dict[str, Any]]:
    """Quiz assignments, newest first, with their exam id and question count."""
    own = conn is None
    conn = conn or get_connection()
    try:
        ensure_link_column(conn)
        sql = (
            "SELECT a.id, a.module_code, a.title, a.due_date, a.max_marks, "
            "       a.duration_minutes, e.id AS exam_id, e.status, "
            "       (SELECT COUNT(*) FROM exam_portal_questions q "
            "         WHERE q.exam_id = e.id) AS question_count "
            "  FROM assignments a "
            "  LEFT JOIN exam_portal_exams e ON e.assignment_id = a.id "
            " WHERE a.assignment_type = ? "
            "   AND COALESCE(a.archived, 0) = 0 "
        )
        params: list[Any] = [QUIZ_TYPE]
        if module_code:
            sql += "   AND a.module_code = ? "
            params.append(module_code)
        sql += " ORDER BY a.id DESC"

        rows = conn.execute(sql, params).fetchall()
        keys = ("assignment_id", "module_code", "title", "due_date", "max_marks",
                "duration_minutes", "exam_id", "status", "question_count")
        return [dict(zip(keys, tuple(r))) for r in rows]
    except sqlite3.Error:
        logger.warning("could not list quizzes", exc_info=True)
        return []
    finally:
        if own:
            conn.close()


def delete_quiz(assignment_id: int, conn=None) -> bool:
    """Delete a quiz: its assignment row, its exam, questions and attempts."""
    own = conn is None
    conn = conn or get_connection()
    try:
        ensure_link_column(conn)
        exam_id = exam_id_for_assignment(assignment_id, conn=conn)
        if exam_id is not None:
            attempts = [r[0] for r in conn.execute(
                "SELECT id FROM exam_portal_attempts WHERE exam_id = ?",
                (exam_id,)).fetchall()]
            for attempt_id in attempts:
                conn.execute("DELETE FROM exam_portal_answers WHERE attempt_id = ?",
                             (attempt_id,))
            conn.execute("DELETE FROM exam_portal_attempts WHERE exam_id = ?", (exam_id,))
            conn.execute("DELETE FROM exam_portal_questions WHERE exam_id = ?", (exam_id,))
            conn.execute("DELETE FROM exam_portal_exams WHERE id = ?", (exam_id,))

        conn.execute("DELETE FROM assignments WHERE id = ? AND assignment_type = ?",
                     (assignment_id, QUIZ_TYPE))
        deleted = conn.total_changes > 0
        conn.commit()
        return deleted
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        if own:
            conn.close()


__all__ = [
    "QUIZ_TYPE", "ensure_link_column", "create_quiz", "exam_id_for_assignment",
    "list_quizzes", "delete_quiz",
]
