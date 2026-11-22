"""Search insights for the Advanced Search window: the dashboard figures,
popular / recommended / recent searches, one student's profile for the
details window, the module catalogue export, and the schema check.

* **Dashboard** figures are counts over the students the person may see,
  plus their own saved searches, follow-ups, favourites and today's
  searches.
* **Popular searches** come from the search audit, but only searches that
  identify nobody: no free text and no condition on a name, ID, email,
  phone, address or date of birth. Anything else could reveal which
  student another member of staff looked up.
* **Recommended** searches are the ready-made ones, the shared saved
  searches people use, and the person's own most repeated searches.
* **Student profile** is the details window's "Basic information": the same
  fields and permissions as the results list.

Functions take an open connection and do not commit.
"""

from __future__ import annotations

import json
from collections import Counter

from education_system.systems.university.application.students import search
from education_system.systems.university.application.students import search_saved as saved
from education_system.systems.university.application.students.search import Viewer

IDENTIFYING = ("student_id", "name", "first_name", "last_name", "email_address", "phone",
               "personal_email", "address", "dob", "age")
SEARCH_TABLES = ("student_saved_searches", "student_search_audit", "student_report_schedules",
                 "student_search_favourites", "student_followups", "student_duplicate_reviews")


def _staff(viewer: Viewer):
    if not viewer.can_view_all:
        raise ValueError("This is for staff who can search all students")


def _count(conn, sql, args=()) -> int:
    try:
        return int(conn.execute(sql, args).fetchone()[0] or 0)
    except Exception:
        return 0


# ── dashboard ───────────────────────────────────────────────────────────


def dashboard(conn, viewer: Viewer) -> dict:
    """Quick figures for the dashboard tab."""
    search.ensure(conn)
    where, args = search._where({}, viewer)
    total = _count(conn, f"SELECT COUNT(*) FROM students s WHERE {where}", args)  # nosec B608
    by_status = conn.execute(
        f"SELECT {search._STATUS} AS st, COUNT(*) FROM students s WHERE {where} "  # nosec B608
        "GROUP BY st ORDER BY COUNT(*) DESC LIMIT 6", args).fetchall()
    me = viewer.username
    figures = {
        "students": total,
        "by_status": [(str(s or "Not recorded"), n) for s, n in by_status],
        "my_saved_searches": _count(conn, "SELECT COUNT(*) FROM student_saved_searches WHERE "
                                          "owner = ?", (me,)),
        "shared_searches": _count(conn, "SELECT COUNT(*) FROM student_saved_searches WHERE "
                                        "shared = 1"),
        "my_scheduled_reports": _count(conn, "SELECT COUNT(*) FROM student_report_schedules "
                                             "WHERE owner = ?", (me,)),
        "searches_today": _count(conn, "SELECT COUNT(*) FROM student_search_audit WHERE actor = ? "
                                       "AND action = 'search' AND at >= date('now')", (me,)),
    }
    if viewer.can_view_all:
        figures["open_followups"] = _count(conn, "SELECT COUNT(*) FROM student_followups WHERE "
                                                 "status = 'open'")
        figures["my_followups"] = _count(conn, "SELECT COUNT(*) FROM student_followups WHERE "
                                               "status = 'open' AND (assigned_to = ? OR "
                                               "created_by = ?)", (me, me))
        figures["favourites"] = _count(conn, "SELECT COUNT(*) FROM student_search_favourites "
                                             "WHERE owner = ?", (me,))
    return figures


# ── popular, recommended and recent searches ────────────────────────────


def anonymous(criteria) -> bool:
    """Does this search identify nobody (safe to show other staff)?"""
    if not isinstance(criteria, dict) or (criteria.get("text") or "").strip():
        return False
    conditions = criteria.get("conditions") or []
    return bool(conditions) and all(c.get("field") not in IDENTIFYING for c in conditions)


def _audited(conn, actor=None, days=90):
    sql = ("SELECT criteria_json FROM student_search_audit WHERE action = 'search' AND "
           "criteria_json IS NOT NULL AND at >= datetime('now', ?)")
    args: list = [f"-{int(days)} days"]
    if actor:
        sql += " AND actor = ?"
        args.append(actor)
    for (raw,) in conn.execute(sql, args):
        try:
            yield json.loads(raw)
        except (ValueError, TypeError):
            continue


def _ranked(criteria_list, limit):
    counts, examples = Counter(), {}
    for crit in criteria_list:
        key = json.dumps({"match": crit.get("match") or "all",
                          "conditions": crit.get("conditions") or [],
                          "text": crit.get("text") or ""}, sort_keys=True)
        counts[key] += 1
        examples.setdefault(key, crit)
    return [{"search": search.describe(examples[k]), "times": n, "criteria": examples[k]}
            for k, n in counts.most_common(limit)]


def popular_searches(conn, viewer: Viewer, days=90, limit=20) -> list[dict]:
    """The searches staff run most, keeping only those that identify nobody."""
    _staff(viewer)
    search.ensure(conn)
    allowed = {f.key for f in search.fields_for(viewer)}
    found = [c for c in _audited(conn, days=days) if anonymous(c)
             and all(x.get("field") in allowed for x in c.get("conditions") or [])]
    return _ranked(found, limit)


def recent_searches(conn, viewer: Viewer, limit=30) -> list[dict]:
    """The person's own recent searches, newest first, without repeats."""
    search.ensure(conn)
    out, seen = [], set()
    for rid, raw, count, at in conn.execute(
            "SELECT id, criteria_json, result_count, at FROM student_search_audit WHERE actor = ? "
            "AND action = 'search' AND criteria_json IS NOT NULL ORDER BY id DESC LIMIT 500",
            (viewer.username,)):
        try:
            crit = json.loads(raw)
        except (ValueError, TypeError):
            continue
        key = json.dumps(crit, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append({"id": rid, "search": search.describe(crit), "count": count, "at": at,
                    "criteria": crit})
        if len(out) >= limit:
            break
    return out


def recommended_searches(conn, viewer: Viewer, limit=20) -> list[dict]:
    """Ready-made searches, the shared saved searches, and your own most
    repeated searches."""
    search.ensure(conn)
    out = [{"source": "Ready-made", "name": name, "search": search.describe(crit),
            "criteria": crit} for name, crit in saved.PRESETS.items()]
    if viewer.can_view_all:
        for r in saved.saved(conn, viewer):
            if r["shared"] and r["owner"] != viewer.username:
                out.append({"source": f"Shared by {r['owner']}", "name": r["name"],
                            "search": r["summary"], "criteria": r["criteria"]})
    for r in _ranked(list(_audited(conn, actor=viewer.username, days=365)), 8):
        if r["times"] > 1:
            out.append({"source": f"You ran it {r['times']} times", "name": r["search"][:60],
                        "search": r["search"], "criteria": r["criteria"]})
    return out[:limit]


# ── one student, the module catalogue ───────────────────────────────────


def student_profile(conn, viewer: Viewer, student_id) -> dict:
    """The results-list fields of one student, as the viewer may see them."""
    criteria = {"match": "all", "conditions": [
        {"field": "student_id", "op": "equals", "value": str(student_id)}]}
    result = search.search(conn, criteria, viewer, page_size=1, audit=False)
    if not result["rows"]:
        raise ValueError(f"No student {student_id} that you may see")
    labels = {f.key: f.label for f in search.columns_for(viewer)}
    row = result["rows"][0]
    return {"student_id": row.get("student_id"), "fields": [
        (labels.get(k, k), "" if row.get(k) is None else row.get(k)) for k in labels]}


def modules_table(conn, viewer: Viewer) -> tuple[list[str], list[dict]]:
    """The module catalogue with current enrolment counts (staff)."""
    _staff(viewer)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(modules)")}
    pick = [c for c in ("module_code", "module_name", "credits", "level", "year", "semester",
                        "department", "instructor") if c in cols]
    rows = [dict(zip(pick, r)) for r in conn.execute(
        f"SELECT {', '.join('m.' + c for c in pick)} FROM modules m "  # nosec B608
        "WHERE COALESCE(TRIM(m.module_code), '') <> '' ORDER BY m.module_code")]
    enrolled = dict(conn.execute(
        "SELECT module_code, COUNT(*) FROM student_modules WHERE LOWER(COALESCE(status, "
        "'enrolled')) = 'enrolled' GROUP BY module_code").fetchall())
    for r in rows:
        r["enrolled"] = enrolled.get(r["module_code"], 0)
    search.record(conn, viewer.username, "report", None, len(rows), "module catalogue export")
    return pick + ["enrolled"], rows


def module_codes(conn) -> list[str]:
    """Module codes for pickers (blank codes left out)."""
    return [r[0] for r in conn.execute("SELECT module_code FROM modules WHERE "
                                       "COALESCE(TRIM(module_code), '') <> '' ORDER BY 1")]


# ── the database ────────────────────────────────────────────────────────


def schema_status(conn, viewer: Viewer, apply=False) -> dict:
    """Which of the search tables exist; with ``apply`` (administrators),
    create any that are missing first."""
    if viewer.role not in search.ADMIN_ROLES:
        raise ValueError("Only an administrator can check or set up the search tables")
    if apply:
        search.ensure(conn)
    present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    tables = [{"table": t, "present": t in present,
               "rows": _count(conn, f'SELECT COUNT(*) FROM "{t}"') if t in present else None}
              for t in SEARCH_TABLES + ("students", "modules", "student_modules",
                                        "module_grades", "attendance_records")]
    if apply:
        search.record(conn, viewer.username, "report", None, None, "search tables set up")
    return {"tables": tables, "missing": [t["table"] for t in tables if not t["present"]]}
