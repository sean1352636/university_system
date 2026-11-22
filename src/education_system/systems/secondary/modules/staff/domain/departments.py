"""Departments: faculties and departments, their people, subjects and meetings.

Kept from the old Departments window:

* A department has a name (unique), code, faculty (the old list), head of
  department, deputy / second in department, location, budget year, budget
  total / allocated / spent (Add spend; over budget when spent passes the
  total), aims, policies, status (Active, Restructuring, Merged, Disbanded,
  Archived) and notes.
* Members: a member of staff (now from the Staff Directory) with a role in
  the department (the old list), primary-department flag, joined / left dates
  and notes; add, edit, end and delete; memberships per member of staff.
* Lists: active, over budget, all (filtered by faculty, status and name), and
  the summary (by faculty, by status, members, budgets).

New:

* **People from the Staff Directory.** Head, second and members are staff
  records (:mod:`staff_directory`); making someone head or second adds the
  membership; a primary membership sets the department on their staff record.
* **Subjects** are the subjects whose ``department`` names this department
  (:mod:`modules.curriculum.domain.subjects` already carries the field) - no
  second list. Assigning or removing a subject changes that field (it needs
  the subject editor's role too); renaming a department renames it on its
  subjects. :func:`import_from_subjects` makes departments for the names the
  subjects already use.
* **Meetings** with attendees, apologies, agenda and minutes, and **actions**
  (owner, due date, open / done / dropped). The head of department manages
  their own department's meetings; :data:`STAFF_EDITORS` manage everything.
* **Overview** (:func:`overview`): current staff, subjects, this year's
  teaching groups, pupils and lessons, open actions.
* Every change in ``department_audit`` and the activity log (ids only).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.staff.domain import staff_directory as SD  # registers the FK target
from education_system.systems.secondary.core.permissions.access import (
    STAFF_EDITORS,
    STAFF_ROLES,
    SUBJECT_EDITORS,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = SD.ValidationError
PermissionDenied = SD.PermissionDenied
NotFound = SD.NotFound
_date, _choice, _text, _number = SD.clean_date, SD.clean_choice, SD.clean_text, SD.clean_number

FACULTIES: tuple[str, ...] = (
    "Sciences", "Mathematics & Computing", "Humanities", "Languages", "Arts",
    "Performing Arts", "Physical Education", "Business & Economics", "Technology",
    "Vocational", "Pastoral", "Support Services", "Senior Leadership", "Other")
DEFAULT_FACULTY = "Other"
STATUSES: tuple[str, ...] = ("Active", "Restructuring", "Merged", "Disbanded", "Archived")
DEFAULT_STATUS = "Active"
DEPT_ROLES: tuple[str, ...] = (
    "Head of Department", "Deputy / 2nd in Dept", "Subject Lead", "Teacher",
    "Teaching Assistant", "Technician", "Administrator", "Coordinator", "Trainee", "Other")
DEFAULT_DEPT_ROLE = "Teacher"
HEAD_ROLE, SECOND_ROLE = "Head of Department", "Deputy / 2nd in Dept"
ACTION_STATUSES: tuple[str, ...] = ("Open", "Done", "Dropped")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    department_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE COLLATE NOCASE,
    code             TEXT,
    faculty          TEXT NOT NULL DEFAULT 'Other',
    head_id          INTEGER REFERENCES staff_members (staff_id) ON DELETE SET NULL,
    second_id        INTEGER REFERENCES staff_members (staff_id) ON DELETE SET NULL,
    location         TEXT,
    budget_year      TEXT,
    budget_total     REAL,
    budget_allocated REAL,
    budget_spent     REAL,
    aims             TEXT,
    policies         TEXT,
    status           TEXT NOT NULL DEFAULT 'Active' CHECK (status IN
                     ('Active', 'Restructuring', 'Merged', 'Disbanded', 'Archived')),
    notes            TEXT,
    created_by       TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS department_members (
    membership_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id      INTEGER NOT NULL REFERENCES departments (department_id) ON DELETE CASCADE,
    staff_id           INTEGER NOT NULL REFERENCES staff_members (staff_id),
    role_in_department TEXT NOT NULL DEFAULT 'Teacher',
    is_primary         INTEGER NOT NULL DEFAULT 0,
    joined_on          TEXT NOT NULL,
    left_on            TEXT,
    notes              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_department_members ON department_members (department_id, staff_id);
CREATE TABLE IF NOT EXISTS department_meetings (
    meeting_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id  INTEGER NOT NULL REFERENCES departments (department_id) ON DELETE CASCADE,
    meeting_date   TEXT NOT NULL,
    title          TEXT NOT NULL,
    attendees      TEXT,
    apologies      TEXT,
    agenda         TEXT,
    minutes        TEXT,
    created_by     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by     TEXT,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS department_actions (
    action_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id   INTEGER NOT NULL REFERENCES department_meetings (meeting_id) ON DELETE CASCADE,
    description  TEXT NOT NULL,
    owner_id     INTEGER REFERENCES staff_members (staff_id) ON DELETE SET NULL,
    due_date     TEXT,
    status       TEXT NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'Done', 'Dropped')),
    done_at      TEXT,
    done_by      TEXT,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS department_audit (
    audit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER,
    action        TEXT NOT NULL,
    detail        TEXT,
    actor         TEXT NOT NULL,
    at            TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("departments", _SCHEMA)
SD.register_reference("department_members", "staff_id", "department membership(s)")
SD.register_reference("departments", "head_id", "department(s) as head")
SD.register_reference("departments", "second_id", "department(s) as second")
SD.register_reference("department_actions", "owner_id", "department action(s)")


@dataclass(frozen=True)
class Department:
    department_id: int
    name: str
    code: str | None
    faculty: str
    head_id: int | None
    second_id: int | None
    location: str | None
    budget_year: str | None
    budget_total: float | None
    budget_allocated: float | None
    budget_spent: float | None
    aims: str | None
    policies: str | None
    status: str
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    head_name: str | None = None
    second_name: str | None = None
    member_count: int = 0

    @property
    def is_active(self) -> bool:
        return self.status == "Active"

    @property
    def budget_remaining(self) -> float | None:
        if self.budget_total is None:
            return None
        return round(self.budget_total - (self.budget_spent or 0.0), 2)

    @property
    def budget_over(self) -> bool:
        rem = self.budget_remaining
        return rem is not None and rem < 0

    @property
    def budget_text(self) -> str:
        if self.budget_total is None:
            return ""
        return f"£{self.budget_spent or 0:,.0f} / £{self.budget_total:,.0f}"


@dataclass(frozen=True)
class Membership:
    membership_id: int
    department_id: int
    staff_id: int
    role_in_department: str
    is_primary: bool
    joined_on: str
    left_on: str | None
    notes: str | None
    created_at: str
    department_name: str = ""
    staff_name: str = ""
    staff_code: str = ""

    @property
    def is_current(self) -> bool:
        return not self.left_on or self.left_on > _today().isoformat()


@dataclass(frozen=True)
class Meeting:
    meeting_id: int
    department_id: int
    meeting_date: str
    title: str
    attendees: str | None
    apologies: str | None
    agenda: str | None
    minutes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str


@dataclass(frozen=True)
class Action:
    action_id: int
    meeting_id: int
    description: str
    owner_id: int | None
    due_date: str | None
    status: str
    done_at: str | None
    done_by: str | None
    notes: str | None
    created_at: str
    owner_name: str | None = None
    department_id: int = 0
    meeting_date: str = ""

    @property
    def overdue(self) -> bool:
        return self.status == "Open" and bool(self.due_date) and \
            self.due_date < _today().isoformat()


_NAME = "coalesce({a}.preferred_name, {a}.first_name) || ' ' || {a}.last_name"
_D_SELECT = f"""
SELECT d.*, {_NAME.format(a='h')} AS head_name, {_NAME.format(a='s')} AS second_name,
       (SELECT COUNT(*) FROM department_members m WHERE m.department_id = d.department_id
        AND (m.left_on IS NULL OR m.left_on > date('now'))) AS member_count
FROM departments d
LEFT JOIN staff_members h ON h.staff_id = d.head_id
LEFT JOIN staff_members s ON s.staff_id = d.second_id
"""
_M_SELECT = f"""
SELECT m.*, d.name AS department_name, {_NAME.format(a='s')} AS staff_name,
       s.staff_code AS staff_code
FROM department_members m JOIN departments d USING (department_id)
JOIN staff_members s ON s.staff_id = m.staff_id
"""
_A_SELECT = f"""
SELECT a.*, {_NAME.format(a='s')} AS owner_name, mt.department_id, mt.meeting_date
FROM department_actions a JOIN department_meetings mt USING (meeting_id)
LEFT JOIN staff_members s ON s.staff_id = a.owner_id
"""


def _make(cls, r):
    d = {k: r[k] for k in cls.__dataclass_fields__ if k in r.keys()}
    if "is_primary" in d:
        d["is_primary"] = bool(d["is_primary"])
    return cls(**d)


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in STAFF_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"departments.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see departments.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only HR / the school office can change departments.")


def is_head(actor: Principal, d: Department) -> bool:
    me = SD.me(actor)
    return bool(me and d.head_id == me.staff_id and actor.role in STAFF_ROLES)


def can_manage_meetings(actor: Principal, d: Department) -> bool:
    return is_editor(actor) or is_head(actor, d)


def _require_meetings(actor: Principal, d: Department, action: str) -> None:
    if not can_manage_meetings(actor, d):
        _deny(actor, action, d.department_id,
              f"Only the head of {d.name} or HR can change its meetings.")


def _audit(conn, action: str, actor: Principal, department_id: int | None, **detail: Any
           ) -> None:
    conn.execute("INSERT INTO department_audit (department_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?)", (department_id, action,
                                         json.dumps(detail, default=str) if detail else None,
                                         actor.username or "unknown"))


def history(department_id: int | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM department_audit", []
    if department_id is not None:
        sql += " WHERE department_id = ?"
        params.append(int(department_id))
    with database.connect() as conn:
        return [{"at": r["at"], "department_id": r["department_id"], "action": r["action"],
                 "actor": r["actor"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── Departments ──────────────────────────────────────────────────────

def get(department_id: int) -> Department:
    with database.connect() as conn:
        r = conn.execute(_D_SELECT + " WHERE d.department_id = ?",
                         (int(department_id),)).fetchone()
    if r is None:
        raise NotFound(f"No department {department_id}")
    return _make(Department, r)


get_department = get


def find(ref: Any) -> Department | None:
    """By id or name (any case)."""
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        try:
            return get(int(ref))
        except NotFound:
            return None
    with database.connect() as conn:
        r = conn.execute(_D_SELECT + " WHERE d.name = ?", (str(ref).strip(),)).fetchone()
    return _make(Department, r) if r else None


def list_departments(*, status: str | None = None, faculty: str | None = None,
                     name: str | None = None, active_only: bool = False,
                     over_budget: bool = False) -> list[Department]:
    sql, params = _D_SELECT + " WHERE 1=1", []
    if active_only:
        sql += " AND d.status = 'Active'"
    for col, val in (("d.status", status), ("d.faculty", faculty)):
        if val:
            sql += f" AND {col} = ?"
            params.append(val)
    if name and name.strip():
        sql += " AND (d.name LIKE ? OR d.code LIKE ?)"
        params += [f"%{name.strip()}%"] * 2
    with database.connect() as conn:
        rows = [_make(Department, r) for r in conn.execute(
            sql + " ORDER BY d.name COLLATE NOCASE", params)]
    return [d for d in rows if d.budget_over] if over_budget else rows


def names() -> list[str]:
    return [d.name for d in list_departments()]


FIELDS = ("name", "code", "faculty", "head_id", "second_id", "location", "budget_year",
          "budget_total", "budget_allocated", "budget_spent", "aims", "policies", "status",
          "notes")


def _person(value: Any, label: str, problems: list[str]) -> int | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    m = SD.find(value)
    if m is None:
        problems.append(f"{label}: no staff record {value}")
        return None
    if m.is_leaver:
        problems.append(f"{label}: {m.full_name} has left")
    return m.staff_id


def _clean(data: dict[str, Any], current: Department | None) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS})
    out: dict[str, Any] = {"name": _text(merged.get("name"), 60)}
    if not out["name"]:
        problems.append("Name is required")
    out["code"] = (_text(merged.get("code"), 10) or "").upper() or None
    out["faculty"] = _choice(merged.get("faculty"), FACULTIES, "Faculty", problems,
                             DEFAULT_FACULTY)
    out["status"] = _choice(merged.get("status"), STATUSES, "Status", problems, DEFAULT_STATUS)
    for k, label in (("head_id", "Head of department"), ("second_id", "Second in department")):
        new = merged.get(k)
        if current is not None and new == getattr(current, k):
            out[k] = new
        else:
            out[k] = _person(new, label, problems)
    if out["head_id"] and out["head_id"] == out["second_id"]:
        problems.append("The head and the second in department must be different people")
    out["location"] = _text(merged.get("location"), 60)
    out["budget_year"] = _text(merged.get("budget_year"), 10)
    for k, label in (("budget_total", "Budget total"), ("budget_allocated", "Budget allocated"),
                     ("budget_spent", "Budget spent")):
        out[k] = _number(merged.get(k), label, problems, 0, 10_000_000)
    for k in ("aims", "policies", "notes"):
        out[k] = _text(merged.get(k), 4000)
    return out, problems


def _ensure_member(conn, department_id: int, staff_id: int, role: str) -> None:
    r = conn.execute("SELECT membership_id FROM department_members WHERE department_id = ? AND "
                     "staff_id = ? AND (left_on IS NULL OR left_on > date('now'))",
                     (department_id, staff_id)).fetchone()
    if r:
        conn.execute("UPDATE department_members SET role_in_department = ? "
                     "WHERE membership_id = ?", (role, r[0]))
    else:
        conn.execute("INSERT INTO department_members (department_id, staff_id, "
                     "role_in_department, joined_on) VALUES (?, ?, ?, ?)",
                     (department_id, staff_id, role, _today().isoformat()))


def _subject_rename_problems(actor: Principal, old: str, new: str) -> list[str]:
    if old.lower() == new.lower() and old == new:
        return []
    if subjects_for_name(old) and actor.role not in SUBJECT_EDITORS:
        return [f"Renaming {old} renames it on its subjects too - that needs the subject "
                "editor's role"]
    return []


def create(data: dict[str, Any], *, actor: Principal) -> Department:
    _require_editor(actor, "create")
    c, problems = _clean(data, None)
    with database.connect() as conn:
        if c["name"] and conn.execute("SELECT 1 FROM departments WHERE name = ?",
                                      (c["name"],)).fetchone():
            problems.append(f"There is already a department called {c['name']}")
        if problems:
            raise ValidationError(problems)
        did = conn.execute(
            f"INSERT INTO departments ({', '.join(FIELDS)}, created_by, updated_by) "  # nosec B608 - fixed
            f"VALUES ({', '.join('?' * len(FIELDS))}, ?, ?)",
            (*(c[k] for k in FIELDS), actor.username, actor.username)).lastrowid
        for k, role in (("head_id", HEAD_ROLE), ("second_id", SECOND_ROLE)):
            if c[k]:
                _ensure_member(conn, did, c[k], role)
        _audit(conn, "create", actor, did, name=c["name"])
    activity_log.record("departments.create", target=did, principal=actor)
    return get(did)


create_department = create


def update(department_id: int, changes: dict[str, Any], *, actor: Principal) -> Department:
    cur = get(department_id)
    _require_editor(actor, "update", cur.department_id)
    c, problems = _clean(changes, cur)
    if c["name"]:
        problems += _subject_rename_problems(actor, cur.name, c["name"])
    with database.connect() as conn:
        if c["name"] and c["name"].lower() != cur.name.lower() and conn.execute(
                "SELECT 1 FROM departments WHERE name = ? AND department_id != ?",
                (c["name"], cur.department_id)).fetchone():
            problems.append(f"There is already a department called {c['name']}")
        if problems:
            raise ValidationError(problems)
        changed = [k for k in FIELDS if c[k] != getattr(cur, k)]
        if not changed:
            return cur
        conn.execute("UPDATE departments SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE department_id = ?",
                     (*(c[k] for k in changed), actor.username, cur.department_id))
        for k, role in (("head_id", HEAD_ROLE), ("second_id", SECOND_ROLE)):
            if k in changed and c[k]:
                _ensure_member(conn, cur.department_id, c[k], role)
        _audit(conn, "update", actor, cur.department_id,
               **{k: {"from": getattr(cur, k), "to": c[k]} for k in changed
                  if k not in ("aims", "policies", "notes")})
    if "name" in changed:
        for s in subjects_for_name(cur.name):
            S.update(s.subject_id, {"department": c["name"]}, actor=actor)
    activity_log.record("departments.update", target=cur.department_id, principal=actor,
                        fields=changed)
    return get(cur.department_id)


update_department = update


def set_status(department_id: int, status: str, *, actor: Principal) -> Department:
    """The old Change status."""
    problems: list[str] = []
    st = _choice(status, STATUSES, "Status", problems, None)
    if problems or st is None:
        raise ValidationError(problems or ["Choose a status"])
    return update(department_id, {"status": st}, actor=actor)


def add_spend(department_id: int, *, amount: Any, actor: Principal) -> Department:
    """The old Add spend (a negative amount is a refund)."""
    cur = get(department_id)
    problems: list[str] = []
    amt = _number(amount, "Amount", problems, -1_000_000, 1_000_000)
    if amt is None and not problems:
        problems.append("Amount is required")
    if problems:
        raise ValidationError(problems)
    new = round((cur.budget_spent or 0.0) + (amt or 0.0), 2)
    if new < 0:
        raise ValidationError(["Spending can't go below zero"])
    return update(department_id, {"budget_spent": new}, actor=actor)


def delete(department_id: int, *, actor: Principal) -> bool:
    """Delete a department set up in error. One with meetings is archived instead."""
    cur = get(department_id)
    _require_editor(actor, "delete", cur.department_id)
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM department_meetings WHERE department_id = ?",
                         (cur.department_id,)).fetchone()[0]
        if n:
            raise ValidationError([f"{cur.name} has {n} meeting(s) on record - set its status "
                                   "to Archived instead"])
        conn.execute("DELETE FROM departments WHERE department_id = ?", (cur.department_id,))
        _audit(conn, "delete", actor, cur.department_id, name=cur.name)
    activity_log.record("departments.delete", target=cur.department_id, principal=actor)
    return True


delete_department = delete


def import_from_subjects(*, actor: Principal) -> list[Department]:
    """A department for each department name the subjects use that has none."""
    _require_editor(actor, "import")
    have = {d.name.lower() for d in list_departments()}
    return [create({"name": n}, actor=actor) for n in S.departments()
            if n and n.lower() not in have]


# ── Memberships ──────────────────────────────────────────────────────

def get_membership(membership_id: int) -> Membership:
    with database.connect() as conn:
        r = conn.execute(_M_SELECT + " WHERE m.membership_id = ?",
                         (int(membership_id),)).fetchone()
    if r is None:
        raise NotFound(f"No membership {membership_id}")
    return _make(Membership, r)


def list_memberships(department_id: int, *, current_only: bool = False) -> list[Membership]:
    with database.connect() as conn:
        rows = [_make(Membership, r) for r in conn.execute(
            _M_SELECT + " WHERE m.department_id = ? ORDER BY m.left_on IS NOT NULL, "
            "CASE m.role_in_department WHEN 'Head of Department' THEN 0 WHEN "
            "'Deputy / 2nd in Dept' THEN 1 ELSE 2 END, s.last_name COLLATE NOCASE",
            (int(department_id),))]
    return [m for m in rows if m.is_current] if current_only else rows


def memberships_for_staff(staff_id: int) -> list[Membership]:
    """The old Per staff: every department someone is or was in."""
    with database.connect() as conn:
        return [_make(Membership, r) for r in conn.execute(
            _M_SELECT + " WHERE m.staff_id = ? ORDER BY m.left_on IS NOT NULL, m.is_primary "
            "DESC, d.name COLLATE NOCASE", (int(staff_id),))]


def member_count(department_id: int) -> int:
    return len(list_memberships(department_id, current_only=True))


M_FIELDS = ("role_in_department", "is_primary", "joined_on", "left_on", "notes")


def _clean_membership(data: dict[str, Any], current: Membership | None
                      ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in M_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in M_FIELDS})
    out = {"role_in_department": _choice(merged.get("role_in_department"), DEPT_ROLES,
                                         "Role", problems, DEFAULT_DEPT_ROLE),
           "is_primary": SD.clean_bool(merged.get("is_primary")),
           "joined_on": _date(merged.get("joined_on"), "Joined on", problems)
           or _today().isoformat(),
           "left_on": _date(merged.get("left_on"), "Left on", problems),
           "notes": _text(merged.get("notes"), 1000)}
    if out["left_on"] and out["left_on"] < out["joined_on"]:
        problems.append("Left on can't be before joined on")
    return out, problems


def _set_primary(conn, m_staff_id: int, membership_id: int) -> None:
    conn.execute("UPDATE department_members SET is_primary = 0 WHERE staff_id = ? AND "
                 "membership_id != ?", (m_staff_id, membership_id))


def _sync_staff_department(staff_id: int, name: str, actor: Principal) -> None:
    m = SD.find(staff_id)
    if m and (m.department or "") != name:
        SD.update(staff_id, {"department": name}, actor=actor)


def add_member(department_id: int, data: dict[str, Any], *, actor: Principal) -> Membership:
    d = get(department_id)
    _require_editor(actor, "member_add", d.department_id)
    problems: list[str] = []
    sid = _person(data.get("staff_id") or data.get("staff"), "Staff", problems)
    if sid is None and not problems:
        problems.append("Staff is required")
    c, more = _clean_membership(data, None)
    problems += more
    with database.connect() as conn:
        if sid and conn.execute(
                "SELECT 1 FROM department_members WHERE department_id = ? AND staff_id = ? AND "
                "(left_on IS NULL OR left_on > date('now'))", (d.department_id, sid)).fetchone():
            problems.append("They are already a member - edit their membership instead")
        if problems:
            raise ValidationError(problems)
        mid = conn.execute(
            "INSERT INTO department_members (department_id, staff_id, role_in_department, "
            "is_primary, joined_on, left_on, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (d.department_id, sid, c["role_in_department"], int(c["is_primary"]),
             c["joined_on"], c["left_on"], c["notes"])).lastrowid
        if c["is_primary"]:
            _set_primary(conn, sid, mid)
        _audit(conn, "member_add", actor, d.department_id, membership=mid, staff=sid,
               role=c["role_in_department"])
    if c["is_primary"]:
        _sync_staff_department(sid, d.name, actor)
    activity_log.record("departments.member_add", target=d.department_id, principal=actor,
                        staff=sid)
    return get_membership(mid)


def update_membership(membership_id: int, changes: dict[str, Any], *, actor: Principal
                      ) -> Membership:
    cur = get_membership(membership_id)
    _require_editor(actor, "member_update", cur.department_id)
    c, problems = _clean_membership(changes, cur)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in M_FIELDS if c[k] != getattr(cur, k)]
    if not changed:
        return cur
    with database.connect() as conn:
        conn.execute("UPDATE department_members SET " + ", ".join(f"{k} = ?" for k in changed)
                     + " WHERE membership_id = ?",
                     (*(int(c[k]) if k == "is_primary" else c[k] for k in changed),
                      cur.membership_id))
        if c["is_primary"]:
            _set_primary(conn, cur.staff_id, cur.membership_id)
        _audit(conn, "member_update", actor, cur.department_id, membership=cur.membership_id,
               fields=changed)
    if c["is_primary"] and "is_primary" in changed:
        _sync_staff_department(cur.staff_id, cur.department_name, actor)
    activity_log.record("departments.member_update", target=cur.department_id,
                        principal=actor)
    return get_membership(cur.membership_id)


def end_membership(membership_id: int, left_on: str | None = None, *, actor: Principal
                   ) -> Membership:
    """The old End: the membership stays, with a left date."""
    cur = get_membership(membership_id)
    if cur.left_on:
        raise ValidationError(["That membership has already ended"])
    m = update_membership(membership_id, {"left_on": left_on or _today().isoformat()},
                          actor=actor)
    d = get(cur.department_id)
    with database.connect() as conn:
        for k in ("head_id", "second_id"):
            if getattr(d, k) == cur.staff_id:
                conn.execute(f"UPDATE departments SET {k} = NULL WHERE department_id = ?",  # nosec B608 - fixed
                             (d.department_id,))
    return m


def delete_membership(membership_id: int, *, actor: Principal) -> bool:
    cur = get_membership(membership_id)
    _require_editor(actor, "member_delete", cur.department_id)
    with database.connect() as conn:
        conn.execute("DELETE FROM department_members WHERE membership_id = ?",
                     (cur.membership_id,))
        _audit(conn, "member_delete", actor, cur.department_id, membership=cur.membership_id,
               staff=cur.staff_id)
    activity_log.record("departments.member_delete", target=cur.department_id, principal=actor)
    return True


# ── Subjects (subjects.department names the department) ──────────────

def subjects_for_name(name: str) -> list[S.Subject]:
    return [s for s in S.list_subjects(active_only=False)
            if (s.department or "").strip().lower() == name.strip().lower()]


def subjects_for(department_id: int) -> list[S.Subject]:
    return subjects_for_name(get(department_id).name)


def assign_subject(department_id: int, subject_id: int, *, actor: Principal) -> S.Subject:
    """Put a subject in this department (sets the subject's department)."""
    d = get(department_id)
    _require_editor(actor, "subject", d.department_id)
    s, _changed = S.update(int(subject_id), {"department": d.name}, actor=actor)
    with database.connect() as conn:
        _audit(conn, "subject_add", actor, d.department_id, subject=s.subject_id)
    return s


def remove_subject(department_id: int, subject_id: int, *, actor: Principal) -> S.Subject:
    d = get(department_id)
    _require_editor(actor, "subject", d.department_id)
    s = S.get(int(subject_id))
    if (s.department or "").lower() != d.name.lower():
        raise ValidationError([f"{s.name} isn't in {d.name}"])
    s, _changed = S.update(s.subject_id, {"department": ""}, actor=actor)
    with database.connect() as conn:
        _audit(conn, "subject_remove", actor, d.department_id, subject=s.subject_id)
    return s


def unassigned_subjects() -> list[S.Subject]:
    have = {n.lower() for n in names()}
    return [s for s in S.list_subjects(active_only=False)
            if (s.department or "").strip().lower() not in have]


# ── Meetings and actions ─────────────────────────────────────────────

def get_meeting(meeting_id: int) -> Meeting:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM department_meetings WHERE meeting_id = ?",
                         (int(meeting_id),)).fetchone()
    if r is None:
        raise NotFound(f"No meeting {meeting_id}")
    return _make(Meeting, r)


def list_meetings(department_id: int) -> list[Meeting]:
    with database.connect() as conn:
        return [_make(Meeting, r) for r in conn.execute(
            "SELECT * FROM department_meetings WHERE department_id = ? "
            "ORDER BY meeting_date DESC, meeting_id DESC", (int(department_id),))]


MT_FIELDS = ("meeting_date", "title", "attendees", "apologies", "agenda", "minutes")


def _clean_meeting(data: dict[str, Any], current: Meeting | None
                   ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in MT_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in MT_FIELDS})
    out = {"meeting_date": _date(merged.get("meeting_date"), "Date", problems)
           or _today().isoformat(),
           "title": _text(merged.get("title"), 120) or "Department meeting"}
    for k in ("attendees", "apologies"):
        out[k] = _text(merged.get(k), 1000)
    for k in ("agenda", "minutes"):
        out[k] = _text(merged.get(k), 20000)
    return out, problems


def add_meeting(department_id: int, data: dict[str, Any], *, actor: Principal) -> Meeting:
    d = get(department_id)
    _require_meetings(actor, d, "meeting_add")
    c, problems = _clean_meeting(data, None)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        mid = conn.execute(
            f"INSERT INTO department_meetings (department_id, {', '.join(MT_FIELDS)}, "  # nosec B608 - fixed
            f"created_by, updated_by) VALUES (?, {', '.join('?' * len(MT_FIELDS))}, ?, ?)",
            (d.department_id, *(c[k] for k in MT_FIELDS), actor.username,
             actor.username)).lastrowid
        _audit(conn, "meeting_add", actor, d.department_id, meeting=mid)
    activity_log.record("departments.meeting_add", target=d.department_id, principal=actor)
    return get_meeting(mid)


def update_meeting(meeting_id: int, changes: dict[str, Any], *, actor: Principal) -> Meeting:
    cur = get_meeting(meeting_id)
    _require_meetings(actor, get(cur.department_id), "meeting_update")
    c, problems = _clean_meeting(changes, cur)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in MT_FIELDS if c[k] != getattr(cur, k)]
    if changed:
        with database.connect() as conn:
            conn.execute("UPDATE department_meetings SET "
                         + ", ".join(f"{k} = ?" for k in changed)
                         + ", updated_by = ?, updated_at = datetime('now') WHERE meeting_id = ?",
                         (*(c[k] for k in changed), actor.username, cur.meeting_id))
            _audit(conn, "meeting_update", actor, cur.department_id, meeting=cur.meeting_id,
                   fields=changed)
    return get_meeting(cur.meeting_id)


def delete_meeting(meeting_id: int, *, actor: Principal) -> bool:
    cur = get_meeting(meeting_id)
    _require_meetings(actor, get(cur.department_id), "meeting_delete")
    with database.connect() as conn:
        conn.execute("DELETE FROM department_meetings WHERE meeting_id = ?", (cur.meeting_id,))
        _audit(conn, "meeting_delete", actor, cur.department_id, meeting=cur.meeting_id)
    activity_log.record("departments.meeting_delete", target=cur.department_id,
                        principal=actor)
    return True


def get_action(action_id: int) -> Action:
    with database.connect() as conn:
        r = conn.execute(_A_SELECT + " WHERE a.action_id = ?", (int(action_id),)).fetchone()
    if r is None:
        raise NotFound(f"No action {action_id}")
    return _make(Action, r)


def list_actions(*, meeting_id: int | None = None, department_id: int | None = None,
                 open_only: bool = False, owner_id: int | None = None) -> list[Action]:
    sql, params = _A_SELECT + " WHERE 1=1", []
    for col, val in (("a.meeting_id", meeting_id), ("mt.department_id", department_id),
                     ("a.owner_id", owner_id)):
        if val is not None:
            sql += f" AND {col} = ?"
            params.append(int(val))
    if open_only:
        sql += " AND a.status = 'Open'"
    with database.connect() as conn:
        return [_make(Action, r) for r in conn.execute(
            sql + " ORDER BY a.status != 'Open', a.due_date IS NULL, a.due_date, a.action_id",
            params)]


def add_action(meeting_id: int, data: dict[str, Any], *, actor: Principal) -> Action:
    mt = get_meeting(meeting_id)
    _require_meetings(actor, get(mt.department_id), "action_add")
    problems: list[str] = []
    desc = _text(data.get("description"), 1000)
    if not desc:
        problems.append("Say what the action is")
    owner = _person(data.get("owner_id") or data.get("owner"), "Owner", problems)
    due = _date(data.get("due_date"), "Due date", problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        aid = conn.execute("INSERT INTO department_actions (meeting_id, description, owner_id, "
                           "due_date, notes) VALUES (?, ?, ?, ?, ?)",
                           (mt.meeting_id, desc, owner, due,
                            _text(data.get("notes"), 1000))).lastrowid
        _audit(conn, "action_add", actor, mt.department_id, action_id=aid)
    return get_action(aid)


def set_action_status(action_id: int, status: str, *, actor: Principal) -> Action:
    """Done / Dropped / Open again. The owner may close their own action."""
    a = get_action(action_id)
    d = get(a.department_id)
    me = SD.me(actor)
    if not (can_manage_meetings(actor, d) or (me and me.staff_id == a.owner_id)):
        _deny(actor, "action_status", d.department_id,
              "Only the action's owner, the head of department or HR can do that.")
    problems: list[str] = []
    st = _choice(status, ACTION_STATUSES, "Status", problems, None)
    if problems or st is None:
        raise ValidationError(problems or ["Choose a status"])
    with database.connect() as conn:
        conn.execute("UPDATE department_actions SET status = ?, done_at = ?, done_by = ? "
                     "WHERE action_id = ?",
                     (st, _dt.datetime.now().isoformat(timespec="seconds") if st != "Open"
                      else None, actor.username if st != "Open" else None, a.action_id))
        _audit(conn, "action_status", actor, a.department_id, action_id=a.action_id, status=st)
    return get_action(a.action_id)


def delete_action(action_id: int, *, actor: Principal) -> bool:
    a = get_action(action_id)
    _require_meetings(actor, get(a.department_id), "action_delete")
    with database.connect() as conn:
        conn.execute("DELETE FROM department_actions WHERE action_id = ?", (a.action_id,))
        _audit(conn, "action_delete", actor, a.department_id, action_id=a.action_id)
    return True


def minutes_text(meeting_id: int) -> str:
    mt = get_meeting(meeting_id)
    d = get(mt.department_id)
    lines = [f"{d.name} - {mt.title}", f"Date: {mt.meeting_date}"]
    for label, v in (("Present", mt.attendees), ("Apologies", mt.apologies)):
        if v:
            lines.append(f"{label}: {v}")
    for label, v in (("Agenda", mt.agenda), ("Minutes", mt.minutes)):
        if v:
            lines += ["", f"{label}:", v]
    acts = list_actions(meeting_id=mt.meeting_id)
    if acts:
        lines += ["", "Actions:"]
        lines += [f"  [{a.status}] {a.description} - {a.owner_name or 'no owner'}"
                  + (f", due {a.due_date}" if a.due_date else "") for a in acts]
    return "\n".join(lines)


# ── Overview and summary ─────────────────────────────────────────────

def overview(department_id: int, *, actor: Principal) -> dict[str, Any]:
    """Staff, subjects, this year's teaching groups and the counts."""
    _require_staff(actor, "overview", department_id)
    from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
    d = get(department_id)
    members = list_memberships(d.department_id, current_only=True)
    staff = [m for m in (SD.find(x.staff_id) for x in members) if m]
    subjects = subjects_for_name(d.name)
    ids = {s.subject_id for s in subjects}
    groups = TG.info([g for g in TG.list_groups() if g.subject_id in ids])
    meetings = list_meetings(d.department_id)
    open_actions = list_actions(department_id=d.department_id, open_only=True)
    activity_log.record("departments.overview", target=d.department_id, principal=actor)
    return {
        "department": d, "members": members, "subjects": subjects, "groups": groups,
        "counts": {
            "staff": len(members),
            "teaching_staff": sum(1 for m in staff if m.role_type == "teaching"),
            "fte": round(sum(m.fte for m in staff), 2),
            "subjects": len(subjects), "groups": len(groups),
            "pupil_places": sum(g.pupils for g in groups),
            "lessons_per_week": sum(g.lessons or 0 for g in groups),
            "meetings": len(meetings), "open_actions": len(open_actions),
            "overdue_actions": sum(1 for a in open_actions if a.overdue)},
        "last_meeting": meetings[0] if meetings else None, "open_actions": open_actions}


def summary() -> dict[str, Any]:
    rows = list_departments()
    return {"total": len(rows), "active": sum(1 for d in rows if d.is_active),
            "members": sum(d.member_count for d in rows),
            "budget_total": round(sum(d.budget_total or 0 for d in rows), 2),
            "budget_spent": round(sum(d.budget_spent or 0 for d in rows), 2),
            "over_budget": sum(1 for d in rows if d.budget_over),
            "by_faculty": dict(Counter(d.faculty for d in rows).most_common()),
            "by_status": dict(Counter(d.status for d in rows).most_common()),
            "without_head": [d.name for d in rows if d.is_active and not d.head_id]}


def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    _require_staff(actor, "export")
    rows = list_departments(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "name", "code", "faculty", "head", "second", "members", "subjects",
                    "budget_year", "budget_total", "budget_spent", "status"])
        for d in rows:
            w.writerow([d.department_id, _safe(d.name), _safe(d.code), d.faculty,
                        _safe(d.head_name), _safe(d.second_name), d.member_count,
                        "; ".join(s.code for s in subjects_for_name(d.name)),
                        _safe(d.budget_year), d.budget_total if d.budget_total is not None
                        else "", d.budget_spent if d.budget_spent is not None else "",
                        d.status])
    activity_log.record("departments.export", principal=actor, rows=len(rows))
    return len(rows)
