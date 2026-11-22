"""Who may do what in graduation, and the graduation audit trail.

* admins and users whose university role is ``registrar`` run graduation;
* ``graduation_roles`` grants staff ``graduation_office`` (everything an
  admin can do in graduation) or ``ceremony_staff`` (check graduands in on
  the day);
* students see and manage only their own graduation.

Any other member of staff (an instructor, say) has no graduation access.
Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from education_system.systems.university.application.research import access as rows
from education_system.systems.university.infrastructure.database.schemas import (
    graduation_schema as schema,
)

OFFICE_ROLES = ("admin", "administrator", "superadmin", "registrar")
ROLES = {"graduation_office": "Graduation office", "ceremony_staff": "Ceremony staff"}

# shared row helpers
dicts, one, has_table = rows.dicts, rows.one, rows.has_table
iso_date, text, money, today, now = rows.iso_date, rows.text, rows.money, rows.today, rows.now
notify, person_name = rows.notify, rows.person_name


def ensure(conn) -> None:
    schema.apply_to_connection(conn)


@dataclass(frozen=True)
class Officer:
    username: str
    role: str = ""
    student_id: str | None = None
    roles: frozenset = field(default_factory=frozenset)

    @property
    def is_student(self) -> bool:
        return self.role == "student"

    @property
    def is_office(self) -> bool:
        return self.role in OFFICE_ROLES or "graduation_office" in self.roles

    @property
    def can_check_in(self) -> bool:
        return self.is_office or "ceremony_staff" in self.roles

    @property
    def has_access(self) -> bool:
        return self.is_student or self.can_check_in


def officer(conn, username, role, student_id=None) -> Officer:
    ensure(conn)
    role = str(role or "").lower()
    username = str(username or "").strip()
    if role == "student" and not student_id:
        row = conn.execute("SELECT student_id FROM students WHERE student_id = ?",
                           (username,)).fetchone()
        student_id = row[0] if row else username
    held = frozenset(r[0] for r in conn.execute(
        "SELECT role FROM graduation_roles WHERE username = ?", (username,)))
    return Officer(username=username, role=role, student_id=student_id, roles=held)


def from_user(conn, user: dict | None) -> Officer | None:
    if not user:
        return None
    username = user.get("username") or user.get("user_id") or user.get("id")
    if not username:
        return None
    return officer(conn, username, user.get("role"), user.get("student_id"))


def require(allowed: bool, message: str) -> None:
    if not allowed:
        raise PermissionError(message)


def require_office(who) -> None:
    require(who is not None and who.is_office, "Only the graduation office can do this")


def require_self_or_office(who, student_id) -> None:
    require(who is not None and (who.is_office or (who.is_student and
                                                   who.student_id == student_id)),
            "You can only do this for your own graduation")


# ── roles ───────────────────────────────────────────────────────────────


def roles(conn) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT * FROM graduation_roles ORDER BY role, username"))


def grant_role(conn, who, username, role) -> None:
    ensure(conn)
    require_office(who)
    if role not in ROLES:
        raise ValueError("Role must be graduation_office or ceremony_staff")
    username = text(username, "Username", True)
    if not rows.is_staff_username(conn, username):
        raise ValueError(f"No member of staff with username {username!r}")
    conn.execute("INSERT OR IGNORE INTO graduation_roles (username, role, granted_by) VALUES "
                 "(?, ?, ?)", (username, role, who.username))
    audit(conn, who, "role", username, "granted", {"role": role})


def revoke_role(conn, who, username, role) -> None:
    ensure(conn)
    require_office(who)
    if not conn.execute("DELETE FROM graduation_roles WHERE username = ? AND role = ?",
                        (username, role)).rowcount:
        raise ValueError("That person does not hold that role")
    audit(conn, who, "role", username, "revoked", {"role": role})


def office_usernames(conn) -> list[str]:
    ensure(conn)
    found = {r[0] for r in conn.execute("SELECT username FROM graduation_roles WHERE role = "
                                        "'graduation_office'")}
    found |= {r[0] for r in conn.execute("SELECT username FROM users WHERE LOWER(COALESCE("
                                         "role, '')) = 'registrar'")}
    return sorted(found)


# ── audit ───────────────────────────────────────────────────────────────


def audit(conn, who, entity, entity_id, action, detail=None) -> None:
    actor = getattr(who, "username", None) or (who if isinstance(who, str) else None)
    conn.execute("INSERT INTO graduation_audit (entity, entity_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (entity, str(entity_id), action, actor,
                  json.dumps(detail, default=str) if detail else None))


def history(conn, entity, entity_id) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT at, actor, action, detail FROM graduation_audit WHERE "
                              "entity = ? AND entity_id = ? ORDER BY audit_id",
                              (entity, str(entity_id))))


def recent_audit(conn, limit=200) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT * FROM graduation_audit ORDER BY audit_id DESC LIMIT ?",
                              (int(limit),)))


def student(conn, student_id) -> dict:
    row = one(conn, "SELECT * FROM students WHERE student_id = ?", (student_id,))
    if not row:
        raise ValueError(f"No student {student_id}")
    row["name"] = " ".join(p for p in (row.get("first_name"), row.get("last_name")) if p) \
        or student_id
    return row
