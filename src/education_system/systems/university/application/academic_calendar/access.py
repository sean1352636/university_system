"""Who may change the academic calendar, and the calendar audit trail.

Institution-wide dates (years, terms, key dates, closures, publishing)
belong to calendar administrators: admins, registrars, and staff given
``calendar_admin`` in ``calendar_roles``. Other staff and students read the
published calendar and manage only their own reminders and feed.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from education_system.systems.university.application.research import access as rows
from education_system.systems.university.infrastructure.database.schemas import (
    calendar_year_schema as schema,
)

ADMIN_ROLES = ("admin", "administrator", "superadmin", "registrar")
STAFF_ROLES = ("staff", "instructor", "teacher", "lecturer", "faculty", "admin", "administrator",
               "superadmin", "registrar")

dicts, one, has_table = rows.dicts, rows.one, rows.has_table
iso_date, text, today, now = rows.iso_date, rows.text, rows.today, rows.now
notify = rows.notify


def ensure(conn) -> None:
    schema.apply_to_connection(conn)


@dataclass(frozen=True)
class CalendarUser:
    username: str
    role: str = ""
    student_id: str | None = None
    calendar_admin: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES or self.calendar_admin

    @property
    def is_student(self) -> bool:
        return self.role == "student"

    @property
    def is_staff(self) -> bool:
        return self.role in STAFF_ROLES

    @property
    def audiences(self) -> tuple:
        """Event audiences this person may see (besides events naming them)."""
        if self.is_admin:
            return ("all", "public", "students", "staff", "")
        if self.is_student:
            return ("all", "public", "students", "")
        return ("all", "public", "staff", "")


def user(conn, username, role, student_id=None) -> CalendarUser:
    ensure(conn)
    role = str(role or "").lower()
    username = str(username or "").strip()
    if role == "student" and not student_id:
        row = conn.execute("SELECT student_id FROM users WHERE username = ? AND student_id IS NOT "
                           "NULL", (username,)).fetchone()
        student_id = row[0] if row else username
    held = conn.execute("SELECT 1 FROM calendar_roles WHERE username = ?",
                        (username,)).fetchone() is not None
    return CalendarUser(username=username, role=role, student_id=student_id,
                        calendar_admin=held)


def from_user(conn, current: dict | None) -> CalendarUser | None:
    if not current:
        return None
    username = current.get("username") or current.get("user_id") or current.get("id")
    if not username:
        return None
    return user(conn, username, current.get("role"), current.get("student_id"))


def require(allowed, message) -> None:
    if not allowed:
        raise PermissionError(message)


def require_admin(who) -> None:
    require(who is not None and who.is_admin,
            "Only calendar administrators can change institution-wide dates")


def grant(conn, who, username) -> None:
    ensure(conn)
    require(who is not None and who.role in ADMIN_ROLES, "Only an administrator can do this")
    username = text(username, "Username", True)
    if not rows.is_staff_username(conn, username):
        raise ValueError(f"No member of staff with username {username!r}")
    conn.execute("INSERT OR IGNORE INTO calendar_roles (username, granted_by) VALUES (?, ?)",
                 (username, who.username))
    audit(conn, who, "role", username, "granted")


def revoke(conn, who, username) -> None:
    ensure(conn)
    require(who is not None and who.role in ADMIN_ROLES, "Only an administrator can do this")
    if not conn.execute("DELETE FROM calendar_roles WHERE username = ?", (username,)).rowcount:
        raise ValueError("That person is not a calendar administrator")
    audit(conn, who, "role", username, "revoked")


def admins(conn) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT * FROM calendar_roles ORDER BY username"))


def audit(conn, who, entity, entity_id, action, detail=None) -> None:
    actor = getattr(who, "username", None) or (who if isinstance(who, str) else None)
    conn.execute("INSERT INTO calendar_audit (entity, entity_id, action, actor, detail) VALUES "
                 "(?, ?, ?, ?, ?)", (entity, str(entity_id), action, actor,
                                     json.dumps(detail, default=str) if detail else None))


def history(conn, entity=None, entity_id=None, limit=200) -> list[dict]:
    ensure(conn)
    where, params = [], []
    if entity:
        where.append("entity = ?")
        params.append(entity)
    if entity_id is not None:
        where.append("entity_id = ?")
        params.append(str(entity_id))
    return dicts(conn.execute("SELECT * FROM calendar_audit" + (" WHERE " + " AND ".join(where)
                                                                if where else "")
                              + " ORDER BY audit_id DESC LIMIT ?", (*params, int(limit))))
