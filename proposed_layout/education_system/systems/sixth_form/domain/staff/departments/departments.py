"""Departments data layer for Sixth Form System.

Two tables:
- `departments`: department definition (name, code, faculty,
  HoD / deputy staff_ids, budget, status).
- `department_members`: many-to-many staff↔department with role
  in department. FK cascade on department delete; soft FK to
  staff_id (no FK, so deleting a staff member doesn't auto-prune
  history — call `prune_for_staff` if desired).
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.systems.sixth_form.infrastructure import paths as _paths

logger = logging.getLogger(__name__)

FACULTIES: tuple[str, ...] = (
    "Sciences",
    "Mathematics & Computing",
    "Humanities",
    "Languages",
    "Arts",
    "Performing Arts",
    "Physical Education",
    "Business & Economics",
    "Technology",
    "Vocational",
    "Pastoral",
    "Support Services",
    "Senior Leadership",
    "Other",
)
DEFAULT_FACULTY = "Other"

STATUSES: tuple[str, ...] = (
    "Active",
    "Restructuring",
    "Merged",
    "Disbanded",
    "Archived",
)
DEFAULT_STATUS = "Active"

DEPT_ROLES: tuple[str, ...] = (
    "Head of Department",
    "Deputy / 2nd in Dept",
    "Subject Lead",
    "Teacher",
    "Teaching Assistant",
    "Technician",
    "Administrator",
    "Coordinator",
    "Trainee",
    "Other",
)
DEFAULT_DEPT_ROLE = "Teacher"


class ValidationError(Exception):
    pass


@dataclass
class Department:
    department_id: int
    name: str
    code: str | None
    faculty: str
    head_of_department: str | None
    deputy_head: str | None
    location: str | None
    budget_year: str | None
    budget_total: float | None
    budget_allocated: float | None
    budget_spent: float | None
    subject_codes: str | None
    aims: str | None
    policies: str | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_active(self) -> bool:
        return self.status == "Active"

    @property
    def budget_remaining(self) -> float | None:
        if self.budget_total is None:
            return None
        spent = self.budget_spent or 0.0
        return round(self.budget_total - spent, 2)

    @property
    def budget_over(self) -> bool:
        rem = self.budget_remaining
        return rem is not None and rem < 0


@dataclass
class Membership:
    membership_id: int
    department_id: int
    staff_id: str
    role_in_department: str
    is_primary: bool
    joined_on: str
    left_on: str | None
    notes: str | None
    created_on: str

    @property
    def is_current(self) -> bool:
        return not self.left_on


@dataclass
class DepartmentsSummary:
    total: int = 0
    active: int = 0
    restructuring: int = 0
    disbanded: int = 0
    total_members: int = 0
    distinct_staff: int = 0
    budget_total: float = 0.0
    budget_spent: float = 0.0
    budget_over_count: int = 0
    by_faculty: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.DEPARTMENTS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                department_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                code TEXT,
                faculty TEXT NOT NULL,
                head_of_department TEXT,
                deputy_head TEXT,
                location TEXT,
                budget_year TEXT,
                budget_total REAL,
                budget_allocated REAL,
                budget_spent REAL,
                subject_codes TEXT,
                aims TEXT,
                policies TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS department_members (
                membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_id INTEGER NOT NULL,
                staff_id TEXT NOT NULL,
                role_in_department TEXT NOT NULL,
                is_primary INTEGER NOT NULL DEFAULT 0,
                joined_on TEXT NOT NULL,
                left_on TEXT,
                notes TEXT,
                created_on TEXT NOT NULL,
                FOREIGN KEY(department_id)
                  REFERENCES departments(department_id)
                  ON DELETE CASCADE
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _staff_exists(staff_id: str) -> bool:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM staff WHERE staff_id=?",
                (staff_id,)).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


# ── Departments ──────────────────────────────────────────────

def _validate_department(p: dict[str, Any], *,
                              existing_id: int | None = None
                              ) -> dict[str, Any]:
    out = dict(p)
    out["name"] = (out.get("name") or "").strip()
    if not out["name"]:
        raise ValidationError("Name is required")
    faculty = (out.get("faculty") or DEFAULT_FACULTY).strip()
    if faculty not in FACULTIES:
        raise ValidationError(
            f"Faculty must be one of: {', '.join(FACULTIES)}")
    out["faculty"] = faculty
    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("code", "head_of_department", "deputy_head",
               "location", "budget_year", "subject_codes",
               "aims", "policies", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None

    # Soft validation of staff ids (only checks if non-empty)
    for k in ("head_of_department", "deputy_head"):
        sid = out.get(k)
        if sid and not _staff_exists(sid):
            raise ValidationError(
                f"{k.replace('_', ' ')}: no staff with id {sid}")

    for key in ("budget_total", "budget_allocated",
                  "budget_spent"):
        v = out.get(key)
        if v in (None, ""):
            out[key] = None
        else:
            try:
                out[key] = float(v)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"{key.replace('_', ' ')} must be a number")
            if out[key] < 0:
                raise ValidationError(
                    f"{key.replace('_', ' ')} must be >= 0")

    # Uniqueness of name
    with _connect() as conn:
        row = conn.execute(
            "SELECT department_id FROM departments "
            "WHERE name=?", (out["name"],)).fetchone()
    if row and row["department_id"] != existing_id:
        raise ValidationError(
            f"A department named {out['name']!r} already exists")
    return out


def _row_department(r: sqlite3.Row) -> Department:
    return Department(
        department_id=r["department_id"],
        name=r["name"],
        code=r["code"],
        faculty=r["faculty"],
        head_of_department=r["head_of_department"],
        deputy_head=r["deputy_head"],
        location=r["location"],
        budget_year=r["budget_year"],
        budget_total=r["budget_total"],
        budget_allocated=r["budget_allocated"],
        budget_spent=r["budget_spent"],
        subject_codes=r["subject_codes"],
        aims=r["aims"],
        policies=r["policies"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_department(payload: dict[str, Any]) -> Department:
    init_db()
    p = _validate_department(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO departments (
              name, code, faculty,
              head_of_department, deputy_head, location,
              budget_year, budget_total, budget_allocated,
              budget_spent, subject_codes, aims, policies,
              status, notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?)
        """, (
            p["name"], p["code"], p["faculty"],
            p["head_of_department"], p["deputy_head"],
            p["location"], p["budget_year"],
            p["budget_total"], p["budget_allocated"],
            p["budget_spent"], p["subject_codes"],
            p["aims"], p["policies"], p["status"],
            p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_department(new_id)


def update_department(department_id: int,
                            payload: dict[str, Any]) -> Department:
    init_db()
    if get_department(department_id) is None:
        raise ValidationError(
            f"No department with id {department_id}")
    p = _validate_department(payload, existing_id=department_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE departments SET
              name=?, code=?, faculty=?,
              head_of_department=?, deputy_head=?, location=?,
              budget_year=?, budget_total=?, budget_allocated=?,
              budget_spent=?, subject_codes=?, aims=?, policies=?,
              status=?, notes=?, updated_on=?
            WHERE department_id=?
        """, (
            p["name"], p["code"], p["faculty"],
            p["head_of_department"], p["deputy_head"],
            p["location"], p["budget_year"],
            p["budget_total"], p["budget_allocated"],
            p["budget_spent"], p["subject_codes"],
            p["aims"], p["policies"], p["status"],
            p["notes"], now, department_id,
        ))
    return get_department(department_id)


def delete_department(department_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM departments WHERE department_id=?",
            (department_id,))
        return cur.rowcount > 0


def get_department(department_id: int) -> Department | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM departments WHERE department_id=?",
            (department_id,)).fetchone()
        return _row_department(r) if r else None


def list_departments(*,
                          faculty: str | None = None,
                          status: str | None = None,
                          active_only: bool = False,
                          over_budget: bool = False,
                          name_like: str | None = None,
                          ) -> list[Department]:
    init_db()
    sql = "SELECT * FROM departments WHERE 1=1"
    params: list[Any] = []
    if faculty:
        sql += " AND faculty=?"
        params.append(faculty)
    if status:
        sql += " AND status=?"
        params.append(status)
    if active_only:
        sql += " AND status='Active'"
    if name_like:
        sql += " AND name LIKE ?"
        params.append(f"%{name_like}%")
    if over_budget:
        sql += (" AND budget_total IS NOT NULL"
                  " AND COALESCE(budget_spent, 0) > budget_total")
    sql += " ORDER BY faculty ASC, name ASC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_department(r) for r in rows]


def _to_department_dict(d: Department) -> dict[str, Any]:
    return {
        "name": d.name,
        "code": d.code,
        "faculty": d.faculty,
        "head_of_department": d.head_of_department,
        "deputy_head": d.deputy_head,
        "location": d.location,
        "budget_year": d.budget_year,
        "budget_total": d.budget_total,
        "budget_allocated": d.budget_allocated,
        "budget_spent": d.budget_spent,
        "subject_codes": d.subject_codes,
        "aims": d.aims,
        "policies": d.policies,
        "status": d.status,
        "notes": d.notes,
    }


def set_status(department_id: int,
                    new_status: str) -> Department:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    d = get_department(department_id)
    if d is None:
        raise ValidationError(
            f"No department with id {department_id}")
    return update_department(department_id,
                                   {**_to_department_dict(d),
                                     "status": new_status})


def add_spend(department_id: int, *,
                  amount: float) -> Department:
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        raise ValidationError("Amount must be a number")
    d = get_department(department_id)
    if d is None:
        raise ValidationError(
            f"No department with id {department_id}")
    data = _to_department_dict(d)
    data["budget_spent"] = round((d.budget_spent or 0.0)
                                       + amt, 2)
    return update_department(department_id, data)


# ── Memberships ──────────────────────────────────────────────

def _validate_membership(p: dict[str, Any], *,
                              existing_id: int | None = None
                              ) -> dict[str, Any]:
    out = dict(p)
    out["staff_id"] = (out.get("staff_id") or "").strip()
    if not out["staff_id"]:
        raise ValidationError("Staff is required")
    if not _staff_exists(out["staff_id"]):
        raise ValidationError(
            f"No staff with id {out['staff_id']}")
    role = (out.get("role_in_department")
              or DEFAULT_DEPT_ROLE).strip()
    if role not in DEPT_ROLES:
        raise ValidationError(
            f"Role must be one of: {', '.join(DEPT_ROLES)}")
    out["role_in_department"] = role
    out["joined_on"] = (out.get("joined_on") or "").strip()
    if not out["joined_on"]:
        out["joined_on"] = _dt.date.today().isoformat()
    _check_date("Joined on", out["joined_on"])
    _check_date("Left on",   out.get("left_on"))
    if (out.get("left_on") and out["left_on"]
            < out["joined_on"]):
        raise ValidationError(
            "Left on must be on or after joined on")
    for k in ("notes",):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    out["left_on"] = (
        (out.get("left_on") or "").strip() or None
        if isinstance(out.get("left_on"), str)
        else out.get("left_on"))
    out["is_primary"] = bool(out.get("is_primary"))
    return out


def _row_membership(r: sqlite3.Row) -> Membership:
    return Membership(
        membership_id=r["membership_id"],
        department_id=r["department_id"],
        staff_id=r["staff_id"],
        role_in_department=r["role_in_department"],
        is_primary=bool(r["is_primary"]),
        joined_on=r["joined_on"],
        left_on=r["left_on"],
        notes=r["notes"],
        created_on=r["created_on"],
    )


def add_member(department_id: int,
                   payload: dict[str, Any]) -> Membership:
    init_db()
    if get_department(department_id) is None:
        raise ValidationError(
            f"No department with id {department_id}")
    p = _validate_membership(payload)
    # Enforce: at most one primary membership per staff_id
    if p["is_primary"]:
        with _connect() as conn:
            row = conn.execute(
                "SELECT membership_id FROM department_members "
                "WHERE staff_id=? AND is_primary=1 "
                "AND left_on IS NULL",
                (p["staff_id"],)).fetchone()
        if row:
            raise ValidationError(
                f"Staff {p['staff_id']} already has a primary "
                "department")
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO department_members (
              department_id, staff_id, role_in_department,
              is_primary, joined_on, left_on, notes, created_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            department_id, p["staff_id"],
            p["role_in_department"],
            1 if p["is_primary"] else 0,
            p["joined_on"], p["left_on"],
            p["notes"], now,
        ))
        new_id = cur.lastrowid
    return get_membership(new_id)


def update_membership(membership_id: int,
                            payload: dict[str, Any]) -> Membership:
    init_db()
    existing = get_membership(membership_id)
    if existing is None:
        raise ValidationError(
            f"No membership with id {membership_id}")
    p = _validate_membership(payload)
    if (p["is_primary"] and not existing.is_primary):
        with _connect() as conn:
            row = conn.execute(
                "SELECT membership_id FROM department_members "
                "WHERE staff_id=? AND is_primary=1 "
                "AND left_on IS NULL AND membership_id != ?",
                (p["staff_id"], membership_id)).fetchone()
        if row:
            raise ValidationError(
                f"Staff {p['staff_id']} already has a primary "
                "department")
    with _connect() as conn:
        conn.execute("""
            UPDATE department_members SET
              staff_id=?, role_in_department=?,
              is_primary=?, joined_on=?, left_on=?, notes=?
            WHERE membership_id=?
        """, (
            p["staff_id"], p["role_in_department"],
            1 if p["is_primary"] else 0,
            p["joined_on"], p["left_on"],
            p["notes"], membership_id,
        ))
    return get_membership(membership_id)


def delete_membership(membership_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM department_members "
            "WHERE membership_id=?", (membership_id,))
        return cur.rowcount > 0


def get_membership(membership_id: int) -> Membership | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM department_members "
            "WHERE membership_id=?",
            (membership_id,)).fetchone()
        return _row_membership(r) if r else None


def list_memberships(department_id: int) -> list[Membership]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM department_members "
            "WHERE department_id=? "
            "ORDER BY left_on IS NULL DESC, "
            "is_primary DESC, role_in_department, staff_id",
            (department_id,)).fetchall()
    return [_row_membership(r) for r in rows]


def memberships_for_staff(staff_id: str) -> list[Membership]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM department_members "
            "WHERE staff_id=? "
            "ORDER BY left_on IS NULL DESC, joined_on DESC",
            (staff_id,)).fetchall()
    return [_row_membership(r) for r in rows]


def member_count(department_id: int, *,
                      current_only: bool = True) -> int:
    init_db()
    sql = ("SELECT COUNT(*) c FROM department_members "
             "WHERE department_id=?")
    params: list[Any] = [department_id]
    if current_only:
        sql += " AND left_on IS NULL"
    with _connect() as conn:
        row = conn.execute(sql, params).fetchone()
    return int(row["c"]) if row else 0


def end_membership(membership_id: int, *,
                        left_on: str | None = None) -> Membership:
    m = get_membership(membership_id)
    if m is None:
        raise ValidationError(
            f"No membership with id {membership_id}")
    payload = {
        "staff_id": m.staff_id,
        "role_in_department": m.role_in_department,
        "is_primary": m.is_primary,
        "joined_on": m.joined_on,
        "left_on": left_on or _dt.date.today().isoformat(),
        "notes": m.notes,
    }
    return update_membership(membership_id, payload)


def prune_for_staff(staff_id: str) -> int:
    """Remove all memberships for a staff id (e.g. when staff
    is deleted). Returns rows removed."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM department_members WHERE staff_id=?",
            (staff_id,))
        return cur.rowcount


# ── Summary ─────────────────────────────────────────────────────

def summary() -> DepartmentsSummary:
    rows = list_departments()
    out = DepartmentsSummary(total=len(rows))
    if not rows:
        return out
    distinct_staff: set[str] = set()
    for d in rows:
        if d.status == "Active":
            out.active += 1
        elif d.status == "Restructuring":
            out.restructuring += 1
        elif d.status == "Disbanded":
            out.disbanded += 1
        out.by_faculty[d.faculty] = (
            out.by_faculty.get(d.faculty, 0) + 1)
        out.by_status[d.status] = (
            out.by_status.get(d.status, 0) + 1)
        if d.budget_total is not None:
            out.budget_total += d.budget_total
        if d.budget_spent is not None:
            out.budget_spent += d.budget_spent
        if d.budget_over:
            out.budget_over_count += 1
        for m in list_memberships(d.department_id):
            if m.is_current:
                out.total_members += 1
                distinct_staff.add(m.staff_id)
    out.budget_total = round(out.budget_total, 2)
    out.budget_spent = round(out.budget_spent, 2)
    out.distinct_staff = len(distinct_staff)
    return out


__all__ = [
    "FACULTIES", "DEFAULT_FACULTY",
    "STATUSES", "DEFAULT_STATUS",
    "DEPT_ROLES", "DEFAULT_DEPT_ROLE",
    "ValidationError",
    "Department", "Membership", "DepartmentsSummary",
    "init_db",
    "create_department", "update_department",
    "delete_department", "get_department",
    "list_departments", "set_status", "add_spend",
    "add_member", "update_membership", "delete_membership",
    "get_membership", "list_memberships",
    "memberships_for_staff", "member_count",
    "end_membership", "prune_for_staff",
    "summary",
]
