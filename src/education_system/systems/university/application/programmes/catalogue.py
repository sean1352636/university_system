"""The course catalogue: what the university offers and what is on each course.

A course here is a degree programme (``courses``), the way Course Management
means it. Students register for the modules on a course, so the catalogue lists
courses and then the modules of the one chosen. Numbers are live counts rather
than the stored ``courses.current_enrollment`` counter, which drifts.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from education_system.systems.university.application.programmes import course_team, record, structure
from education_system.systems.university.infrastructure.sql_safety import escape_like

_CODE = "COALESCE(NULLIF(course_code, ''), code)"
_NAME = "COALESCE(NULLIF(course_name, ''), name)"
_OFFERED = "LOWER(COALESCE(NULLIF(status, ''), 'active')) = 'active'"


def course_types(conn) -> list[str]:
    # db-audit: ignore[DBW001] - module constants only
    return [r[0] for r in conn.execute(
        f"SELECT DISTINCT course_type FROM courses WHERE {_OFFERED} "
        "AND COALESCE(course_type, '') <> '' ORDER BY course_type COLLATE NOCASE")]


def courses(conn, search="", course_type=None, student_id=None) -> list[dict]:
    """Offered courses matching *search* in the course or the modules on it."""
    # db-audit: ignore[DBW001] - module constants and placeholders only
    sql = (f"SELECT {_CODE} AS code, {_NAME} AS name, credits, COALESCE(course_type, '') AS type, "
           f"COALESCE(department, '') AS department, COALESCE(max_enrollment, 0) AS capacity "
           f"FROM courses c WHERE {_CODE} IS NOT NULL AND {_OFFERED}")
    params: list = []
    search = (search or "").strip()
    if search:
        like = f"%{escape_like(search)}%"
        sql += (f" AND ({_CODE} LIKE ? ESCAPE '\\' OR {_NAME} LIKE ? ESCAPE '\\' "
                "OR department LIKE ? ESCAPE '\\' OR EXISTS ("
                "SELECT 1 FROM course_curriculum cc JOIN modules m ON m.module_code = cc.module_code "
                "WHERE cc.course_code = COALESCE(NULLIF(c.course_code, ''), c.code) AND (m.module_code LIKE ? ESCAPE '\\' "
                "OR m.module_name LIKE ? ESCAPE '\\')))")
        params += [like] * 5
    if course_type:
        sql += " AND course_type = ?"
        params.append(course_type)
    # db-audit: ignore[DBW001] - built above from constants and placeholders
    rows = conn.execute(sql + f" ORDER BY {_CODE}", params).fetchall()
    own = course_team.course_for_student(conn, student_id) if student_id else None
    out = []
    for code, name, credits, kind, department, capacity in (tuple(r) for r in rows):
        out.append({"code": code, "name": name or "", "credits": credits or 0, "type": kind,
                    "department": department, "capacity": capacity,
                    "enrolled": record.active_students(conn, code),
                    "status": "Your course" if code == own else "Offered"})
    return out


def modules_on(conn, code, student_id=None) -> list[dict]:
    """The active modules of a course by year, with this student's status on each."""
    mine = {}
    if student_id:
        mine = {r[0]: r[1] for r in conn.execute(
            "SELECT module_code, status FROM student_modules WHERE student_id = ?",
            (student_id,))}
    enrolled = {r[0]: r[1] for r in conn.execute(
        "SELECT module_code, COUNT(*) FROM student_modules WHERE status = 'Enrolled' "
        "GROUP BY module_code")}
    kinds = {r[0]: r[1] for r in conn.execute("SELECT module_code, module_type FROM modules")}
    out = []
    for stage in structure.stages(conn, code):
        for module in stage["modules"]:
            if not module["active"]:
                continue
            out.append({"code": module["module_code"], "name": module["module_name"],
                        "year": stage.get("year") or "", "credits": module["credits"],
                        "designation": (kinds.get(module["module_code"]) or ""
                                        if module["designation"] == "not designated"
                                        else module["designation"]),
                        "enrolled": enrolled.get(module["module_code"], 0),
                        "status": mine.get(module["module_code"], "Available")})
    return out
