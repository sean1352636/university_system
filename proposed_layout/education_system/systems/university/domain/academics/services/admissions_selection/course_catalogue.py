"""Read the live course catalogue so the student-create flow is DB-driven.

Reading from the ``courses`` table (the same table the course-management
GUI/CLI writes to) means any course an admin creates automatically appears
in the student-create menu without code changes.
"""

from __future__ import annotations

import logging

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domain.academics.services.admissions_selection.schema import (
    ensure_selection_schema,
)

logger = logging.getLogger(__name__)

# Statuses that mean "not open for new students".
_INACTIVE_STATUSES = {"inactive", "archived", "deleted", "withdrawn", "closed", "draft"}


def _coalesce(row: dict, *keys, default=None):
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return default


def list_active_courses() -> list[dict]:
    """Return active courses as dicts: code, name, duration, min_tariff.

    Deduplicates by course code (first row wins) and skips inactive statuses.
    """
    ensure_selection_schema()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM courses")
        rows = cur.fetchall()
    finally:
        conn.close()

    courses: list[dict] = []
    seen: set[str] = set()
    for r in rows:
        row = dict(r)
        status = str(_coalesce(row, "status", default="active")).strip().lower()
        if status in _INACTIVE_STATUSES:
            continue
        code = _coalesce(row, "course_code", "code")
        name = _coalesce(row, "course_name", "name", default=code)
        if not code or code in seen:
            continue
        seen.add(code)
        try:
            min_tariff = int(_coalesce(row, "min_ucas_tariff", default=0) or 0)
        except (TypeError, ValueError):
            min_tariff = 0
        courses.append({
            "code": code,
            "name": name,
            "duration": _coalesce(row, "duration", default=""),
            "min_tariff": min_tariff,
        })
    courses.sort(key=lambda c: str(c["name"]).lower())
    return courses


def get_course(course_code: str) -> dict | None:
    """Return a single active course dict by code, or None."""
    for c in list_active_courses():
        if c["code"] == course_code:
            return c
    return None
