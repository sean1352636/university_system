"""What a student has actually *earned*, as opposed to enrolled on.

Every degree-audit surface used to compute progress as::

    SELECT COUNT(DISTINCT sm.module_code), SUM(COALESCE(m.credits, 0))
      FROM student_modules sm
      LEFT JOIN modules m ON m.module_code = sm.module_code
     WHERE sm.student_id = ?

which counts a module the moment a student *registers* for it. Enrolling on
six 15-credit modules therefore read as "90 credits earned" before a single
piece of work had been marked.

Credits are earned by passing. This module is the single place that decides
what that means, so the progress tab, the graduation audit and the ceremony
eligibility check cannot disagree.

Two things the earlier version missed, both of which left every student
reading 0 credits / 0.00 GPA:

* **Marks live in ``module_grades``.** Grade Tracking records a module's final
  grade there and never touches ``student_modules``, whose rows stay
  'Enrolled' with no grade. A passing final grade is the outcome, so it earns
  the module whatever the enrolment row still says.
* **Seeded modules carry ``credits = 0``.** As in Academic Progress, the
  programme's credit requirement split across its modules (360 over 18 = 20)
  stands in for a module that records no credit value of its own.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Grades that are a fail however the rest of the row looks.
FAILING_GRADES = ("f", "fail", "failed", "u", "unsatisfactory", "n", "ng")

#: Enrolment statuses that mean the module is finished and credit-bearing.
COMPLETED_STATUSES = ("completed", "complete", "passed", "pass", "awarded")

#: Statuses under which a grade on the enrolment row alone does not earn it.
_NOT_FINISHED_STATUSES = ("enrolled", "withdrawn", "deferred")

#: Latest final grade per (student, module) — resits supersede earlier marks.
_LATEST_MODULE_GRADE = """(
    SELECT x.id FROM module_grades x
     WHERE x.student_id = {student} AND x.module_code = {module}
     ORDER BY COALESCE(x.completion_date, x.date_recorded, '') DESC, x.id DESC
     LIMIT 1
)"""

_ROWS_SQL = f"""
SELECT sm.module_code,
       COALESCE(NULLIF(m.module_type, ''), NULLIF(sm.module_type, ''), 'Standard'),
       COALESCE(m.module_name, sm.module_name, sm.module_code),
       COALESCE(m.credits, 0),
       COALESCE(sm.credits_earned, 0),
       sm.status,
       sm.grade,
       mg.final_grade
  FROM student_modules sm
  LEFT JOIN modules m ON m.module_code = sm.module_code
  LEFT JOIN module_grades mg
         ON mg.id = {_LATEST_MODULE_GRADE.format(student='sm.student_id', module='sm.module_code')}
 WHERE sm.student_id = ?
UNION ALL
SELECT mg.module_code,
       COALESCE(NULLIF(m.module_type, ''), 'Standard'),
       COALESCE(m.module_name, mg.module_code),
       COALESCE(m.credits, 0),
       0,
       'Completed',
       NULL,
       mg.final_grade
  FROM module_grades mg
  LEFT JOIN modules m ON m.module_code = mg.module_code
 WHERE mg.student_id = ?
   AND mg.id = {_LATEST_MODULE_GRADE.format(student='mg.student_id', module='mg.module_code')}
   AND NOT EXISTS (SELECT 1 FROM student_modules s
                    WHERE s.student_id = mg.student_id
                      AND s.module_code = mg.module_code)
"""

# Databases without a module_grades table still get enrolment-based progress.
_ROWS_SQL_NO_MODULE_GRADES = """
SELECT sm.module_code,
       COALESCE(NULLIF(m.module_type, ''), NULLIF(sm.module_type, ''), 'Standard'),
       COALESCE(m.module_name, sm.module_name, sm.module_code),
       COALESCE(m.credits, 0),
       COALESCE(sm.credits_earned, 0),
       sm.status,
       sm.grade,
       NULL
  FROM student_modules sm
  LEFT JOIN modules m ON m.module_code = sm.module_code
 WHERE sm.student_id = ?
"""

_GRADE_POINTS = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0}


def _clean(value):
    return str(value).strip() if value not in (None, "") else ""


def _passing(grade):
    return bool(grade) and grade.lower() not in FAILING_GRADES


def _grade_points(grade):
    """GPA points for a letter grade; ``None`` for anything unrecognised."""
    g = grade.upper()
    if g in ("F", "FAIL", "U"):
        return 0.0
    if g and g[0] in _GRADE_POINTS and len(g) <= 2:
        return _GRADE_POINTS[g[0]]
    return None


def _module_credit_default(conn, student_id):
    """Per-module credits for modules that record none.

    The student's programme requirement divided by the number of modules the
    programme has — the same rule Academic Progress applies. 0 when either
    side is unknown, rather than inventing a figure.
    """
    try:
        row = conn.execute(
            "SELECT COALESCE(course, '') FROM students WHERE student_id = ?",
            (student_id,)).fetchone()
        course = row[0] if row else ""
        if not course:
            return 0
        count = conn.execute(
            "SELECT COUNT(*) FROM modules WHERE course = ? "
            "AND COALESCE(module_code, '') <> '' AND COALESCE(is_active, 1) = 1",
            (course,)).fetchone()[0] or 0
    except Exception:
        logger.debug("module credit default lookup failed for %s", student_id, exc_info=True)
        return 0
    required = required_credits_for_course(conn, course, default=0)
    if required > 0 and count > 0:
        return max(1, round(required / count))
    return 0


def module_progress(conn, student_id) -> list[dict]:
    """One row per module the student is on or has a final grade for.

    Keys: ``module_code``, ``module_type``, ``module_name``, ``credits``,
    ``status``, ``grade`` and ``earned``. ``grade`` prefers the enrolment
    row's own grade and falls back to the latest ``module_grades`` mark.
    """
    try:
        raw = list(conn.execute(_ROWS_SQL, (student_id, student_id)).fetchall())
    except Exception:
        logger.debug("module_grades unavailable; using enrolments only", exc_info=True)
        try:
            raw = list(conn.execute(_ROWS_SQL_NO_MODULE_GRADES, (student_id,)).fetchall())
        except Exception:
            logger.warning("progress lookup failed for %s", student_id, exc_info=True)
            return []

    default_credits = None
    rows, seen = [], set()
    for code, mtype, name, module_credits, credits_earned, status, sm_grade, final_grade in raw:
        if code in seen:
            continue
        seen.add(code)
        sm_grade, final_grade = _clean(sm_grade), _clean(final_grade)
        status_l = _clean(status).lower()
        grade = sm_grade or final_grade

        earned = (
            (credits_earned or 0) > 0
            or (status_l in COMPLETED_STATUSES and _passing(grade))
            or (_passing(final_grade) and status_l != "withdrawn")
            or (_passing(sm_grade) and status_l not in _NOT_FINISHED_STATUSES)
        )

        credits = credits_earned if (credits_earned or 0) > 0 else module_credits
        if not credits:
            if default_credits is None:
                default_credits = _module_credit_default(conn, student_id)
            credits = default_credits

        rows.append({
            "module_code": code,
            "module_type": mtype,
            "module_name": name,
            "credits": float(credits or 0),
            "status": _clean(status) or "Enrolled",
            "grade": grade,
            "earned": earned,
        })
    return rows


def earned_progress(conn, student_id) -> dict:
    """Progress for *student_id*.

    ``credits_earned`` / ``modules_completed`` count only passed work.
    ``credits_enrolled`` / ``modules_enrolled`` describe everything registered,
    so a caller can show "0 of 90 credits so far" rather than a bare zero that
    looks like missing data.
    """
    rows = module_progress(conn, student_id)
    points = [p for p in (_grade_points(r["grade"]) for r in rows if r["grade"])
              if p is not None]
    return {
        "modules_completed": sum(1 for r in rows if r["earned"]),
        "credits_earned": float(sum(r["credits"] for r in rows if r["earned"])),
        "gpa": (sum(points) / len(points)) if points else 0.0,
        "modules_enrolled": len(rows),
        "modules_graded": sum(1 for r in rows if r["grade"]),
        "credits_enrolled": float(sum(r["credits"] for r in rows)),
    }


def required_credits_for_course(conn, course_code, default=120):
    """The course's own credit requirement, or *default* when it has none.

    The progress tab hard-coded 120. A BSc here is 360 credits, so completion
    was reported at three times the true figure. Order matches Academic
    Progress: the degree programme, then ``courses.credits``, then
    ``credit_hours`` — ACC carries credits 360 but credit_hours 400.
    """
    if not course_code:
        return default
    lookups = (
        ("SELECT total_credits_required FROM degree_programs "
         "WHERE program_code = ? AND COALESCE(total_credits_required, 0) > 0 LIMIT 1"),
        ("SELECT CASE WHEN COALESCE(credits, 0) > 0 THEN credits "
         "            ELSE credit_hours END FROM courses "
         "WHERE COALESCE(course_code, code) = ? LIMIT 1"),
    )
    for sql in lookups:
        try:
            row = conn.execute(sql, (course_code,)).fetchone()
        except Exception:
            logger.debug("credit requirement lookup failed for %r", course_code, exc_info=True)
            continue
        try:
            value = int(row[0]) if row and row[0] not in (None, "") else 0
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return default


__all__ = ["earned_progress", "module_progress", "required_credits_for_course",
           "FAILING_GRADES", "COMPLETED_STATUSES"]


#: What a prerequisite's minimum grade can be, best first. These are the bands
#: Grade Tracking records (application/assessment/classification_rules).
PREREQUISITE_GRADES = ("First", "2:1", "2:2", "Third")

_GRADE_RANKS = {"first": 4, "1st": 4, "a": 4, "2:1": 3, "2.1": 3, "b": 3,
                "2:2": 2, "2.2": 2, "c": 2, "third": 1, "3rd": 1, "d": 1, "pass": 1}


def _grade_rank(grade):
    g = _clean(grade).lower()
    return _GRADE_RANKS.get(g, _GRADE_RANKS.get(g[:1]) if len(g) == 2 and g[1] in "+-" else None)


def grade_meets_minimum(grade, minimum):
    """Whether *grade* reaches *minimum*. No minimum asks only for a pass, which
    the caller has already established; a grade off the scale cannot be shown to
    reach one, so it does not."""
    if not _clean(minimum):
        return True
    wanted, got = _grade_rank(minimum), _grade_rank(grade)
    return wanted is not None and got is not None and got >= wanted


def declared_prerequisites(conn, module_code) -> dict:
    """{prerequisite code: minimum grade or ""} for a module.

    Prerequisites live in two places: ``modules.prerequisites`` (a comma-separated
    list on the catalogue record) and ``degree_course_prerequisites`` (where Add
    Prerequisite writes). Both count.
    """
    declared = {}
    row = conn.execute("SELECT prerequisites FROM modules WHERE module_code = ?",
                       (module_code,)).fetchone()
    for code in _clean(row[0] if row else "").split(","):
        code = code.strip()
        if code and code.lower() != "none":
            declared[code] = ""
    try:
        for code, minimum in conn.execute(
                "SELECT prerequisite_module_code, min_grade FROM degree_course_prerequisites "
                "WHERE module_code = ? AND COALESCE(is_corequisite, 0) = 0",
                (module_code,)).fetchall():
            declared[code] = _clean(minimum)
    except Exception:  # noqa: BLE001 - table is created on first use of the audit
        logger.debug("degree_course_prerequisites unavailable", exc_info=True)
    return declared


def prerequisite_status(conn, student_id, module_code) -> list[dict]:
    """Each prerequisite of a module against this student's record.

    Keys: ``code``, ``name``, ``status``, ``grade``, ``min_grade``, ``met``. A
    prerequisite is met when the module is earned (see :func:`module_progress`,
    so marks in ``module_grades`` count) at the minimum grade, if one is set.
    """
    taken = {r["module_code"]: r for r in module_progress(conn, student_id)}
    out = []
    for code, minimum in declared_prerequisites(conn, module_code).items():
        row = taken.get(code)
        name = conn.execute("SELECT module_name FROM modules WHERE module_code = ?",
                            (code,)).fetchone()
        out.append({
            "code": code,
            "name": (name[0] if name else "") or "—",
            "status": row["status"] if row else "Not taken",
            "grade": row["grade"] if row else "",
            "min_grade": minimum,
            "met": bool(row and row["earned"] and grade_meets_minimum(row["grade"], minimum)),
        })
    return out
