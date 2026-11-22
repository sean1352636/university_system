"""Who may do what in the research office, and the research audit trail.

Everyone signs in with the university's own roles (admin, staff, student).
Research jobs on top of that are held in ``research_office_roles``:

* ``research_office``    – runs the office: grants sign-off, awards, REF, roles
* ``ethics_chair``       – allocates ethics reviewers and decides applications
* ``ethics_reviewer``    – reviews applications allocated to them
* ``head_of_department`` – signs off grant applications for one department
  (``scope`` is the department name)
* ``ref_lead``           – runs REF selection for a unit of assessment
  (``scope`` is the UoA, or blank for all)
* ``tto``                – technology transfer: IP decisions, licences, revenue

Admins hold every research role. Staff are addressed by username, students
by student id.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime

from education_system.systems.university.infrastructure.database.schemas import (
    research_office_schema as schema,
)

ADMIN_ROLES = ("admin", "administrator", "superadmin")
ROLES = {
    "research_office": "Research office",
    "ethics_chair": "Ethics committee chair",
    "ethics_reviewer": "Ethics reviewer",
    "head_of_department": "Head of department",
    "ref_lead": "REF lead",
    "tto": "Technology transfer",
}
SCOPED = ("head_of_department", "ref_lead")


def ensure(conn) -> None:
    schema.apply_to_connection(conn)


def dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def one(conn, sql, params=()) -> dict | None:
    rows = dicts(conn.execute(sql, params))
    return rows[0] if rows else None


def has_table(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND "
                        "name = ?", (name,)).fetchone() is not None


def today() -> str:
    return date.today().isoformat()


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def iso_date(value, label, required=False) -> str | None:
    if value in (None, ""):
        if required:
            raise ValueError(f"{label} is required")
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10]).isoformat()
    except ValueError:
        raise ValueError(f"{label} must be YYYY-MM-DD") from None


def text(value, label, required=False) -> str | None:
    value = (str(value).strip() if value is not None else "")
    if not value:
        if required:
            raise ValueError(f"{label} is required")
        return None
    return value


def money(value, label) -> float:
    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number") from None
    if amount < 0:
        raise ValueError(f"{label} cannot be negative")
    return amount


# ── the person using the portal ─────────────────────────────────────────


@dataclass(frozen=True)
class Researcher:
    username: str
    role: str = ""
    student_id: str | None = None
    roles: frozenset = field(default_factory=frozenset)   # {(role, scope)}

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES

    @property
    def is_student(self) -> bool:
        return self.role == "student"

    @property
    def is_staff(self) -> bool:
        return bool(self.username) and not self.is_student

    def holds(self, role, scope=None) -> bool:
        if self.is_admin:
            return True
        if scope is None:
            return any(r == role for r, _ in self.roles)
        scope = str(scope or "").strip().lower()
        return any(r == role and (s == "" or s.lower() == scope) for r, s in self.roles)

    @property
    def is_office(self) -> bool:
        return self.holds("research_office")

    @property
    def chairs_ethics(self) -> bool:
        return self.holds("ethics_chair") or self.is_office

    @property
    def reviews_ethics(self) -> bool:
        return self.holds("ethics_reviewer") or self.chairs_ethics

    @property
    def is_tto(self) -> bool:
        return self.holds("tto") or self.is_office

    def heads(self, department) -> bool:
        return self.holds("head_of_department", department or "")

    def leads_ref(self, uoa=None) -> bool:
        return self.is_office or self.holds("ref_lead", uoa)

    @property
    def me(self) -> str:
        """The id this person's own records are keyed on."""
        return self.student_id if self.is_student and self.student_id else self.username


def researcher(conn, username, role, student_id=None) -> Researcher:
    """Build a :class:`Researcher` for a signed-in user."""
    ensure(conn)
    role = str(role or "").lower()
    username = str(username or "").strip()
    if role == "student" and not student_id:
        row = conn.execute("SELECT student_id FROM students WHERE student_id = ? OR "
                           "LOWER(COALESCE(email_address, '')) = LOWER(?) LIMIT 1",
                           (username, username)).fetchone()
        student_id = row[0] if row else username
    held = frozenset((r, s or "") for r, s in conn.execute(
        "SELECT role, scope FROM research_office_roles WHERE username = ?", (username,)))
    return Researcher(username=username, role=role, student_id=student_id, roles=held)


def from_user(conn, user: dict | None) -> Researcher | None:
    """From an auth ``current_user`` dict; ``None`` when nobody is signed in."""
    if not user:
        return None
    username = user.get("username") or user.get("user_id") or user.get("id")
    if not username:
        return None
    return researcher(conn, username, user.get("role"), user.get("student_id"))


def require(allowed: bool, message: str) -> None:
    if not allowed:
        raise PermissionError(message)


def require_staff(who: Researcher) -> None:
    require(who is not None and who.is_staff, "Only staff can do this")


# ── research roles ──────────────────────────────────────────────────────


def roles(conn) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT * FROM research_office_roles ORDER BY role, scope, "
                              "username"))


def grant_role(conn, who: Researcher, username, role, scope="") -> None:
    ensure(conn)
    require(who.is_admin or who.is_office, "Only the research office can assign roles")
    if role not in ROLES:
        raise ValueError(f"Unknown research role {role!r}")
    username = text(username, "Username", True)
    if not is_staff_username(conn, username):
        raise ValueError(f"No member of staff with username {username!r}")
    scope = (scope or "").strip()
    if role == "head_of_department" and not scope:
        raise ValueError("A head of department needs the department")
    conn.execute("INSERT OR IGNORE INTO research_office_roles (username, role, scope, "
                 "granted_by) VALUES (?, ?, ?, ?)", (username, role, scope, who.username))
    audit(conn, who, "role", username, "granted", {"role": role, "scope": scope})


def revoke_role(conn, who: Researcher, username, role, scope="") -> None:
    ensure(conn)
    require(who.is_admin or who.is_office, "Only the research office can remove roles")
    if not conn.execute("DELETE FROM research_office_roles WHERE username = ? AND role = ? "
                        "AND scope = ?", (username, role, scope or "")).rowcount:
        raise ValueError("That person does not hold that role")
    audit(conn, who, "role", username, "revoked", {"role": role, "scope": scope or ""})


def holders(conn, role, scope=None) -> list[str]:
    """Usernames holding ``role`` (for ``scope``, or unscoped)."""
    ensure(conn)
    if scope is None:
        rows = conn.execute("SELECT DISTINCT username FROM research_office_roles WHERE role = ?",
                            (role,))
    else:
        rows = conn.execute("SELECT DISTINCT username FROM research_office_roles WHERE role = ? "
                            "AND (scope = '' OR LOWER(scope) = LOWER(?))", (role, scope))
    return sorted(r[0] for r in rows)


# ── audit ───────────────────────────────────────────────────────────────


def audit(conn, who, entity, entity_id, action, detail=None) -> None:
    actor = who.username if isinstance(who, Researcher) else who
    conn.execute("INSERT INTO research_audit (entity, entity_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (entity, str(entity_id), action, actor,
                  json.dumps(detail, default=str) if detail else None))


def history(conn, entity, entity_id) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT at, actor, action, detail FROM research_audit WHERE "
                              "entity = ? AND entity_id = ? ORDER BY audit_id",
                              (entity, str(entity_id))))


def recent_audit(conn, limit=200) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT * FROM research_audit ORDER BY audit_id DESC LIMIT ?",
                              (int(limit),)))


# ── people ──────────────────────────────────────────────────────────────

#: Staff logins that have no ``staff`` row (the seeded ``staff`` account).
_STAFF_USERS = ("SELECT username, TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, "
                "'')) AS name, '' AS department, COALESCE(email, '') AS email FROM users WHERE "
                "LOWER(COALESCE(role, '')) NOT IN ('student', 'parent', 'applicant', '') AND "
                "COALESCE(service_account, 0) = 0")


def staff_list(conn) -> list[dict]:
    """Active staff: username, name, department, email."""
    dept = ("COALESCE((SELECT p.department FROM staff_profiles p WHERE p.user_id = s.username "
            "LIMIT 1), '')" if has_table(conn, "staff_profiles") else "''")
    rows = dicts(conn.execute(
        f"SELECT s.username, s.name, {dept} AS department, COALESCE(s.email, '') AS email "
        "FROM staff s WHERE COALESCE(s.status, 'active') <> 'inactive'"))
    known = {r["username"] for r in rows}
    for r in dicts(conn.execute(_STAFF_USERS)):
        if r["username"] not in known:
            r["department"] = department_of(conn, r["username"])
            rows.append(r)
    return sorted(rows, key=lambda r: (r["name"] or r["username"]).lower())


def person_name(conn, ref) -> str:
    """Display name for a username or student id (the id itself if unknown)."""
    if not ref:
        return "—"
    row = conn.execute("SELECT name FROM staff WHERE username = ? UNION ALL SELECT TRIM("
                       "COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) FROM users "
                       "WHERE username = ?", (ref, ref)).fetchone()
    if row and row[0]:
        return row[0]
    row = conn.execute("SELECT TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) "
                       "FROM students WHERE student_id = ?", (ref,)).fetchone()
    if row and row[0]:
        return row[0]
    return str(ref)


def department_of(conn, username) -> str:
    if has_table(conn, "staff_profiles"):
        row = conn.execute("SELECT department FROM staff_profiles WHERE user_id = ? LIMIT 1",
                           (username,)).fetchone()
        if row and row[0]:
            return row[0]
    return ""


def is_staff_username(conn, username) -> bool:
    return bool(username) and conn.execute(
        "SELECT 1 FROM staff WHERE username = ? AND COALESCE(status, 'active') <> 'inactive' "
        "UNION ALL SELECT 1 FROM users WHERE username = ? AND LOWER(COALESCE(role, '')) NOT IN "
        "('student', 'parent', 'applicant', '')", (username, username)).fetchone() is not None


def staff_ref(conn, username, label) -> str:
    username = text(username, label, True)
    if not is_staff_username(conn, username):
        raise ValueError(f"{label}: no member of staff with username {username!r}")
    return username


def notify(conn, recipients, subject, body) -> list:
    """Inbox message to each username / student id; returns e-mails to send."""
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    emails = []
    for ref in dict.fromkeys(r for r in recipients if r):
        deliver_inbox_message_on(conn, ref, subject, body)
        row = conn.execute("SELECT email FROM staff WHERE username = ? UNION ALL SELECT "
                           "email_address FROM students WHERE student_id = ? UNION ALL SELECT "
                           "email FROM users WHERE username = ?", (ref, ref, ref)).fetchone()
        if row and row[0] and "@" in row[0]:
            emails.append((row[0], subject, body))
    return emails
