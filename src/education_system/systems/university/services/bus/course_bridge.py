"""The join between the two course models — programmes and taught modules.

The university carries two parallel structures that never met:

* ``courses`` (21 rows) is really a **programme** catalogue: ``CS`` /
  "Computer Science", 360 credits, ``max_enrollment`` 120. ``course_sections``
  and ``course_schedule`` hang off it.
* ``modules`` (388 rows) is the **taught unit** catalogue: ``ACC-Y1-1`` and
  friends. ``student_modules`` and ``module_enrolments`` hang off *that*, and
  that is what a student actually registers for.

``course_curriculum`` (360 rows, 20 of the 21 courses) and ``modules.course``
already record which modules make up a course, but nothing consulted them, so
readers joined the two universes on code equality:

    LEFT JOIN student_modules sm ON sm.module_code = COALESCE(c.course_code, c.code)

That matches **0 of 198** enrolments — a course code is never a module code —
so every capacity/fill-rate report read zero enrolled against a real capacity.

This module owns the mapping and the occupancy arithmetic so there is one
answer to "how many students are on this course", and exposes it as SQL views
as well as functions, because most readers are inline queries rather than
Python calls.

Occupancy vocabulary
--------------------
``headcount``   distinct students taking at least one module of the course —
                the number to compare against ``courses.max_enrollment``.
``enrolments``  module-enrolment rows for the course; a student taking six
                modules counts six times. Useful for teaching load, wrong for
                capacity.

Column drift
------------
``courses`` carries three duplicate pairs from an unfinished rename —
``code``/``course_code``, ``name``/``course_name``, ``credits``/
``credit_hours`` — with nothing keeping them equal (2 of 21 rows disagree
today). ``reconcile_course_columns`` reports and repairs the drift, and
``install_course_column_sync`` adds triggers so new writes cannot re-introduce
it whichever column the writer happens to use.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from education_system.systems.university.infrastructure.database.db import (
    sqlite3,
    get_connection,
)

logger = logging.getLogger(__name__)

#: The canonical code expression for a course row: the rename left two columns.
COURSE_CODE_SQL = "COALESCE(NULLIF(TRIM(c.course_code), ''), c.code)"

#: Duplicate column pairs on ``courses``: (canonical, legacy alias).
COURSE_COLUMN_PAIRS: tuple[tuple[str, str], ...] = (
    ("course_code", "code"),
    ("course_name", "name"),
    ("credit_hours", "credits"),
)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

#: Course -> module mapping, from all three recorded sources.
#:
#: ``course_curriculum`` is the year-structured programme map;
#: ``course_module_map`` is the explicit link table the Course ⇄ Module Links
#: tab writes (and it carries ``link_source``, so an inferred link is
#: distinguishable from one a person made); ``modules.course`` carries the
#: same relationship denormalised. A module recorded in only one of them must
#: not be invisible, so all three are unioned.
_V_COURSE_MODULE_MAP = """
CREATE VIEW IF NOT EXISTS v_course_module_map AS
SELECT DISTINCT TRIM(course_code) AS course_code, TRIM(module_code) AS module_code
  FROM course_curriculum
 WHERE COALESCE(TRIM(course_code), '') <> ''
   AND COALESCE(TRIM(module_code), '') <> ''
UNION
SELECT DISTINCT TRIM(course_code) AS course_code, TRIM(module_code) AS module_code
  FROM course_module_map
 WHERE COALESCE(TRIM(course_code), '') <> ''
   AND COALESCE(TRIM(module_code), '') <> ''
UNION
SELECT DISTINCT TRIM(course) AS course_code, TRIM(module_code) AS module_code
  FROM modules
 WHERE COALESCE(TRIM(course), '') <> ''
   AND COALESCE(TRIM(module_code), '') <> ''
"""

#: Which programme a student is registered on.
#:
#: ``students.course`` is free text: mostly a course code ('CS', 'DS') but
#: sometimes the course's name ('Computer Science'). Both are resolved here so
#: occupancy can tell a CS student from a DS student taking the same shared
#: module. Students whose value matches nothing resolve to NULL and are
#: counted wherever they are enrolled.
_V_STUDENT_COURSE = """
CREATE VIEW IF NOT EXISTS v_student_course AS
SELECT s.student_id AS student_id,
       COALESCE(
           (SELECT COALESCE(NULLIF(TRIM(c.course_code), ''), c.code) FROM courses c
             WHERE UPPER(TRIM(COALESCE(NULLIF(TRIM(c.course_code), ''), c.code)))
                   = UPPER(TRIM(s.course)) LIMIT 1),
           (SELECT COALESCE(NULLIF(TRIM(c.course_code), ''), c.code) FROM courses c
             WHERE UPPER(TRIM(COALESCE(NULLIF(TRIM(c.course_name), ''), c.name)))
                   = UPPER(TRIM(s.course)) LIMIT 1)
       ) AS course_code
FROM students s
WHERE COALESCE(TRIM(s.course), '') <> ''
"""

#: One row per course with its real occupancy against its declared capacity.
#:
#: ``headcount`` is programme-attributed: a module shared between two courses
#: (CIS0001 is taught to both Computer Science and Data Science) would
#: otherwise count every one of its students against *both* capacities. A
#: student registered on another programme is therefore excluded, while a
#: student whose programme is unrecorded still counts wherever they enrol.
#: ``enrolments`` is deliberately unfiltered — for teaching volume, everyone
#: sitting in the room counts, whichever programme they are on.
_V_COURSE_OCCUPANCY = """
CREATE VIEW IF NOT EXISTS v_course_occupancy AS
SELECT
    c.id AS course_id,
    COALESCE(NULLIF(TRIM(c.course_code), ''), c.code) AS course_code,
    COALESCE(c.max_enrollment, 0) AS capacity,
    (SELECT COUNT(DISTINCT sm.student_id)
       FROM student_modules sm
       JOIN v_course_module_map m ON m.module_code = sm.module_code
       LEFT JOIN v_student_course sc ON sc.student_id = sm.student_id
      WHERE m.course_code = COALESCE(NULLIF(TRIM(c.course_code), ''), c.code)
        AND sm.status = 'Enrolled'
        AND (sc.course_code IS NULL
             OR sc.course_code = COALESCE(NULLIF(TRIM(c.course_code), ''), c.code))
      ) AS headcount,
    (SELECT COUNT(*)
       FROM student_modules sm
       JOIN v_course_module_map m ON m.module_code = sm.module_code
      WHERE m.course_code = COALESCE(NULLIF(TRIM(c.course_code), ''), c.code)
        AND sm.status = 'Enrolled') AS enrolments,
    (SELECT COUNT(DISTINCT m.module_code)
       FROM v_course_module_map m
      WHERE m.course_code = COALESCE(NULLIF(TRIM(c.course_code), ''), c.code)) AS module_count
FROM courses c
"""

#: Per-module occupancy, the unit registration actually writes against.
_V_MODULE_OCCUPANCY = """
CREATE VIEW IF NOT EXISTS v_module_occupancy AS
SELECT
    m.module_code AS module_code,
    m.module_name AS module_name,
    CASE WHEN COALESCE(m.capacity, 0) > 0 THEN m.capacity ELSE NULL END AS capacity,
    (SELECT COUNT(*) FROM student_modules sm
      WHERE sm.module_code = m.module_code AND sm.status = 'Enrolled') AS enrolled
FROM modules m
"""

_VIEWS = (_V_COURSE_MODULE_MAP, _V_STUDENT_COURSE, _V_COURSE_OCCUPANCY,
          _V_MODULE_OCCUPANCY)

#: Bump when a view definition changes: the installer drops and recreates on
#: mismatch, since ``CREATE VIEW IF NOT EXISTS`` will not update an existing one.
#: v2 added ``course_module_map`` as a mapping source and made ``headcount``
#: programme-attributed, so shared modules stop double-counting.
_VIEW_VERSION = 2
_VIEW_NAMES = ("v_course_module_map", "v_student_course", "v_course_occupancy",
               "v_module_occupancy")


def install_views(conn=None) -> bool:
    """Create (or refresh) the bridge views. Idempotent; safe on every launch.

    Returns True when the views are present afterwards. Never raises: a reader
    that cannot install them falls back to its own SQL.
    """
    own = conn is None
    try:
        if own:
            conn = get_connection()
        current = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='view' AND name IN "
            "(" + ",".join(f"'{n}'" for n in _VIEW_NAMES) + ")"
        ).fetchone()[0]
        stored = _stored_view_version(conn)
        if current == len(_VIEW_NAMES) and stored == _VIEW_VERSION:
            return True
        for name in _VIEW_NAMES:
            conn.execute(f"DROP VIEW IF EXISTS {name}")
        for ddl in _VIEWS:
            conn.execute(ddl)
        _store_view_version(conn, _VIEW_VERSION)
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("course bridge view install failed: %s", exc)
        return False
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


def _stored_view_version(conn) -> Optional[int]:
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS course_bridge_meta ("
            "  key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        row = conn.execute(
            "SELECT value FROM course_bridge_meta WHERE key = 'view_version'"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return None


def _store_view_version(conn, version: int) -> None:
    conn.execute(
        "INSERT INTO course_bridge_meta (key, value) VALUES ('view_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(version),),
    )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def modules_for_course(course_code: str, *, conn=None) -> list[str]:
    """Module codes that make up *course_code* (empty when unmapped)."""
    if not course_code:
        return []
    rows = _query(
        "SELECT DISTINCT module_code FROM v_course_module_map "
        "WHERE course_code = ? ORDER BY module_code",
        (course_code.strip(),), conn=conn, ensure_views=True,
    )
    return [r[0] for r in rows]


def courses_for_module(module_code: str, *, conn=None) -> list[str]:
    """Every course that teaches *module_code*.

    Usually one, but shared teaching is real: CIS0001 is taught to both
    Computer Science and Data Science, so a module genuinely belongs to more
    than one programme.
    """
    if not module_code:
        return []
    rows = _query(
        "SELECT DISTINCT course_code FROM v_course_module_map "
        "WHERE module_code = ? ORDER BY course_code",
        (module_code.strip(),), conn=conn, ensure_views=True,
    )
    return [r[0] for r in rows]


def course_for_module(module_code: str, *, conn=None) -> Optional[str]:
    """The course a module belongs to, or None when the module is unmapped.

    A shared module belongs to several; this returns the first alphabetically
    and is only appropriate where one answer is needed (a label, a heading).
    Use ``courses_for_module`` wherever all of them matter — counting, for
    one, which is why occupancy uses the mapping view directly.
    """
    courses = courses_for_module(module_code, conn=conn)
    return courses[0] if courses else None


def course_occupancy(course_code: str, *, conn=None) -> dict[str, Any]:
    """Occupancy for one course: headcount, enrolments, capacity, fill rate."""
    empty = {"course_code": course_code, "capacity": 0, "headcount": 0,
             "enrolments": 0, "module_count": 0, "fill_rate": None}
    if not course_code:
        return empty
    rows = _query(
        "SELECT course_code, capacity, headcount, enrolments, module_count "
        "FROM v_course_occupancy WHERE course_code = ?",
        (course_code.strip(),), conn=conn, ensure_views=True,
    )
    if not rows:
        return empty
    code, capacity, headcount, enrolments, module_count = rows[0]
    return {
        "course_code": code,
        "capacity": capacity or 0,
        "headcount": headcount or 0,
        "enrolments": enrolments or 0,
        "module_count": module_count or 0,
        "fill_rate": (headcount / capacity * 100) if capacity else None,
    }


def module_occupancy(module_code: str, *, conn=None) -> dict[str, Any]:
    """Occupancy for one module: enrolled against its own capacity."""
    empty = {"module_code": module_code, "capacity": None, "enrolled": 0,
             "course_code": None, "full": False}
    if not module_code:
        return empty
    rows = _query(
        "SELECT module_code, capacity, enrolled FROM v_module_occupancy "
        "WHERE module_code = ?",
        (module_code.strip(),), conn=conn, ensure_views=True,
    )
    if not rows:
        return empty
    code, capacity, enrolled = rows[0]
    return {
        "module_code": code,
        "capacity": capacity,
        "enrolled": enrolled or 0,
        "course_code": course_for_module(code, conn=conn),
        "full": bool(capacity) and (enrolled or 0) >= capacity,
    }


def course_occupancy_map(*, conn=None) -> dict[str, dict[str, Any]]:
    """Every course's occupancy in one pass, keyed by course code."""
    rows = _query(
        "SELECT course_code, capacity, headcount, enrolments, module_count "
        "FROM v_course_occupancy ORDER BY course_code",
        conn=conn, ensure_views=True,
    )
    out: dict[str, dict[str, Any]] = {}
    for code, capacity, headcount, enrolments, module_count in rows:
        out[code] = {
            "course_code": code,
            "capacity": capacity or 0,
            "headcount": headcount or 0,
            "enrolments": enrolments or 0,
            "module_count": module_count or 0,
            "fill_rate": (headcount / capacity * 100) if capacity else None,
        }
    return out


def unmapped_modules(*, conn=None) -> list[str]:
    """Modules that belong to no course — enrolments there reach no report."""
    rows = _query(
        "SELECT m.module_code FROM modules m "
        "LEFT JOIN v_course_module_map v ON v.module_code = m.module_code "
        "WHERE v.module_code IS NULL AND COALESCE(TRIM(m.module_code), '') <> '' "
        "ORDER BY m.module_code",
        conn=conn, ensure_views=True,
    )
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Duplicate column drift
# ---------------------------------------------------------------------------

def find_column_drift(*, conn=None) -> list[dict[str, Any]]:
    """Rows where a duplicate column pair disagrees."""
    clauses = " OR ".join(
        f"COALESCE(TRIM(CAST({a} AS TEXT)), '') <> COALESCE(TRIM(CAST({b} AS TEXT)), '')"
        for a, b in COURSE_COLUMN_PAIRS
    )
    cols = ", ".join(f"{a}, {b}" for a, b in COURSE_COLUMN_PAIRS)
    rows = _query(f"SELECT id, {cols} FROM courses WHERE {clauses}", conn=conn)
    out = []
    for row in rows:
        entry: dict[str, Any] = {"id": row[0], "pairs": {}}
        for i, (a, b) in enumerate(COURSE_COLUMN_PAIRS):
            canonical, legacy = row[1 + i * 2], row[2 + i * 2]
            if str(canonical or "").strip() != str(legacy or "").strip():
                entry["pairs"][a] = {"canonical": canonical, "legacy": legacy}
        out.append(entry)
    return out


def reconcile_course_columns(*, apply: bool = False, conn=None) -> dict[str, Any]:
    """Report drift between the duplicate pairs, and optionally repair it.

    The canonical column wins (``course_code``/``course_name``/
    ``credit_hours``) unless it is empty, in which case the legacy value is
    promoted rather than blanked. Pass ``apply=True`` to write.
    """
    drift = find_column_drift(conn=conn)
    result = {"drifted": len(drift), "rows": drift, "applied": False}
    if not drift or not apply:
        return result

    own = conn is None
    try:
        if own:
            conn = get_connection()
        for entry in drift:
            sets, params = [], []
            for canonical, legacy in COURSE_COLUMN_PAIRS:
                sets.append(
                    f"{canonical} = COALESCE(NULLIF(TRIM(CAST({canonical} AS TEXT)), ''), {legacy})"
                )
                sets.append(
                    f"{legacy} = COALESCE(NULLIF(TRIM(CAST({canonical} AS TEXT)), ''), {legacy})"
                )
            conn.execute(f"UPDATE courses SET {', '.join(sets)} WHERE id = ?",
                         (*params, entry["id"]))
        conn.commit()
        result["applied"] = True
    except Exception as exc:
        logger.warning("course column reconcile failed: %s", exc)
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
    return result


def install_course_column_sync(conn=None) -> bool:
    """Add triggers keeping each duplicate pair equal on INSERT and UPDATE.

    Writers are split across the CLI, the GUI and the CSV importer, and they
    do not agree on which column of a pair to write. Rather than find and fix
    every writer, the pairs are kept equal in the database: whichever side a
    writer sets, the other follows.
    """
    own = conn is None
    try:
        if own:
            conn = get_connection()
        for canonical, legacy in COURSE_COLUMN_PAIRS:
            for name, changed, mirrored in (
                (f"trg_courses_sync_{canonical}", canonical, legacy),
                (f"trg_courses_sync_{legacy}", legacy, canonical),
            ):
                conn.execute(f"DROP TRIGGER IF EXISTS {name}")
                conn.execute(f"""
                    CREATE TRIGGER {name}
                    AFTER UPDATE OF {changed} ON courses
                    FOR EACH ROW
                    WHEN COALESCE(TRIM(CAST(NEW.{changed} AS TEXT)), '')
                      <> COALESCE(TRIM(CAST(NEW.{mirrored} AS TEXT)), '')
                    BEGIN
                        UPDATE courses SET {mirrored} = NEW.{changed}
                         WHERE id = NEW.id;
                    END
                """)
            insert_trigger = f"trg_courses_sync_insert_{canonical}"
            conn.execute(f"DROP TRIGGER IF EXISTS {insert_trigger}")
            conn.execute(f"""
                CREATE TRIGGER {insert_trigger}
                AFTER INSERT ON courses
                FOR EACH ROW
                WHEN COALESCE(TRIM(CAST(NEW.{canonical} AS TEXT)), '')
                  <> COALESCE(TRIM(CAST(NEW.{legacy} AS TEXT)), '')
                BEGIN
                    UPDATE courses
                       SET {canonical} = COALESCE(NULLIF(TRIM(CAST(NEW.{canonical} AS TEXT)), ''), NEW.{legacy}),
                           {legacy}    = COALESCE(NULLIF(TRIM(CAST(NEW.{canonical} AS TEXT)), ''), NEW.{legacy})
                     WHERE id = NEW.id;
                END
            """)
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("course column sync trigger install failed: %s", exc)
        return False
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _query(sql: str, params: tuple = (), *, conn=None, ensure_views: bool = False):
    """Run a read query, opening a connection when the caller passed none."""
    own = conn is None
    try:
        if own:
            conn = get_connection()
        if ensure_views:
            install_views(conn)
        return conn.execute(sql, params).fetchall()
    except Exception as exc:
        logger.warning("course bridge query failed: %s", exc)
        return []
    finally:
        if own and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
