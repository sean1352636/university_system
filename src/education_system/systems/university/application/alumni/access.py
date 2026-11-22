"""Who may do what in the alumni system, and the alumni audit trail.

* **Alumni** (university role ``alumni``, or a student who has an
  ``alumni`` record) manage their own profile, privacy, consent, giving,
  chapters, mentoring offer and stories.
* **Staff roles** from ``alumni_roles``: ``alumni_office`` (everything),
  ``fundraising`` (gifts, Gift Aid, pledges, campaigns),
  ``mentoring_coordinator`` (vetting, matches, concerns), ``moderator``
  (forum, stories, photos). Admins hold every role. Other staff only see the
  directory as alumni would.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from education_system.systems.university.application.research import access as rows
from education_system.systems.university.infrastructure.database.schemas import (
    alumni_office_schema as schema,
)

ADMIN_ROLES = ("admin", "administrator", "superadmin")
ROLES = {"alumni_office": "Alumni office", "fundraising": "Fundraising",
         "mentoring_coordinator": "Mentoring coordinator", "moderator": "Moderator"}

dicts, one, has_table = rows.dicts, rows.one, rows.has_table
iso_date, text, money, today, now = rows.iso_date, rows.text, rows.money, rows.today, rows.now
notify, person_name = rows.notify, rows.person_name


def ensure(conn) -> None:
    schema.apply_to_connection(conn)


@dataclass(frozen=True)
class AlumniUser:
    username: str
    role: str = ""
    alumni_id: str | None = None
    student_id: str | None = None
    roles: frozenset = field(default_factory=frozenset)

    def holds(self, role) -> bool:
        return self.role in ADMIN_ROLES or "alumni_office" in self.roles or role in self.roles

    @property
    def is_office(self) -> bool:
        return self.holds("alumni_office")

    @property
    def is_fundraiser(self) -> bool:
        return self.holds("fundraising")

    @property
    def is_coordinator(self) -> bool:
        return self.holds("mentoring_coordinator")

    @property
    def is_moderator(self) -> bool:
        return self.holds("moderator")

    @property
    def is_staff_role(self) -> bool:
        return self.is_office or bool(self.roles)

    @property
    def is_alumnus(self) -> bool:
        return self.alumni_id is not None

    @property
    def is_student(self) -> bool:
        return self.role == "student"


def user(conn, username, role, student_id=None) -> AlumniUser:
    ensure(conn)
    role = str(role or "").lower()
    username = str(username or "").strip()
    sid = student_id
    if role in ("student", "alumni") and not sid:
        row = conn.execute("SELECT student_id FROM users WHERE username = ? AND student_id IS NOT "
                           "NULL", (username,)).fetchone()
        sid = row[0] if row else username
    alumni_id = None
    if sid:
        row = conn.execute("SELECT alumni_id FROM alumni WHERE (alumni_id = ? OR student_id = ?) "
                           "AND anonymised_at IS NULL", (sid, sid)).fetchone()
        alumni_id = row[0] if row else None
    held = frozenset(r[0] for r in conn.execute(
        "SELECT role FROM alumni_roles WHERE username = ?", (username,)))
    return AlumniUser(username=username, role=role, alumni_id=alumni_id, student_id=sid,
                      roles=held)


def from_user(conn, current: dict | None) -> AlumniUser | None:
    if not current:
        return None
    username = current.get("username") or current.get("user_id") or current.get("id")
    if not username:
        return None
    return user(conn, username, current.get("role"), current.get("student_id"))


def require(allowed, message) -> None:
    if not allowed:
        raise PermissionError(message)


def require_self_or(who, alumni_id, allowed_role_check, message="You can only do this for "
                                                               "yourself") -> None:
    require(who is not None and (who.alumni_id == alumni_id or allowed_role_check(who)),
            message)


# ── roles ───────────────────────────────────────────────────────────────


def roles(conn) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT * FROM alumni_roles ORDER BY role, username"))


def grant_role(conn, who, username, role) -> None:
    ensure(conn)
    require(who is not None and who.is_office, "Only the alumni office can assign roles")
    if role not in ROLES:
        raise ValueError("Role must be one of " + ", ".join(ROLES))
    username = text(username, "Username", True)
    if not rows.is_staff_username(conn, username):
        raise ValueError(f"No member of staff with username {username!r}")
    conn.execute("INSERT OR IGNORE INTO alumni_roles (username, role, granted_by) VALUES "
                 "(?, ?, ?)", (username, role, who.username))
    audit(conn, who, "role", username, "granted", {"role": role})


def revoke_role(conn, who, username, role) -> None:
    ensure(conn)
    require(who is not None and who.is_office, "Only the alumni office can remove roles")
    if not conn.execute("DELETE FROM alumni_roles WHERE username = ? AND role = ?",
                        (username, role)).rowcount:
        raise ValueError("That person does not hold that role")
    audit(conn, who, "role", username, "revoked", {"role": role})


def holders(conn, role) -> list[str]:
    ensure(conn)
    found = {r[0] for r in conn.execute("SELECT username FROM alumni_roles WHERE role IN (?, "
                                        "'alumni_office')", (role,))}
    return sorted(found) or sorted(r[0] for r in conn.execute(
        "SELECT username FROM users WHERE LOWER(COALESCE(role, '')) = 'admin'"))


# ── audit ───────────────────────────────────────────────────────────────


def audit(conn, who, entity, entity_id, action, detail=None) -> None:
    actor = getattr(who, "username", None) or (who if isinstance(who, str) else None)
    conn.execute("INSERT INTO alumni_audit (entity, entity_id, action, actor, detail) VALUES "
                 "(?, ?, ?, ?, ?)", (entity, str(entity_id), action, actor,
                                     json.dumps(detail, default=str) if detail else None))


def history(conn, entity, entity_id) -> list[dict]:
    ensure(conn)
    return dicts(conn.execute("SELECT at, actor, action, detail FROM alumni_audit WHERE entity = "
                              "? AND entity_id = ? ORDER BY audit_id", (entity, str(entity_id))))


def recent_audit(conn, who, limit=200) -> list[dict]:
    ensure(conn)
    require(who is not None and who.is_office, "Only the alumni office can read the audit log")
    return dicts(conn.execute("SELECT * FROM alumni_audit ORDER BY audit_id DESC LIMIT ?",
                              (int(limit),)))


def alumnus(conn, alumni_id) -> dict:
    ensure(conn)
    row = one(conn, "SELECT * FROM alumni WHERE alumni_id = ?", (alumni_id,))
    if not row:
        raise ValueError(f"No alumni record {alumni_id}")
    row["name"] = " ".join(p for p in (row.get("first_name"), row.get("last_name")) if p) \
        or str(alumni_id)
    return row


def contactable(row) -> bool:
    """May this alumnus be sent anything beyond what the law requires?"""
    return not (row.get("deceased_at") or row.get("anonymised_at") or row.get("do_not_contact"))
