"""The rules every kind of staff leave shares: policy settings, the leave
year, who works which days (and their FTE), bank holidays and closures,
counting working days, and telling people.

**Settings.** :data:`DEFAULTS` holds every policy value; a row in
``staff_leave_settings`` overrides one (HR, via :func:`set_setting`). The
statutory family-leave rates are the 2025/26 figures — HR updates them each
April.

**Leave year.** ``leave_year_start`` (``MM-DD``, default ``01-01``). A leave
year is named by the calendar year it starts in, so with ``09-01`` the year
``2026`` runs 1 Sep 2026 – 31 Aug 2027; ``leave_balances.year`` holds that.

**FTE.** ``staff_working_patterns.fte`` when set; else a ``staff_contracts``
``fte`` column if there is one; else contracted ``working_hours_per_week``
over ``full_time_hours``; else 1.

**Working days.** A day counts when it is one of the person's working
weekdays and is not a bank holiday or closure (those are accounted for in
the annual leave allocation instead, see ``entitlement``).
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

#: key -> (default, label, kind). kind: int / float / bool / str / mmdd.
DEFAULTS = {
    'leave_year_start': ('01-01', 'Leave year starts (MM-DD)', 'mmdd'),
    'full_time_hours': (37.5, 'Full-time hours per week', 'float'),
    'carry_over_cap_days': (5.0, 'Most days carried into the next leave year', 'float'),
    'carry_over_expiry_months': (3, 'Carried days expire this many months into the year', 'int'),
    'bank_holiday_region': ('england-and-wales', 'Bank holiday region', 'str'),
    'bank_holidays_pro_rata': (True, 'Part-time staff get bank holidays pro rata', 'bool'),
    'allow_negative_balance': (False, 'Allow leave beyond the remaining balance', 'bool'),
    'absence_window_months': (12, 'Absence triggers look back this many months', 'int'),
    'trigger_bradford': (200.0, 'Bradford factor trigger', 'float'),
    'trigger_episodes': (3, 'Absence episodes trigger', 'int'),
    'trigger_days': (10.0, 'Absence days trigger', 'float'),
    'triggers_exclude_protected': (True, 'Disability / pregnancy absence is not counted', 'bool'),
    'self_cert_days': (7, 'Calendar days covered by self-certification', 'int'),
    'rtw_due_days': (5, 'Return-to-work interview due within (days)', 'int'),
    'statutory_weekly_rate': (187.18, 'Statutory family pay weekly rate (£)', 'float'),
    'lower_earnings_limit': (125.0, 'Lower earnings limit (£ a week)', 'float'),
    'pay_service_weeks': (26, 'Weeks of service for statutory pay', 'int'),
    'paternity_leave_service_weeks': (0, 'Weeks of service for paternity leave', 'int'),
    'spl_service_weeks': (26, 'Weeks of service for shared parental leave', 'int'),
    'maternity_leave_weeks': (52, 'Maternity / adoption leave weeks', 'int'),
    'statutory_pay_weeks': (39, 'SMP / SAP weeks', 'int'),
    'higher_rate_weeks': (6, 'Weeks paid at 90% of earnings', 'int'),
    'paternity_weeks': (2, 'Paternity leave / SPP weeks', 'int'),
    'spl_max_weeks': (50, 'Most shared parental leave weeks', 'int'),
    'kit_days_limit': (10, 'Keeping-in-touch days', 'int'),
    'split_days_limit': (20, 'Shared parental (SPLIT) days', 'int'),
    'fw_decision_months': (2, 'Flexible working decision within (months)', 'int'),
    'fw_requests_per_year': (2, 'Flexible working requests in any 12 months', 'int'),
}

WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
FULL_WEEK = (0, 1, 2, 3, 4)


def ensure(conn) -> None:
    from education_system.systems.university.domains.staff.infrastructure.database import (
        staff_hr_ddl,
    )
    staff_hr_ddl.apply_to_connection(conn)


def _conn(conn):
    return conn if conn is not None else get_connection()


def as_date(value: Any) -> Optional[date]:
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()


def today() -> date:
    return date.today()


def now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ── settings ────────────────────────────────────────────────────────────


def _cast(key: str, raw: Any):
    default, _label, kind = DEFAULTS[key]
    if raw is None or raw == '':
        return default
    try:
        if kind == 'int':
            return int(float(raw))
        if kind == 'float':
            return float(raw)
        if kind == 'bool':
            return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')
        if kind == 'mmdd':
            text = str(raw).strip()
            datetime.strptime(f'2024-{text}', '%Y-%m-%d')
            return text
        return str(raw)
    except (TypeError, ValueError):
        logger.warning("Bad staff leave setting %s=%r; using the default", key, raw)
        return default


def settings(conn=None) -> dict:
    """Every policy value (overrides applied)."""
    own = conn is None
    c = _conn(conn)
    try:
        ensure(c)
        stored = {k: v for k, v in c.execute("SELECT key, value FROM staff_leave_settings")}
        return {k: _cast(k, stored.get(k)) for k in DEFAULTS}
    finally:
        if own:
            c.close()


def setting(key: str, conn=None):
    return settings(conn)[key]


def set_setting(actor: Any, key: str, value: Any) -> Any:
    """Change one policy value (HR administrators)."""
    access.require(actor, 'hr_admin', "Only an HR administrator can change leave policy")
    if key not in DEFAULTS:
        raise ValueError(f"Unknown leave setting '{key}'")
    kind = DEFAULTS[key][2]
    if kind == 'mmdd':
        datetime.strptime(f'2024-{value}', '%Y-%m-%d')
    elif kind in ('int', 'float'):
        if float(value) < 0:
            raise ValueError(f"{DEFAULTS[key][1]} cannot be negative")
    stored = ('1' if _cast(key, value) else '0') if kind == 'bool' else str(value).strip()
    with get_connection() as conn:
        ensure(conn)
        conn.execute("INSERT INTO staff_leave_settings (key, value, updated_by, updated_at) "
                     "VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                     "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
                     (key, stored, access.username_of(actor), now()))
        access.audit(conn, actor, 'leave_setting', None, 'staff_leave_settings', key,
                     {'value': stored})
        conn.commit()
    return _cast(key, stored)


# ── leave year ──────────────────────────────────────────────────────────


def _year_start(year: int, mmdd: str) -> date:
    month, day = (int(p) for p in mmdd.split('-'))
    if month == 2 and day == 29:
        day = 28
    return date(year, month, day)


def _year_for(d: date, mmdd: str) -> int:
    return d.year if d >= _year_start(d.year, mmdd) else d.year - 1


def leave_year_of(day: Any = None, conn=None) -> int:
    """The leave year ``day`` falls in."""
    return _year_for(as_date(day) or today(), setting('leave_year_start', conn))


def leave_year_bounds(year: int, conn=None) -> tuple:
    """``(first day, last day)`` of leave year ``year``."""
    mmdd = setting('leave_year_start', conn)
    start = _year_start(year, mmdd)
    return start, _year_start(year + 1, mmdd) - timedelta(days=1)


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    for d in (31, 30, 29, 28):
        try:
            return date(year, month, min(day.day, d))
        except ValueError:
            continue
    raise ValueError("bad date")


# ── working pattern / FTE ───────────────────────────────────────────────


def _columns(conn, table: str) -> set:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _current_contract(conn, username: str):
    if not _columns(conn, 'staff_contracts'):
        return None
    return conn.execute(
        "SELECT * FROM staff_contracts WHERE user_id = ? AND COALESCE(status, 'active') "
        "NOT IN ('terminated', 'expired', 'cancelled', 'draft') "
        "ORDER BY COALESCE(start_date, '') DESC, contract_id DESC LIMIT 1",
        (username,)).fetchone()


def pattern_of(username: str, conn=None) -> dict:
    """``{'work_days': (0..6, ...), 'fte': float, 'hours': float|None,
    'source': str}`` for ``username``."""
    own = conn is None
    c = _conn(conn)
    try:
        ensure(c)
        full_hours = float(setting('full_time_hours', c)) or 37.5
        row = c.execute("SELECT * FROM staff_working_patterns WHERE user_id = ?",
                        (username,)).fetchone()
        days = FULL_WEEK
        fte = hours = None
        source = 'default'
        if row:
            row = dict(row)
            parsed = tuple(sorted({int(p) for p in str(row['work_days'] or '').split(',')
                                   if p.strip().isdigit() and 0 <= int(p) <= 6}))
            days = parsed or FULL_WEEK
            fte = row.get('fte')
            hours = row.get('hours_per_week')
            source = 'pattern'
            if fte is None and hours:
                fte = float(hours) / full_hours
        if fte is None:
            contract = _current_contract(c, username)
            if contract is not None:
                contract = dict(contract)
                if contract.get('fte') not in (None, ''):
                    fte, source = float(contract['fte']), 'contract'
                elif contract.get('working_hours_per_week'):
                    hours = float(contract['working_hours_per_week'])
                    fte, source = hours / full_hours, 'contract hours'
        if fte is None:
            fte = len(days) / 5.0 if row else 1.0
        return {'work_days': days, 'fte': round(min(max(float(fte), 0.0), 1.0), 4),
                'hours': hours, 'source': source}
    finally:
        if own:
            c.close()


def set_pattern(actor: Any, username: str, work_days: Iterable[int],
                hours_per_week: Optional[float] = None, fte: Optional[float] = None,
                effective_from: Optional[str] = None, source: str = 'hr', conn=None) -> dict:
    """Record ``username``'s working days / hours (HR, or via a flexible
    working decision — ``conn`` then belongs to that decision)."""
    own = conn is None
    c = _conn(conn)
    try:
        ensure(c)
        if source == 'hr' and not access.can(actor, 'hr', c):
            raise PermissionError("Only HR can change a working pattern")
        days = sorted({int(d) for d in work_days if 0 <= int(d) <= 6})
        if not days:
            raise ValueError("A working pattern needs at least one working day")
        if fte is not None and not 0 < float(fte) <= 1:
            raise ValueError("FTE must be more than 0 and at most 1")
        c.execute("INSERT INTO staff_working_patterns (user_id, work_days, hours_per_week, fte, "
                  "effective_from, source, updated_by, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                  "ON CONFLICT(user_id) DO UPDATE SET work_days = excluded.work_days, "
                  "hours_per_week = excluded.hours_per_week, fte = excluded.fte, "
                  "effective_from = excluded.effective_from, source = excluded.source, "
                  "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
                  (username, ','.join(str(d) for d in days), hours_per_week, fte,
                   effective_from, source, access.username_of(actor), now()))
        access.audit(c, actor, 'working_pattern', username, 'staff_working_patterns', username,
                     {'days': days, 'hours': hours_per_week, 'fte': fte})
        if own:
            c.commit()
        return pattern_of(username, c)
    finally:
        if own:
            c.close()


def employment_dates(username: str, conn=None) -> tuple:
    """``(start, end)`` of employment (either may be None)."""
    own = conn is None
    c = _conn(conn)
    try:
        start = end = None
        row = c.execute("SELECT hire_date, contract_end_date FROM staff_profiles "
                        "WHERE user_id = ?", (username,)).fetchone()
        if row:
            start, end = as_date(row[0]), as_date(row[1])
        contract = _current_contract(c, username)
        if contract is not None:
            contract = dict(contract)
            start = start or as_date(contract.get('start_date'))
            end = end or as_date(contract.get('end_date'))
        return start, end
    except ValueError:
        return None, None
    finally:
        if own:
            c.close()


# ── holidays ────────────────────────────────────────────────────────────


def holidays(start: date, end: date, conn=None) -> dict:
    """date -> name: UK bank holidays (computed for the region) plus the
    closure days HR has added."""
    own = conn is None
    c = _conn(conn)
    try:
        ensure(c)
        region = setting('bank_holiday_region', c)
        out = {}
        try:
            from education_system.systems.university.application.academic_calendar.dates import (
                bank_holidays,
            )
            for year in range(start.year, end.year + 1):
                for name, day in bank_holidays(year, region):
                    if start <= day <= end:
                        out[day] = name
        except Exception:
            logger.warning("Bank holidays unavailable; only HR closure days are used",
                           exc_info=True)
        for day, name in c.execute("SELECT holiday_date, name FROM staff_leave_holidays "
                                   "WHERE holiday_date BETWEEN ? AND ?",
                                   (start.isoformat(), end.isoformat())).fetchall():
            out[as_date(day)] = name
        return out
    finally:
        if own:
            c.close()


def add_closure(actor: Any, day: str, name: str) -> None:
    access.require(actor, 'hr', "Only HR can add closure days")
    as_date(day)
    with get_connection() as conn:
        ensure(conn)
        conn.execute("INSERT OR REPLACE INTO staff_leave_holidays (holiday_date, name, kind, "
                     "added_by) VALUES (?, ?, 'closure', ?)",
                     (str(day)[:10], name.strip() or 'Closure', access.username_of(actor)))
        conn.commit()


def remove_closure(actor: Any, day: str) -> bool:
    access.require(actor, 'hr', "Only HR can remove closure days")
    with get_connection() as conn:
        ensure(conn)
        cur = conn.execute("DELETE FROM staff_leave_holidays WHERE holiday_date = ?",
                           (str(day)[:10],))
        conn.commit()
        return bool(cur.rowcount)


def working_days(username: str, start: Any, end: Any, conn=None,
                 start_half: bool = False, end_half: bool = False) -> float:
    """Working days ``username`` has between ``start`` and ``end``
    inclusive (their weekdays, not bank holidays / closures)."""
    s, e = as_date(start), as_date(end)
    if s is None or e is None or e < s:
        return 0.0
    return sum(working_days_by_year(username, s, e, conn, start_half, end_half).values())


def working_dates(username: str, start: Any, end: Any, conn=None) -> list:
    s, e = as_date(start), as_date(end)
    if s is None or e is None or e < s:
        return []
    own = conn is None
    c = _conn(conn)
    try:
        days = set(pattern_of(username, c)['work_days'])
        off = holidays(s, e, c)
        out, d = [], s
        while d <= e:
            if d.weekday() in days and d not in off:
                out.append(d)
            d += timedelta(days=1)
        return out
    finally:
        if own:
            c.close()


def working_days_by_year(username: str, start: Any, end: Any, conn=None,
                         start_half: bool = False, end_half: bool = False) -> dict:
    """leave year -> working days, for a booking that may cross years."""
    own = conn is None
    c = _conn(conn)
    try:
        dates = working_dates(username, start, end, c)
        mmdd = setting('leave_year_start', c)
        out: dict = {}
        for d in dates:
            out[_year_for(d, mmdd)] = out.get(_year_for(d, mmdd), 0.0) + 1.0
        s, e = as_date(start), as_date(end)
        if dates and start_half and dates[0] == s:
            out[_year_for(s, mmdd)] -= 0.5
        if dates and end_half and dates[-1] == e and (s != e or not start_half):
            out[_year_for(e, mmdd)] -= 0.5
        return out
    finally:
        if own:
            c.close()


def leave_type_id(conn, name: str, colour: str = '#6c757d', active: bool = False) -> int:
    """The id of leave type ``name`` (made, inactive, when missing — the
    sickness and family leave bookings use one)."""
    row = conn.execute("SELECT leave_type_id FROM leave_types WHERE LOWER(name) = LOWER(?)",
                       (name,)).fetchone()
    if row:
        return int(row[0])
    cur = conn.execute("INSERT INTO leave_types (name, description, max_days_per_year, "
                       "requires_approval, is_paid, color_code, is_active) "
                       "VALUES (?, ?, 0, 0, 1, ?, ?)",
                       (name, 'Booked automatically', colour, int(active)))
    return int(cur.lastrowid)


def hr_people(conn) -> list:
    """HR administrators and officers (for notices)."""
    try:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT username FROM staff_hr_roles WHERE role IN ('hr_admin', "
            "'hr_officer') ORDER BY username").fetchall()]
    except Exception:
        return []


_LOCAL = threading.local()


def publish_change(username: str, action: str, start, end, type_id, source: str) -> None:
    """Queue an availability change; :func:`write` sends it after commit
    (the bus logs on its own connection, which would wait on ours)."""
    if not hasattr(_LOCAL, 'events'):
        _LOCAL.events = []
    _LOCAL.events.append((username, action, str(start), str(end), str(type_id), source))


def flush_events() -> None:
    events, _LOCAL.events = getattr(_LOCAL, 'events', []), []
    if not events:
        return
    try:
        from education_system.systems.university.services.bus.integration_bus import (
            publish_leave_decision,
        )
    except Exception:
        logger.debug("leave availability bus unavailable", exc_info=True)
        return
    for username, action, start, end, type_id, source in events:
        try:
            publish_leave_decision(username, action=action, start_date=start, end_date=end,
                                   leave_type=type_id, source=source)
        except Exception:
            logger.debug("leave availability not published", exc_info=True)


@contextmanager
def write():
    """A connection for one piece of leave work: committed (then the queued
    availability changes are published) or rolled back (and dropped)."""
    conn = get_connection()
    _LOCAL.depth = getattr(_LOCAL, 'depth', 0) + 1
    try:
        ensure(conn)
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        _LOCAL.events, _LOCAL.mails = [], []
        raise
    finally:
        conn.close()
        _LOCAL.depth -= 1
    if _LOCAL.depth == 0:
        flush_events()
        mails, _LOCAL.mails = getattr(_LOCAL, 'mails', []), []
        for args in mails:
            _send(*args)


def book_linked(conn, username: str, type_id: int, start, end, source: str, source_id: int,
                actor: Any = None, reason: Optional[str] = None) -> int:
    """An approved ``leave_requests`` row standing for an absence / family
    leave period (so the calendar and cover planning see it). Never uses
    up a balance."""
    s, e = as_date(start), as_date(end) or as_date(start)
    days = working_days(username, s, e, conn)
    who = access.username_of(actor) if actor is not None and not isinstance(actor, str) \
        else (actor or source)
    cur = conn.execute(
        "INSERT INTO leave_requests (user_id, leave_type_id, start_date, end_date, total_days, "
        "working_days, reason, status, approved_by, approved_date, source, source_id, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?, ?, ?, ?)",
        (username, type_id, s.isoformat(), e.isoformat(), days, days, reason, who, now(),
         source, source_id, now(), now()))
    publish_change(username, 'approved', s, e, type_id, source)
    return int(cur.lastrowid)


def update_linked(conn, request_id: Optional[int], start, end) -> None:
    if not request_id:
        return
    row = conn.execute("SELECT user_id, leave_type_id, source FROM leave_requests "
                       "WHERE request_id = ?", (request_id,)).fetchone()
    if not row:
        return
    s, e = as_date(start), as_date(end) or as_date(start)
    days = working_days(row[0], s, e, conn)
    conn.execute("UPDATE leave_requests SET start_date = ?, end_date = ?, total_days = ?, "
                 "working_days = ?, updated_at = ? WHERE request_id = ?",
                 (s.isoformat(), e.isoformat(), days, days, now(), request_id))
    publish_change(row[0], 'approved', s, e, row[1], row[2] or 'leave')


def cancel_linked(conn, request_id: Optional[int], actor: Any = None) -> None:
    if not request_id:
        return
    row = conn.execute("SELECT user_id, leave_type_id, start_date, end_date, source FROM "
                       "leave_requests WHERE request_id = ?", (request_id,)).fetchone()
    conn.execute("UPDATE leave_requests SET status = 'cancelled', cancelled_by = ?, "
                 "updated_at = ? WHERE request_id = ?",
                 (access.username_of(actor) if actor is not None and not isinstance(actor, str)
                  else actor, now(), request_id))
    if row:
        publish_change(row[0], 'cancelled', row[2], row[3], row[1], row[4] or 'leave')


# ── telling people ──────────────────────────────────────────────────────


def remind_once(conn, key: str, recipient: str) -> bool:
    """True the first time ``key`` goes to ``recipient`` (then recorded)."""
    cur = conn.execute("INSERT OR IGNORE INTO staff_leave_reminders (reminder_key, recipient) "
                       "VALUES (?, ?)", (key, recipient))
    return bool(cur.rowcount)


def mail(username: Optional[str], subject: str, body: str, actor: Any = None,
         conn=None) -> bool:
    """E-mail a member of staff through the outbox (best effort). Never put
    medical detail in ``body``."""
    if not username:
        return False
    who = (access.username_of(actor) if actor is not None and not isinstance(actor, str)
           else actor)
    if getattr(_LOCAL, 'depth', 0):
        # the outbox commits on its own connection: send after our commit
        if not hasattr(_LOCAL, 'mails'):
            _LOCAL.mails = []
        _LOCAL.mails.append((username, subject, body, who))
        return True
    return _send(username, subject, body, who)


def _send(username: str, subject: str, body: str, who: Optional[str]) -> bool:
    try:
        address = access.email_of(username)
    except Exception:
        address = None
    if not address:
        logger.debug("staff leave mail to %s skipped: no address", username)
        return False
    try:
        from education_system.systems.university.infrastructure.email.outbox_delivery import (
            enqueue,
        )
        enqueue(address, subject, body, category='staff_hr', to_ref=username, created_by=who)
        return True
    except Exception:
        logger.warning("staff leave mail to %s failed", username, exc_info=True)
        return False


def actor_for(value: Any, conn=None) -> Optional[dict]:
    """An actor dict for callers that only hold an id (old signatures):
    the username plus the university role from ``users``."""
    if value is None:
        return None
    if isinstance(value, dict) or hasattr(value, 'current_user'):
        return access.user_of(value)
    own = conn is None
    c = _conn(conn)
    try:
        name = access.staff_key(value, c) or str(value)
        row = c.execute("SELECT role FROM users WHERE username = ?", (name,)).fetchone()
        return {'username': name, 'role': (row[0] if row else '') or ''}
    finally:
        if own:
            c.close()


__all__ = [
    'DEFAULTS', 'WEEKDAYS', 'ensure', 'as_date', 'today', 'now',
    'settings', 'setting', 'set_setting',
    'leave_year_of', 'leave_year_bounds', 'add_months',
    'pattern_of', 'set_pattern', 'employment_dates',
    'holidays', 'add_closure', 'remove_closure', 'leave_type_id', 'hr_people',
    'publish_change', 'book_linked', 'update_linked', 'cancel_linked', 'write', 'flush_events',
    'working_days', 'working_dates', 'working_days_by_year',
    'remind_once', 'mail', 'actor_for',
]
