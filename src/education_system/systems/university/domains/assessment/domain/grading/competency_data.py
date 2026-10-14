"""Competency framework and student attainment, without presentation.

``competency.py`` already manages all of this, but like the rest of the
grading CLI it prints as it goes and stops for ``input()``, so the GUI
could not reuse any of it. The Competencies screen in Grade Tracking
filled its table with three hard-coded rows instead — "Technical
Skills / Advanced / Portfolio Project / Dr. Smith" — which look exactly
like real records and are not.

The queries live here and return plain data, so the CLI and the GUI show
the same thing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "list_competencies", "competency_levels", "student_attainment",
    "attainment_summary", "record_attainment",
]


def _connect():
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    return get_connection()


def _rows(sql: str, params=()) -> List[Any]:
    try:
        with _connect() as conn:
            return conn.execute(sql, params).fetchall()
    except Exception:
        logger.debug("competency query failed: %s", sql, exc_info=True)
        return []


def list_competencies(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """The competency framework, with how many students hold each."""
    sql = ("SELECT c.competency_id, c.name, COALESCE(c.description, ''), "
           "       COALESCE(c.category, ''), "
           "       (SELECT COUNT(DISTINCT sc.student_id) FROM student_competencies sc "
           "        WHERE sc.competency_id = c.competency_id) AS holders "
           "FROM competencies c")
    params: tuple = ()
    if category:
        sql += " WHERE c.category = ?"
        params = (category,)
    sql += " ORDER BY c.category, c.name"
    return [{"competency_id": r[0], "name": r[1], "description": r[2],
             "category": r[3], "holders": r[4]} for r in _rows(sql, params)]


def competency_levels(competency_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Defined attainment levels, highest value first."""
    sql = ("SELECT l.level_id, l.competency_id, c.name, l.level_name, "
           "       l.level_value, COALESCE(l.description, '') "
           "FROM competency_levels l "
           "LEFT JOIN competencies c ON c.competency_id = l.competency_id")
    params: tuple = ()
    if competency_id is not None:
        sql += " WHERE l.competency_id = ?"
        params = (competency_id,)
    sql += " ORDER BY c.name, l.level_value DESC"
    return [{"level_id": r[0], "competency_id": r[1], "competency": r[2] or "",
             "level_name": r[3], "level_value": r[4], "description": r[5]}
            for r in _rows(sql, params)]


def student_attainment(student_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """What students have actually been assessed as holding."""
    sql = ("SELECT sc.student_id, "
           "       TRIM(COALESCE(s.first_name,'') || ' ' || COALESCE(s.last_name,'')), "
           "       c.name, COALESCE(l.level_name, ''), "
           "       COALESCE(sc.assessment_date, ''), COALESCE(sc.evidence, '') "
           "FROM student_competencies sc "
           "LEFT JOIN students s ON s.student_id = sc.student_id "
           "LEFT JOIN competencies c ON c.competency_id = sc.competency_id "
           "LEFT JOIN competency_levels l ON l.level_id = sc.level_id")
    params: tuple = ()
    if student_id:
        sql += " WHERE sc.student_id = ?"
        params = (student_id,)
    sql += " ORDER BY sc.assessment_date DESC, c.name"
    return [{"student_id": r[0], "student_name": r[1] or r[0], "competency": r[2] or "",
             "level": r[3], "assessed": str(r[4])[:10], "evidence": r[5]}
            for r in _rows(sql, params)]


def attainment_summary() -> Dict[str, int]:
    """Headline counts for the screen."""
    def one(sql):
        rows = _rows(sql)
        return int(rows[0][0]) if rows else 0
    return {
        "competencies": one("SELECT COUNT(*) FROM competencies"),
        "levels": one("SELECT COUNT(*) FROM competency_levels"),
        "records": one("SELECT COUNT(*) FROM student_competencies"),
        "students_assessed": one(
            "SELECT COUNT(DISTINCT student_id) FROM student_competencies"),
    }


def record_attainment(student_id: str, competency_id: int, level_id: int,
                      assessment_date: str, evidence: str = "") -> bool:
    """Record (or update) a student's attainment of one competency.

    One row per student per competency: re-assessing replaces the level
    rather than stacking a second record, which is how the CLI treats it.
    """
    try:
        with _connect() as conn:
            existing = conn.execute(
                "SELECT id FROM student_competencies "
                "WHERE student_id = ? AND competency_id = ?",
                (student_id, competency_id)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE student_competencies "
                    "SET level_id = ?, assessment_date = ?, evidence = ? WHERE id = ?",
                    (level_id, assessment_date, evidence, existing[0]))
            else:
                conn.execute(
                    "INSERT INTO student_competencies "
                    "(student_id, competency_id, level_id, assessment_date, evidence) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (student_id, competency_id, level_id, assessment_date, evidence))
            conn.commit()
        return True
    except Exception:
        logger.exception("Failed to record competency attainment for %s", student_id)
        return False
