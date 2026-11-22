"""What the Staff HR API may show and do, for the signed-in caller.

The HR routes (``hr_routes.py``, ``staff_hr_routes.py``) call these
functions through ``_hr_gated``; each takes the caller first and decides
with ``domain/staff_hr/access.py``:

* staff are their *username* (the token's ``sub``) — never a numeric id;
* lists hold only the people the caller may see (``access.visible_people``:
  themselves and their reports; HR sees everyone);
* leave and timesheet approval needs ``access.can_approve_for`` (their line,
  their approvers or HR — never themselves);
* staff records are created and changed by HR only; pay is not part of a
  staff record (it is payroll's, see the payroll manager) and is refused.

Reads and writes go through the Staff HR managers. The few the managers do
not offer — organisation-wide lists of leave, timesheets and appraisals, a
new timesheet, a timesheet rejection or hours change, shifts — are the small
queries below, always narrowed to the people the caller may see.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers import (
    EmployeeManager,
    LeaveManager,
    PerformanceManager,
    TimeManager,
)
from education_system.systems.university.infrastructure.database.db import get_connection, transaction

#: Learner roles that are never Staff HR callers unless they hold a staff
#: profile (a student who also works for the university does).
LEARNER_ROLES = frozenset({'student', 'applicant', 'alumni', 'alumnus', 'parent', 'guardian'})

#: ``staff_profiles`` fields HR may set through the API (``position`` and
#: ``phone`` are the old ``staff_records`` names for two of them).
PROFILE_FIELDS = (
    'employee_id', 'department', 'job_title', 'employment_type', 'hire_date',
    'contract_end_date', 'manager_id', 'office_location', 'phone_extension',
    'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
    'bio', 'expertise_areas', 'qualifications',
)
ALIASES = {'position': 'job_title', 'phone': 'phone_extension'}
#: Pay lives with payroll; a staff record never carries it.
PAY_FIELDS = ('salary', 'pay', 'annual_salary', 'hourly_rate', 'grade_point', 'spine_point')
#: Personal details a line manager does not need about a report.
PRIVATE_FIELDS = ('emergency_contact_name', 'emergency_contact_phone',
                  'emergency_contact_relationship')


# ── who is asking ───────────────────────────────────────────────────────


def caller_of(actor: Any) -> dict:
    """The signed-in member of staff (or HR); anyone else is refused."""
    user = access.require_user(actor)
    me = user['username']
    if user['role'] in LEARNER_ROLES and not access.is_hr(user) \
            and EmployeeManager.get_profile(me) is None:
        raise PermissionError("Staff HR is for members of staff")
    return user


def _person(value: Any, me: str) -> str:
    """The username ``value`` names (default: the caller)."""
    if value in (None, ''):
        return me
    key = access.staff_key(value)
    if not key:
        raise ValueError(f"Staff member {value} not found")
    return key


def _scope(actor: dict, person: Optional[str]) -> Optional[list]:
    """The usernames a list may hold: one ``person`` the caller may see, or
    everyone the caller may see (None: HR, everyone)."""
    if person:
        access.require_view_person(actor, person)
        return [person]
    return access.visible_people(actor)


def _where(people: Optional[list], column: str, extra: list, params: list,
           also: Optional[str] = None) -> str:
    """``WHERE`` for a list narrowed to ``people`` (or ``also``, a second
    person column naming the caller) plus ``extra`` conditions."""
    conditions = list(extra)
    if people is not None:
        marks = ", ".join("?" * len(people)) or "NULL"
        scope = f"{column} IN ({marks})"
        params[:0] = list(people)
        if also:
            scope = f"({scope} OR {also[0]} = ?)"
            params.insert(len(people), also[1])
        conditions.insert(0, scope)
    return (" WHERE " + " AND ".join(conditions)) if conditions else ""


def _page(rows: list, total: int, page: int, per_page: int) -> dict:
    pages = (total + per_page - 1) // per_page if per_page else 1
    return {"items": rows, "total": total, "page": page, "per_page": per_page, "pages": pages}


# ── staff records ───────────────────────────────────────────────────────


def _public(row: dict, actor: dict) -> dict:
    """A staff record without pay or login secrets, and without personal
    contacts unless the caller is the person or HR."""
    out = {k: v for k, v in row.items()
           if k not in PAY_FIELDS and k not in ('password_hash', 'salt')}
    if not (out.get('user_id') == actor['username'] or access.is_hr(actor)):
        for field in PRIVATE_FIELDS:
            out.pop(field, None)
    out['name'] = access.display_name(out.get('user_id') or '')
    return out


def list_staff(actor, search=None, department=None, page=1, per_page=20) -> dict:
    """The staff directory, narrowed to the people the caller may see."""
    user = caller_of(actor)
    people = access.visible_people(user)
    offset = (page - 1) * per_page
    if people is None:
        rows = EmployeeManager.search_directory(search=search, department=department,
                                                limit=per_page, offset=offset)
        total = EmployeeManager.get_directory_count(search=search, department=department)
    else:
        allowed = set(people)
        rows = [r for r in EmployeeManager.search_directory(search=search, department=department,
                                                           limit=10000)
                if r.get('user_id') in allowed]
        total = len(rows)
        rows = rows[offset:offset + per_page]
    return _page([_public(r, user) for r in rows], total, page, per_page)


def _profile_by_id(profile_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT user_id FROM staff_profiles WHERE profile_id = ?",
                           (profile_id,)).fetchone()
    if not row:
        raise ValueError(f"Staff {profile_id} not found")
    return EmployeeManager.get_profile(row[0]) or {}


def get_staff(actor, profile_id: int) -> dict:
    """One staff record (themselves, a report or HR)."""
    user = caller_of(actor)
    profile = _profile_by_id(profile_id)
    access.require_view_person(user, profile['user_id'])
    if profile['user_id'] != user['username']:
        with transaction() as conn:
            access.audit(conn, user, 'view_staff_record', profile['user_id'],
                         'staff_profiles', profile_id)
    return _public(profile, user)


def _profile_data(data: dict) -> dict:
    pay = [f for f in PAY_FIELDS if data.get(f) not in (None, '')]
    if pay:
        raise ValueError("Pay is set through payroll, not on the staff record")
    out = {}
    for key, value in data.items():
        field = ALIASES.get(key, key)
        if field in PROFILE_FIELDS:
            out[field] = value
    if out.get('manager_id'):
        manager = access.staff_key(out['manager_id'])
        if not manager:
            raise ValueError(f"Line manager {out['manager_id']} not found")
        out['manager_id'] = manager
    return out


def create_staff(actor, data: dict) -> dict:
    """A staff record for an existing login (HR only)."""
    user = access.require(caller_of(actor), 'hr', "Only HR can add staff records")
    username = str(data.get('username') or data.get('user_id') or '').strip()
    if not username:
        raise ValueError("Missing required field: username (the member of staff's login)")
    with get_connection() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            raise ValueError(f"No login named {username}; create the login first")
    if EmployeeManager.get_profile(username):
        raise ValueError(f"{username} already has a staff record")
    fields = _profile_data(data)
    if not fields.get('department'):
        raise ValueError("Missing required field: department")
    profile_id = EmployeeManager.create_profile(username, **fields)
    with transaction() as conn:
        access.audit(conn, user, 'create_staff_record', username, 'staff_profiles', profile_id,
                     sorted(fields))
    return _public(EmployeeManager.get_profile(username) or {}, user)


def update_staff(actor, profile_id: int, data: dict) -> dict:
    """Change a staff record (HR only)."""
    user = access.require(caller_of(actor), 'hr', "Only HR can change staff records")
    profile = _profile_by_id(profile_id)
    fields = _profile_data(data)
    if not fields:
        raise ValueError("No valid fields to update")
    if fields.get('manager_id') == profile['user_id']:
        raise ValueError("Nobody can be their own line manager")
    EmployeeManager.update_profile(profile['user_id'], **fields)
    with transaction() as conn:
        access.audit(conn, user, 'update_staff_record', profile['user_id'], 'staff_profiles',
                     profile_id, sorted(fields))
    return _public(EmployeeManager.get_profile(profile['user_id']) or {}, user)


def my_team(actor, deep: bool = False) -> list:
    """The caller's reports (direct, or the whole tree with ``deep``)."""
    user = caller_of(actor)
    team = []
    for username in access.reports_of(user['username'], deep=deep):
        profile = EmployeeManager.get_profile(username) or {'user_id': username}
        row = _public(profile, user)
        row['manager_id'] = access.manager_of(username)
        team.append(row)
    return team


def role_holders(actor) -> list:
    """Who holds which HR role (HR administrators)."""
    return access.list_role_holders(caller_of(actor))


# ── leave ───────────────────────────────────────────────────────────────


def list_leave(actor, person=None, status=None, leave_type=None, page=1, per_page=20) -> dict:
    user = caller_of(actor)
    people = _scope(user, _person(person, user['username']) if person else None)
    params: list = []
    extra = []
    if status:
        extra.append("r.status = ?")
        params.append(status)
    if leave_type:
        extra.append("(t.name = ? OR CAST(r.leave_type_id AS TEXT) = ?)")
        params.extend([str(leave_type), str(leave_type)])
    where = _where(people, "r.user_id", extra, params)
    base = (" FROM leave_requests r LEFT JOIN leave_types t ON t.leave_type_id = r.leave_type_id"
            + where)
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*)" + base, params).fetchone()[0]
        rows = conn.execute("SELECT r.*, t.name AS leave_type_name" + base +
                            " ORDER BY r.created_at DESC LIMIT ? OFFSET ?",
                            params + [per_page, (page - 1) * per_page]).fetchall()
    return _page([dict(r) for r in rows], total, page, per_page)


def _leave(request_id: int) -> dict:
    row = LeaveManager.get_request(request_id)
    if not row:
        raise ValueError(f"Leave request {request_id} not found")
    return row


def get_leave(actor, request_id: int) -> dict:
    user = caller_of(actor)
    row = _leave(request_id)
    access.require_view_person(user, row['user_id'], what="this leave request")
    return row


def _leave_type_id(data: dict) -> int:
    value = data.get('leave_type_id') or data.get('leave_type')
    if value in (None, ''):
        raise ValueError("Missing required field: leave_type_id")
    for t in LeaveManager.get_leave_types():
        if str(t['leave_type_id']) == str(value) or str(t['name']).lower() == str(value).lower():
            return int(t['leave_type_id'])
    raise ValueError(f"Leave type {value} not found")


def submit_leave(actor, data: dict) -> dict:
    """A leave request for the caller, or (their line / HR) for a report."""
    user = caller_of(actor)
    owner = _person(data.get('user_id') or data.get('staff_id'), user['username'])
    if owner != user['username']:
        access.require_manage_person(user, owner, what="request leave for this person")
    for field in ('start_date', 'end_date'):
        if not data.get(field):
            raise ValueError(f"Missing required field: {field}")
    try:
        start = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        end = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        raise ValueError("Dates must be YYYY-MM-DD") from None
    if end < start:
        raise ValueError("The leave ends before it starts")
    request_id = LeaveManager.submit_request(owner, _leave_type_id(data), data['start_date'],
                                             data['end_date'], reason=data.get('reason') or '')
    return _leave(request_id)


def decide_leave(actor, request_id: int, data: dict) -> dict:
    """Approve / reject (their approvers or HR) or cancel (the owner, their
    line or HR) a pending leave request."""
    user = caller_of(actor)
    row = _leave(request_id)
    owner, me = row['user_id'], user['username']
    status = str(data.get('status') or '').strip().lower()
    if status not in ('approved', 'rejected', 'cancelled'):
        raise ValueError("status must be approved, rejected or cancelled")
    if status == 'cancelled':
        if owner != me:
            access.require_manage_person(user, owner, what="cancel this leave request")
        if not LeaveManager.cancel_request(request_id, owner):
            raise ValueError("Only a pending leave request can be cancelled")
        return _leave(request_id)
    if not access.can_approve_for(user, owner):
        raise PermissionError("Only their line manager, an approver or HR can decide this "
                              "leave request")
    if row.get('status') != 'pending':
        raise ValueError(f"This leave request is already {row.get('status')}")
    mail = {'recipient_email': access.email_of(owner) or '',
            'staff_name': access.display_name(owner)}
    if status == 'approved':
        if not LeaveManager.approve_request(request_id, me, **mail):
            raise ValueError("This leave request could not be approved")
    else:
        reason = str(data.get('rejection_reason') or '').strip()
        if not reason:
            raise ValueError("Give a reason for turning the leave down")
        LeaveManager.reject_request(request_id, me, reason, **mail)
    return _leave(request_id)


def leave_balances(actor, person=None, year=None) -> dict:
    """Leave balances (themselves, a report or HR)."""
    user = caller_of(actor)
    owner = _person(person, user['username'])
    access.require_view_person(user, owner, what="this person's leave")
    year = int(year) if year else datetime.now().year
    return {"user_id": owner, "year": year, "items": LeaveManager.get_balance(owner, year)}


# ── timesheets ──────────────────────────────────────────────────────────


def list_timesheets(actor, person=None, status=None, page=1, per_page=20) -> dict:
    user = caller_of(actor)
    people = _scope(user, _person(person, user['username']) if person else None)
    params: list = []
    extra = []
    if status:
        extra.append("status = ?")
        params.append(status)
    where = _where(people, "user_id", extra, params)
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM timesheets" + where, params).fetchone()[0]
        rows = conn.execute("SELECT * FROM timesheets" + where +
                            " ORDER BY week_start DESC LIMIT ? OFFSET ?",
                            params + [per_page, (page - 1) * per_page]).fetchall()
    return _page([dict(r) for r in rows], total, page, per_page)


def _timesheet(timesheet_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM timesheets WHERE timesheet_id = ?",
                           (timesheet_id,)).fetchone()
    if not row:
        raise ValueError(f"Timesheet {timesheet_id} not found")
    return dict(row)


def _hours(data: dict) -> dict:
    out = {}
    for field in ('total_hours', 'regular_hours', 'overtime_hours'):
        if field in data:
            try:
                out[field] = float(data[field] or 0)
            except (TypeError, ValueError):
                raise ValueError(f"{field} must be a number") from None
            if out[field] < 0:
                raise ValueError(f"{field} cannot be negative")
    if 'notes' in data:
        out['notes'] = str(data.get('notes') or '')
    return out


def create_timesheet(actor, data: dict) -> dict:
    """A draft timesheet for the caller, or (their line / HR) for a report."""
    user = caller_of(actor)
    owner = _person(data.get('user_id'), user['username'])
    if owner != user['username']:
        access.require_manage_person(user, owner, what="start a timesheet for this person")
    for field in ('week_start', 'week_end'):
        if not data.get(field):
            raise ValueError(f"Missing required field: {field}")
    if TimeManager.get_timesheet(owner, data['week_start']):
        raise ValueError("There is already a timesheet for that week")
    hours = _hours(data)
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO timesheets (user_id, week_start, week_end, total_hours, regular_hours, "
            "overtime_hours, status, notes) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)",
            (owner, data['week_start'], data['week_end'], hours.get('total_hours', 0),
             hours.get('regular_hours', 0), hours.get('overtime_hours', 0),
             hours.get('notes', '')))
        timesheet_id = cur.lastrowid
    return _timesheet(timesheet_id)


def update_timesheet(actor, timesheet_id: int, data: dict) -> dict:
    """Owner: change hours/notes on a draft (or rejected) sheet, submit it.
    Their approvers / HR: approve or reject a submitted sheet."""
    user = caller_of(actor)
    sheet = _timesheet(timesheet_id)
    owner, me = sheet['user_id'], user['username']
    status = str(data.get('status') or '').strip().lower()
    hours = _hours(data)
    if status in ('approved', 'rejected'):
        if not access.can_approve_for(user, owner):
            raise PermissionError("Only their line manager, an approver or HR can decide "
                                  "this timesheet")
        if sheet['status'] != 'submitted':
            raise ValueError(f"Only a submitted timesheet can be {status}")
        if status == 'approved':
            TimeManager.approve_timesheet(timesheet_id, me)
        else:
            reason = str(data.get('rejection_reason') or '').strip()
            if not reason:
                raise ValueError("Give a reason for sending the timesheet back")
            now = datetime.now().isoformat()
            with transaction() as conn:
                conn.execute("UPDATE timesheets SET status = 'rejected', approved_by = ?, "
                             "approved_date = ?, rejection_reason = ?, updated_at = ? "
                             "WHERE timesheet_id = ? AND status = 'submitted'",
                             (me, now, reason, now, timesheet_id))
        return _timesheet(timesheet_id)
    if owner != me:
        raise PermissionError("Only the member of staff can change or submit their timesheet")
    if status not in ('', 'submitted', 'draft'):
        raise ValueError("status must be submitted, approved or rejected")
    if hours:
        if sheet['status'] not in ('draft', 'rejected'):
            raise ValueError("A submitted or approved timesheet cannot be changed")
        sets = ", ".join(f"{field} = ?" for field in hours)
        with transaction() as conn:
            conn.execute(f"UPDATE timesheets SET {sets}, status = 'draft', "  # nosec B608
                         "updated_at = ? WHERE timesheet_id = ?",
                         list(hours.values()) + [datetime.now().isoformat(), timesheet_id])
    if status == 'submitted':
        if _timesheet(timesheet_id)['status'] != 'draft':
            raise ValueError("Only a draft timesheet can be submitted")
        TimeManager.submit_timesheet(timesheet_id)
    elif not hours:
        raise ValueError("No valid fields to update")
    return _timesheet(timesheet_id)


# ── appraisals ──────────────────────────────────────────────────────────


def list_appraisals(actor, person=None, status=None, cycle_id=None, page=1, per_page=20) -> dict:
    """Appraisals of the caller, their line (the whole tree) and any they
    review; HR sees all."""
    user = caller_of(actor)
    people = _scope(user, _person(person, user['username']) if person else None)
    params: list = []
    extra = []
    if status:
        extra.append("status = ?")
        params.append(status)
    if cycle_id:
        extra.append("cycle_id = ?")
        params.append(cycle_id)
    also = None if person else ("reviewer_id", user['username'])
    where = _where(people, "user_id", extra, params, also=also)
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM appraisal_records" + where,
                             params).fetchone()[0]
        rows = conn.execute("SELECT * FROM appraisal_records" + where +
                            " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                            params + [per_page, (page - 1) * per_page]).fetchall()
    active = PerformanceManager.get_active_cycle()
    result = _page([dict(r) for r in rows], total, page, per_page)
    result['active_cycle_id'] = active.get('cycle_id') if active else None
    return result


# ── shifts ──────────────────────────────────────────────────────────────


def list_shifts(actor, person=None, status=None, page=1, per_page=20) -> dict:
    """Shifts of the people the caller may see. ``shifts.staff_id`` is the
    rota's ``staff.id`` (not ``users.id``); its ``staff.username`` is the
    person, returned as ``username``."""
    user = caller_of(actor)
    owner = _person(person, user['username']) if person else None
    people = _scope(user, owner)
    params: list = []
    extra = []
    if status:
        extra.append("sh.status = ?")
        params.append(status)
    where = _where(people, "st.username", extra, params)
    base = " FROM shifts sh LEFT JOIN staff st ON st.id = sh.staff_id" + where
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*)" + base, params).fetchone()[0]
        rows = conn.execute("SELECT sh.*, st.username" + base +
                            " ORDER BY sh.shift_date DESC LIMIT ? OFFSET ?",
                            params + [per_page, (page - 1) * per_page]).fetchall()
    return _page([dict(r) for r in rows], total, page, per_page)


def create_shift(actor, data: dict) -> dict:
    """A shift on the rota (HR only); ``staff_id`` is a rota ``staff.id``
    or the person's username."""
    access.require(caller_of(actor), 'hr', "Only HR can schedule shifts")
    for field in ('staff_id', 'shift_date', 'start_time', 'end_time'):
        if not data.get(field):
            raise ValueError(f"Missing required field: {field}")
    value = str(data['staff_id']).strip()
    with transaction() as conn:
        row = conn.execute("SELECT id, username FROM staff WHERE username = ?",
                           (value,)).fetchone()
        if row is None and value.isdigit():
            row = conn.execute("SELECT id, username FROM staff WHERE id = ?",
                               (int(value),)).fetchone()
        if row is None:
            raise ValueError(f"Staff member {value} not found on the rota")
        cur = conn.execute(
            "INSERT INTO shifts (staff_id, shift_date, start_time, end_time, position, notes, "
            "status) VALUES (?, ?, ?, ?, ?, ?, 'scheduled')",
            (row[0], data['shift_date'], data['start_time'], data['end_time'],
             data.get('position') or 'general', data.get('notes') or ''))
        shift_id = cur.lastrowid
    with get_connection() as conn:
        out = dict(conn.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,)).fetchone())
    out['username'] = row[1]
    return out


__all__ = [
    'caller_of', 'list_staff', 'get_staff', 'create_staff', 'update_staff', 'my_team',
    'role_holders', 'list_leave', 'get_leave', 'submit_leave', 'decide_leave', 'leave_balances',
    'list_timesheets', 'create_timesheet', 'update_timesheet', 'list_appraisals',
    'list_shifts', 'create_shift',
]
