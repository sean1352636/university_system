"""Who may see and do what in Staff HR.

Every Staff HR screen, menu and API route asks this module; the managers
that hold confidential data (pay, cases, appraisals, personal files) check
it themselves too, so a screen that forgets cannot leak.

**Identity.** A member of staff is their *username* — the key every Staff
HR table uses (``staff_profiles.user_id``, ``leave_requests.user_id`` ...).
:func:`staff_key` turns whatever a caller holds (a username, the local
``users.id``, an employee number) into it. Never key on ``current_user['id']``:
the university and the shared login have different id spaces.

**Roles.**

* *Administrators* (``admin`` / ``administrator`` / ``superadmin``) hold
  every HR role.
* HR roles are granted per person in ``staff_hr_roles``:
  ``hr_admin`` (all of HR, grants roles), ``hr_officer`` (cases, contracts,
  absence, onboarding/exit, people records), ``payroll`` (pay, pay
  structure, pensions), ``recruiter`` (vacancies, applications, offers,
  pre-employment checks).
* A *line manager* is whoever ``staff_profiles.manager_id`` names, and
  their managers up the chain. Managers see and act for their reports
  (approvals, absence, appraisals) — never their pay or HR cases.
* Everyone else sees their own records only. The university role
  ``staff`` grants nothing extra.

Capabilities used by screens are in :data:`CAPABILITIES`;
:func:`can` answers "may this person use that part of Staff HR".
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Iterable, Optional

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

ADMIN_ROLES = frozenset({'admin', 'administrator', 'superadmin'})
HR_ROLES = ('hr_admin', 'hr_officer', 'payroll', 'recruiter')
ROLE_LABELS = {
    'hr_admin': 'HR administrator',
    'hr_officer': 'HR officer',
    'payroll': 'Payroll',
    'recruiter': 'Recruitment',
}
#: Roles that may grant or revoke HR roles.
GRANTING = ('hr_admin',)
MAX_CHAIN = 25


# ── who is asking ───────────────────────────────────────────────────────


def user_of(actor: Any) -> Optional[dict]:
    """The ``current_user`` dict for an auth object, a user dict or None."""
    if actor is None:
        return None
    if isinstance(actor, dict):
        return actor or None
    user = getattr(actor, 'current_user', None)
    return user if isinstance(user, dict) and user else None


def role_of(actor: Any) -> str:
    return str((user_of(actor) or {}).get('role') or '').strip().lower()


def username_of(actor: Any) -> Optional[str]:
    """The signed-in person's username (the Staff HR key)."""
    user = user_of(actor) or {}
    name = str(user.get('username') or user.get('sub') or '').strip()
    return name or None


def require_user(actor: Any) -> dict:
    user = user_of(actor)
    if not user or not username_of(user):
        raise PermissionError("Please sign in to use Staff HR")
    return {**user, 'username': username_of(user), 'role': role_of(user)}


def is_admin(actor: Any) -> bool:
    return role_of(actor) in ADMIN_ROLES


# ── identity ────────────────────────────────────────────────────────────


def _conn(conn):
    return conn if conn is not None else get_connection()


def staff_key(value: Any, conn=None) -> Optional[str]:
    """The username for ``value``: a username, a local ``users.id`` or an
    employee number. None when it names nobody."""
    if value is None:
        return None
    if isinstance(value, dict) or hasattr(value, 'current_user'):
        return username_of(value)
    text = str(value).strip()
    if not text:
        return None
    own = conn is None
    c = _conn(conn)
    try:
        if c.execute("SELECT 1 FROM users WHERE username = ?", (text,)).fetchone():
            return text
        if c.execute("SELECT 1 FROM staff_profiles WHERE user_id = ?", (text,)).fetchone():
            return text
        row = c.execute("SELECT user_id FROM staff_profiles WHERE employee_id = ?",
                        (text,)).fetchone()
        if row:
            return row[0]
        if text.isdigit():
            row = c.execute("SELECT username FROM users WHERE id = ?", (int(text),)).fetchone()
            if row:
                return row[0]
        return None
    finally:
        if own:
            c.close()


def display_name(username: str, conn=None) -> str:
    own = conn is None
    c = _conn(conn)
    try:
        row = c.execute("SELECT first_name, last_name FROM users WHERE username = ?",
                        (username,)).fetchone()
    except Exception:
        row = None
    finally:
        if own:
            c.close()
    name = " ".join(p for p in (row or ()) if p) if row else ""
    return name or str(username)


def email_of(username: str, conn=None) -> Optional[str]:
    own = conn is None
    c = _conn(conn)
    try:
        row = c.execute("SELECT email FROM users WHERE username = ?", (username,)).fetchone()
        return row[0] if row and row[0] else None
    finally:
        if own:
            c.close()


# ── HR roles ────────────────────────────────────────────────────────────


def _ensure(conn) -> None:
    from education_system.systems.university.domains.staff.infrastructure.database import (
        staff_hr_ddl,
    )
    staff_hr_ddl.apply_to_connection(conn)


def roles_of(actor: Any, conn=None) -> set:
    """The HR roles ``actor`` holds (administrators: all)."""
    if is_admin(actor):
        return set(HR_ROLES)
    name = username_of(actor)
    if not name:
        return set()
    own = conn is None
    c = _conn(conn)
    try:
        try:
            rows = c.execute("SELECT role FROM staff_hr_roles WHERE username = ?",
                             (name,)).fetchall()
        except Exception:   # table not created yet
            return set()
        return {r[0] for r in rows}
    finally:
        if own:
            c.close()


def has_role(actor: Any, *roles: str, conn=None) -> bool:
    held = roles_of(actor, conn)
    return bool(held & set(roles)) or 'hr_admin' in held


def is_hr(actor: Any, conn=None) -> bool:
    """HR administrator or officer (cases, contracts, people records)."""
    return has_role(actor, 'hr_officer', conn=conn)


def is_payroll(actor: Any, conn=None) -> bool:
    return has_role(actor, 'payroll', conn=conn)


def is_recruiter(actor: Any, conn=None) -> bool:
    return has_role(actor, 'recruiter', conn=conn)


def is_hr_admin(actor: Any, conn=None) -> bool:
    return has_role(actor, 'hr_admin', conn=conn)


def list_role_holders(actor: Any, conn=None) -> list:
    """``[{'username', 'role', 'granted_by', 'granted_at'}]`` (HR administrators)."""
    if not is_hr_admin(actor, conn):
        raise PermissionError("Only an HR administrator can see who holds HR roles")
    own = conn is None
    c = _conn(conn)
    try:
        _ensure(c)
        return [dict(zip(('username', 'role', 'granted_by', 'granted_at'), r)) for r in
                c.execute("SELECT username, role, granted_by, granted_at FROM staff_hr_roles "
                          "ORDER BY role, username").fetchall()]
    finally:
        if own:
            c.close()


def grant_role(actor: Any, username: str, role: str) -> bool:
    """Give ``username`` an HR role (HR administrators); True when new."""
    from education_system.systems.university.infrastructure.database.db import transaction
    if role not in HR_ROLES:
        raise ValueError(f"Unknown HR role '{role}'")
    if not is_hr_admin(actor):
        raise PermissionError("Only an HR administrator can grant HR roles")
    me = require_user(actor)['username']
    with transaction() as conn:
        _ensure(conn)
        key = staff_key(username, conn)
        if not key:
            raise ValueError(f"No user '{username}' was found")
        if conn.execute("SELECT 1 FROM staff_hr_roles WHERE username = ? AND role = ?",
                        (key, role)).fetchone():
            return False
        conn.execute("INSERT INTO staff_hr_roles (username, role, granted_by, granted_at) "
                     "VALUES (?, ?, ?, ?)", (key, role, me, _now()))
        audit(conn, actor, 'grant_hr_role', key, 'staff_hr_roles', role)
    return True


def revoke_role(actor: Any, username: str, role: str) -> bool:
    from education_system.systems.university.infrastructure.database.db import transaction
    if not is_hr_admin(actor):
        raise PermissionError("Only an HR administrator can revoke HR roles")
    with transaction() as conn:
        _ensure(conn)
        key = staff_key(username, conn) or username
        cur = conn.execute("DELETE FROM staff_hr_roles WHERE username = ? AND role = ?",
                           (key, role))
        if cur.rowcount:
            audit(conn, actor, 'revoke_hr_role', key, 'staff_hr_roles', role)
        return bool(cur.rowcount)


# ── line management ─────────────────────────────────────────────────────


def manager_of(username: str, conn=None) -> Optional[str]:
    own = conn is None
    c = _conn(conn)
    try:
        row = c.execute("SELECT manager_id FROM staff_profiles WHERE user_id = ?",
                        (username,)).fetchone()
        if not row or not row[0]:
            return None
        return staff_key(row[0], c)
    finally:
        if own:
            c.close()


def management_chain(username: str, conn=None) -> list:
    """``username``'s managers, nearest first (cycle-safe)."""
    own = conn is None
    c = _conn(conn)
    try:
        chain, seen, current = [], {username}, username
        for _ in range(MAX_CHAIN):
            boss = manager_of(current, c)
            if not boss or boss in seen:
                break
            chain.append(boss)
            seen.add(boss)
            current = boss
        return chain
    finally:
        if own:
            c.close()


def reports_of(manager: str, conn=None, deep: bool = False) -> list:
    """Usernames whose line manager is ``manager`` (``deep``: the whole tree)."""
    own = conn is None
    c = _conn(conn)
    try:
        rows = c.execute("SELECT user_id, manager_id FROM staff_profiles "
                         "WHERE manager_id IS NOT NULL AND manager_id != ''").fetchall()
        by_manager: dict = {}
        for user, boss in rows:
            key = staff_key(boss, c) or boss
            by_manager.setdefault(key, []).append(user)
        out, todo, seen = [], [manager], {manager}
        while todo:
            for user in by_manager.get(todo.pop(0), []):
                if user in seen:
                    continue
                seen.add(user)
                out.append(user)
                if deep:
                    todo.append(user)
        return out
    finally:
        if own:
            c.close()


def manages(manager: Any, staff: str, conn=None) -> bool:
    """Is ``manager`` anywhere above ``staff`` in the line?"""
    name = username_of(manager) if not isinstance(manager, str) else manager
    return bool(name) and name != staff and name in management_chain(staff, conn)


def is_line_manager(actor: Any, conn=None) -> bool:
    name = username_of(actor)
    return bool(name) and bool(reports_of(name, conn))


def approvers_for(staff: str, conn=None) -> list:
    """Who approves ``staff``'s requests (leave, timesheets, flexible
    working): their line manager — the next one up when there is none
    directly — else the HR administrators and officers."""
    chain = management_chain(staff, conn)
    if chain:
        return [chain[0]]
    own = conn is None
    c = _conn(conn)
    try:
        try:
            hr = [r[0] for r in c.execute(
                "SELECT DISTINCT username FROM staff_hr_roles WHERE role IN "
                "('hr_admin', 'hr_officer') ORDER BY username").fetchall()]
        except Exception:
            hr = []
        return hr
    finally:
        if own:
            c.close()


# ── decisions ───────────────────────────────────────────────────────────


def can_view_person(actor: Any, staff: str, conn=None) -> bool:
    """Their own record, a line manager's report, or HR."""
    me = username_of(actor)
    if not me:
        return False
    return me == staff or is_hr(actor, conn) or manages(me, staff, conn)


def can_manage_person(actor: Any, staff: str, conn=None) -> bool:
    """Act *for* someone (approve, record absence, review): their line
    manager or HR — never yourself."""
    me = username_of(actor)
    if not me or me == staff:
        return False
    return is_hr(actor, conn) or manages(me, staff, conn)


def can_approve_for(actor: Any, staff: str, conn=None) -> bool:
    """Approve ``staff``'s leave / timesheets / flexible working: anyone
    above them in the line, an HR officer/administrator; not themselves."""
    me = username_of(actor)
    if not me or me == staff:
        return False
    return is_hr(actor, conn) or manages(me, staff, conn) or me in approvers_for(staff, conn)


def can_view_pay(actor: Any, staff: str, conn=None) -> bool:
    """Pay is the person's own business and payroll's — not their manager's."""
    me = username_of(actor)
    return bool(me) and (me == staff or is_payroll(actor, conn))


#: capability -> who has it (screens / menus / API ask :func:`can`).
CAPABILITIES = {
    'hr': lambda a, c: is_hr(a, c),                    # HR admin screens in general
    'hr_admin': lambda a, c: is_hr_admin(a, c),        # roles, settings, retention
    'cases': lambda a, c: is_hr(a, c),                 # grievances, discipline (all)
    'payroll': lambda a, c: is_payroll(a, c),          # pay runs, allowances, tax, spine
    'recruitment': lambda a, c: is_recruiter(a, c),    # vacancies, applications, offers
    'manager': lambda a, c: is_hr(a, c) or is_line_manager(a, c),   # approvals for reports
    'reports': lambda a, c: is_hr(a, c),               # organisation-wide HR reports
    'operations': lambda a, c: is_hr(a, c),            # assets, equipment, committees admin
}


def can(actor: Any, capability: str, conn=None) -> bool:
    """May ``actor`` use ``capability`` (a key of :data:`CAPABILITIES`)?"""
    check = CAPABILITIES.get(capability)
    if check is None:
        raise ValueError(f"Unknown Staff HR capability '{capability}'")
    if not username_of(actor):
        return False
    try:
        return bool(check(actor, conn))
    except Exception:
        logger.warning("Staff HR capability %s check failed; refusing", capability,
                       exc_info=True)
        return False


def require(actor: Any, capability: str, message: Optional[str] = None, conn=None) -> dict:
    user = require_user(actor)
    if not can(actor, capability, conn):
        raise PermissionError(message or "You do not have access to this part of Staff HR")
    return user


def require_view_person(actor: Any, staff: str, conn=None, what: str = "this person's record") -> dict:
    user = require_user(actor)
    if not can_view_person(actor, staff, conn):
        raise PermissionError(f"You cannot see {what}")
    return user


def require_manage_person(actor: Any, staff: str, conn=None, what: str = "act for this person") -> dict:
    user = require_user(actor)
    if not can_manage_person(actor, staff, conn):
        raise PermissionError(f"Only their line manager or HR can {what}")
    return user


def visible_people(actor: Any, conn=None) -> Optional[list]:
    """Usernames ``actor`` may see records of; None means everyone (HR)."""
    if is_hr(actor, conn):
        return None
    me = username_of(actor)
    if not me:
        return []
    return [me] + reports_of(me, conn, deep=True)


# ── audit ───────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def audit(conn, actor: Any, action: str, subject: Optional[str] = None,
          entity: Optional[str] = None, entity_id: Any = None, details: Any = None) -> None:
    """Record who did or read what (on ``conn``, inside the caller's work)."""
    try:
        conn.execute("INSERT INTO staff_hr_audit (at, actor, action, subject_username, entity, "
                     "entity_id, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (_now(), username_of(actor) if not isinstance(actor, str) else actor,
                      action, subject, entity, None if entity_id is None else str(entity_id),
                      None if details is None else json.dumps(details, default=str)))
    except Exception:
        logger.warning("Staff HR audit row not written (%s)", action, exc_info=True)


def audit_trail(actor: Any, subject: Optional[str] = None, limit: int = 500) -> list:
    """The HR audit trail (HR administrators), optionally for one person."""
    if not is_hr_admin(actor):
        raise PermissionError("Only an HR administrator can read the HR audit trail")
    with get_connection() as conn:
        _ensure(conn)
        sql, params = "SELECT * FROM staff_hr_audit", []
        if subject:
            sql += " WHERE subject_username = ?"
            params.append(subject)
        rows = conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?", params + [int(limit)])
        return [dict(r) for r in rows.fetchall()]


def filter_people(rows: Iterable[dict], actor: Any, key: str = 'user_id', conn=None) -> list:
    """Keep the rows about people ``actor`` may see."""
    allowed = visible_people(actor, conn)
    rows = list(rows)
    if allowed is None:
        return rows
    allowed = set(allowed)
    return [r for r in rows if str(r.get(key)) in allowed]


__all__ = [
    'ADMIN_ROLES', 'HR_ROLES', 'ROLE_LABELS', 'CAPABILITIES',
    'user_of', 'role_of', 'username_of', 'require_user', 'is_admin',
    'staff_key', 'display_name', 'email_of',
    'roles_of', 'has_role', 'is_hr', 'is_payroll', 'is_recruiter', 'is_hr_admin',
    'list_role_holders', 'grant_role', 'revoke_role',
    'manager_of', 'management_chain', 'reports_of', 'manages', 'is_line_manager',
    'approvers_for', 'can_view_person', 'can_manage_person', 'can_approve_for',
    'can_view_pay', 'can', 'require', 'require_view_person', 'require_manage_person',
    'visible_people', 'filter_people', 'audit', 'audit_trail',
]
