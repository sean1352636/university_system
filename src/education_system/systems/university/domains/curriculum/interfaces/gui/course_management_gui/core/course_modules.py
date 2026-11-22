"""The modules that make up a course, for the Course Management views.

Three tables record the course -> module relationship: ``course_curriculum``
(the year-structured programme map), ``course_module_map`` (the explicit link
table the Course <-> Module Links tab writes) and ``modules.course`` (the same
relationship denormalised). ``services.bus.course_bridge`` already unions all
three into ``v_course_module_map``, so this reads through that view rather
than picking one source and silently hiding modules recorded only in another.

The view is installed on demand by ``course_bridge.ensure_views``; if that
fails, the query below still works against the denormalised ``modules.course``
column, so the tab degrades to the single best-populated source instead of
showing nothing.
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

#: Columns shown in the Modules tables, in order.
COLUMNS = ("Code", "Module", "Credits", "Semester", "Type", "Instructor", "Status")

_VIA_VIEW = """
SELECT DISTINCT
       COALESCE(NULLIF(TRIM(m.module_code), ''), v.module_code) AS code,
       COALESCE(m.module_name, '')                              AS name,
       COALESCE(m.credits, '')                                  AS credits,
       COALESCE(m.semester, '')                                 AS semester,
       COALESCE(m.module_type, '')                              AS module_type,
       COALESCE(m.instructor, '')                               AS instructor,
       CASE WHEN m.is_active IS NULL THEN ''
            WHEN m.is_active THEN 'Active' ELSE 'Inactive' END  AS status
  FROM v_course_module_map v
  LEFT JOIN modules m ON TRIM(m.module_code) = TRIM(v.module_code)
 WHERE TRIM(v.course_code) = TRIM(?)
 ORDER BY code
"""

_VIA_MODULES = """
SELECT DISTINCT
       COALESCE(NULLIF(TRIM(module_code), ''), module_id)      AS code,
       COALESCE(module_name, '')                               AS name,
       COALESCE(credits, '')                                   AS credits,
       COALESCE(semester, '')                                  AS semester,
       COALESCE(module_type, '')                               AS module_type,
       COALESCE(instructor, '')                                AS instructor,
       CASE WHEN is_active IS NULL THEN ''
            WHEN is_active THEN 'Active' ELSE 'Inactive' END    AS status
  FROM modules
 WHERE TRIM(COALESCE(course, '')) = TRIM(?)
 ORDER BY code
"""


def modules_for_course(course_code: str, conn) -> list[tuple]:
    """Rows for the Modules table of *course_code*, ordered by module code.

    Returns ``[]`` for an unmapped course — the caller renders its own empty
    state, which reads better than an empty grid.
    """
    if not course_code or conn is None:
        return []
    code = str(course_code).strip()
    if not code:
        return []

    try:
        from education_system.systems.university.services.bus import course_bridge
        if course_bridge.ensure_views(conn=conn):
            return [tuple(r) for r in conn.execute(_VIA_VIEW, (code,)).fetchall()]
    except (sqlite3.Error, ImportError, AttributeError) as exc:
        # Fall through to the denormalised source below; a missing view or an
        # unavailable bridge must not empty the tab.
        logger.debug("course bridge unavailable, using modules.course: %s", exc)

    try:
        return [tuple(r) for r in conn.execute(_VIA_MODULES, (code,)).fetchall()]
    except sqlite3.Error as exc:
        logger.warning("could not load modules for course %r: %s", code, exc)
        return []


__all__ = ["COLUMNS", "modules_for_course"]
