"""What a student is actually enrolled on, for the evaluation portals.

The three evaluation GUIs each offered a dropdown of *everything*: every
active course, all 380 modules in the catalogue, every instructor on the
books. A student was expected to find their own among them, and nothing
stopped them evaluating a module they had never taken or a lecturer who
had never taught them.

These helpers answer the narrower question the portals actually need:
which course is this student on, which modules are they enrolled on, and
who teaches those modules.

The module → lecturer link comes from ``module_schedule``: ``modules``
has ``instructor`` and ``instructor_id`` columns but both are empty for
every row, so scheduled sessions are the only record of who teaches
what.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "student_course", "student_modules", "module_lecturers",
    "student_lecturers", "enrolment_summary",
]

#: Enrolment states that count as "currently taking this module".
ACTIVE_ENROLMENT = ("active", "enrolled", "registered", "in_progress")


def _connect(db_path: Optional[str] = None):
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    return get_connection(db_path) if db_path else get_connection()


def _rows(sql: str, params=(), db_path=None) -> List[Any]:
    try:
        with _connect(db_path) as conn:
            return conn.execute(sql, params).fetchall()
    except Exception:
        logger.debug("enrolment query failed: %s", sql, exc_info=True)
        return []


def student_course(student_id: str, db_path=None) -> Optional[Dict[str, str]]:
    """The course a student is registered on, or None.

    ``programme_registrations`` is authoritative where it has a row;
    ``students.course`` is the fallback for records that predate it.
    """
    if not student_id:
        return None

    rows = _rows(
        "SELECT pr.programme_code, "
        "       COALESCE(NULLIF(c.course_name,''), NULLIF(c.name,''), pr.programme_code) "
        "FROM programme_registrations pr "
        "LEFT JOIN courses c "
        "       ON COALESCE(NULLIF(c.course_code,''), c.code) = pr.programme_code "
        "WHERE pr.student_id = ? "
        "ORDER BY pr.academic_year DESC LIMIT 1",
        (str(student_id),), db_path)
    if rows:
        return {"code": str(rows[0][0]), "name": str(rows[0][1] or rows[0][0])}

    rows = _rows(
        "SELECT s.course, "
        "       COALESCE(NULLIF(c.course_name,''), NULLIF(c.name,''), s.course) "
        "FROM students s "
        "LEFT JOIN courses c "
        "       ON COALESCE(NULLIF(c.course_code,''), c.code) = s.course "
        "WHERE s.student_id = ? AND s.course IS NOT NULL AND TRIM(s.course) != ''",
        (str(student_id),), db_path)
    if rows:
        return {"code": str(rows[0][0]), "name": str(rows[0][1] or rows[0][0])}
    return None


def student_modules(student_id: str, db_path=None) -> List[Dict[str, str]]:
    """The modules a student is currently enrolled on."""
    if not student_id:
        return []
    placeholders = ",".join("?" * len(ACTIVE_ENROLMENT))
    rows = _rows(
        "SELECT me.module_code, "
        "       COALESCE(NULLIF(m.module_name,''), me.module_code) AS module_name, "
        "       COALESCE(me.academic_year,'') "
        "FROM module_enrolments me "
        "LEFT JOIN modules m ON m.module_code = me.module_code "
        "WHERE me.student_id = ? "
        f"  AND LOWER(COALESCE(me.status,'active')) IN ({placeholders}) "
        "ORDER BY me.module_code",
        (str(student_id), *ACTIVE_ENROLMENT), db_path)

    seen, out = set(), []
    for code, name, year in rows:
        if code in seen:
            continue
        seen.add(code)
        out.append({"code": str(code), "name": str(name), "academic_year": str(year)})
    return out


def module_lecturers(module_code: str, db_path=None) -> List[Dict[str, str]]:
    """Who teaches a module, from its scheduled sessions."""
    if not module_code:
        return []
    rows = _rows(
        "SELECT DISTINCT i.id, "
        "       TRIM(COALESCE(i.first_name,'') || ' ' || COALESCE(i.last_name,'')), "
        "       COALESCE(i.department,''), COALESCE(i.email,''), "
        "       COALESCE(NULLIF(TRIM(i.specialization),''), 'Lecturer') "
        "FROM module_schedule ms "
        "JOIN instructors i ON i.id = ms.instructor_id "
        "WHERE ms.module_code = ? AND ms.instructor_id IS NOT NULL "
        "  AND COALESCE(i.is_active, 1) = 1",
        (str(module_code),), db_path)
    return [{"id": str(r[0]), "name": r[1] or f"Instructor {r[0]}",
             "department": r[2], "email": r[3], "title": r[4]} for r in rows]


def student_lecturers(student_id: str, db_path=None) -> List[Dict[str, Any]]:
    """Every lecturer who teaches a module this student is enrolled on.

    Each entry carries the modules they teach the student, so the portal
    can say *why* a lecturer is on the list.
    """
    by_id: Dict[str, Dict[str, Any]] = {}
    for module in student_modules(student_id, db_path):
        for lecturer in module_lecturers(module["code"], db_path):
            entry = by_id.setdefault(lecturer["id"], dict(lecturer, modules=[]))
            entry["modules"].append(module["code"])
    return sorted(by_id.values(), key=lambda l: l["name"].lower())


def enrolment_summary(student_id: str, db_path=None) -> Dict[str, Any]:
    """Course, modules and lecturers in one call, plus why it may be empty.

    ``reason`` is set when there is nothing to show, so a portal can
    explain itself instead of presenting an empty dropdown.
    """
    course = student_course(student_id, db_path)
    modules = student_modules(student_id, db_path)
    lecturers = student_lecturers(student_id, db_path)

    reason = None
    if not student_id:
        reason = "No student record is linked to this account."
    elif not modules:
        reason = ("You are not currently enrolled on any modules, so there is "
                  "nothing to evaluate yet.")
    elif not lecturers:
        reason = ("No lecturer is recorded as teaching your modules, so there "
                  "is nobody to evaluate. Ask an administrator to schedule "
                  "teaching sessions for them.")
    return {"student_id": student_id, "course": course, "modules": modules,
            "lecturers": lecturers, "reason": reason}
