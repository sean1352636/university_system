"""Academic terms — the single owner of ``academic_terms``.

Terms used to be owned by Course Management: its "Terms & Sections" tab held
the create/edit/delete UI, a second independent editor lived in the
``curriculum_extensions`` CLI, and the table's DDL was declared twice in two
packages. Meanwhile the Academic Calendar owned the *other* model of the same
concept — ``academic_years`` and ``semesters`` — and the two were reconciled by
best-effort sync code in the Course Management GUI.

That sync only ever worked in one direction. A term created on the calendar
side was imported into ``academic_terms``; a term created on the Course
Management side was pushed to the calendar as a plain *event*, not a semester,
so it never came back. The live database still shows it: ``summer`` exists in
``academic_terms`` with no counterpart in ``semesters``.

Terms are an academic-calendar concept — the calendar already owns academic
years and semesters, and ``current_period()`` reads calendar periods to gate
exam dates. Course Management merely *consumes* a term as a foreign key on
``course_sections.term_id``. So this module is the one writer, and everything
else reads through it:

* the Academic Calendar GUI edits terms here;
* the Course Management GUI shows them read-only;
* the ``curriculum_extensions`` CLI delegates here.

It deliberately imports no GUI code, so the CLI can use it without pulling in
tkinter — the reason the DDL was duplicated in the first place.
"""
from __future__ import annotations

import logging
from contextlib import closing
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    sqlite3,
)

logger = logging.getLogger(__name__)

#: The single declaration of the table. Both the Course Management GUI schema
#: bootstrap and the CLI schema bootstrap import this rather than repeating it;
#: two copies of a ``CREATE TABLE IF NOT EXISTS`` can drift silently, because
#: whichever runs first wins and the other becomes a no-op.
ACADEMIC_TERMS_DDL = """
    CREATE TABLE IF NOT EXISTS academic_terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        term_type TEXT NOT NULL DEFAULT 'Semester',
        academic_year TEXT NOT NULL DEFAULT '',
        start_date TEXT DEFAULT '',
        end_date TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Planned',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
"""

TERM_TYPES = ("Semester", "Trimester", "Quarter", "Term", "Session")
TERM_STATUSES = ("Planned", "In Progress", "Completed", "Archived", "Cancelled")


class TermError(Exception):
    """A term operation failed for a reason worth showing the user."""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_terms_schema(conn=None) -> None:
    """Create ``academic_terms`` if it is missing. Idempotent."""
    close = conn is None
    conn = conn or get_connection()
    try:
        conn.execute(ACADEMIC_TERMS_DDL)
        if close:
            conn.commit()
    finally:
        if close:
            conn.close()


def _validate(name, start_date, end_date):
    name = (name or "").strip()
    if not name:
        raise TermError("A term needs a name.")
    start = (start_date or "").strip()
    end = (end_date or "").strip()
    # Both-or-neither: a half-specified span breaks the term timetable view,
    # which expands sessions between the two dates.
    if bool(start) != bool(end):
        raise TermError("Give both a start and an end date, or neither.")
    if start and end and start >= end:
        raise TermError("The end date must be after the start date.")
    return name, start, end


def list_terms(conn=None) -> list[dict]:
    """Every term, newest first. Never raises — an unreadable table is []."""
    close = conn is None
    conn = conn or get_connection()
    try:
        ensure_terms_schema(conn)
        rows = conn.execute(
            "SELECT id, name, term_type, academic_year, start_date, end_date, "
            "       status, created_at, updated_at "
            "FROM academic_terms ORDER BY COALESCE(start_date, '') DESC, name"
        ).fetchall()
    except sqlite3.Error as exc:
        logger.warning("could not list academic terms: %s", exc)
        return []
    finally:
        if close:
            conn.close()

    fields = ("id", "name", "term_type", "academic_year", "start_date",
              "end_date", "status", "created_at", "updated_at")
    return [dict(zip(fields, row)) for row in rows]


def count_sections(term_id, conn=None) -> int:
    """How many ``course_sections`` depend on this term.

    Foreign keys are enforced, so deleting a term that still has sections
    fails outright. Callers show this number before offering to cascade.
    """
    close = conn is None
    conn = conn or get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM course_sections WHERE term_id = ?",
            (term_id,)).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        # No course_sections table yet — nothing can depend on the term.
        return 0
    finally:
        if close:
            conn.close()


def create_term(name, term_type="Semester", academic_year="",
                start_date="", end_date="", status="Planned",
                conn=None) -> int:
    """Create a term and return its id. Raises :class:`TermError` on refusal."""
    name, start_date, end_date = _validate(name, start_date, end_date)
    close = conn is None
    conn = conn or get_connection()
    try:
        ensure_terms_schema(conn)
        cursor = conn.execute(
            "INSERT INTO academic_terms (name, term_type, academic_year, "
            " start_date, end_date, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, term_type or "Semester", academic_year or "",
             start_date, end_date, status or "Planned", _now(), _now()))
        if close:
            conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        # name is UNIQUE.
        raise TermError(f"A term named '{name}' already exists.") from exc
    finally:
        if close:
            conn.close()


def update_term(term_id, name, term_type="Semester", academic_year="",
                start_date="", end_date="", status="Planned",
                conn=None) -> None:
    """Update an existing term in place."""
    name, start_date, end_date = _validate(name, start_date, end_date)
    close = conn is None
    conn = conn or get_connection()
    try:
        ensure_terms_schema(conn)
        conn.execute(
            "UPDATE academic_terms SET name = ?, term_type = ?, "
            " academic_year = ?, start_date = ?, end_date = ?, status = ?, "
            " updated_at = ? WHERE id = ?",
            (name, term_type or "Semester", academic_year or "",
             start_date, end_date, status or "Planned", _now(), term_id))
        if close:
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise TermError(f"A term named '{name}' already exists.") from exc
    finally:
        if close:
            conn.close()


def _delete_term_sections(conn, term_id) -> None:
    from education_system.systems.university.application.modules import sections as section_rules
    from education_system.systems.university.domains.teaching.domain.section_meeting_calendar import (
        clear_occurrences,
    )
    rows = conn.execute("SELECT id, course_code, section_number FROM course_sections "
                        "WHERE term_id = ? ORDER BY course_code, section_number",
                        (term_id,)).fetchall()
    in_use = []
    for section_id, course_code, number in (tuple(r) for r in rows):
        blockers = section_rules.delete_blockers(conn, section_id)
        if blockers:
            in_use.append(f"{course_code} section {number}:\n"
                          f"{section_rules.describe_blockers(blockers)}")
    if in_use:
        raise TermError("That term can't be deleted while its sections are in use.\n\n"
                        + "\n".join(in_use))
    for row in rows:
        clear_occurrences(conn, section_rules.delete_section(conn, tuple(row)[0]))


def delete_term(term_id, cascade_sections=False, conn=None) -> int:
    """Delete a term, returning how many sections went with it.

    Without *cascade_sections* a term that still has sections is refused
    rather than left to fail on the foreign key with an opaque error. With it,
    each section goes the way a single section delete does, taking its meeting
    times and their calendar entries. It is refused if any section is still in
    use, before anything is removed.
    """
    close = conn is None
    conn = conn or get_connection()
    try:
        dependents = count_sections(term_id, conn)
        if dependents and not cascade_sections:
            raise TermError(
                f"That term still has {dependents} course section(s). "
                f"Delete or move them first, or confirm cascading.")
        if dependents:
            _delete_term_sections(conn, term_id)
        conn.execute("DELETE FROM academic_terms WHERE id = ?", (term_id,))
        if close:
            conn.commit()
        return dependents
    finally:
        if close:
            conn.close()


def get_term(term_id, conn=None) -> dict | None:
    """One term by id, or None."""
    close = conn is None
    conn = conn or get_connection()
    try:
        with closing(conn.execute(
            "SELECT id, name, term_type, academic_year, start_date, end_date, "
            "       status, created_at, updated_at "
            "FROM academic_terms WHERE id = ?", (term_id,)
        )) as cur:
            row = cur.fetchone()
    except sqlite3.Error:
        return None
    finally:
        if close:
            conn.close()
    if row is None:
        return None
    fields = ("id", "name", "term_type", "academic_year", "start_date",
              "end_date", "status", "created_at", "updated_at")
    return dict(zip(fields, row))


__all__ = [
    "ACADEMIC_TERMS_DDL", "TERM_TYPES", "TERM_STATUSES", "TermError",
    "ensure_terms_schema", "list_terms", "count_sections",
    "create_term", "update_term", "delete_term", "get_term",
]
