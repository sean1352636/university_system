"""Service levels for support tickets: targets, the business-hours clock,
due times and the out-of-hours response.

Targets
-------
Per team and priority, from the Helpdesk ``sla_policies``: a row for the
ticket's team (``sla_policies.team``) wins over a row for every team
(``team`` NULL); with neither, :data:`DEFAULT_TARGETS`. 'urgent' uses the
'high' targets when it has none of its own. ``business_hours_only`` says
which clock a policy runs on (the seeded 'Critical' policy runs 24/7).

The clock
---------
Business hours are Monday to Friday 09:00-17:00 Europe/London, not on a UK
bank holiday (``application.calendar_dates.bank_holidays``, for the region
of the published academic year) or a university closure day
(``calendar_key_dates`` kind 'closure'). Stored times are naive local
times, as everywhere else in the support tables.

Due times
---------
``sla_due_at`` is the next deadline: the first-response due time until a
member of staff first replies (:func:`on_first_response`), then the
resolution due time. Both are worked out again from ``created_at`` by
:func:`due_times`, which is what the reports and breach checks use.

Waiting on the student
----------------------
The resolution clock stops while a ticket waits on the student (setting
``sla_pause_waiting``, on by default): :func:`sync_pause` stamps
``sla_paused_at`` when a ticket goes to waiting on student and, when it
leaves, adds the clock hours it waited to ``sla_paused_hours`` and moves
``sla_due_at`` on. The resolution due time is the target plus every hour
paused (including a pause still running), so a ticket waiting on the student
never breaches and its time left is frozen. The first-response target never
pauses: a ticket is answered before it is waiting on anyone.

Out of hours
------------
A ticket raised outside business hours gets a public automatic reply with
the out-of-hours and crisis contacts (``crisis_resources``). A Critical one
also goes to a duty officer: a member of the ``duty`` team (Helpdesk
department 'Duty Officer', members in ``staff_assignments``), least loaded
first. With no duty officer on the rota the team's leads are told instead.
"""

from __future__ import annotations

import datetime as _dt
import logging
from functools import lru_cache
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

LONDON = ZoneInfo('Europe/London')
DAY_START = _dt.time(9, 0)
DAY_END = _dt.time(17, 0)
FMT = '%Y-%m-%d %H:%M:%S'

# priority -> (first response hours, resolution hours, business hours only)
DEFAULT_TARGETS = {
    'critical': (1, 8, False),
    'urgent': (2, 16, True),
    'high': (4, 24, True),
    'medium': (8, 40, True),
    'low': (16, 80, True),
}
OUT_OF_HOURS_PRIORITIES = ('critical',)


def _now() -> _dt.datetime:
    return _dt.datetime.now()


def parse(value) -> Optional[_dt.datetime]:
    if value in (None, ''):
        return None
    if isinstance(value, _dt.datetime):
        return value
    text = str(value).strip().replace('T', ' ')
    for fmt in (FMT, '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return _dt.datetime.strptime(text[:26], fmt)
        except ValueError:
            continue
    return None


def fmt(value: Optional[_dt.datetime]) -> Optional[str]:
    return value.strftime(FMT) if value else None


def _to_london(local: _dt.datetime) -> _dt.datetime:
    """A naive local time as an aware Europe/London time."""
    return local.astimezone(LONDON)


def _to_local(aware: _dt.datetime) -> _dt.datetime:
    return aware.astimezone().replace(tzinfo=None)


# ── closed days ──────────────────────────────────────────────────────────


@lru_cache(maxsize=32)
def _bank_holidays(year: int, region: str) -> frozenset:
    from education_system.systems.university.application.academic_calendar.dates import bank_holidays
    return frozenset(day for _name, day in bank_holidays(year, region))


def _region(conn) -> str:
    try:
        row = conn.execute("SELECT bank_holiday_region FROM calendar_years "
                           "WHERE status = 'published' ORDER BY start_date DESC LIMIT 1").fetchone()
        return (row[0] if row and row[0] else None) or 'england-and-wales'
    except Exception:
        return 'england-and-wales'


def closed_days(conn, start: _dt.date, end: _dt.date) -> set:
    """UK bank holidays and university closure days between two dates."""
    days = set()
    region = _region(conn) if conn is not None else 'england-and-wales'
    for year in range(start.year, end.year + 1):
        days |= _bank_holidays(year, region)
    if conn is not None:
        try:
            for s, e in conn.execute(
                    "SELECT start_date, COALESCE(end_date, start_date) FROM calendar_key_dates "
                    "WHERE kind = 'closure' AND audience IN ('all', 'staff') "
                    "AND start_date <= ? AND COALESCE(end_date, start_date) >= ?",
                    (end.isoformat(), start.isoformat())).fetchall():
                d, last = _dt.date.fromisoformat(s[:10]), _dt.date.fromisoformat(e[:10])
                while d <= last:
                    days.add(d)
                    d += _dt.timedelta(days=1)
        except Exception:
            logger.debug("No calendar closures read", exc_info=True)
    return days


class Clock:
    """The business-hours clock over one connection's calendar."""

    def __init__(self, conn=None):
        self.conn = conn
        self._closed: dict = {}

    def is_working_day(self, day: _dt.date) -> bool:
        if day.weekday() >= 5:
            return False
        if day.year not in self._closed:
            self._closed[day.year] = closed_days(self.conn, _dt.date(day.year, 1, 1),
                                                 _dt.date(day.year, 12, 31))
        return day not in self._closed[day.year]

    def is_business_time(self, local: _dt.datetime) -> bool:
        t = _to_london(local)
        return self.is_working_day(t.date()) and DAY_START <= t.time() < DAY_END

    def add(self, start_local: _dt.datetime, hours: float,
            business_only: bool = True) -> _dt.datetime:
        """``start_local`` plus ``hours`` of the clock (naive local in and out)."""
        if not business_only:
            return start_local + _dt.timedelta(hours=hours)
        remaining = _dt.timedelta(hours=hours)
        t = _to_london(start_local)
        for _ in range(3660):          # ten years of days: a guard, never reached
            day = t.date()
            if self.is_working_day(day):
                opens = _dt.datetime.combine(day, DAY_START, tzinfo=LONDON)
                closes = _dt.datetime.combine(day, DAY_END, tzinfo=LONDON)
                if t < opens:
                    t = opens
                if t < closes:
                    available = closes - t
                    if remaining <= available:
                        return _to_local(t + remaining)
                    remaining -= available
            t = _dt.datetime.combine(day + _dt.timedelta(days=1), _dt.time(0, 0), tzinfo=LONDON)
        raise ValueError("No business hours found to count an SLA against")

    def hours_between(self, a_local: _dt.datetime, b_local: _dt.datetime,
                      business_only: bool = True) -> float:
        """Clock hours from ``a`` to ``b`` (negative when b is earlier)."""
        if b_local < a_local:
            return -self.hours_between(b_local, a_local, business_only)
        if not business_only:
            return (b_local - a_local).total_seconds() / 3600
        a, b = _to_london(a_local), _to_london(b_local)
        total = _dt.timedelta()
        day = a.date()
        while day <= b.date():
            if self.is_working_day(day):
                opens = max(a, _dt.datetime.combine(day, DAY_START, tzinfo=LONDON))
                closes = min(b, _dt.datetime.combine(day, DAY_END, tzinfo=LONDON))
                if closes > opens:
                    total += closes - opens
            day += _dt.timedelta(days=1)
        return total.total_seconds() / 3600


def is_business_time(when=None, conn=None) -> bool:
    return Clock(conn).is_business_time(parse(when) or _now())


def add_business_hours(start, hours, conn=None) -> _dt.datetime:
    return Clock(conn).add(parse(start) or _now(), float(hours))


# ── targets and due times ────────────────────────────────────────────────


def _priority(value) -> str:
    p = str(value or 'medium').strip().lower()
    return p if p in DEFAULT_TARGETS else 'medium'


def targets(conn, team, priority) -> dict:
    """``{'first_response_hours', 'resolution_hours', 'business_hours_only',
    'policy_id', 'source'}`` for a team and priority."""
    p = _priority(priority)
    has_policies = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                                "AND name = 'sla_policies'").fetchone()
    if has_policies:
        has_team = 'team' in {r[1] for r in conn.execute("PRAGMA table_info(sla_policies)")}
        tries = [p] + (['high'] if p == 'urgent' else [])
        for want in tries:
            if has_team and team:
                row = conn.execute(
                    "SELECT sla_id, first_response_hours, resolution_hours, business_hours_only "
                    "FROM sla_policies WHERE is_active = 1 AND lower(priority) = ? AND team = ? "
                    "ORDER BY sla_id LIMIT 1", (want, str(team))).fetchone()
                if row and row[1] is not None and row[2] is not None:
                    return {'first_response_hours': float(row[1]), 'resolution_hours': float(row[2]),
                            'business_hours_only': bool(row[3]), 'policy_id': row[0],
                            'source': 'team policy'}
            team_sql = " AND (team IS NULL OR team = '')" if has_team else ""
            row = conn.execute(
                "SELECT sla_id, first_response_hours, resolution_hours, business_hours_only "
                f"FROM sla_policies WHERE is_active = 1 AND lower(priority) = ?{team_sql} "  # nosec B608
                "ORDER BY sla_id LIMIT 1", (want,)).fetchone()
            if row and row[1] is not None and row[2] is not None:
                return {'first_response_hours': float(row[1]), 'resolution_hours': float(row[2]),
                        'business_hours_only': bool(row[3]), 'policy_id': row[0],
                        'source': 'policy'}
    fr, res, business = DEFAULT_TARGETS[p]
    return {'first_response_hours': float(fr), 'resolution_hours': float(res),
            'business_hours_only': business, 'policy_id': None, 'source': 'default'}


def _get(ticket, key):
    try:
        return ticket[key]
    except (KeyError, IndexError, TypeError):
        return None


def _is_waiting(ticket) -> bool:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    return schema.normalize_status(_get(ticket, 'status'), default='open') == 'waiting_on_student'


def paused_hours(ticket, clock: Clock, business: bool, now=None) -> float:
    """Clock hours the ticket's resolution target has been paused: the
    finished pauses plus the one still running (if it is still waiting)."""
    total = float(_get(ticket, 'sla_paused_hours') or 0)
    started = parse(_get(ticket, 'sla_paused_at'))
    if started and _is_waiting(ticket):
        total += max(0.0, clock.hours_between(started, parse(now) or _now(), business))
    return total


def due_times(conn, ticket, clock: Optional[Clock] = None, now=None) -> dict:
    """``{'first_response_due', 'resolution_due', 'targets', 'paused_hours'}``
    (datetimes) for a ticket row, counted from its ``created_at``; the
    resolution due time moves on by every hour the ticket waited on the
    student."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing,
    )
    created = parse(_get(ticket, 'created_at')) or _now()
    team = _get(ticket, 'team') or routing.route(_get(ticket, 'category'),
                                                 _get(ticket, 'subcategory'))
    t = targets(conn, team, _get(ticket, 'priority'))
    clock = clock or Clock(conn)
    business = t['business_hours_only']
    paused = paused_hours(ticket, clock, business, now)
    return {'first_response_due': clock.add(created, t['first_response_hours'], business),
            'resolution_due': clock.add(created, t['resolution_hours'] + paused, business),
            'targets': t, 'paused_hours': round(paused, 2)}


def ticket_sla(conn, ticket, now=None, clock: Optional[Clock] = None) -> dict:
    """Where a ticket stands against its SLA: the due times, whether each
    target was met / breached, and hours left on the next one (negative
    when overdue)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    now = parse(now) or _now()
    due = due_times(conn, ticket, clock, now)
    first = parse(_get(ticket, 'first_response_at'))
    done_at = parse(_get(ticket, 'resolved_at')) or parse(_get(ticket, 'closed_at'))
    status = schema.normalize_status(_get(ticket, 'status'), default='open')
    done = status in schema.DONE_STATUSES
    fr_due, res_due = due['first_response_due'], due['resolution_due']
    fr_breached = (first > fr_due) if first else (now > fr_due and not done)
    res_breached = (done_at > res_due) if (done and done_at) else (not done and now > res_due)
    nxt = None if done else (res_due if first else fr_due)
    return {
        'first_response_due': fmt(fr_due), 'resolution_due': fmt(res_due),
        'first_response_met': (not fr_breached) if (first or done) else None,
        'resolution_met': (not res_breached) if done else None,
        'first_response_breached': fr_breached, 'resolution_breached': res_breached,
        'next_due': fmt(nxt),
        'hours_left': round((nxt - now).total_seconds() / 3600, 2) if nxt else None,
        'targets': due['targets'],
        'paused': bool(parse(_get(ticket, 'sla_paused_at'))) and _is_waiting(ticket),
        'paused_hours': due['paused_hours'],
    }


# ── hooks called by the ticket service ───────────────────────────────────


def _crisis_contacts(conn) -> list:
    try:
        return [f"{r[0]}: {r[1]}" + (f" ({r[2]})" if r[2] else '')
                for r in conn.execute(
                    "SELECT resource_name, contact_info, availability FROM crisis_resources "
                    "WHERE COALESCE(is_active, 1) = 1 ORDER BY resource_id").fetchall()]
    except Exception:
        return []


def out_of_hours_message(conn) -> str:
    """The automatic reply for a ticket raised out of hours."""
    lines = ["Thank you for contacting Student Support. Our advisers work Monday to Friday, "
             "09:00-17:00 (UK time), except bank holidays and university closure days, so "
             "your request will be picked up on the next working day."]
    contacts = _crisis_contacts(conn)
    if contacts:
        lines.append("If you need help urgently, or you are worried about your safety or "
                     "someone else's, please contact:")
        lines += [f"  - {c}" for c in contacts]
    else:
        lines.append("If you or someone else is in immediate danger, call 999.")
    return "\n".join(lines)


def _note(conn, ticket_id, text, *, internal):
    conn.execute(
        "INSERT INTO ticket_responses (ticket_id, responder_id, responder_role, response_text, "
        "response_datetime, is_internal, is_auto_generated) VALUES (?, 'system', 'system', ?, ?, ?, 1)",
        (ticket_id, text, fmt(_now()), 1 if internal else 0))


def set_due(conn, ticket_id) -> dict:
    """Set a new ticket's team (if missing) and ``sla_due_at``; when it was
    raised out of hours, add the out-of-hours reply and, for a Critical
    ticket, give it to a duty officer. Runs on the caller's transaction.

    Returns ``{'team', 'sla_due_at', 'resolution_due', 'out_of_hours',
    'duty_officer'}``.
    """
    from education_system.systems.university.domains.student_support.domain.student_support import (
        notify,
        routing,
    )
    ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                          (int(ticket_id),)).fetchone()
    if ticket is None:
        raise ValueError(f"Ticket #{ticket_id} was not found")
    keys = ticket.keys() if hasattr(ticket, 'keys') else None
    if keys is None:
        raise TypeError("set_due needs a connection with row_factory = sqlite3.Row")
    team = ticket['team'] or routing.route(ticket['category'], ticket['subcategory'])
    clock = Clock(conn)
    created = parse(ticket['created_at']) or _now()
    row = dict(ticket)
    row['team'] = team
    due = due_times(conn, row, clock)
    sla_due = due['resolution_due'] if ticket['first_response_at'] else due['first_response_due']
    conn.execute("UPDATE support_tickets SET team = ?, sla_due_at = ? WHERE ticket_id = ?",
                 (team, fmt(sla_due), ticket['ticket_id']))
    result = {'team': team, 'sla_due_at': fmt(sla_due), 'resolution_due': fmt(due['resolution_due']),
              'out_of_hours': False, 'duty_officer': None}
    if clock.is_business_time(created):
        return result
    result['out_of_hours'] = True
    _note(conn, ticket['ticket_id'], out_of_hours_message(conn), internal=False)
    if _priority(ticket['priority']) not in OUT_OF_HOURS_PRIORITIES:
        return result
    officer = routing.pick_assignee(routing.DUTY_TEAM, conn) or next(
        iter(sorted(routing.duty_officers(conn))), None)
    notices = []
    if officer:
        previous = ticket['assigned_to']
        conn.execute("UPDATE support_tickets SET assigned_to = ? WHERE ticket_id = ?",
                     (officer, ticket['ticket_id']))
        _note(conn, ticket['ticket_id'],
              f"Critical ticket raised out of hours: given to the duty officer {officer}"
              + (f" (was {previous})." if previous and previous != officer else "."), internal=True)
        result['duty_officer'] = officer
        notices = notify.duty_alert(ticket['ticket_id'], ticket['subject'], officer)
    else:
        _note(conn, ticket['ticket_id'], "Critical ticket raised out of hours and no duty officer "
              "is on the rota; the team leads have been told.", internal=True)
        for lead in sorted(routing.team_leads(team, conn)):
            notices += notify.duty_alert(ticket['ticket_id'], ticket['subject'], lead)
    notify.deliver_in_app(conn, notices)
    return result


def on_first_response(conn, ticket_id) -> bool:
    """Record the first staff response (if not yet recorded) and move
    ``sla_due_at`` on to the resolution due time. True when it was the first."""
    ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                          (int(ticket_id),)).fetchone()
    if ticket is None:
        return False
    first = ticket['first_response_at'] is None
    stamp = ticket['first_response_at'] or fmt(_now())
    due = due_times(conn, ticket)
    conn.execute("UPDATE support_tickets SET first_response_at = ?, sla_due_at = ? "
                 "WHERE ticket_id = ?", (stamp, fmt(due['resolution_due']), ticket['ticket_id']))
    return first


def _pause_enabled(conn) -> bool:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        settings,
    )
    try:
        return bool(settings.get('sla_pause_waiting', conn))
    except Exception:
        logger.debug("Support settings unreadable; SLA pause left on", exc_info=True)
        return True


def sync_pause(conn, ticket_id, now=None) -> dict:
    """Start or end the resolution pause to match the ticket's status, on the
    caller's transaction. Call it after any change of status. Returns
    ``{'paused', 'paused_hours', 'sla_due_at'}``."""
    ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                          (int(ticket_id),)).fetchone()
    if ticket is None:
        raise ValueError(f"Ticket #{ticket_id} was not found")
    keys = set(ticket.keys()) if hasattr(ticket, 'keys') else set()
    if 'sla_paused_at' not in keys:
        return {'paused': False, 'paused_hours': 0.0, 'sla_due_at': _get(ticket, 'sla_due_at')}
    now = parse(now) or _now()
    started = parse(ticket['sla_paused_at'])
    waiting = _is_waiting(ticket)
    total = float(ticket['sla_paused_hours'] or 0)
    due_at = ticket['sla_due_at']
    if waiting and not started and _pause_enabled(conn):
        conn.execute("UPDATE support_tickets SET sla_paused_at = ? WHERE ticket_id = ?",
                     (fmt(now), ticket['ticket_id']))
        return {'paused': True, 'paused_hours': total, 'sla_due_at': due_at}
    if started and (not waiting or not _pause_enabled(conn)):
        clock = Clock(conn)
        business = due_times(conn, ticket, clock, now)['targets']['business_hours_only']
        total += max(0.0, clock.hours_between(started, now, business))
        row = dict(ticket)
        row.update({'sla_paused_at': None, 'sla_paused_hours': total})
        if due_at is not None:
            due = due_times(conn, row, clock, now)
            due_at = fmt(due['resolution_due'] if row.get('first_response_at')
                         else due['first_response_due'])
        conn.execute("UPDATE support_tickets SET sla_paused_at = NULL, sla_paused_hours = ?, "
                     "sla_due_at = ? WHERE ticket_id = ?",
                     (round(total, 4), due_at, ticket['ticket_id']))
        return {'paused': False, 'paused_hours': total, 'sla_due_at': due_at}
    return {'paused': bool(started) and waiting, 'paused_hours': total, 'sla_due_at': due_at}


def sync_all_pauses(conn, now=None) -> int:
    """Bring every ticket whose pause does not match its status into line
    (a status written by code that did not call :func:`sync_pause`)."""
    if 'sla_paused_at' not in {r[1] for r in conn.execute("PRAGMA table_info(support_tickets)")}:
        return 0
    rows = conn.execute(
        "SELECT ticket_id FROM support_tickets WHERE "
        "(status = 'waiting_on_student' AND sla_paused_at IS NULL) OR "
        "(status <> 'waiting_on_student' AND sla_paused_at IS NOT NULL)").fetchall()
    changed = 0
    for (tid,) in rows:
        before = conn.total_changes
        sync_pause(conn, tid, now)
        changed += conn.total_changes != before
    return changed


__all__ = [
    'DEFAULT_TARGETS', 'Clock', 'closed_days', 'is_business_time', 'add_business_hours',
    'targets', 'due_times', 'ticket_sla', 'out_of_hours_message', 'set_due',
    'on_first_response', 'parse', 'fmt', 'paused_hours', 'sync_pause', 'sync_all_pauses',
]
