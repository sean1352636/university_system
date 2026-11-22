"""Support teams, categories and who gets a ticket.

Teams
-----
UK student-services teams (:data:`TEAMS`). A team is a Helpdesk
``departments`` row carrying its key in ``departments.team_key`` (migration
0b09872e815a adds the column and the rows for teams that had none): the
row gives the team its display name, e-mail, lead (``manager_id``) and an
optional SLA policy. Membership is ``staff_assignments``: one row per
(adviser, team) with ``category`` = the team key, ``max_concurrent_tickets``
the adviser's capacity, ``auto_assign_enabled`` and ``is_primary`` (a team
lead). Rows written before teams existed carry a ticket category ('Mental
Health', 'Technical' ...); they count for the team that category routes to.

``duty`` is not a routing target: its members are the duty officers who
take Critical tickets raised out of hours (see ``sla.set_due``).

Categories
----------
New tickets are offered :data:`UK_CATEGORIES`. The older US-style values
(:data:`LEGACY_CATEGORIES`, and the Helpdesk's 'Technical Support' ...)
stay on the rows that have them and still route and display:
:func:`uk_category` maps any of them to its UK category and
:func:`stored_categories` gives every stored value a UK category stands for
(for filters).

Assignment
----------
:func:`pick_assignee` gives a ticket to the least-loaded active member of
the team who is under their capacity; ties go to whoever was given a
ticket least recently (round robin).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# key -> (display label, default department name, other department names)
TEAMS = {
    'wellbeing': ('Wellbeing', 'Wellbeing', ('Student Wellbeing', 'Counselling')),
    'disability': ('Disability & Reasonable Adjustments', 'Disability & Inclusion',
                   ('Disability Service', 'Disability Services')),
    'finance': ('Fees & Funding', 'Financial Services', ('Student Funding', 'Fees & Funding')),
    'accommodation': ('Accommodation', 'Accommodation', ('Accommodation Services', 'Housing')),
    'academic_registry': ('Academic Registry', 'Academic Affairs',
                          ('Academic Registry', 'Registry')),
    'international_visa': ('International/Visa', 'International Student Support',
                           ('International Office',)),
    'it_services': ('IT Services', 'IT Support', ('IT Services',)),
    'careers': ('Careers', 'Careers Service', ('Careers',)),
    'general': ('General', 'Student Services', ('General Enquiries',)),
}
DUTY_TEAM = 'duty'
DUTY_DEPARTMENT = 'Duty Officer'
DEFAULT_TEAM = 'general'

# The categories offered for new tickets, and the team each goes to.
CATEGORY_TEAM = {
    'International/Visa': 'international_visa',
    'Wellbeing': 'wellbeing',
    'Disability & Reasonable Adjustments': 'disability',
    'Accommodation': 'accommodation',
    'Fees & Funding': 'finance',
    'Academic Registry': 'academic_registry',
    'IT': 'it_services',
    'Careers': 'careers',
    'General': 'general',
}
UK_CATEGORIES = list(CATEGORY_TEAM)

# Values already on tickets (Student Support's first list and the
# Helpdesk's) -> the UK category they now mean.
LEGACY_CATEGORIES = {
    'Academic': 'Academic Registry',
    'Technical': 'IT',
    'Financial Aid': 'Fees & Funding',
    'Library Services': 'General',
    'Accommodation': 'Accommodation',
    'Accessibility': 'Disability & Reasonable Adjustments',
    'Mental Health': 'Wellbeing',
    'Registration': 'Academic Registry',
    'Housing': 'Accommodation',
    'Dining': 'General',
    'Parking': 'General',
    'Career Services': 'Careers',
    'Student Activities': 'General',
    'Other': 'General',
    # Helpdesk
    'Technical Support': 'IT',
    'Account Access': 'IT',
    'Academic Inquiry': 'Academic Registry',
    'Financial Services': 'Fees & Funding',
    'Financial': 'Fees & Funding',
    'Hardware': 'IT',
    'Software': 'IT',
    'Network': 'IT',
    'General Inquiry': 'General',
    'Visa': 'International/Visa',
    'International': 'International/Visa',
    'Disability': 'Disability & Reasonable Adjustments',
    'Finance': 'Fees & Funding',
    'Careers': 'Careers',
    'IT Support': 'IT',
}

_STAFF_ROLES = ('staff', 'support_staff', 'support_agent', 'helpdesk_agent',
                'admin', 'super_admin', 'superadmin')


def _fold(value) -> str:
    return ' '.join(str(value or '').replace('_', ' ').split()).lower()


_BY_FOLD = {_fold(k): v for k, v in LEGACY_CATEGORIES.items()}
_BY_FOLD.update({_fold(k): k for k in UK_CATEGORIES})
_TEAM_BY_FOLD = {_fold(k): k for k in TEAMS}
_TEAM_BY_FOLD.update({_fold(v[0]): k for k, v in TEAMS.items()})


# ── categories ───────────────────────────────────────────────────────────


def uk_category(category) -> Optional[str]:
    """The UK category for any stored or offered value (None if unknown)."""
    return _BY_FOLD.get(_fold(category))


def category_label(category) -> str:
    """How a stored category is shown: its UK category, else as stored."""
    return uk_category(category) or str(category or '')


def stored_categories(category) -> list:
    """Every stored value that means ``category`` (a UK or legacy value),
    for filtering old and new tickets together."""
    uk = uk_category(category)
    if uk is None:
        return [str(category)]
    return [uk] + sorted(k for k, v in LEGACY_CATEGORIES.items() if v == uk and k != uk)


def team_for_category(category) -> Optional[str]:
    """The team a category (UK or legacy) goes to."""
    uk = uk_category(category)
    return CATEGORY_TEAM.get(uk) if uk else None


def team_key(value) -> Optional[str]:
    """A team key from a key or display label ('IT Services' -> 'it_services')."""
    folded = _fold(value)
    if folded == DUTY_TEAM:
        return DUTY_TEAM
    return _TEAM_BY_FOLD.get(folded)


def team_label(team) -> str:
    key = team_key(team)
    if key == DUTY_TEAM:
        return DUTY_DEPARTMENT
    return TEAMS[key][0] if key else str(team or '')


def route(category, subcategory=None, team=None) -> str:
    """The team for a ticket: ``team`` when it names one, else the team of
    the subcategory or category, else :data:`DEFAULT_TEAM`."""
    key = team_key(team) if team else None
    if key and key != DUTY_TEAM:
        return key
    for value in (subcategory, category):
        key = team_for_category(value) if value else None
        if key:
            return key
    return DEFAULT_TEAM


# ── membership ───────────────────────────────────────────────────────────

_CACHE_SECONDS = 30
_cache: dict = {}
_cache_lock = threading.Lock()


def clear_cache() -> None:
    """Forget cached memberships (called after any membership change)."""
    with _cache_lock:
        _cache.clear()


def _open():
    from education_system.systems.university.domains.student_support.domain.student_support import (
        store,
    )
    return store.connect()


def _has(conn, table) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table,)).fetchone() is not None


def _columns(conn, table) -> set:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}  # nosec B608


def _membership_rows(conn) -> list:
    """``(username, team, max_concurrent, auto_assign, is_primary)`` for every
    staff_assignments row whose person is an active support user."""
    if not _has(conn, 'staff_assignments'):
        return []
    marks = ", ".join("?" * len(_STAFF_ROLES))
    rows = conn.execute(
        "SELECT sa.staff_id, sa.category, COALESCE(sa.max_concurrent_tickets, 10), "
        "COALESCE(sa.auto_assign_enabled, 1), COALESCE(sa.is_primary, 0) "
        "FROM staff_assignments sa JOIN users u ON u.username = sa.staff_id "
        f"WHERE u.role IN ({marks}) ORDER BY sa.assignment_id", _STAFF_ROLES).fetchall()  # nosec B608
    out = []
    for username, category, cap, auto, primary in rows:
        team = team_key(category) or team_for_category(category)
        if team:
            out.append((str(username), team, int(cap), bool(auto), bool(primary)))
    return out


def _department_rows(conn) -> list:
    """``(team, department name, manager username, e-mail, sla_policy_id)``."""
    if not _has(conn, 'departments'):
        return []
    has_key = 'team_key' in _columns(conn, 'departments')
    key_sql = "d.team_key" if has_key else "NULL"
    rows = conn.execute(
        f"SELECT {key_sql}, d.name, u.username, d.email, d.sla_policy_id FROM departments d "  # nosec B608
        "LEFT JOIN users u ON u.id = d.manager_id WHERE COALESCE(d.is_active, 1) = 1").fetchall()
    out = []
    for key, name, manager, email, policy in rows:
        team = team_key(key) if key else None
        if team is None:
            for k, (_label, default, aliases) in TEAMS.items():
                if name == default or name in aliases:
                    team = k
                    break
            if team is None and name == DUTY_DEPARTMENT:
                team = DUTY_TEAM
        if team:
            out.append((team, name, manager, email, policy))
    return out


def _snapshot(conn=None) -> dict:
    """Memberships and departments, cached for a few seconds per database."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        config,
    )
    key = str(config.SUPPORT_DB)
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < _CACHE_SECONDS:
            return hit[1]
    own = conn is None
    conn = _open() if own else conn
    try:
        snap = {'members': _membership_rows(conn), 'departments': _department_rows(conn)}
    finally:
        if own:
            conn.close()
    with _cache_lock:
        _cache[key] = (time.monotonic(), snap)
    return snap


def team_members(team, conn=None) -> set:
    """Usernames of the team's members (its lead included)."""
    key = team_key(team)
    if not key:
        return set()
    snap = _snapshot(conn)
    names = {m[0] for m in snap['members'] if m[1] == key}
    names |= {d[2] for d in snap['departments'] if d[0] == key and d[2]}
    return names


def user_teams(username, conn=None) -> set:
    """The teams ``username`` belongs to (as a member or a department lead)."""
    if not username:
        return set()
    username = str(username)
    snap = _snapshot(conn)
    teams = {m[1] for m in snap['members'] if m[0] == username}
    teams |= {d[0] for d in snap['departments'] if d[2] == username}
    return teams


def team_leads(team, conn=None) -> set:
    """Who hears about breaches: the department's manager and any primary
    members; the admins when the team has neither."""
    key = team_key(team)
    snap = _snapshot(conn)
    leads = {d[2] for d in snap['departments'] if d[0] == key and d[2]}
    leads |= {m[0] for m in snap['members'] if m[1] == key and m[4]}
    if leads:
        return leads
    own = conn is None
    conn = _open() if own else conn
    try:
        return {r[0] for r in conn.execute(
            "SELECT username FROM users WHERE role IN ('admin', 'super_admin', 'superadmin')")}
    finally:
        if own:
            conn.close()


def team_department(team, conn=None) -> Optional[dict]:
    """``{'name', 'manager', 'email', 'sla_policy_id'}`` of the team's department."""
    key = team_key(team)
    for d in _snapshot(conn)['departments']:
        if d[0] == key:
            return {'name': d[1], 'manager': d[2], 'email': d[3], 'sla_policy_id': d[4]}
    return None


def duty_officers(conn=None) -> set:
    return team_members(DUTY_TEAM, conn)


# ── workload and assignment ──────────────────────────────────────────────


def open_load(conn, usernames: Iterable[str]) -> dict:
    """``{username: active tickets assigned}`` (0 for anyone with none)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    names = sorted({str(u) for u in usernames if u})
    if not names:
        return {}
    marks = ", ".join("?" * len(names))
    active = ", ".join("?" * len(schema.ACTIVE_STATUSES))
    load = dict.fromkeys(names, 0)
    for user, count in conn.execute(
            f"SELECT assigned_to, COUNT(*) FROM support_tickets WHERE assigned_to IN ({marks}) "  # nosec B608
            f"AND status IN ({active}) GROUP BY assigned_to",
            names + list(schema.ACTIVE_STATUSES)).fetchall():
        load[str(user)] = count
    return load


def capacity(conn, team=None) -> list:
    """Per member: ``{'username', 'team', 'open', 'max', 'available',
    'auto_assign', 'lead'}`` (all teams when ``team`` is None)."""
    key = team_key(team) if team else None
    members = [m for m in _membership_rows(conn) if key is None or m[1] == key]
    load = open_load(conn, [m[0] for m in members])
    return [{'username': u, 'team': t, 'open': load.get(u, 0), 'max': cap,
             'available': max(cap - load.get(u, 0), 0), 'auto_assign': auto, 'lead': lead}
            for u, t, cap, auto, lead in members]


def pick_assignee(team, conn=None, exclude: Iterable[str] = ()) -> Optional[str]:
    """The member to give a new ticket to, or None when nobody is free.

    Candidates are the team's members with auto-assign on and fewer active
    tickets than their capacity. The least loaded wins; on a tie, whoever
    was last given a ticket longest ago (never first) — a round robin.
    """
    key = team_key(team)
    if not key:
        return None
    own = conn is None
    conn = _open() if own else conn
    try:
        skip = {str(e) for e in exclude}
        caps: dict = {}
        for username, t, cap, auto, _lead in _membership_rows(conn):
            if t == key and auto and username not in skip:
                caps[username] = max(caps.get(username, 0), cap)
        if not caps:
            return None
        load = open_load(conn, caps)
        free = [u for u in caps if load.get(u, 0) < caps[u]]
        if not free:
            return None
        marks = ", ".join("?" * len(free))
        last = dict(conn.execute(
            f"SELECT assigned_to, MAX(COALESCE(created_at, '')) FROM support_tickets "  # nosec B608
            f"WHERE assigned_to IN ({marks}) GROUP BY assigned_to", free).fetchall())
        return min(free, key=lambda u: (load.get(u, 0), last.get(u) or '', u))
    finally:
        if own:
            conn.close()


# ── membership changes (team leads and admins) ───────────────────────────


def _may_manage(actor, team, conn) -> bool:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as _auth,
    )
    user = _auth.require_auth(actor)
    if _auth.is_admin(user):
        return True
    return str(user['username']) in team_leads(team, conn) and _auth.is_support_staff(user)


def set_member(actor, team, username, *, max_concurrent=None, auto_assign=None,
               lead=None) -> dict:
    """Add ``username`` to ``team`` or change their capacity / auto-assign /
    lead flag. Admins and the team's leads only; audited."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as _auth,
        store,
    )
    from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
        log_audit,
    )
    key = team_key(team)
    if not key:
        raise ValueError(f"Unknown team '{team}'. Choose from: {', '.join(list(TEAMS) + [DUTY_TEAM])}")
    if max_concurrent is not None:
        max_concurrent = int(max_concurrent)
        if not 0 <= max_concurrent <= 200:
            raise ValueError("Capacity must be between 0 and 200 tickets")
    with store.writing() as conn:
        if not _may_manage(actor, key, conn):
            raise PermissionError("Only an administrator or the team's lead can change its members")
        row = conn.execute("SELECT username, role FROM users WHERE username = ?",
                           (str(username or '').strip(),)).fetchone()
        if row is None:
            raise ValueError(f"No user '{username}' was found")
        if not _auth.is_support_staff({'username': row[0], 'role': row[1]}):
            raise ValueError(f"{row[0]} is not support staff")
        existing = conn.execute("SELECT assignment_id, max_concurrent_tickets, auto_assign_enabled, "
                                "is_primary FROM staff_assignments WHERE staff_id = ? AND category = ?",
                                (row[0], key)).fetchone()
        old = dict(zip(('max', 'auto_assign', 'lead'), existing[1:])) if existing else None
        new = {'max': max_concurrent if max_concurrent is not None else (old or {}).get('max', 10),
               'auto_assign': int(bool(auto_assign)) if auto_assign is not None
               else (old or {}).get('auto_assign', 1),
               'lead': int(bool(lead)) if lead is not None else (old or {}).get('lead', 0)}
        if existing:
            conn.execute("UPDATE staff_assignments SET max_concurrent_tickets = ?, "
                         "auto_assign_enabled = ?, is_primary = ? WHERE assignment_id = ?",
                         (new['max'], new['auto_assign'], new['lead'], existing[0]))
        else:
            conn.execute("INSERT INTO staff_assignments (staff_id, category, is_primary, "
                         "max_concurrent_tickets, auto_assign_enabled) VALUES (?, ?, ?, ?, ?)",
                         (row[0], key, new['lead'], new['max'], new['auto_assign']))
        log_audit('team_member_set', resource_id=key, resource_type='support_team', actor=actor,
                  conn=conn, old_values=old, new_values={'username': row[0], **new})
    clear_cache()
    return {'team': key, 'username': row[0], **new}


def remove_member(actor, team, username) -> bool:
    """Take ``username`` out of ``team`` (their tickets stay with them)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        store,
    )
    from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
        log_audit,
    )
    key = team_key(team)
    if not key:
        raise ValueError(f"Unknown team '{team}'")
    with store.writing() as conn:
        if not _may_manage(actor, key, conn):
            raise PermissionError("Only an administrator or the team's lead can change its members")
        cur = conn.execute("DELETE FROM staff_assignments WHERE staff_id = ? AND category = ?",
                           (str(username), key))
        if cur.rowcount:
            log_audit('team_member_removed', resource_id=key, resource_type='support_team',
                      actor=actor, conn=conn, old_values={'username': str(username)})
    clear_cache()
    return bool(cur.rowcount)


def teams() -> list:
    """``[{'key', 'label'}]`` for every routing team (duty officers excluded)."""
    return [{'key': k, 'label': v[0]} for k, v in TEAMS.items()]


__all__ = [
    'TEAMS', 'DUTY_TEAM', 'DEFAULT_TEAM', 'CATEGORY_TEAM', 'UK_CATEGORIES', 'LEGACY_CATEGORIES',
    'uk_category', 'category_label', 'stored_categories', 'team_for_category', 'team_key',
    'team_label', 'route', 'team_members', 'user_teams', 'team_leads', 'team_department',
    'duty_officers', 'open_load', 'capacity', 'pick_assignee', 'set_member', 'remove_member',
    'teams', 'clear_cache',
]
