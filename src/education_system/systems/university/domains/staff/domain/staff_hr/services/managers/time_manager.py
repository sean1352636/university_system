"""
Time Manager

Handles time entries, clock in/out, timesheets,
attendance tracking, and time reports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers import (
    _people as people,
)

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)

#: Hours worked by one entry, in SQL.
HOURS_SQL = ("(julianday(clock_out) - julianday(clock_in)) * 24 "
             "- COALESCE(break_minutes, 0) / 60.0")
#: Entry fields a correction may change.
ENTRY_FIELDS = ('entry_date', 'clock_in', 'clock_out', 'break_minutes', 'work_type',
                'location', 'notes')


def _check_time(value: str, label: str) -> str:
    text = str(value or '').strip()
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(text, fmt).strftime('%H:%M:%S')
        except ValueError:
            continue
    raise ValueError(f"{label} must be HH:MM or HH:MM:SS")


def _check_date(value: str) -> str:
    try:
        return datetime.strptime(str(value or '').strip(), '%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError:
        raise ValueError("Date must be YYYY-MM-DD") from None


#: The standard working day and the leeway either side, for the late-arrival
#: and early-departure counts (working patterns hold days, not hours).
STANDARD_DAY_START = '09:15'
STANDARD_DAY_END = '16:45'


def _month_bounds(period: Optional[str]) -> tuple:
    """``(first day, last day, YYYY-MM)`` of a month (default this one)."""
    try:
        first = (datetime.strptime(period.strip(), '%Y-%m') if period
                 else datetime.now().replace(day=1))
    except ValueError:
        raise ValueError("Period must be in the form YYYY-MM") from None
    first = first.replace(hour=0, minute=0, second=0, microsecond=0)
    after = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    return (first.strftime('%Y-%m-%d'), (after - timedelta(days=1)).strftime('%Y-%m-%d'),
            first.strftime('%Y-%m'))


def _username_lookup(conn):
    """A function from ``time_entries.user_id`` (a username or, on older rows,
    the numeric ``users.id``) to the username."""
    usernames = {}
    known = set()
    for uid, name in conn.execute('SELECT id, username FROM users').fetchall():
        usernames[str(uid)] = name
        known.add(name)

    def lookup(value: Any) -> str:
        text = str(value)
        return text if text in known else usernames.get(text, text)
    return lookup


def _week_of(day: str) -> tuple:
    d = datetime.strptime(day, '%Y-%m-%d')
    start = d - timedelta(days=d.weekday())
    return start.strftime('%Y-%m-%d'), (start + timedelta(days=6)).strftime('%Y-%m-%d')


def _owner(conn, table: str, key: str, value: int) -> Optional[str]:
    row = conn.execute(f'SELECT user_id FROM {table} WHERE {key} = ?',  # nosec B608 - fixed names
                       (value,)).fetchone()
    return people.key(row[0], conn) if row else None


def _as_actor(actor: Any, username: Optional[str]) -> Any:
    return actor if actor is not None else ({'username': username} if username else None)


class TimeManager:
    """Manager for time and attendance tracking."""

    @staticmethod
    def clock_in(user_id: str, location: str = 'office',
                 work_type: str = 'regular', notes: Optional[str] = None,
                 actor: Any = None) -> int:
        """Record clock-in time for a user (with ``actor``: only yourself)."""
        now = datetime.now()
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                if people.me(actor) != user_id:
                    raise PermissionError("You can only clock yourself in")
            existing = conn.execute('''
                SELECT entry_id FROM time_entries
                WHERE user_id = ? AND entry_date = ? AND clock_out IS NULL
            ''', (user_id, now.strftime('%Y-%m-%d'))).fetchone()

            if existing:
                raise ValueError("Already clocked in. Please clock out first.")

            cursor = conn.execute('''
                INSERT INTO time_entries (
                    user_id, entry_date, clock_in, work_type, location, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S'),
                  work_type, location, notes))
            entry_id = cursor.lastrowid
            log_activity('clock_in', 'time_entry', user_id=user_id,
                        details={'entry_id': entry_id})
            return entry_id

    @staticmethod
    def clock_out(user_id: str, notes: Optional[str] = None, actor: Any = None) -> bool:
        """Record clock-out time for a user (with ``actor``: only yourself)."""
        now = datetime.now()
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                if people.me(actor) != user_id:
                    raise PermissionError("You can only clock yourself out")
            entry = conn.execute('''
                SELECT entry_id FROM time_entries
                WHERE user_id = ? AND entry_date = ? AND clock_out IS NULL
            ''', (user_id, now.strftime('%Y-%m-%d'))).fetchone()

            if not entry:
                raise ValueError("No active clock-in found.")

            conn.execute('''
                UPDATE time_entries
                SET clock_out = ?, updated_at = ?
                WHERE entry_id = ?
            ''', (now.strftime('%H:%M:%S'), now.isoformat(), entry[0]))
            log_activity('clock_out', 'time_entry', user_id=user_id,
                        details={'entry_id': entry[0]})
            return True

    @staticmethod
    def get_current_status(user_id: str, actor: Any = None) -> Optional[Dict[str, Any]]:
        """Check if user is currently clocked in."""
        today = datetime.now().strftime('%Y-%m-%d')
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "this time record")
            row = conn.execute('''
                SELECT * FROM time_entries
                WHERE user_id = ? AND entry_date = ? AND clock_out IS NULL
            ''', (user_id, today)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def day_summary(user_id: str, actor: Any = None) -> Dict[str, Any]:
        """Today's entry count and hours, and this week's hours."""
        today = datetime.now().strftime('%Y-%m-%d')
        week_start = _week_of(today)[0]
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "this time record")
            entries, hours = conn.execute(
                f'SELECT COUNT(*), SUM(CASE WHEN clock_out IS NOT NULL THEN {HOURS_SQL} ELSE 0 END) '  # nosec B608
                'FROM time_entries WHERE user_id = ? AND entry_date = ?', (user_id, today)).fetchone()
            week = conn.execute(
                f'SELECT SUM(CASE WHEN clock_out IS NOT NULL THEN {HOURS_SQL} ELSE 0 END) '  # nosec B608
                'FROM time_entries WHERE user_id = ? AND entry_date >= ?',
                (user_id, week_start)).fetchone()[0]
            return {'entries': entries or 0, 'hours_today': hours or 0.0,
                    'hours_week': week or 0.0}

    @staticmethod
    def get_entries(user_id: str, start_date: str, end_date: str,
                    actor: Any = None) -> List[Dict[str, Any]]:
        """Get time entries for a user within a date range (with ``actor``:
        the person, their line managers or HR); each row carries ``hours``."""
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "this time record")
            rows = conn.execute(f'''
                SELECT *, CASE WHEN clock_out IS NOT NULL THEN {HOURS_SQL} ELSE 0 END AS hours
                FROM time_entries
                WHERE user_id = ? AND entry_date BETWEEN ? AND ?
                ORDER BY entry_date DESC, clock_in DESC
            ''', (user_id, start_date, end_date)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_manual_entry(user_id: str, entry_date: str, clock_in: str,
                         clock_out: str, actor: Any = None, **data) -> int:
        """Add a manual time entry (with ``actor``: the person, their line
        managers or HR; times are checked and the entry must not fall in an
        approved timesheet's week)."""
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_self_or_manager(actor, user_id, conn, "record time")
                entry_date = _check_date(entry_date)
                clock_in = _check_time(clock_in, "Clock in")
                clock_out = _check_time(clock_out, "Clock out")
                if clock_out <= clock_in:
                    raise ValueError("Clock out must be after clock in")
                TimeManager._refuse_if_approved(conn, user_id, entry_date)
            cursor = conn.execute('''
                INSERT INTO time_entries (
                    user_id, entry_date, clock_in, clock_out,
                    break_minutes, work_type, location, notes, is_manual
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (user_id, entry_date, clock_in, clock_out,
                  data.get('break_minutes', 0), data.get('work_type', 'regular'),
                  data.get('location', 'office'), data.get('notes')))
            log_activity('create', 'time_entry', user_id=user_id,
                         details={'entry_id': cursor.lastrowid, 'manual': True})
            return cursor.lastrowid

    @staticmethod
    def _refuse_if_approved(conn, user_id: str, entry_date: str) -> None:
        start = _week_of(entry_date)[0]
        row = conn.execute("SELECT status FROM timesheets WHERE user_id = ? AND week_start = ?",
                           (user_id, start)).fetchone()
        if row and row[0] in ('submitted', 'approved'):
            raise ValueError(f"The timesheet for the week of {start} is {row[0]}; "
                             "ask your line manager to reject it before changing its time")

    @staticmethod
    def get_entry(entry_id: int, actor: Any = None) -> Optional[Dict[str, Any]]:
        """One time entry (with ``actor``: the person, their line managers
        or HR)."""
        with get_connection() as conn:
            row = conn.execute('SELECT * FROM time_entries WHERE entry_id = ?',
                               (entry_id,)).fetchone()
            if row and actor is not None:
                people.require_view(actor, people.key(row['user_id'], conn), conn,
                                    "this time record")
            return dict(row) if row else None

    @staticmethod
    def update_entry(entry_id: int, actor: Any = None, **data) -> bool:
        """Correct a time entry (with ``actor``: the person, their line
        managers or HR; not inside a submitted or approved timesheet's week).
        Corrections are marked manual."""
        changes = {k: v for k, v in data.items() if k in ENTRY_FIELDS}
        if not changes:
            return False
        with transaction() as conn:
            row = conn.execute('SELECT * FROM time_entries WHERE entry_id = ?',
                               (entry_id,)).fetchone()
            if not row:
                return False
            owner = people.key(row['user_id'], conn)
            if actor is not None:
                people.require_self_or_manager(actor, owner, conn, "correct this time")
            merged = {**dict(row), **changes}
            merged['entry_date'] = _check_date(merged['entry_date'])
            merged['clock_in'] = _check_time(merged['clock_in'], "Clock in")
            if merged.get('clock_out'):
                merged['clock_out'] = _check_time(merged['clock_out'], "Clock out")
                if merged['clock_out'] <= merged['clock_in']:
                    raise ValueError("Clock out must be after clock in")
            for day in {row['entry_date'], merged['entry_date']}:
                TimeManager._refuse_if_approved(conn, owner, day)
            changes = {k: merged[k] for k in changes}
            conn.execute('UPDATE time_entries SET ' +
                         ', '.join(validate_identifier(c, "column") + ' = ?' for c in changes) +
                         ', is_manual = 1, updated_at = ? WHERE entry_id = ?',
                         list(changes.values()) + [datetime.now().isoformat(), entry_id])
            if actor is not None and people.me(actor) != owner:
                access.audit(conn, actor, 'correct_time_entry', owner, 'time_entries', entry_id,
                             {'fields': sorted(changes)})
        log_activity('update', 'time_entry', user_id=owner, details={'entry_id': entry_id})
        return True

    @staticmethod
    def get_timesheets(user_id: str, status: Optional[str] = None,
                       actor: Any = None) -> List[Dict[str, Any]]:
        """A person's timesheets, newest week first, optionally of one
        ``status`` (with ``actor``: the person, their line managers or HR)."""
        with get_connection() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                people.require_view(actor, user_id, conn, "these timesheets")
            rows = conn.execute('SELECT * FROM timesheets WHERE user_id = ? '
                                'AND (? IS NULL OR status = ?) ORDER BY week_start DESC',
                                (user_id, status, status)).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def create_timesheet(user_id: str, week_start: Optional[str] = None,
                         actor: Any = None) -> int:
        """A draft timesheet for the week holding ``week_start`` (default:
        this week), totalled from the time entries (overtime entries count as
        overtime). With ``actor``: only yourself."""
        start, end = _week_of(week_start or datetime.now().strftime('%Y-%m-%d'))
        with transaction() as conn:
            if actor is not None:
                user_id = people.key(user_id, conn)
                if people.me(actor) != user_id:
                    raise PermissionError("You can only create your own timesheets")
            if conn.execute('SELECT 1 FROM timesheets WHERE user_id = ? AND week_start = ?',
                            (user_id, start)).fetchone():
                raise ValueError("Timesheet for this week already exists")
            regular = overtime = 0.0
            for work_type, hours in conn.execute(
                    f'SELECT work_type, SUM({HOURS_SQL}) FROM time_entries '  # nosec B608
                    'WHERE user_id = ? AND entry_date BETWEEN ? AND ? AND clock_out IS NOT NULL '
                    'GROUP BY work_type', (user_id, start, end)).fetchall():
                if work_type == 'overtime':
                    overtime += hours or 0
                else:
                    regular += hours or 0
            cur = conn.execute("INSERT INTO timesheets (user_id, week_start, week_end, "
                               "regular_hours, overtime_hours, total_hours, status) "
                               "VALUES (?, ?, ?, ?, ?, ?, 'draft')",
                               (user_id, start, end, round(regular, 2), round(overtime, 2),
                                round(regular + overtime, 2)))
            log_activity('create', 'timesheet', user_id=user_id,
                         details={'timesheet_id': cur.lastrowid})
            return cur.lastrowid

    @staticmethod
    def get_timesheet(user_id: str, week_start: str) -> Optional[Dict[str, Any]]:
        """Get a timesheet for a specific week."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM timesheets WHERE user_id = ? AND week_start = ?
            ''', (user_id, week_start)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def submit_timesheet(timesheet_id: int, actor: Any = None) -> bool:
        """Submit a draft (or rejected) timesheet for approval (with ``actor``:
        only its owner)."""
        with transaction() as conn:
            if actor is not None:
                owner = _owner(conn, 'timesheets', 'timesheet_id', timesheet_id)
                if owner is None or people.me(actor) != owner:
                    raise PermissionError("You can only submit your own timesheets")
            cur = conn.execute('''
                UPDATE timesheets
                SET status = 'submitted', submitted_date = ?, rejection_reason = NULL,
                    updated_at = ?
                WHERE timesheet_id = ? AND status IN ('draft', 'rejected')
            ''', (datetime.now().isoformat(), datetime.now().isoformat(), timesheet_id))
            if actor is not None and not cur.rowcount:
                raise ValueError("Only draft or rejected timesheets can be submitted")
            return True if actor is None else bool(cur.rowcount)

    @staticmethod
    def approve_timesheet(timesheet_id: int, approver_id: Optional[str] = None,
                          actor: Any = None) -> bool:
        """Approve a submitted timesheet (with ``actor``: someone who may
        approve for its owner — access.can_approve_for — never the owner).
        Without ``actor`` the decider is the person ``approver_id`` names,
        held to the same rule."""
        with transaction() as conn:
            owner = _owner(conn, 'timesheets', 'timesheet_id', timesheet_id)
            if owner is None:
                return False
            who = people.require_approver(actor, approver_id, owner, conn,
                                          "approve this timesheet")
            approver_id = who['username']
            cur = conn.execute('''
                UPDATE timesheets
                SET status = 'approved', approved_by = ?, approved_date = ?, updated_at = ?
                WHERE timesheet_id = ? AND status = 'submitted'
            ''', (approver_id, datetime.now().isoformat(),
                  datetime.now().isoformat(), timesheet_id))
            if cur.rowcount:
                access.audit(conn, who, 'approve_timesheet', owner, 'timesheets', timesheet_id)
            return True if actor is None else bool(cur.rowcount)

    @staticmethod
    def reject_timesheet(timesheet_id: int, reason: str, actor: Any = None,
                         approver_id: Optional[str] = None) -> bool:
        """Send a submitted timesheet back with a reason; who may decide as
        for :meth:`approve_timesheet`. Its owner may correct and resubmit."""
        if not str(reason or '').strip():
            raise ValueError("A reason is required")
        with transaction() as conn:
            owner = _owner(conn, 'timesheets', 'timesheet_id', timesheet_id)
            if owner is None:
                return False
            who = people.require_approver(actor, approver_id, owner, conn,
                                          "reject this timesheet")
            cur = conn.execute("UPDATE timesheets SET status = 'rejected', rejection_reason = ?, "
                               "updated_at = ? WHERE timesheet_id = ? AND status = 'submitted'",
                               (reason.strip(), datetime.now().isoformat(), timesheet_id))
            if cur.rowcount:
                access.audit(conn, who, 'reject_timesheet', owner, 'timesheets', timesheet_id,
                             {'reason': reason.strip()})
            return bool(cur.rowcount)

    @staticmethod
    def get_pending_approvals(approver_id: Optional[str] = None,
                              actor: Any = None) -> List[Dict[str, Any]]:
        """Submitted timesheets the approver may approve (their reports' —
        anyone's for HR — never their own)."""
        with get_connection() as conn:
            who = _as_actor(actor, people.key(approver_id, conn) if approver_id else None)
            if who is None:
                return []
            rows = conn.execute('''
                SELECT t.*, p.department, u.first_name, u.last_name
                FROM timesheets t
                LEFT JOIN staff_profiles p ON t.user_id = p.user_id
                LEFT JOIN users u ON u.username = t.user_id
                WHERE t.status = 'submitted'
                ORDER BY t.submitted_date
            ''').fetchall()
            return [dict(row) for row in rows
                    if access.can_approve_for(who, people.key(row['user_id'], conn), conn)]

    @staticmethod
    def get_attendance_report(department: Optional[str] = None,
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get attendance report — one row per user who recorded time entries.

        Driven from ``time_entries`` so anyone who actually clocked in appears,
        including users without a staff profile (department shown as 'N/A').

        Note: ``time_entries.user_id`` is stored as the numeric ``users.id``
        (e.g. '1'), whereas ``staff_profiles.user_id`` keys on the username.
        We bridge the two via the ``users`` table so departments resolve
        regardless of which identifier a time entry was recorded under.
        """
        start = start_date or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        end = end_date or datetime.now().strftime('%Y-%m-%d')

        with get_connection() as conn:
            query = '''
                SELECT te.user_id,
                       COALESCE(p.department, 'N/A') AS department,
                       u.first_name, u.last_name,
                       COUNT(DISTINCT te.entry_date) AS days_worked
                FROM time_entries te
                LEFT JOIN users u
                    ON u.username = te.user_id OR CAST(u.id AS TEXT) = te.user_id
                LEFT JOIN staff_profiles p
                    ON p.user_id = te.user_id OR p.user_id = u.username
                WHERE te.entry_date BETWEEN ? AND ?
            '''
            params = [start, end]

            if department:
                query += ' AND p.department = ?'
                params.append(department)

            query += ' GROUP BY te.user_id ORDER BY department, te.user_id'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_attendance_summary(period: Optional[str] = None) -> Dict[str, Any]:
        """Attendance for a month (``YYYY-MM``, default this one, counted up
        to today). The rate is the days people clocked in over the days they
        were due: their working pattern (Monday to Friday by default) from
        their hire date, less approved leave and university closure days."""
        first, last, label = _month_bounds(period)
        through = min(last, datetime.now().strftime('%Y-%m-%d'))
        with get_connection() as conn:
            who = _username_lookup(conn)
            entries = conn.execute(
                f'SELECT user_id, entry_date, clock_in, clock_out, work_type, {HOURS_SQL} AS hours '  # nosec B608
                'FROM time_entries WHERE entry_date BETWEEN ? AND ?', (first, through)).fetchall()
            hired = {str(r[0]): r[1] for r in conn.execute(
                'SELECT user_id, hire_date FROM staff_profiles').fetchall()}
            patterns = {str(r[0]): {int(d) for d in str(r[1]).split(',') if d.strip().isdigit()}
                        for r in conn.execute(
                            'SELECT user_id, work_days FROM staff_working_patterns').fetchall()}
            closed = {r[0][:10] for r in conn.execute(
                'SELECT holiday_date FROM staff_leave_holidays '
                'WHERE holiday_date BETWEEN ? AND ?', (first, through)).fetchall()}
            away: Dict[str, set] = {}
            for row in conn.execute('''
                SELECT user_id, start_date, end_date FROM leave_requests
                WHERE status = 'approved' AND start_date <= ? AND end_date >= ?
            ''', (through, first)).fetchall():
                day = max(str(row[1])[:10], first)
                end = min(str(row[2])[:10], through)
                while day <= end:
                    away.setdefault(str(row[0]), set()).add(day)
                    day = (datetime.strptime(day, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

        present = set()
        first_in: Dict[tuple, str] = {}
        last_out: Dict[tuple, str] = {}
        hours = overtime = 0.0
        for row in entries:
            person_day = (who(row['user_id']), row['entry_date'])
            present.add(person_day)
            hours += row['hours'] or 0
            if row['work_type'] == 'overtime':
                overtime += row['hours'] or 0
                continue
            arrived = str(row['clock_in'])[:5]
            first_in[person_day] = min(first_in.get(person_day, arrived), arrived)
            if row['clock_out']:
                left = str(row['clock_out'])[:5]
                last_out[person_day] = max(last_out.get(person_day, left), left)

        due = set()
        work_days = 0
        everyone = set(hired) | {person for person, _ in present}
        day = first
        while day <= through:
            weekday = datetime.strptime(day, '%Y-%m-%d').weekday()
            if weekday < 5 and day not in closed:
                work_days += 1
            if day not in closed:
                for person in everyone:
                    if weekday in patterns.get(person, (0, 1, 2, 3, 4)) \
                            and day not in away.get(person, ()) \
                            and (hired.get(person) or '') <= day:
                        due.add((person, day))
            day = (datetime.strptime(day, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

        return {
            'period': label,
            'work_days': work_days,
            'attendance_rate': len(present & due) * 100.0 / len(due) if due else 0.0,
            'late_arrivals': sum(1 for t in first_in.values() if t > STANDARD_DAY_START),
            'early_departures': sum(1 for t in last_out.values() if t < STANDARD_DAY_END),
            'total_clockins': len(entries),
            'avg_hours': hours / len(present) if present else 0.0,
            'overtime_hours': overtime,
        }

    @staticmethod
    def get_overtime_report(period: Optional[str] = None) -> Dict[str, Any]:
        """Hours on overtime time entries in a month (``YYYY-MM``, default
        this one), overall and per department (most first)."""
        first, last, label = _month_bounds(period)
        with get_connection() as conn:
            who = _username_lookup(conn)
            departments = {str(r[0]): r[1] for r in conn.execute(
                'SELECT user_id, department FROM staff_profiles').fetchall()}
            rows = conn.execute(
                f'SELECT user_id, {HOURS_SQL} AS hours FROM time_entries '  # nosec B608
                "WHERE work_type = 'overtime' AND clock_out IS NOT NULL "
                'AND entry_date BETWEEN ? AND ?', (first, last)).fetchall()
        per_person: Dict[str, float] = {}
        per_department: Dict[str, float] = {}
        for row in rows:
            person = who(row['user_id'])
            per_person[person] = per_person.get(person, 0) + (row['hours'] or 0)
            dept = departments.get(person) or 'Unassigned'
            per_department[dept] = per_department.get(dept, 0) + (row['hours'] or 0)
        total = sum(per_person.values())
        return {
            'period': label,
            'total_hours': total,
            'employee_count': len(per_person),
            'average_hours': total / len(per_person) if per_person else 0.0,
            'by_department': dict(sorted(per_department.items(), key=lambda kv: -kv[1])),
        }
