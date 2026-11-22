"""Keep ``courses.current_enrollment`` honest against the students table.

``current_enrollment`` is a denormalised counter, incremented and decremented
from about ten different call sites (student create, delete, CSV import,
waitlist processing, course operations...). Any path that misses one — a
student added another way, a direct edit, a transaction that half-failed —
leaves the counter permanently behind, and nothing notices.

That is why the Course List showed ``10/120`` for Computer Science while the
enrolled-students popup listed 11 people: both were reading honestly, from
different places.

The authority is the ``students`` table: a course's enrolment is the number of
student rows registered to it. ``students.course`` is free text that usually
holds the course code but sometimes the course name, so both are matched — the
same resolution ``course_bridge.v_student_course`` uses.

Note this is programme registration, deliberately not the module-registration
count in ``v_course_occupancy``: those answer different questions (who is on
the degree vs who is sitting in the modules), and it is the former the course
list and the students popup both report.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Live headcount for one course row, matching students by code or by name.
#: Correlated against the aliased ``courses`` row referenced as ``c``.
HEADCOUNT_SQL = """(
    SELECT COUNT(*) FROM students s
     WHERE UPPER(TRIM(COALESCE(s.course, ''))) IN (
               UPPER(TRIM(COALESCE(NULLIF(TRIM(c.course_code), ''), c.code, ''))),
               UPPER(TRIM(COALESCE(NULLIF(TRIM(c.course_name), ''), c.name, '')))
           )
       AND COALESCE(TRIM(s.course), '') <> ''
)"""

_DRIFT_SQL = f"""
SELECT c.id,
       COALESCE(NULLIF(TRIM(c.course_code), ''), c.code) AS code,
       COALESCE(c.current_enrollment, 0)                 AS stored,
       {HEADCOUNT_SQL}                                   AS actual
  FROM courses c
 WHERE COALESCE(c.current_enrollment, 0) <> {HEADCOUNT_SQL}
 ORDER BY code
"""


#: Students registered on a course, matched the same way as HEADCOUNT_SQL.
#: Parameters: (course_code, course_name).
_STUDENTS_SQL = """
SELECT student_id,
       TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) AS name,
       COALESCE(email_address, '') AS email,
       COALESCE(year_of_study, '')  AS year,
       COALESCE(status, '')         AS status
  FROM students
 WHERE COALESCE(TRIM(course), '') <> ''
   AND UPPER(TRIM(course)) IN (UPPER(TRIM(?)), UPPER(TRIM(?)))
 ORDER BY last_name, first_name
"""


def students_for_course(conn, course_code, course_name=""):
    """Rows for the enrolled-students table.

    Matching on the name as well as the code matters: a handful of students
    are registered as 'Computer Science' rather than 'CS', and a code-only
    lookup silently left them off the list.
    """
    return [tuple(r) for r in conn.execute(
        _STUDENTS_SQL, (course_code or "", course_name or course_code or "")
    ).fetchall()]


def find_drift(conn):
    """Rows whose stored counter disagrees with the real headcount.

    Returns ``[(course_id, course_code, stored, actual), ...]``.
    """
    return [tuple(r) for r in conn.execute(_DRIFT_SQL).fetchall()]


def reconcile(conn, commit=True):
    """Reset every drifted ``current_enrollment`` to the real headcount.

    Returns the list of rows that were corrected, in the same shape as
    :func:`find_drift`, so the caller can report exactly what it changed.
    Only drifted rows are written, so a clean database is untouched.
    """
    drift = find_drift(conn)
    if not drift:
        return []

    conn.executemany(
        "UPDATE courses SET current_enrollment = ? WHERE id = ?",
        [(actual, course_id) for course_id, _code, _stored, actual in drift],
    )
    if commit:
        conn.commit()
    logger.info("reconciled current_enrollment for %d course(s)", len(drift))
    return drift


__all__ = ["HEADCOUNT_SQL", "students_for_course", "find_drift", "reconcile"]
