"""The module catalogue for students: every active module, filtered by
department, level or text, with each module's details (description,
credits, prerequisites, co-requisites, exclusions, teaching team, weekly
sessions, assessment) and how it stands for the student. Read-only:
enrolling outside a course structure stays with staff
(``module_registration.enrol`` with an override).

Functions take an open connection and do not commit.
"""

from __future__ import annotations

from education_system.systems.university.application.modules import enrolment as module_enrolment
from education_system.systems.university.application.modules.registration import (
    _dicts, _has, _states, ensure, structure, student,
)



def catalogue_filters(conn) -> dict:
    """Departments and levels to filter the catalogue by."""
    ensure(conn)
    return {
        "departments": [r[0] for r in conn.execute(
            "SELECT DISTINCT department FROM modules WHERE COALESCE(is_active, 1) = 1 AND "
            "COALESCE(department, '') <> '' ORDER BY department")],
        "levels": [r[0] for r in conn.execute(
            "SELECT DISTINCT CAST(level AS TEXT) FROM modules WHERE COALESCE(is_active, 1) = 1 "
            "AND COALESCE(level, '') <> '' ORDER BY 1")],
    }


def catalogue(conn, *, department=None, level=None, search=None, student_id=None,
              limit=500) -> list[dict]:
    """Active modules, filtered; with ``student_id`` each row also says how
    the module stands for that student (in their structure, enrolled …)."""
    ensure(conn)
    sql = ("SELECT module_code, module_name, NULLIF(credits, 0) AS credits, department, level, "
           "semester, module_type FROM modules WHERE COALESCE(is_active, 1) = 1 AND "
           "COALESCE(module_code, '') <> ''")
    params: list = []
    if department:
        sql += " AND department = ?"
        params.append(department)
    if level:
        sql += " AND CAST(level AS TEXT) = ?"
        params.append(str(level))
    if search and str(search).strip():
        term = f"%{str(search).strip()}%"
        sql += " AND (module_code LIKE ? OR module_name LIKE ? OR COALESCE(description, '') LIKE ?)"
        params += [term, term, term]
    rows = _dicts(conn.execute(sql + " ORDER BY module_code LIMIT ?", params + [int(limit)]))
    if student_id:
        standing = _catalogue_standing(conn, student_id)
        for r in rows:
            r["for_you"] = standing.get(r["module_code"], "")
    return rows


def _catalogue_standing(conn, student_id) -> dict:
    s = student(conn, student_id)
    out = {}
    if s["course"]:
        plan = structure(conn, s["course"], s["year_of_study"])
        for kind in ("compulsory", "optional"):
            for m in plan[kind]:
                out[m["code"]] = f"{kind} on your course"
    for code, state in _states(conn, s["student_id"]).items():
        if state:
            out[code] = state.lower() if code not in out else f"{out[code]} · {state.lower()}"
    return out


def _requisites(conn, code) -> list[dict]:
    if not _has(conn, "degree_course_prerequisites"):
        return []
    return [{"module_code": r[0], "min_grade": r[1], "corequisite": bool(r[2])}
            for r in conn.execute(
                "SELECT prerequisite_module_code, min_grade, COALESCE(is_corequisite, 0) FROM "
                "degree_course_prerequisites WHERE module_code = ?", (code,))]


def _team(conn, code, instructor) -> list[dict]:
    team = []
    if _has(conn, "module_staff"):
        team = [{"name": r[0], "role": r[1]} for r in conn.execute(
            "SELECT COALESCE(NULLIF(TRIM(COALESCE(u.first_name, '') || ' ' || "
            "COALESCE(u.last_name, '')), ''), ms.username), COALESCE(ms.role, 'teaching') FROM "
            "module_staff ms LEFT JOIN users u ON u.username = ms.username COLLATE NOCASE "
            "WHERE ms.module_code = ? ORDER BY ms.role, ms.username", (code,))]
    if not team and instructor:
        team = [{"name": instructor, "role": "module leader"}]
    return team


def _sessions(conn, code) -> list[dict]:
    if not _has(conn, "module_schedule"):
        return []
    return [{"day": r[0], "start": r[1], "end": r[2], "type": r[3]} for r in conn.execute(
        "SELECT day_of_week, start_time, end_time, COALESCE(session_type, '') FROM "
        "module_schedule WHERE module_code = ? AND COALESCE(status, 'active') <> 'cancelled' "
        "ORDER BY day_of_week, start_time", (code,))]


def _assessment(conn, code) -> list[dict]:
    if _has(conn, "module_assessment_plan"):
        plan = [{"component": r[0], "type": r[1], "weight": r[2], "size": r[3]}
                for r in conn.execute("SELECT component, assessment_type, weight, size FROM "
                                      "module_assessment_plan WHERE module_code = ? ORDER BY "
                                      "sort_order, id", (code,))]
        if plan:
            return plan
    if not _has(conn, "assignments"):
        return []
    cols = {c[1] for c in conn.execute("PRAGMA table_info(assignments)")}
    weight = "weight" if "weight" in cols else "NULL"
    return [{"component": r[0], "type": "assignment", "weight": r[1], "size": None}
            for r in conn.execute(f"SELECT title, {weight} FROM assignments "  # nosec B608
                                  "WHERE module_code = ? ORDER BY id", (code,))]


def module_details(conn, code, student_id=None) -> dict:
    """Everything a student needs to judge a module: description, credits,
    level, prerequisites / co-requisites / exclusions, who teaches it, when
    it runs, how it is assessed, and how it stands for ``student_id``."""
    ensure(conn)
    rows = _dicts(conn.execute("SELECT * FROM modules WHERE module_code = ?", (code,)))
    if not rows:
        raise ValueError(f"No module {code}")
    m = rows[0]
    out = {k: m.get(k) for k in ("module_code", "module_name", "description", "credits",
                                 "level", "semester", "department", "module_type", "capacity",
                                 "instructor")}
    requisites = _requisites(conn, code)
    out["prerequisites"] = [p for p in requisites if not p["corequisite"]]
    out["corequisites"] = [p for p in requisites if p["corequisite"]]
    out["prerequisite_note"] = (m.get("prerequisites") or "").strip() or None
    out["exclusions"] = [e["other"] for e in module_enrolment.exclusions(conn, code)]
    out["team"] = _team(conn, code, m.get("instructor"))
    out["sessions"] = _sessions(conn, code)
    out["assessment"] = _assessment(conn, code)
    out["enrolled"] = conn.execute("SELECT COUNT(*) FROM student_modules WHERE module_code = ? "
                                   "AND status = 'Enrolled'", (code,)).fetchone()[0]
    if student_id:
        out["for_you"] = _catalogue_standing(conn, student_id).get(code) or (
            "not part of your course structure - ask your personal tutor or the Registry to "
            "enrol you (staff can add it with a reason)")
    return out


def details_text(d) -> str:
    """:func:`module_details` as plain text (the portal's dialog and the CLI)."""
    def listing(items, fmt):
        return "\n".join("  • " + fmt(i) for i in items) if items else "  none"
    lines = [f"{d['module_code']} — {d['module_name'] or ''}", "",
             f"Credits: {d['credits'] or 'not recorded'}    Level: {d['level'] or '—'}    "
             f"Semester: {d['semester'] or '—'}",
             f"Department: {d['department'] or '—'}    Type: {d['module_type'] or '—'}    "
             f"Enrolled: {d['enrolled']}" + (f" / {d['capacity']}" if d.get("capacity") else ""),
             ""]
    if d.get("for_you"):
        lines += [f"For you: {d['for_you']}", ""]
    lines += ["Description", "  " + (d["description"] or "No description recorded."), "",
              "Prerequisites", listing(d["prerequisites"], lambda p: p["module_code"] + (
                  f" (grade {p['min_grade']}+)" if p.get("min_grade") else ""))]
    if d.get("prerequisite_note"):
        lines.append(f"  Note: {d['prerequisite_note']}")
    lines += ["", "Co-requisites", listing(d["corequisites"], lambda p: p["module_code"]),
              "", "Cannot be taken with", listing(d["exclusions"], str),
              "", "Teaching team", listing(d["team"], lambda t: f"{t['name']} ({t['role']})"),
              "", "Weekly sessions", listing(d["sessions"], lambda s: f"{s['day']} "
                                             f"{s['start']}–{s['end']} {s['type']}".strip()),
              "", "Assessment", listing(d["assessment"], lambda a: f"{a['component']} "
                                        f"({a['type']})" + (f" — {a['weight']}%"
                                                             if a.get("weight") else ""))]
    return "\n".join(lines)
