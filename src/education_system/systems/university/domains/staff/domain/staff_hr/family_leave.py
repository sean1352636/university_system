"""Family leave: maternity, paternity, adoption and shared parental leave
cases, statutory eligibility and pay, KIT / SPLIT days and the return.

**Key dates.** Births work from the expected week of childbirth (EWC — the
Sunday-to-Saturday week the baby is due); the *qualifying week* is the 15th
week before it. Adoptions work from the week the adopter is told of the
match.

**Eligibility** (weeks and rates are settings in ``leave_rules``):

* maternity / adoption leave — a day-one right, ``maternity_leave_weeks``
  (52); maternity leave starts no earlier than 11 weeks before the EWC and
  the two weeks after the birth are compulsory leave;
* paternity leave — ``paternity_leave_service_weeks`` of service (0: day
  one), up to ``paternity_weeks`` (2), within 52 weeks of the birth /
  placement;
* shared parental leave — ``spl_service_weeks`` of service by the
  qualifying week; up to ``spl_max_weeks`` less the maternity / adoption
  leave already taken;
* statutory pay (SMP / SAP / SPP / ShPP) — ``pay_service_weeks`` of service
  into the qualifying week and average weekly earnings at least the
  ``lower_earnings_limit``. SMP / SAP: ``higher_rate_weeks`` at 90% of
  earnings, the rest of ``statutory_pay_weeks`` at the lower of the
  ``statutory_weekly_rate`` and 90%; SPP the same lower rate; ShPP the same
  rate for the statutory pay weeks not already used.

**Who.** The person notifies their own case; HR confirms and maintains it.
The person, their management chain and HR see the case; earnings and pay
are the person's, HR's and payroll's only. KIT / SPLIT days are agreed by
the line manager or HR.

A confirmed case books its leave (an approved ``leave_requests`` row of the
matching inactive family leave type) so the calendar and cover planning see
it; no balance is used.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr import leave_rules as lr
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

KINDS = ('maternity', 'paternity', 'adoption', 'shared_parental')
KIND_LABELS = {'maternity': 'Maternity', 'paternity': 'Paternity', 'adoption': 'Adoption',
               'shared_parental': 'Shared parental'}
TYPE_NAMES = {'maternity': ('Maternity Leave', '#e83e8c'),
              'paternity': ('Paternity Leave', '#6f42c1'),
              'adoption': ('Adoption Leave', '#fd7e14'),
              'shared_parental': ('Shared Parental Leave', '#20c997')}
PAY_NAMES = {'maternity': 'SMP', 'adoption': 'SAP', 'paternity': 'SPP', 'shared_parental': 'ShPP'}
STATUSES = ('notified', 'confirmed', 'on_leave', 'returned', 'cancelled')
_PAY_FIELDS = ('average_weekly_earnings', 'pay_schedule', 'pay_eligible')


def week_start(day: date) -> date:
    """The Sunday that starts ``day``'s week."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def key_dates(kind: str, due_or_match: Any) -> dict:
    """``{'ewc', 'qualifying_week'}`` from the due date (births) or the
    matching date (adoption)."""
    day = lr.as_date(due_or_match)
    if day is None:
        return {'ewc': None, 'qualifying_week': None}
    if kind == 'adoption':
        return {'ewc': None, 'qualifying_week': week_start(day).isoformat()}
    ewc = week_start(day)
    return {'ewc': ewc.isoformat(), 'qualifying_week': (ewc - timedelta(weeks=15)).isoformat()}


def _served(service_start: Optional[date], qualifying_week: Optional[date], weeks: int) -> bool:
    """Employed continuously for ``weeks`` weeks into the qualifying week."""
    if weeks <= 0:
        return True
    if service_start is None or qualifying_week is None:
        return False
    return service_start <= qualifying_week + timedelta(days=6) - timedelta(weeks=weeks) + \
        timedelta(days=1)


def assess(case: dict, settings: dict) -> dict:
    """Eligibility, leave end / return date and the statutory pay schedule
    for a case (pure; nothing stored)."""
    kind = case['kind']
    qw = lr.as_date(case.get('qualifying_week'))
    service = lr.as_date(case.get('service_start'))
    awe = case.get('average_weekly_earnings')
    awe = float(awe) if awe not in (None, '') else None
    notes = []
    used = int(case.get('statutory_weeks_used') or 0)
    rate = float(settings['statutory_weekly_rate'])

    if kind in ('maternity', 'adoption'):
        leave_ok, max_weeks = True, int(settings['maternity_leave_weeks'])
    elif kind == 'paternity':
        leave_ok = _served(service, qw, int(settings['paternity_leave_service_weeks']))
        max_weeks = int(settings['paternity_weeks'])
        if not leave_ok:
            notes.append(f"Paternity leave needs {settings['paternity_leave_service_weeks']} "
                         "weeks' service by the qualifying week")
    else:
        leave_ok = _served(service, qw, int(settings['spl_service_weeks']))
        max_weeks = max(0, int(settings['spl_max_weeks']) - used)
        if not leave_ok:
            notes.append(f"Shared parental leave needs {settings['spl_service_weeks']} weeks' "
                         "service by the qualifying week")
        notes.append("The partner must also meet the employment and earnings test")

    served = _served(service, qw, int(settings['pay_service_weeks']))
    earns = awe is not None and awe >= float(settings['lower_earnings_limit'])
    pay_ok = served and earns
    if not served:
        notes.append(f"Statutory pay needs {settings['pay_service_weeks']} weeks' service into "
                     "the qualifying week")
    if awe is None:
        notes.append("Average weekly earnings not recorded yet")
    elif not earns:
        notes.append(f"Average weekly earnings £{awe:.2f} are below the lower earnings limit "
                     f"£{float(settings['lower_earnings_limit']):.2f}")

    weeks = case.get('leave_weeks')
    weeks = int(weeks) if weeks not in (None, '') else max_weeks
    if weeks > max_weeks:
        notes.append(f"Only {max_weeks} weeks are available; {weeks} asked for")
        weeks = max_weeks
    start = lr.as_date(case.get('leave_start'))
    end = start + timedelta(weeks=weeks) - timedelta(days=1) if start and weeks else None

    if kind == 'maternity' and start and case.get('ewc'):
        earliest = lr.as_date(case['ewc']) - timedelta(weeks=11)
        if start < earliest:
            notes.append(f"Maternity leave cannot start before {earliest.isoformat()} (11 weeks "
                         "before the EWC) unless the baby is born early")
    if kind == 'paternity' and start:
        born = lr.as_date(case.get('birth_date') or case.get('placement_date'))
        anchor = born or lr.as_date(case.get('ewc'))
        if anchor and start < anchor:
            notes.append("Paternity leave starts on or after the birth / placement")
        if anchor and end and end > anchor + timedelta(weeks=52):
            notes.append("Paternity leave must be taken within 52 weeks of the birth / placement")

    schedule = []
    if pay_ok and start and awe is not None:
        ninety = round(awe * 0.9, 2)
        lower = round(min(rate, ninety), 2)
        if kind in ('maternity', 'adoption'):
            pay_weeks = min(int(settings['statutory_pay_weeks']), weeks)
            higher = int(settings['higher_rate_weeks'])
        elif kind == 'paternity':
            pay_weeks, higher = min(int(settings['paternity_weeks']), weeks), 0
        else:
            pay_weeks = min(max(0, int(settings['statutory_pay_weeks']) - used), weeks)
            higher = 0
        for n in range(pay_weeks):
            w_start = start + timedelta(weeks=n)
            amount = ninety if n < higher else lower
            schedule.append({'week': n + 1, 'from': w_start.isoformat(),
                             'to': (w_start + timedelta(days=6)).isoformat(),
                             'amount': amount,
                             'basis': '90% of earnings' if n < higher else
                             ('statutory rate' if amount == rate else '90% of earnings')})
    return {'leave_eligible': int(leave_ok), 'pay_eligible': int(pay_ok),
            'leave_weeks': weeks, 'leave_end': end.isoformat() if end else None,
            'return_date': (end + timedelta(days=1)).isoformat() if end else None,
            'pay_schedule': schedule, 'pay_total': round(sum(w['amount'] for w in schedule), 2),
            'notes': notes, 'max_weeks': max_weeks}


# ── access ──────────────────────────────────────────────────────────────


def _case(conn, case_id: int) -> dict:
    row = conn.execute("SELECT * FROM staff_family_leave_cases WHERE case_id = ?",
                       (case_id,)).fetchone()
    if not row:
        raise ValueError("No such family leave case")
    return dict(row)


def sees_pay(actor: Any, username: str, conn=None) -> bool:
    return access.username_of(actor) == username or access.is_hr(actor, conn) or \
        access.is_payroll(actor, conn)


def _shape(conn, case: dict, actor: Any) -> dict:
    case = dict(case)
    case['name'] = access.display_name(case['user_id'], conn)
    case['kind_label'] = KIND_LABELS.get(case['kind'], case['kind'])
    case['pay_name'] = PAY_NAMES.get(case['kind'])
    try:
        case['pay_schedule'] = json.loads(case.get('pay_schedule') or '[]')
    except ValueError:
        case['pay_schedule'] = []
    case['kit_days'] = [dict(r) for r in conn.execute(
        "SELECT * FROM staff_kit_days WHERE case_id = ? ORDER BY day", (case['case_id'],))]
    case['kit_limit'] = kit_limit(case['kind'], conn)
    if not sees_pay(actor, case['user_id'], conn):
        for f in _PAY_FIELDS:
            case[f] = None if f != 'pay_schedule' else []
        case['pay_hidden'] = True
    return case


def kit_limit(kind: str, conn=None) -> int:
    if kind in ('maternity', 'adoption'):
        return int(lr.setting('kit_days_limit', conn))
    if kind == 'shared_parental':
        return int(lr.setting('split_days_limit', conn))
    return 0


def _refresh(conn, case_id: int, actor: Any) -> dict:
    """Recompute eligibility / dates / pay and keep the booking in step."""
    case = _case(conn, case_id)
    result = assess(case, lr.settings(conn))
    conn.execute("UPDATE staff_family_leave_cases SET leave_eligible = ?, pay_eligible = ?, "
                 "leave_weeks = ?, leave_end = ?, return_date = COALESCE(?, return_date), "
                 "eligibility_notes = ?, pay_schedule = ?, updated_at = ? WHERE case_id = ?",
                 (result['leave_eligible'], result['pay_eligible'], result['leave_weeks'],
                  result['leave_end'], result['return_date'], '\n'.join(result['notes']),
                  json.dumps(result['pay_schedule']), lr.now(), case_id))
    case = _case(conn, case_id)
    booked = case['status'] in ('confirmed', 'on_leave') and case['leave_start'] and \
        case['leave_end'] and case['leave_eligible']
    if booked and not case['leave_request_id']:
        name, colour = TYPE_NAMES[case['kind']]
        type_id = lr.leave_type_id(conn, name, colour)
        conn.execute("INSERT OR IGNORE INTO staff_leave_entitlements (leave_type_id, basis, "
                     "updated_by) VALUES (?, 'case', 'family_leave')", (type_id,))
        rid = lr.book_linked(conn, case['user_id'], type_id, case['leave_start'],
                             case['leave_end'], 'family_leave', case_id, actor,
                             f"{KIND_LABELS[case['kind']]} leave")
        conn.execute("UPDATE staff_family_leave_cases SET leave_request_id = ? WHERE case_id = ?",
                     (rid, case_id))
    elif booked:
        end = case['leave_end']
        if case['actual_return_date']:
            end = (lr.as_date(case['actual_return_date']) - timedelta(days=1)).isoformat()
        lr.update_linked(conn, case['leave_request_id'], case['leave_start'], end)
    elif case['leave_request_id'] and case['status'] == 'cancelled':
        lr.cancel_linked(conn, case['leave_request_id'], actor)
    return _case(conn, case_id)


# ── cases ───────────────────────────────────────────────────────────────


def notify(actor: Any, username: str, kind: str, *, due_date: Optional[str] = None,
           matching_date: Optional[str] = None, placement_date: Optional[str] = None,
           leave_start: Optional[str] = None, leave_weeks: Optional[int] = None,
           statutory_weeks_used: int = 0, notes: Optional[str] = None) -> int:
    """Open a case: the person notifies their own, or HR records it."""
    me = access.require_user(actor)['username']
    if kind not in KINDS:
        raise ValueError(f"Kind must be one of {', '.join(KINDS)}")
    if kind == 'adoption' and not matching_date:
        raise ValueError("An adoption case needs the matching date")
    if kind != 'adoption' and not (due_date or placement_date):
        raise ValueError("Give the expected due date (or placement date for an adoption)")
    with lr.write() as conn:
        key = access.staff_key(username, conn) or username
        if me != key and not access.is_hr(actor, conn):
            raise PermissionError("Only the person or HR can open a family leave case")
        dates = key_dates(kind, matching_date if kind == 'adoption' else
                          (due_date or placement_date))
        hired, _ = lr.employment_dates(key, conn)
        cur = conn.execute(
            "INSERT INTO staff_family_leave_cases (user_id, kind, status, ewc, matching_date, "
            "placement_date, qualifying_week, leave_start, leave_weeks, statutory_weeks_used, "
            "service_start, notes, created_by) VALUES (?, ?, 'notified', ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?)",
            (key, kind, dates['ewc'], lr.as_date(matching_date).isoformat() if matching_date
             else None, lr.as_date(placement_date).isoformat() if placement_date else None,
             dates['qualifying_week'], lr.as_date(leave_start).isoformat() if leave_start
             else None, leave_weeks, int(statutory_weeks_used or 0),
             hired.isoformat() if hired else None, notes, me))
        case_id = int(cur.lastrowid)
        _refresh(conn, case_id, actor)
        access.audit(conn, actor, 'family_leave_notified', key, 'staff_family_leave_cases',
                     case_id, {'kind': kind})
        for person in set(access.approvers_for(key, conn)) | set(lr.hr_people(conn)):
            if person != me:
                lr.mail(person, f"{KIND_LABELS[kind]} leave notified: "
                        f"{access.display_name(key, conn)}",
                        f"{access.display_name(key, conn)} has notified "
                        f"{KIND_LABELS[kind].lower()} leave. Please see Staff HR > Leave > "
                        "Family Leave.", actor)
        return case_id


EDITABLE = ('leave_start', 'leave_weeks', 'birth_date', 'placement_date', 'matching_date',
            'average_weekly_earnings', 'service_start', 'statutory_weeks_used', 'return_date',
            'notes', 'ewc')


def update(actor: Any, case_id: int, **fields) -> dict:
    """HR maintains a case (dates, earnings, service); the person may
    change their planned start / weeks / return while it is only notified."""
    unknown = set(fields) - set(EDITABLE)
    if unknown:
        raise ValueError(f"Cannot change {', '.join(sorted(unknown))}")
    with lr.write() as conn:
        case = _case(conn, case_id)
        hr = access.is_hr(actor, conn)
        own = access.username_of(actor) == case['user_id']
        personal = set(fields) <= {'leave_start', 'leave_weeks', 'return_date', 'notes'}
        if not (hr or (own and personal and case['status'] == 'notified')):
            raise PermissionError("Only HR can change this family leave case")
        for f in ('leave_start', 'birth_date', 'placement_date', 'matching_date',
                  'service_start', 'return_date', 'ewc'):
            if fields.get(f):
                fields[f] = lr.as_date(fields[f]).isoformat()
        if 'ewc' in fields and fields['ewc']:
            fields.update({k: v for k, v in key_dates(case['kind'], fields['ewc']).items() if v})
        if 'matching_date' in fields and fields['matching_date'] and case['kind'] == 'adoption':
            fields['qualifying_week'] = key_dates('adoption',
                                                  fields['matching_date'])['qualifying_week']
        if case['kind'] == 'maternity' and fields.get('birth_date'):
            born = lr.as_date(fields['birth_date'])
            start = lr.as_date(fields.get('leave_start') or case['leave_start'])
            if start is None or start > born:
                # an early birth starts maternity leave the day after
                fields['leave_start'] = (born + timedelta(days=1)).isoformat()
        sets = ', '.join(f"{k} = ?" for k in fields)
        # db-audit: ignore[DBW001] - column names come from EDITABLE
        conn.execute(f"UPDATE staff_family_leave_cases SET {sets}, updated_at = ? "  # nosec B608
                     "WHERE case_id = ?", (*fields.values(), lr.now(), case_id))
        case = _refresh(conn, case_id, actor)
        access.audit(conn, actor, 'family_leave_updated', case['user_id'],
                     'staff_family_leave_cases', case_id, {'fields': sorted(fields)})
        return _shape(conn, case, actor)


def confirm(actor: Any, case_id: int) -> dict:
    """HR confirms the case: the leave is booked and the person told their
    dates and return date."""
    access.require(actor, 'hr', "Only HR can confirm family leave")
    with lr.write() as conn:
        case = _case(conn, case_id)
        if case['status'] != 'notified':
            raise ValueError("Only a notified case can be confirmed")
        if not case['leave_start']:
            raise ValueError("Set the leave start date first")
        result = assess(case, lr.settings(conn))
        if not result['leave_eligible']:
            raise ValueError("Not eligible for this leave: " + '; '.join(result['notes']))
        conn.execute("UPDATE staff_family_leave_cases SET status = 'confirmed', updated_at = ? "
                     "WHERE case_id = ?", (lr.now(), case_id))
        case = _refresh(conn, case_id, actor)
        access.audit(conn, actor, 'family_leave_confirmed', case['user_id'],
                     'staff_family_leave_cases', case_id)
        lr.mail(case['user_id'], f"Your {KIND_LABELS[case['kind']].lower()} leave is confirmed",
                f"Your {KIND_LABELS[case['kind']].lower()} leave runs from {case['leave_start']} "
                f"to {case['leave_end']}; you are due back on {case['return_date']}. Statutory "
                "pay details are in Staff HR > Leave > Family Leave.", actor)
        return _shape(conn, case, actor)


def record_return(actor: Any, case_id: int, return_date: str) -> dict:
    """The person is back (HR or their line manager records it)."""
    with lr.write() as conn:
        case = _case(conn, case_id)
        if not access.can_manage_person(actor, case['user_id'], conn):
            raise PermissionError("Only their line manager or HR can record the return")
        if case['status'] not in ('confirmed', 'on_leave'):
            raise ValueError("The leave is not under way")
        back = lr.as_date(return_date)
        if case['leave_start'] and back <= lr.as_date(case['leave_start']):
            raise ValueError("The return date is before the leave started")
        if case['kind'] == 'maternity' and case['birth_date'] and \
                back <= lr.as_date(case['birth_date']) + timedelta(weeks=2):
            raise ValueError("The two weeks after the birth are compulsory maternity leave")
        conn.execute("UPDATE staff_family_leave_cases SET status = 'returned', "
                     "actual_return_date = ?, updated_at = ? WHERE case_id = ?",
                     (back.isoformat(), lr.now(), case_id))
        case = _refresh(conn, case_id, actor)
        access.audit(conn, actor, 'family_leave_returned', case['user_id'],
                     'staff_family_leave_cases', case_id, {'return': back.isoformat()})
        return _shape(conn, case, actor)


def cancel(actor: Any, case_id: int, reason: str = '') -> bool:
    with lr.write() as conn:
        case = _case(conn, case_id)
        own = access.username_of(actor) == case['user_id'] and case['status'] == 'notified'
        if not (own or access.is_hr(actor, conn)):
            raise PermissionError("Only HR can cancel a confirmed family leave case")
        conn.execute("UPDATE staff_family_leave_cases SET status = 'cancelled', notes = "
                     "TRIM(COALESCE(notes, '') || ' ' || ?), updated_at = ? WHERE case_id = ?",
                     (f"Cancelled: {reason}".strip(), lr.now(), case_id))
        _refresh(conn, case_id, actor)
        access.audit(conn, actor, 'family_leave_cancelled', case['user_id'],
                     'staff_family_leave_cases', case_id, {'reason': reason})
        return True


def add_kit_day(actor: Any, case_id: int, day: str, hours: Optional[float] = None,
                notes: Optional[str] = None) -> int:
    """A keeping-in-touch (maternity / adoption) or SPLIT (shared parental)
    day, agreed by the line manager or HR."""
    with lr.write() as conn:
        case = _case(conn, case_id)
        if not access.can_manage_person(actor, case['user_id'], conn):
            raise PermissionError("KIT days are agreed by the line manager or HR")
        limit = kit_limit(case['kind'], conn)
        if not limit:
            raise ValueError(f"{KIND_LABELS[case['kind']]} leave has no keeping-in-touch days")
        if case['status'] not in ('confirmed', 'on_leave'):
            raise ValueError("KIT days are worked during confirmed leave")
        d = lr.as_date(day)
        start, end = lr.as_date(case['leave_start']), lr.as_date(case['leave_end'])
        if not (start and end and start <= d <= end):
            raise ValueError("A KIT day must fall within the leave")
        if case['kind'] == 'maternity' and case['birth_date'] and \
                d < lr.as_date(case['birth_date']) + timedelta(weeks=2):
            raise ValueError("No work in the two weeks of compulsory maternity leave")
        count = conn.execute("SELECT COUNT(*) FROM staff_kit_days WHERE case_id = ?",
                             (case_id,)).fetchone()[0]
        if count >= limit:
            label = 'SPLIT' if case['kind'] == 'shared_parental' else 'KIT'
            raise ValueError(f"All {limit} {label} days are used")
        if conn.execute("SELECT 1 FROM staff_kit_days WHERE case_id = ? AND day = ?",
                        (case_id, d.isoformat())).fetchone():
            raise ValueError("That day is already a KIT day")
        cur = conn.execute("INSERT INTO staff_kit_days (case_id, day, hours, notes, agreed_by) "
                           "VALUES (?, ?, ?, ?, ?)",
                           (case_id, d.isoformat(), hours, notes, access.username_of(actor)))
        access.audit(conn, actor, 'kit_day', case['user_id'], 'staff_kit_days', cur.lastrowid,
                     {'day': d.isoformat()})
        return int(cur.lastrowid)


def remove_kit_day(actor: Any, kit_id: int) -> bool:
    with lr.write() as conn:
        row = conn.execute("SELECT k.case_id, c.user_id FROM staff_kit_days k JOIN "
                           "staff_family_leave_cases c ON c.case_id = k.case_id "
                           "WHERE k.kit_id = ?", (kit_id,)).fetchone()
        if not row:
            raise ValueError("No such KIT day")
        if not access.can_manage_person(actor, row[1], conn):
            raise PermissionError("KIT days are agreed by the line manager or HR")
        conn.execute("DELETE FROM staff_kit_days WHERE kit_id = ?", (kit_id,))
        access.audit(conn, actor, 'kit_day_removed', row[1], 'staff_kit_days', kit_id)
        return True


def case(actor: Any, case_id: int) -> dict:
    with get_connection() as conn:
        lr.ensure(conn)
        c = _case(conn, case_id)
        access.require_view_person(actor, c['user_id'], conn, "this family leave case")
        return _shape(conn, c, actor)


def cases(actor: Any, username: Optional[str] = None, include_closed: bool = True) -> list:
    with get_connection() as conn:
        lr.ensure(conn)
        sql, params = "SELECT * FROM staff_family_leave_cases WHERE 1 = 1", []
        if username:
            key = access.staff_key(username, conn) or username
            access.require_view_person(actor, key, conn, "this person's family leave")
            sql += " AND user_id = ?"
            params.append(key)
        if not include_closed:
            sql += " AND status NOT IN ('returned', 'cancelled')"
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY created_at DESC", params)]
        if not username and not access.is_payroll(actor, conn):
            rows = access.filter_people(rows, actor, conn=conn)
        return [_shape(conn, r, actor) for r in rows]


def run_daily(on: Optional[date] = None) -> dict:
    """Scheduler job: confirmed leave that has started is 'on leave'; the
    manager and the person are reminded four weeks before the return."""
    on = on or lr.today()
    started = reminded = 0
    with lr.write() as conn:
        cur = conn.execute("UPDATE staff_family_leave_cases SET status = 'on_leave', "
                           "updated_at = ? WHERE status = 'confirmed' AND leave_start <= ?",
                           (lr.now(), on.isoformat()))
        started = cur.rowcount
        for c in [dict(r) for r in conn.execute(
                "SELECT * FROM staff_family_leave_cases WHERE status = 'on_leave' AND "
                "return_date IS NOT NULL AND return_date BETWEEN ? AND ?",
                (on.isoformat(), (on + timedelta(weeks=4)).isoformat()))]:
            people = {c['user_id']} | set(access.approvers_for(c['user_id'], conn))
            for person in people:
                if lr.remind_once(conn, f"family_return:{c['case_id']}:{c['return_date']}",
                                  person):
                    lr.mail(person, "Return from family leave",
                            f"{access.display_name(c['user_id'], conn)} is due back from "
                            f"{KIND_LABELS[c['kind']].lower()} leave on {c['return_date']}.")
                    reminded += 1
    return {'started': started, 'reminded': reminded}


__all__ = [
    'KINDS', 'KIND_LABELS', 'PAY_NAMES', 'STATUSES', 'EDITABLE', 'week_start', 'key_dates',
    'assess', 'sees_pay', 'kit_limit', 'notify', 'update', 'confirm', 'record_return', 'cancel',
    'add_kit_day', 'remove_kit_day', 'case', 'cases', 'run_daily',
]
