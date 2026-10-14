"""Grade distribution and performance figures, without any presentation.

``curve_analysis.py`` computes all of this already, but every function
there prints as it goes and several stop to ``input()`` for a choice, so
none of it can be reused by a GUI — which is why the Grade Curve
Analysis and Performance Analysis buttons in Grade Tracking silently
showed the generic Analytics screen instead.

The queries live here and return plain data. The CLI keeps its menus and
printing; the GUI renders the same numbers as tables. One set of
queries, two front-ends.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "grade_distribution_overall", "grade_distribution_by_course",
    "grade_distribution_by_module_type", "performance_by_course",
    "performance_by_module_type", "grade_trend_by_period",
    "curve_preview",
]


def _connect():
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    return get_connection()


def _grade_rank(letter: str) -> float:
    """Sort key so A comes before F, using the shared conversion."""
    try:
        from education_system.systems.university.domains.assessment.domain.grading.curve_analysis import (
            letter_to_gpa,
        )
        return float(letter_to_gpa(letter) or 0.0)
    except Exception:
        return 0.0


def _rows(sql: str, params=()) -> List[Any]:
    try:
        with _connect() as conn:
            return conn.execute(sql, params).fetchall()
    except Exception:
        logger.debug("curve analysis query failed: %s", sql, exc_info=True)
        return []


def _with_percentages(pairs) -> List[Dict[str, Any]]:
    """[(label, count)] -> rows carrying each label's share of the total."""
    total = sum(count for _label, count in pairs) or 0
    out = []
    for label, count in sorted(pairs, key=lambda p: _grade_rank(p[0]), reverse=True):
        out.append({
            "grade": label,
            "count": count,
            "percentage": (count / total * 100.0) if total else 0.0,
        })
    return out


# --------------------------------------------------------------------------
# Distribution
# --------------------------------------------------------------------------

def grade_distribution_overall() -> Dict[str, List[Dict[str, Any]]]:
    """Module final grades and assessment grades, each as a distribution."""
    module_rows = _rows(
        "SELECT final_grade, COUNT(*) FROM module_grades "
        "WHERE final_grade IS NOT NULL AND TRIM(final_grade) != '' "
        "GROUP BY final_grade")
    assessment_rows = _rows(
        "SELECT letter_grade, COUNT(*) FROM grades "
        "WHERE letter_grade IS NOT NULL AND TRIM(letter_grade) != '' "
        "GROUP BY letter_grade")
    return {
        "module_grades": _with_percentages([(r[0], r[1]) for r in module_rows]),
        "assessment_grades": _with_percentages([(r[0], r[1]) for r in assessment_rows]),
    }


def grade_distribution_by_course() -> Dict[str, List[Dict[str, Any]]]:
    """{course: [{grade, count, percentage}, ...]}."""
    rows = _rows(
        "SELECT s.course, mg.final_grade, COUNT(*) "
        "FROM students s JOIN module_grades mg ON s.student_id = mg.student_id "
        "WHERE mg.final_grade IS NOT NULL AND TRIM(mg.final_grade) != '' "
        "GROUP BY s.course, mg.final_grade")
    grouped: Dict[str, List] = {}
    for course, grade, count in rows:
        grouped.setdefault(course or "(no course)", []).append((grade, count))
    return {course: _with_percentages(pairs) for course, pairs in grouped.items()}


def grade_distribution_by_module_type() -> Dict[str, List[Dict[str, Any]]]:
    """{module_type: [{grade, count, percentage}, ...]}."""
    rows = _rows(
        "SELECT m.module_type, mg.final_grade, COUNT(*) "
        "FROM modules m JOIN module_grades mg ON m.module_code = mg.module_code "
        "WHERE mg.final_grade IS NOT NULL AND TRIM(mg.final_grade) != '' "
        "GROUP BY m.module_type, mg.final_grade")
    grouped: Dict[str, List] = {}
    for mtype, grade, count in rows:
        grouped.setdefault(mtype or "(no type)", []).append((grade, count))
    return {mtype: _with_percentages(pairs) for mtype, pairs in grouped.items()}


# --------------------------------------------------------------------------
# Performance comparison
# --------------------------------------------------------------------------

def performance_by_course() -> List[Dict[str, Any]]:
    """Mean / min / max final score per course, best first."""
    rows = _rows(
        "SELECT s.course, COUNT(mg.id), AVG(mg.final_score), "
        "       MIN(mg.final_score), MAX(mg.final_score) "
        "FROM students s JOIN module_grades mg ON s.student_id = mg.student_id "
        "WHERE mg.final_score IS NOT NULL "
        "GROUP BY s.course ORDER BY AVG(mg.final_score) DESC")
    return [{"group": r[0] or "(no course)", "results": r[1],
             "average": r[2] or 0.0, "lowest": r[3] or 0.0, "highest": r[4] or 0.0}
            for r in rows]


def performance_by_module_type() -> List[Dict[str, Any]]:
    """Mean / min / max final score per module type, best first."""
    rows = _rows(
        "SELECT m.module_type, COUNT(mg.id), AVG(mg.final_score), "
        "       MIN(mg.final_score), MAX(mg.final_score) "
        "FROM modules m JOIN module_grades mg ON m.module_code = mg.module_code "
        "WHERE mg.final_score IS NOT NULL "
        "GROUP BY m.module_type ORDER BY AVG(mg.final_score) DESC")
    return [{"group": r[0] or "(no type)", "results": r[1],
             "average": r[2] or 0.0, "lowest": r[3] or 0.0, "highest": r[4] or 0.0}
            for r in rows]


def grade_trend_by_period() -> List[Dict[str, Any]]:
    """Average final score by month, oldest first."""
    rows = _rows(
        "SELECT strftime('%Y-%m', COALESCE(completion_date, date_recorded)) AS period, "
        "       COUNT(*), AVG(final_score) "
        "FROM module_grades "
        "WHERE final_score IS NOT NULL "
        "  AND COALESCE(completion_date, date_recorded) IS NOT NULL "
        "GROUP BY period ORDER BY period")
    return [{"period": r[0], "results": r[1], "average": r[2] or 0.0}
            for r in rows if r[0]]


# --------------------------------------------------------------------------
# Curve
# --------------------------------------------------------------------------

def curve_preview(module_code: Optional[str] = None,
                  adjustment: float = 0.0) -> Dict[str, Any]:
    """What a flat *adjustment* would do, without writing anything.

    Applying a curve changes recorded marks, so the GUI shows the effect
    first and leaves the decision to a person.
    """
    sql = ("SELECT student_id, module_code, final_score, final_grade "
           "FROM module_grades WHERE final_score IS NOT NULL")
    params: tuple = ()
    if module_code:
        sql += " AND module_code = ?"
        params = (module_code,)
    rows = _rows(sql + " ORDER BY final_score", params)

    try:
        from education_system.systems.university.domains.assessment.domain.grading.curve_analysis import (
            percentage_to_letter,
        )
    except Exception:
        percentage_to_letter = None

    preview, improved = [], 0
    for student_id, mod, score, grade in rows:
        new_score = max(0.0, min(100.0, float(score) + adjustment))
        new_grade = (percentage_to_letter(new_score)
                     if callable(percentage_to_letter) else grade)
        if new_grade != grade:
            improved += 1
        preview.append({"student_id": student_id, "module_code": mod,
                        "old_score": float(score), "new_score": new_score,
                        "old_grade": grade, "new_grade": new_grade})
    return {"rows": preview, "changed": improved, "adjustment": adjustment,
            "module_code": module_code}
