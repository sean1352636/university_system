"""Course-level external examiner appointments.

Examiners are tracked centrally in ``external_examiners`` (owned by the
external_examiners module). Two consumers attach examiners to academic
artefacts:

- The exam scheduler links per-exam panels via ``exam_external_examiners``.
- Course management appoints year-long examiners via this service, which
  writes to the canonical ``examiner_assignments`` table.

Both consumers point at the same ``external_examiners.examiner_id``, so
the master roster is never duplicated. When the exam scheduler picks an
examiner for an exam it can prefer the course's appointed examiners
without having to rebuild that mapping itself —
``list_examiners_for_course`` is the lookup it would use.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def _connect():
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        return get_connection()
    except Exception as exc:
        logger.debug("DB unavailable for examiner assignments: %s", exc)
        return None


def _examiner_pk_column(conn) -> str:
    """Return the actual PK column name on external_examiners.

    Older deployments use ``examiner_id``; auto-created variants use
    ``id``. Detect at runtime so JOINs work either way.
    """
    try:
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(external_examiners)").fetchall()}
        return "examiner_id" if "examiner_id" in cols else "id"
    except Exception:
        return "examiner_id"


def attach_examiner_to_course(course_code: str, examiner_id: int,
                              academic_year: Optional[str] = None,
                              assignment_type: str = "module_review",
                              ) -> Optional[int]:
    """Appoint an external examiner to a course for the given year.

    Returns the new ``assignment_id``, or the existing one if an active
    appointment for the same triple already exists (idempotent).
    """
    conn = _connect()
    if conn is None:
        return None
    try:
        with conn:
            existing = conn.execute(
                "SELECT assignment_id FROM examiner_assignments "
                "WHERE examiner_id = ? AND course_code = ? "
                "  AND COALESCE(academic_year,'') = COALESCE(?,'') "
                "  AND COALESCE(assignment_type,'') = COALESCE(?,'') "
                "LIMIT 1",
                (int(examiner_id), course_code, academic_year,
                 assignment_type),
            ).fetchone()
            if existing:
                return int(existing[0])
            cur = conn.execute(
                "INSERT INTO examiner_assignments "
                "(examiner_id, course_code, assignment_type, "
                " academic_year) "
                "VALUES (?, ?, ?, ?)",
                (int(examiner_id), course_code, assignment_type,
                 academic_year),
            )
            return int(cur.lastrowid) if cur.lastrowid else None
    except Exception as exc:
        logger.error("attach_examiner_to_course failed: %s", exc)
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def detach_examiner_from_course(assignment_id: int) -> bool:
    conn = _connect()
    if conn is None:
        return False
    try:
        with conn:
            conn.execute(
                "DELETE FROM examiner_assignments WHERE assignment_id = ?",
                (int(assignment_id),),
            )
        return True
    except Exception as exc:
        logger.error("detach_examiner_from_course failed: %s", exc)
        return False


def list_examiners_for_course(course_code: str,
                              academic_year: Optional[str] = None
                              ) -> List[Dict]:
    """Return examiners appointed to *course_code*, joined to the master
    roster so the caller has name / institution / email.

    When *academic_year* is given, only assignments for that year (or
    rows with NULL year) are returned.
    """
    conn = _connect()
    if conn is None:
        return []
    try:
        pk = _examiner_pk_column(conn)
        # Pick the right "expertise" column for the deployment.
        ee_cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(external_examiners)").fetchall()}
        expertise = (
            "ee.expertise_area" if "expertise_area" in ee_cols
            else ("ee.specialisation" if "specialisation" in ee_cols
                  else "''")
        )
        sql = (
            f"""SELECT ea.assignment_id, ea.examiner_id,
                       ea.assignment_type, ea.academic_year,
                       ea.report_submitted,
                       ee.name, ee.institution, ee.email,
                       {expertise} AS expertise
                FROM examiner_assignments ea
                JOIN external_examiners ee ON ee.{pk} = ea.examiner_id
                WHERE ea.course_code = ?"""
        )
        params: List = [course_code]
        if academic_year:
            sql += " AND (ea.academic_year = ? OR ea.academic_year IS NULL)"
            params.append(academic_year)
        sql += " ORDER BY ee.name"

        rows = conn.execute(sql, params).fetchall()
        return [
            {"assignment_id": r[0], "examiner_id": r[1],
             "assignment_type": r[2], "academic_year": r[3],
             "report_submitted": bool(r[4]),
             "name": r[5], "institution": r[6], "email": r[7],
             "expertise": r[8]}
            for r in rows
        ]
    except Exception as exc:
        logger.debug("list_examiners_for_course failed: %s", exc)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def list_courses_for_examiner(examiner_id: int) -> List[Dict]:
    """Return courses an examiner is appointed to."""
    conn = _connect()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """SELECT ea.assignment_id, ea.course_code, ea.assignment_type,
                      ea.academic_year, ea.report_submitted
               FROM examiner_assignments ea
               WHERE ea.examiner_id = ?
               ORDER BY ea.academic_year DESC, ea.course_code""",
            (int(examiner_id),),
        ).fetchall()
        return [
            {"assignment_id": r[0], "course_code": r[1],
             "assignment_type": r[2], "academic_year": r[3],
             "report_submitted": bool(r[4])}
            for r in rows
        ]
    except Exception as exc:
        logger.debug("list_courses_for_examiner failed: %s", exc)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def find_examiners_for_module(module_code: str,
                              academic_year: Optional[str] = None
                              ) -> List[Dict]:
    """Resolve a module code to its parent course (via the ``courses``
    table) and return any appointed examiners.

    Useful for the exam scheduler: when picking external examiners for
    an exam in module CIS2001, this returns the course-level appointees
    so the picker can default to them.
    """
    conn = _connect()
    if conn is None:
        return []
    try:
        # Find course code(s) the module belongs to.
        course_codes = [
            row[0] for row in conn.execute(
                "SELECT COALESCE(c.code, c.course_code) "
                "FROM courses c "
                "WHERE c.code = ? OR c.course_code = ?",
                (module_code, module_code),
            ).fetchall() if row[0]
        ]
        if not course_codes:
            course_codes = [module_code]
    finally:
        try:
            conn.close()
        except Exception:
            pass

    seen: set = set()
    out: List[Dict] = []
    for code in course_codes:
        for ex in list_examiners_for_course(code, academic_year):
            if ex["examiner_id"] in seen:
                continue
            seen.add(ex["examiner_id"])
            out.append(ex)
    return out
