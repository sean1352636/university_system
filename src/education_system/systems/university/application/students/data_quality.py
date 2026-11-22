"""Checks on the student records, and the fixes that are safe to apply once
someone confirms them. Every fix is written to the change history.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import re

from education_system.systems.university.application.students import record_rules as rules

STATUSES = ("Active", "Registration Pending", "Interrupted", "Withdrawn", "Deferred",
            "Suspended", "Completed", "Closed")
#: Legacy statuses with an obvious lifecycle equivalent.
LEGACY = {"graduated": "Completed", "enrolled": "Active", "inactive": None}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _courses(conn):
    rows = conn.execute("SELECT COALESCE(NULLIF(course_code, ''), code), "
                        "COALESCE(NULLIF(course_name, ''), name) FROM courses").fetchall()
    return {r[0] for r in rows if r[0]}, {str(r[1]).lower(): r[0] for r in rows if r[1]}


def _issue(kind, student, detail, fix=None):
    return {"key": f"{kind}:{student['student_id']}", "kind": kind,
            "student_id": student["student_id"],
            "name": f"{student['first_name'] or ''} {student['last_name'] or ''}".strip(),
            "detail": detail, "fix": fix}


def _course_issue(student, codes, by_name):
    course = student["course"]
    if not course or course in codes:
        return None
    code = by_name.get(str(course).lower())
    if code:
        return _issue("course", student, f"filed under the name '{course}'",
                      {"course": code})
    return _issue("course", student, f"'{course}' matches no course in the catalogue")


def _status_target(status):
    for known in STATUSES:
        if str(status or "").lower() == known.lower():
            return known
    return LEGACY.get(str(status or "").lower())


def _status_issues(student):
    out = []
    status = student["status"]
    target = status if status in STATUSES else _status_target(status)
    if status not in STATUSES:
        out.append(_issue("status", student, f"status '{status}' is not a lifecycle status",
                          {"status": target} if target else None))
    # Registration Pending is active or not depending on where provisioning
    # has got to, so it is never flagged.
    if target and target != "Registration Pending" and student["is_active"] is not None and \
            int(student["is_active"]) != int(target == "Active"):
        out.append(_issue("active_flag", student,
                          f"marked {'active' if student['is_active'] else 'inactive'} while "
                          f"{target}", {"is_active": int(target == "Active")}))
    return out


def _detail_issues(student):
    out = []
    if not student["dob"]:
        out.append(_issue("dob", student, "no date of birth"))
    if student["email_address"] and not _EMAIL.match(student["email_address"]):
        out.append(_issue("email", student, f"'{student['email_address']}' is not an email"))
    return out


def issues(conn) -> list[dict]:
    """Every problem found; ``fix`` is the change that would correct it, or
    None when a person has to decide."""
    codes, by_name = _courses(conn)
    out = []
    students = conn.execute("SELECT student_id, first_name, last_name, dob, course, status, "
                            "is_active, email_address FROM students ORDER BY student_id")
    names = [d[0] for d in students.description]
    rows = [dict(zip(names, r)) for r in students.fetchall()]
    rows = [s for s in rows if not str(s["student_id"]).startswith("ERASED-")]
    for s in rows:
        course = _course_issue(s, codes, by_name)
        out += ([course] if course else []) + _status_issues(s) + _detail_issues(s)
    out += _duplicate_issues(conn, rows)
    return out


def _duplicate_issues(conn, rows):
    out, seen = [], set()
    for s in rows:
        if s["student_id"] in seen:
            continue
        matches = rules.find_duplicates(conn, s["first_name"], s["last_name"], s["dob"],
                                        exclude=s["student_id"])
        if matches:
            seen.update(m["student_id"] for m in matches)
            out.append(_issue("duplicate", s, "same name and date of birth as "
                              + ", ".join(m["student_id"] for m in matches)))
    return out


def apply_fixes(conn, keys, actor) -> int:
    """Apply the fixes for ``keys`` (from :func:`issues`); returns how many
    records changed."""
    wanted = set(keys)
    fixes: dict[str, dict] = {}
    for issue in issues(conn):
        if issue["key"] in wanted and issue["fix"]:
            fixes.setdefault(issue["student_id"], {}).update(issue["fix"])
    for student_id, change in fixes.items():
        old = conn.execute(f"SELECT {', '.join(change)} FROM students WHERE student_id = ?",  # nosec B608
                           (student_id,)).fetchone()
        rules.record_changes(conn, student_id, dict(zip(change, old)), change,
                             "Data quality fix", actor)
        conn.execute(f"UPDATE students SET {', '.join(f'{k} = ?' for k in change)} "  # nosec B608
                     "WHERE student_id = ?", (*change.values(), student_id))
    return len(fixes)
