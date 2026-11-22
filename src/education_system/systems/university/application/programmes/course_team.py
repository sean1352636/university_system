"""A course's (programme's) people: the active students filed under it and
its course team - a leader and members, plus the leaders of the course's
modules. Course evaluation uses these to decide who is invited and who may
read results.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from education_system.systems.university.infrastructure.database.schemas import (
    course_evaluation_schema as schema,
)

_INACTIVE = ("withdrawn", "graduated", "completed", "inactive", "suspended", "transferred",
             "merged")


def ensure(conn):
    schema.apply_to_connection(conn)


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _one(conn, sql, params=()):
    rows = _dicts(conn.execute(sql, params))
    return rows[0] if rows else None


def _columns(conn, table):
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}

def course(conn, code) -> dict:
    row = _one(conn, "SELECT COALESCE(NULLIF(course_code, ''), code) AS code, "
                     "COALESCE(NULLIF(course_name, ''), name) AS name, department FROM courses "
                     "WHERE COALESCE(NULLIF(course_code, ''), code) = ?", (code,))
    if not row:
        raise ValueError(f"No course {code}")
    return row


def courses(conn) -> list[dict]:
    return _dicts(conn.execute(
        "SELECT COALESCE(NULLIF(course_code, ''), code) AS code, "
        "COALESCE(NULLIF(course_name, ''), name) AS name, department FROM courses WHERE "
        "COALESCE(NULLIF(course_code, ''), code) IS NOT NULL ORDER BY 1"))


def _names(conn, code):
    c = course(conn, code)
    return [v for v in (c["code"], c["name"]) if v]


def _active_clause(conn):
    cols = _columns(conn, "students")
    clause = ""
    if "is_active" in cols:
        clause += " AND COALESCE(is_active, 1) = 1"
    if "status" in cols:
        clause += (" AND LOWER(COALESCE(status, 'active')) NOT IN ("
                   + ", ".join(f"'{s}'" for s in _INACTIVE) + ")")
    return clause


def students_on(conn, code) -> list[str]:
    """Active students filed under the course's code or name."""
    names = _names(conn, code)
    marks = ", ".join("?" for _ in names)
    # db-audit: ignore[DBW001] - placeholders and literal clauses only
    return [str(r[0]) for r in conn.execute(
        f"SELECT student_id FROM students WHERE course IN ({marks}){_active_clause(conn)} "
        f"ORDER BY student_id", names)]


def course_for_student(conn, student_id):
    """The course code an active student is on, or None."""
    # db-audit: ignore[DBW001] - literal clause only
    row = conn.execute(f"SELECT course FROM students WHERE student_id = ?{_active_clause(conn)}",
                       (str(student_id),)).fetchone()
    if not row or not row[0]:
        return None
    match = conn.execute("SELECT COALESCE(NULLIF(course_code, ''), code) FROM courses WHERE "
                         "COALESCE(NULLIF(course_code, ''), code) = ? OR "
                         "COALESCE(NULLIF(course_name, ''), name) = ?", (row[0], row[0])).fetchone()
    return match[0] if match else None


def leader(conn, code):
    ensure(conn)
    row = conn.execute("SELECT username FROM course_team WHERE course_code = ? AND "
                       "role = 'leader'", (code,)).fetchone()
    return row[0] if row else None


def _staff_user(conn, username):
    username = (username or "").strip()
    if not username or not conn.execute("SELECT 1 FROM users WHERE username = ? COLLATE NOCASE "
                                        "AND LOWER(COALESCE(role, '')) <> 'student'",
                                        (username,)).fetchone():
        raise ValueError(f"{username or 'That user'} is not a member of staff")
    return username


def set_team_member(conn, code, username, role="member", actor=None):
    """Add someone to the course team; a new leader replaces the old one
    (who stays on the team)."""
    ensure(conn)
    course(conn, code)
    username = _staff_user(conn, username)
    if role not in ("leader", "member"):
        raise ValueError("Role must be leader or member")
    if role == "leader":
        conn.execute("UPDATE course_team SET role = 'member' WHERE course_code = ? AND "
                     "role = 'leader'", (code,))
    conn.execute("INSERT INTO course_team (course_code, username, role, added_by) VALUES "
                 "(?, ?, ?, ?) ON CONFLICT (course_code, username) DO UPDATE SET "
                 "role = excluded.role", (code, username, role, actor))


def remove_team_member(conn, code, username):
    ensure(conn)
    conn.execute("DELETE FROM course_team WHERE course_code = ? AND username = ?",
                 (code, username))


def team(conn, code) -> list[dict]:
    """The course team plus the leaders of the course's modules."""
    from education_system.systems.university.application.modules import delivery as module_delivery
    ensure(conn)
    people = {r["username"]: r["role"] for r in _dicts(conn.execute(
        "SELECT username, role FROM course_team WHERE course_code = ?", (code,)))}
    names = _names(conn, code)
    marks = ", ".join("?" for _ in names)
    for (module_code,) in conn.execute(f"SELECT module_code FROM modules WHERE course IN "
                                       f"({marks})", names).fetchall():
        who = module_delivery.leader(conn, module_code)
        if who and who not in people:
            people[who] = "module leader"
    out = []
    for username, role in sorted(people.items()):
        row = conn.execute("SELECT TRIM(COALESCE(first_name, '') || ' ' || "
                           "COALESCE(last_name, '')) FROM users WHERE username = ?",
                           (username,)).fetchone()
        out.append({"username": username, "role": role,
                    "name": (row[0] if row and row[0] else username)})
    return out


def access(conn, code, viewer, admin=False):
    """'admin' / 'leader' / 'team', or None."""
    if admin:
        return "admin"
    if viewer and viewer == leader(conn, code):
        return "leader"
    if viewer and viewer in {p["username"] for p in team(conn, code)}:
        return "team"
    return None


def _require_leader(conn, code, actor, admin):
    if access(conn, code, actor, admin) not in ("admin", "leader"):
        raise ValueError("Only the course leader or an admin can do that")
