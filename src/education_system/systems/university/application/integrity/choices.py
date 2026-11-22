"""The lists behind the Academic Integrity dropdowns (GUI and CLI).

Every list is scoped to what the signed-in person may see, by the same
rules as the rest of academic integrity (``integrity_access``):

* modules — integrity officers and reviewers every module; other staff the
  modules they teach; a student the modules they are enrolled on;
* students — officers and reviewers every student; other staff the
  students enrolled on their modules; a student only themselves;
* assignments and submissions — on the modules above.

Each function takes an open connection and returns ``[(value, label)]``
pairs; labels read "value — description" so a typed filter matches either.
Nothing here writes.
"""

from __future__ import annotations

from education_system.systems.university.application.integrity import access

ENROLLED = ("Enrolled", "enrolled", "Active", "active")


def _has(conn, table) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND "
                        "name = ?", (table,)).fetchone() is not None


def _marks(items) -> str:
    return ",".join("?" * len(items)) or "NULL"


def module_scope(conn, who: access.Person) -> list[str] | None:
    """Module codes ``who`` may pick; ``None`` means every module."""
    if who.is_student:
        if not _has(conn, "student_modules"):
            return []
        return sorted({r[0] for r in conn.execute(
            "SELECT module_code FROM student_modules WHERE student_id = ? AND module_code "
            "IS NOT NULL", (who.student_id or "",))})
    return access.taught_modules(conn, who)


def modules(conn, who: access.Person) -> list[tuple]:
    scope = module_scope(conn, who)
    sql = ("SELECT module_code, COALESCE(module_name, '') FROM modules WHERE "
           "COALESCE(module_code, '') <> ''")
    params: list = []
    if scope is not None:
        sql += f" AND module_code IN ({_marks(scope)})"
        params += scope
    rows = conn.execute(sql + " ORDER BY module_code", params).fetchall()
    return [(code, f"{code} — {name}" if name else code) for code, name in rows]


def _student_rows(conn, ids=None, module_code=None):
    sql = ("SELECT s.student_id, TRIM(COALESCE(s.first_name, '') || ' ' || "
           "COALESCE(s.last_name, '')) FROM students s WHERE 1 = 1")
    params: list = []
    if ids is not None:
        sql += f" AND s.student_id IN ({_marks(ids)})"
        params += list(ids)
    if module_code and _has(conn, "student_modules"):
        sql += (" AND s.student_id IN (SELECT student_id FROM student_modules WHERE "
                f"module_code = ? AND COALESCE(status, 'Enrolled') IN ({_marks(ENROLLED)}))")
        params += [module_code, *ENROLLED]
    return conn.execute(sql + " ORDER BY s.last_name, s.first_name, s.student_id",
                        params).fetchall()


def students(conn, who: access.Person, module_code=None) -> list[tuple]:
    """``[(student number, "number — name")]``; with ``module_code`` only
    the students enrolled on it."""
    if who.is_student:
        rows = _student_rows(conn, [who.student_id or ""])
    else:
        scope = access.taught_modules(conn, who)
        if module_code and scope is not None and module_code not in scope:
            return []
        if scope is None or module_code:
            rows = _student_rows(conn, None, module_code)
        else:
            if not _has(conn, "student_modules") or not scope:
                return []
            ids = sorted({r[0] for r in conn.execute(
                f"SELECT student_id FROM student_modules WHERE module_code IN ({_marks(scope)})",
                scope)})
            rows = _student_rows(conn, ids)
    return [(sid, f"{sid} — {name}" if name else str(sid)) for sid, name in rows]


def assignments(conn, who: access.Person, module_code=None) -> list[tuple]:
    """``[(assignment id, "id — module: title")]`` on the modules ``who``
    may see (only ``module_code``'s when given)."""
    scope = module_scope(conn, who)
    sql = "SELECT id, module_code, title FROM assignments WHERE 1 = 1"
    params: list = []
    if scope is not None:
        sql += f" AND module_code IN ({_marks(scope)})"
        params += scope
    if module_code:
        sql += " AND module_code = ?"
        params.append(module_code)
    rows = conn.execute(sql + " ORDER BY module_code, title", params).fetchall()
    return [(aid, f"{aid} — {module}: {title}") for aid, module, title in rows]


def submissions(conn, who: access.Person, module_code=None, assignment_id=None) -> list[tuple]:
    """Assignment submissions staff may read: ``[(id, "id — student,
    module: assignment")]``, newest first. Students see their own."""
    sql = ("SELECT s.id, s.student_id, a.module_code, a.title FROM assignment_submissions s "
           "JOIN assignments a ON a.id = s.assignment_id WHERE 1 = 1")
    params: list = []
    if who.is_student:
        sql += " AND s.student_id = ?"
        params.append(who.student_id or "")
    else:
        scope = access.taught_modules(conn, who)
        if scope is not None:
            sql += f" AND a.module_code IN ({_marks(scope)})"
            params += scope
    if module_code:
        sql += " AND a.module_code = ?"
        params.append(module_code)
    if assignment_id:
        sql += " AND s.assignment_id = ?"
        params.append(assignment_id)
    rows = conn.execute(sql + " ORDER BY s.id DESC LIMIT 500", params).fetchall()
    out = []
    for sid, student, module, title in rows:
        label = access.student_label(conn, who, student, None) if not who.is_student else student
        out.append((sid, f"{sid} — {label}, {module}: {title}"))
    return out


def file_types(conn, who: access.Person) -> list[tuple]:
    """File types of documents ``who`` may see."""
    access.ensure(conn)
    scope = access.taught_modules(conn, who)
    sql = ("SELECT DISTINCT LOWER(file_type) FROM document_repository WHERE "
           "COALESCE(file_type, '') <> ''")
    params: list = []
    if scope is not None:
        sql += f" AND (module_code IN ({_marks(scope)}) OR kind = 'external')"
        params += scope
    return [(r[0], r[0]) for r in conn.execute(sql + " ORDER BY 1", params)]


def document_students(conn, who: access.Person) -> list[tuple]:
    """Student labels as the documents list shows them (a candidate number
    while marking is anonymous) — for the documents filter."""
    from education_system.systems.university.application.integrity import (
        plagiarism_checks as checks,
    )
    seen = sorted({str(d["student_id"]) for d in checks.documents(conn, who, limit=5000)
                   if d.get("student_id")})
    return [(s, s) for s in seen]


def document_authors(conn, who: access.Person) -> list[tuple]:
    """Usernames of staff who added reference / template documents."""
    access.ensure(conn)
    scope = access.taught_modules(conn, who)
    sql = ("SELECT DISTINCT u.username FROM document_repository d JOIN users u ON "
           "u.id = d.author_id WHERE d.kind IN ('reference', 'template', 'external')")
    params: list = []
    if scope is not None:
        sql += f" AND (d.module_code IN ({_marks(scope)}) OR d.kind = 'external')"
        params += scope
    return [(r[0], r[0]) for r in conn.execute(sql + " ORDER BY 1", params)]


def cases(conn, who: access.Person) -> list[tuple]:
    from education_system.systems.university.application.integrity import review
    return [(c["id"], f"{c['id']} — {c['student_id']}, {c['case_type']} ({c['stage']})")
            for c in review.cases(conn, who)]


def results(conn, who: access.Person, review_status=None) -> list[tuple]:
    from education_system.systems.university.application.integrity import review
    return [(r["id"], f"{r['id']} — {r['title']} ({float(r['similarity_score'] or 0):.0%}, "
                      f"{r['review_status']})")
            for r in review.results(conn, who, review_status=review_status, limit=500)]


def readings(conn, who: access.Person, flagged=False) -> list[tuple]:
    from education_system.systems.university.application.integrity import ai as integrity_ai
    rows = integrity_ai.flags(conn, who, include_reviewed=True) if flagged else \
        integrity_ai.results(conn, who)
    return [(r["id"], f"{r['id']} — {r['title'] or 'reading'} ({r['level'] or '-'})")
            for r in rows]


def documents(conn, who: access.Person, kind=None) -> list[tuple]:
    from education_system.systems.university.application.integrity import (
        plagiarism_checks as checks,
    )
    rows = checks.documents(conn, who, limit=1000)
    return [(d["id"], f"{d['id']} — {d['title']} ({d['kind']}, {d['module_code'] or '-'})")
            for d in rows if not kind or d["kind"] == kind]


def staff(conn, who: access.Person) -> list[tuple]:
    """Staff usernames (for role grants)."""
    marks = _marks(access.STAFF_ROLES)
    rows = conn.execute(
        "SELECT username, TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) "
        f"FROM users WHERE LOWER(COALESCE(role, '')) IN ({marks}) ORDER BY username",  # nosec B608
        access.STAFF_ROLES).fetchall()
    return [(u, f"{u} — {n}" if n else u) for u, n in rows]
