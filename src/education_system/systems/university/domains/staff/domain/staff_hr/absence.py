"""Sickness absence: episodes, fit notes, return-to-work interviews,
trigger points and occupational health referrals.

Sickness is *absence*, not an allowance: an episode books an approved
``leave_requests`` row against the sick leave type (so the calendar and
cover planning see it) and never uses up a balance.

**Who records.** Someone may report their own sickness (self-certified);
their line manager (anyone above them) or HR records, updates and closes
episodes, holds the return-to-work interview and refers to occupational
health.

**Who sees.** The person, their management chain and HR see episodes,
dates, days, the reason *category*, fit note dates and adjustments, RTW
interviews and OH status / fitness / adjustments. **Medical detail** — the
reason detail, the condition on a fit note and the OH outcome — is the
person's and HR's only; everyone else gets it blanked.

**Triggers** (rolling ``absence_window_months``): the Bradford factor
(spells² × days), the number of episodes and the number of days, each
against a configurable threshold. Disability- and pregnancy-related
absence is left out when ``triggers_exclude_protected`` (Equality Act).
A breach raises one open alert per trigger for the manager / HR to review.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr import leave_rules as lr
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

REASONS = (
    'Cold / flu / respiratory', 'Covid-19', 'Gastrointestinal', 'Headache / migraine',
    'Musculoskeletal (back)', 'Musculoskeletal (other)', 'Stress / anxiety / mental health',
    'Injury / accident', 'Operation / recovery', 'Pregnancy-related', 'Disability-related',
    'Infectious disease', 'Other',
)
CERTIFICATION = ('self', 'fit_note', 'none')
ADJUSTMENTS = ('phased return', 'altered hours', 'amended duties', 'workplace adaptations')
OH_FITNESS = ('fit', 'fit_with_adjustments', 'temporarily_unfit', 'long_term_unfit')
ALERT_STATUSES = ('open', 'reviewed', 'actioned', 'dismissed')
SICK_TYPE = 'Sick Leave'

_MEDICAL_EPISODE = ('reason_detail',)
_MEDICAL_FIT_NOTE = ('condition',)
_MEDICAL_OH = ('outcome',)


# ── access ──────────────────────────────────────────────────────────────


def _who(actor: Any) -> str:
    return access.require_user(actor)['username']


def sees_medical(actor: Any, username: str, conn=None) -> bool:
    me = access.username_of(actor)
    return bool(me) and (me == username or access.is_hr(actor, conn))


def _may_record(actor: Any, username: str, conn) -> bool:
    return access.username_of(actor) == username or access.can_manage_person(actor, username, conn)


def _require_manage(actor: Any, username: str, conn, what: str) -> None:
    if not access.can_manage_person(actor, username, conn):
        raise PermissionError(f"Only their line manager or HR can {what}")


def _redact(row: dict, fields, show: bool) -> dict:
    if not show:
        for f in fields:
            if row.get(f):
                row[f] = None
        row['medical_hidden'] = True
    return row


def _sick_type(conn) -> int:
    row = conn.execute("SELECT e.leave_type_id FROM staff_leave_entitlements e JOIN leave_types t "
                       "ON t.leave_type_id = e.leave_type_id WHERE e.basis = 'absence' "
                       "ORDER BY t.is_active DESC, e.leave_type_id LIMIT 1").fetchone()
    if row:
        return int(row[0])
    return lr.leave_type_id(conn, SICK_TYPE, '#dc3545', active=True)


def _episode(conn, episode_id: int) -> dict:
    row = conn.execute("SELECT * FROM staff_absence_episodes WHERE episode_id = ?",
                       (episode_id,)).fetchone()
    if not row:
        raise ValueError("No such absence episode")
    return dict(row)


def _overlapping(conn, username: str, start: date, end: Optional[date],
                 exclude: Optional[int] = None) -> Optional[dict]:
    far = (end or date(9999, 12, 31)).isoformat()
    row = conn.execute(
        "SELECT * FROM staff_absence_episodes WHERE user_id = ? AND status != 'cancelled' "
        "AND start_date <= ? AND COALESCE(end_date, '9999-12-31') >= ? AND episode_id != ?",
        (username, far, start.isoformat(), exclude or -1)).fetchone()
    return dict(row) if row else None


def _days(conn, username: str, start, end, half: bool = False) -> float:
    end = lr.as_date(end) or lr.today()
    start = lr.as_date(start)
    if end < start:
        return 0.0
    return lr.working_days(username, start, end, conn, start_half=half)


def _tell_line(conn, username: str, subject: str, body: str, actor: Any = None) -> None:
    for person in access.approvers_for(username, conn):
        if person != access.username_of(actor):
            lr.mail(person, subject, body, actor)


# ── episodes ────────────────────────────────────────────────────────────


def record(actor: Any, username: str, start_date: str, end_date: Optional[str] = None, *,
           reason_category: str = 'Other', reason_detail: Optional[str] = None,
           certification: str = 'self', first_day_half: bool = False,
           work_related: bool = False, disability_related: bool = False,
           pregnancy_related: bool = False, notes: Optional[str] = None) -> int:
    """Record a sickness absence (the person themselves, their manager or
    HR). Returns the episode id."""
    me = _who(actor)
    with lr.write() as conn:
        key = access.staff_key(username, conn) or str(username)
        if not _may_record(actor, key, conn):
            raise PermissionError("Only the person, their line manager or HR can record absence")
        start, end = lr.as_date(start_date), lr.as_date(end_date)
        if start is None:
            raise ValueError("A start date is needed")
        if end and end < start:
            raise ValueError("The end date is before the start date")
        if start > lr.today() + timedelta(days=1):
            raise ValueError("Sickness cannot be recorded in advance")
        if reason_category not in REASONS:
            raise ValueError("Choose a reason category from the list")
        if certification not in CERTIFICATION:
            raise ValueError(f"Certification must be one of {', '.join(CERTIFICATION)}")
        clash = _overlapping(conn, key, start, end)
        if clash:
            raise ValueError(f"This overlaps absence episode {clash['episode_id']} "
                             f"from {clash['start_date']}")
        status = 'closed' if end else 'open'
        days = _days(conn, key, start, end, first_day_half)
        cur = conn.execute(
            "INSERT INTO staff_absence_episodes (user_id, start_date, end_date, first_day_half, "
            "reason_category, reason_detail, certification, working_days, work_related, "
            "disability_related, pregnancy_related, status, reported_by, reported_at, closed_by, "
            "closed_at, notes, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?)",
            (key, start.isoformat(), end.isoformat() if end else None, int(first_day_half),
             reason_category, reason_detail, certification, days, int(work_related),
             int(disability_related or reason_category == 'Disability-related'),
             int(pregnancy_related or reason_category == 'Pregnancy-related'), status, me,
             lr.now(), me if end else None, lr.now() if end else None, notes, lr.now()))
        episode_id = int(cur.lastrowid)
        request_id = lr.book_linked(conn, key, _sick_type(conn), start,
                                    end or max(start, lr.today()), 'absence', episode_id, actor)
        conn.execute("UPDATE staff_absence_episodes SET leave_request_id = ? WHERE episode_id = ?",
                     (request_id, episode_id))
        access.audit(conn, actor, 'absence_recorded', key, 'staff_absence_episodes', episode_id,
                     {'start': start.isoformat(), 'end': end.isoformat() if end else None,
                      'category': reason_category})
        name = access.display_name(key, conn)
        _tell_line(conn, key, f"Absence: {name} from {start.isoformat()}",
                   f"{name} has been recorded as absent through sickness from "
                   f"{start.isoformat()}" + (f" to {end.isoformat()}" if end else "") +
                   ". Please see Staff HR > Leave > Absence.", actor)
        return episode_id


def close(actor: Any, episode_id: int, end_date: str, notes: Optional[str] = None) -> dict:
    """Record the last day of absence (the person, manager or HR)."""
    me = _who(actor)
    with lr.write() as conn:
        ep = _episode(conn, episode_id)
        if not _may_record(actor, ep['user_id'], conn):
            raise PermissionError("Only the person, their line manager or HR can close absence")
        if ep['status'] == 'cancelled':
            raise ValueError("This episode was cancelled")
        end = lr.as_date(end_date)
        if end < lr.as_date(ep['start_date']):
            raise ValueError("The end date is before the start date")
        clash = _overlapping(conn, ep['user_id'], lr.as_date(ep['start_date']), end, episode_id)
        if clash:
            raise ValueError(f"This overlaps absence episode {clash['episode_id']}")
        days = _days(conn, ep['user_id'], ep['start_date'], end, bool(ep['first_day_half']))
        conn.execute("UPDATE staff_absence_episodes SET end_date = ?, working_days = ?, "
                     "status = 'closed', closed_by = ?, closed_at = ?, notes = COALESCE(?, notes), "
                     "updated_at = ? WHERE episode_id = ?",
                     (end.isoformat(), days, me, lr.now(), notes, lr.now(), episode_id))
        lr.update_linked(conn, ep['leave_request_id'], ep['start_date'], end)
        access.audit(conn, actor, 'absence_closed', ep['user_id'], 'staff_absence_episodes',
                     episode_id, {'end': end.isoformat(), 'days': days})
        if access.username_of(actor) == ep['user_id']:
            _tell_line(conn, ep['user_id'], "Back at work: return-to-work interview due",
                       f"{access.display_name(ep['user_id'], conn)} is back at work after "
                       f"absence ending {end.isoformat()}. Please hold a return-to-work "
                       "interview.", actor)
        return _episode(conn, episode_id)


def update(actor: Any, episode_id: int, **fields) -> dict:
    """Change an episode's details. The reason detail only by the person or
    HR; everything else by the manager or HR."""
    allowed = {'reason_category', 'reason_detail', 'certification', 'work_related',
               'disability_related', 'pregnancy_related', 'notes', 'start_date',
               'first_day_half'}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Cannot change {', '.join(sorted(unknown))}")
    with lr.write() as conn:
        ep = _episode(conn, episode_id)
        medical_only = set(fields) <= {'reason_detail'}
        if medical_only:
            if not sees_medical(actor, ep['user_id'], conn):
                raise PermissionError("Only the person or HR can change the medical detail")
        else:
            _require_manage(actor, ep['user_id'], conn, "change an absence record")
            if 'reason_detail' in fields and not sees_medical(actor, ep['user_id'], conn):
                raise PermissionError("Only the person or HR can change the medical detail")
        if 'reason_category' in fields and fields['reason_category'] not in REASONS:
            raise ValueError("Choose a reason category from the list")
        if 'certification' in fields and fields['certification'] not in CERTIFICATION:
            raise ValueError("Unknown certification")
        if 'start_date' in fields:
            start = lr.as_date(fields['start_date'])
            if ep['end_date'] and start > lr.as_date(ep['end_date']):
                raise ValueError("The start date is after the end date")
            if _overlapping(conn, ep['user_id'], start, lr.as_date(ep['end_date']), episode_id):
                raise ValueError("This overlaps another absence episode")
            fields['start_date'] = start.isoformat()
        for flag in ('work_related', 'disability_related', 'pregnancy_related', 'first_day_half'):
            if flag in fields:
                fields[flag] = int(bool(fields[flag]))
        sets = ', '.join(f"{k} = ?" for k in fields)
        # db-audit: ignore[DBW001] - column names come from the ``allowed`` set
        conn.execute(f"UPDATE staff_absence_episodes SET {sets}, updated_at = ? "  # nosec B608
                     "WHERE episode_id = ?", (*fields.values(), lr.now(), episode_id))
        ep = _episode(conn, episode_id)
        if {'start_date', 'first_day_half'} & set(fields):
            days = _days(conn, ep['user_id'], ep['start_date'], ep['end_date'],
                         bool(ep['first_day_half']))
            conn.execute("UPDATE staff_absence_episodes SET working_days = ? WHERE episode_id = ?",
                         (days, episode_id))
            lr.update_linked(conn, ep['leave_request_id'], ep['start_date'],
                             ep['end_date'] or max(lr.as_date(ep['start_date']), lr.today()))
        access.audit(conn, actor, 'absence_updated', ep['user_id'], 'staff_absence_episodes',
                     episode_id, {'fields': sorted(fields)})
        return _episode(conn, episode_id)


def cancel(actor: Any, episode_id: int, reason: str = '') -> bool:
    """Withdraw an episode recorded in error (manager or HR)."""
    with lr.write() as conn:
        ep = _episode(conn, episode_id)
        _require_manage(actor, ep['user_id'], conn, "cancel an absence record")
        conn.execute("UPDATE staff_absence_episodes SET status = 'cancelled', notes = "
                     "TRIM(COALESCE(notes, '') || ' ' || ?), updated_at = ? WHERE episode_id = ?",
                     (f"Cancelled: {reason}".strip(), lr.now(), episode_id))
        lr.cancel_linked(conn, ep['leave_request_id'], actor)
        access.audit(conn, actor, 'absence_cancelled', ep['user_id'], 'staff_absence_episodes',
                     episode_id, {'reason': reason})
        return True


# ── fit notes / return to work ──────────────────────────────────────────


def add_fit_note(actor: Any, episode_id: int, issued_date: str, from_date: str, to_date: str, *,
                 assessment: str = 'not_fit', adjustments: Optional[str] = None,
                 condition: Optional[str] = None, issued_by: Optional[str] = None,
                 document_path: Optional[str] = None) -> int:
    """Record a fit note against an episode ('may_be_fit' with the
    adjustments the doctor suggests)."""
    me = _who(actor)
    if assessment not in ('not_fit', 'may_be_fit'):
        raise ValueError("Assessment must be 'not_fit' or 'may_be_fit'")
    with lr.write() as conn:
        ep = _episode(conn, episode_id)
        if not _may_record(actor, ep['user_id'], conn):
            raise PermissionError("Only the person, their line manager or HR can add a fit note")
        f, t = lr.as_date(from_date), lr.as_date(to_date)
        lr.as_date(issued_date)
        if t < f:
            raise ValueError("The fit note ends before it starts")
        if assessment == 'may_be_fit' and not (adjustments or '').strip():
            raise ValueError("Say which adjustments a 'may be fit' note suggests")
        cur = conn.execute(
            "INSERT INTO staff_fit_notes (episode_id, issued_date, from_date, to_date, assessment, "
            "adjustments, condition, issued_by, document_path, received_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (episode_id, str(issued_date)[:10], f.isoformat(), t.isoformat(), assessment,
             adjustments, condition, issued_by, document_path, me))
        conn.execute("UPDATE staff_absence_episodes SET certification = 'fit_note', "
                     "updated_at = ? WHERE episode_id = ?", (lr.now(), episode_id))
        access.audit(conn, actor, 'fit_note_added', ep['user_id'], 'staff_fit_notes',
                     cur.lastrowid, {'from': f.isoformat(), 'to': t.isoformat(),
                                     'assessment': assessment})
        return int(cur.lastrowid)


def record_rtw(actor: Any, episode_id: int, interview_date: str, *, fit_to_return: bool = True,
               adjustments_agreed: Optional[str] = None, support_offered: Optional[str] = None,
               wellbeing_notes: Optional[str] = None, triggers_discussed: bool = False,
               oh_referral_recommended: bool = False) -> int:
    """The return-to-work interview (line manager or HR; one per episode)."""
    me = _who(actor)
    with lr.write() as conn:
        ep = _episode(conn, episode_id)
        _require_manage(actor, ep['user_id'], conn, "hold a return-to-work interview")
        if ep['status'] == 'cancelled':
            raise ValueError("This episode was cancelled")
        day = lr.as_date(interview_date)
        if ep['end_date'] and day < lr.as_date(ep['end_date']):
            raise ValueError("The interview is before the absence ended")
        if conn.execute("SELECT 1 FROM staff_rtw_interviews WHERE episode_id = ?",
                        (episode_id,)).fetchone():
            raise ValueError("This episode already has a return-to-work interview")
        cur = conn.execute(
            "INSERT INTO staff_rtw_interviews (episode_id, interview_date, conducted_by, "
            "fit_to_return, adjustments_agreed, support_offered, wellbeing_notes, "
            "triggers_discussed, oh_referral_recommended) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (episode_id, day.isoformat(), me, int(fit_to_return), adjustments_agreed,
             support_offered, wellbeing_notes, int(triggers_discussed),
             int(oh_referral_recommended)))
        access.audit(conn, actor, 'rtw_recorded', ep['user_id'], 'staff_rtw_interviews',
                     cur.lastrowid)
        lr.mail(ep['user_id'], "Your return-to-work interview",
                f"Your return-to-work interview on {day.isoformat()} has been recorded. Please "
                "read it in Staff HR > Leave > Absence and confirm it, adding any comments.",
                actor)
        return int(cur.lastrowid)


def confirm_rtw(actor: Any, episode_id: int, comments: Optional[str] = None) -> bool:
    """The person confirms their interview record (with comments)."""
    me = _who(actor)
    with lr.write() as conn:
        ep = _episode(conn, episode_id)
        if me != ep['user_id']:
            raise PermissionError("Only the person interviewed can confirm the record")
        cur = conn.execute("UPDATE staff_rtw_interviews SET employee_comments = ?, "
                           "employee_confirmed = 1, employee_confirmed_at = ? "
                           "WHERE episode_id = ?", (comments, lr.now(), episode_id))
        if not cur.rowcount:
            raise ValueError("There is no interview record to confirm")
        access.audit(conn, actor, 'rtw_confirmed', me, 'staff_rtw_interviews', episode_id)
        return True


# ── reading ─────────────────────────────────────────────────────────────


def _full(conn, ep: dict, actor: Any) -> dict:
    show = sees_medical(actor, ep['user_id'], conn)
    ep = _redact(dict(ep), _MEDICAL_EPISODE, show)
    ep['name'] = access.display_name(ep['user_id'], conn)
    ep['fit_notes'] = [_redact(dict(r), _MEDICAL_FIT_NOTE, show) for r in conn.execute(
        "SELECT * FROM staff_fit_notes WHERE episode_id = ? ORDER BY from_date",
        (ep['episode_id'],)).fetchall()]
    rtw = conn.execute("SELECT * FROM staff_rtw_interviews WHERE episode_id = ?",
                       (ep['episode_id'],)).fetchone()
    ep['rtw'] = dict(rtw) if rtw else None
    if ep['status'] == 'open':
        ep['working_days'] = _days(conn, ep['user_id'], ep['start_date'], None,
                                   bool(ep['first_day_half']))
    return ep


def episode(actor: Any, episode_id: int) -> dict:
    with get_connection() as conn:
        lr.ensure(conn)
        ep = _episode(conn, episode_id)
        access.require_view_person(actor, ep['user_id'], conn, "this absence record")
        return _full(conn, ep, actor)


def episodes(actor: Any, username: Optional[str] = None, since: Optional[str] = None,
             include_cancelled: bool = False) -> list:
    """Episodes ``actor`` may see (one person's, or everyone visible)."""
    with get_connection() as conn:
        lr.ensure(conn)
        sql, params = "SELECT * FROM staff_absence_episodes WHERE 1 = 1", []
        if username:
            key = access.staff_key(username, conn) or username
            access.require_view_person(actor, key, conn, "this person's absence")
            sql += " AND user_id = ?"
            params.append(key)
        if since:
            sql += " AND COALESCE(end_date, '9999-12-31') >= ?"
            params.append(str(since)[:10])
        if not include_cancelled:
            sql += " AND status != 'cancelled'"
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY start_date DESC", params)]
        if not username:
            rows = access.filter_people(rows, actor, conn=conn)
        return [_full(conn, r, actor) for r in rows]


# ── triggers ────────────────────────────────────────────────────────────


def stats(username: str, on: Optional[date] = None, conn=None) -> dict:
    """Spells, days and Bradford factor over the rolling window to ``on``."""
    own = conn is None
    c = get_connection() if own else conn
    try:
        lr.ensure(c)
        settings = lr.settings(c)
        on = on or lr.today()
        start = lr.add_months(on, -int(settings['absence_window_months'])) + timedelta(days=1)
        sql = ("SELECT * FROM staff_absence_episodes WHERE user_id = ? AND status != 'cancelled' "
               "AND start_date <= ? AND COALESCE(end_date, ?) >= ?")
        rows = [dict(r) for r in c.execute(sql, (username, on.isoformat(), on.isoformat(),
                                                 start.isoformat()))]
        if settings['triggers_exclude_protected']:
            rows = [r for r in rows if not (r['disability_related'] or r['pregnancy_related'])]
        days = 0.0
        for r in rows:
            s = max(lr.as_date(r['start_date']), start)
            e = min(lr.as_date(r['end_date']) if r['end_date'] else on, on)
            days += _days(c, username, s, e, bool(r['first_day_half']) and
                          s == lr.as_date(r['start_date']))
        spells = len(rows)
        return {'user_id': username, 'window_start': start.isoformat(),
                'window_end': on.isoformat(), 'spells': spells, 'days': days,
                'bradford': spells * spells * days}
    finally:
        if own:
            c.close()


def triggers_hit(username: str, on: Optional[date] = None, conn=None) -> list:
    own = conn is None
    c = get_connection() if own else conn
    try:
        s = stats(username, on, c)
        settings = lr.settings(c)
        out = []
        for kind, value, limit in (('bradford', s['bradford'], settings['trigger_bradford']),
                                   ('episodes', s['spells'], settings['trigger_episodes']),
                                   ('days', s['days'], settings['trigger_days'])):
            if limit and value >= float(limit):
                out.append({'trigger_kind': kind, 'value': value, 'threshold': float(limit),
                            'window_start': s['window_start'], 'window_end': s['window_end']})
        return out
    finally:
        if own:
            c.close()


def raise_alerts(on: Optional[date] = None) -> int:
    """Open an alert for each trigger reached (one open alert per person
    and trigger); tell the manager / HR."""
    on = on or lr.today()
    raised = 0
    with lr.write() as conn:
        since = lr.add_months(on, -int(lr.setting('absence_window_months', conn))).isoformat()
        people = [r[0] for r in conn.execute(
            "SELECT DISTINCT user_id FROM staff_absence_episodes WHERE status != 'cancelled' "
            "AND COALESCE(end_date, '9999-12-31') >= ?", (since,))]
        for person in people:
            for hit in triggers_hit(person, on, conn):
                if conn.execute("SELECT 1 FROM staff_absence_alerts WHERE user_id = ? AND "
                                "trigger_kind = ? AND status = 'open'",
                                (person, hit['trigger_kind'])).fetchone():
                    continue
                conn.execute("INSERT INTO staff_absence_alerts (user_id, trigger_kind, value, "
                             "threshold, window_start, window_end) VALUES (?, ?, ?, ?, ?, ?)",
                             (person, hit['trigger_kind'], hit['value'], hit['threshold'],
                              hit['window_start'], hit['window_end']))
                raised += 1
                name = access.display_name(person, conn)
                for to in set(access.approvers_for(person, conn)) | set(lr.hr_people(conn)):
                    lr.mail(to, f"Absence review due: {name}",
                            f"{name} has reached the absence trigger point for "
                            f"{hit['trigger_kind']} ({hit['value']:g} against "
                            f"{hit['threshold']:g}) in the period {hit['window_start']} to "
                            f"{hit['window_end']}. Please review in Staff HR > Leave > Absence.")
    return raised


def alerts(actor: Any, status: Optional[str] = 'open') -> list:
    with get_connection() as conn:
        lr.ensure(conn)
        sql, params = "SELECT * FROM staff_absence_alerts", []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY raised_at DESC", params)]
        me = access.username_of(actor)
        rows = [r for r in rows if r['user_id'] != me or access.is_hr(actor, conn)]
        rows = access.filter_people(rows, actor, conn=conn)
        for r in rows:
            r['name'] = access.display_name(r['user_id'], conn)
        return rows


def review_alert(actor: Any, alert_id: int, status: str, outcome: str) -> bool:
    """Record what was done about a trigger (manager or HR)."""
    if status not in ('reviewed', 'actioned', 'dismissed'):
        raise ValueError("Status must be reviewed, actioned or dismissed")
    if not (outcome or '').strip():
        raise ValueError("Record the outcome of the review")
    with lr.write() as conn:
        row = conn.execute("SELECT user_id FROM staff_absence_alerts WHERE alert_id = ?",
                           (alert_id,)).fetchone()
        if not row:
            raise ValueError("No such alert")
        _require_manage(actor, row[0], conn, "review an absence trigger")
        conn.execute("UPDATE staff_absence_alerts SET status = ?, outcome = ?, reviewed_by = ?, "
                     "reviewed_at = ? WHERE alert_id = ?",
                     (status, outcome.strip(), access.username_of(actor), lr.now(), alert_id))
        access.audit(conn, actor, 'absence_alert_reviewed', row[0], 'staff_absence_alerts',
                     alert_id, {'status': status})
        return True


# ── occupational health ─────────────────────────────────────────────────


def _referral(conn, referral_id: int) -> dict:
    row = conn.execute("SELECT * FROM staff_oh_referrals WHERE referral_id = ?",
                       (referral_id,)).fetchone()
    if not row:
        raise ValueError("No such referral")
    return dict(row)


def refer(actor: Any, username: str, reason: str, questions: Optional[str] = None,
          episode_id: Optional[int] = None) -> int:
    """Refer someone to occupational health (manager or HR). It waits for
    their consent."""
    me = _who(actor)
    if not (reason or '').strip():
        raise ValueError("Give the reason for the referral")
    with lr.write() as conn:
        key = access.staff_key(username, conn) or username
        _require_manage(actor, key, conn, "refer someone to occupational health")
        if episode_id is not None and _episode(conn, episode_id)['user_id'] != key:
            raise ValueError("That absence episode belongs to someone else")
        cur = conn.execute("INSERT INTO staff_oh_referrals (user_id, episode_id, referred_by, "
                           "reason, questions) VALUES (?, ?, ?, ?, ?)",
                           (key, episode_id, me, reason.strip(), questions))
        access.audit(conn, actor, 'oh_referred', key, 'staff_oh_referrals', cur.lastrowid)
        lr.mail(key, "Occupational health referral — your consent",
                "You have been referred to occupational health. Please read the referral in "
                "Staff HR > Leave > Absence and give or decline your consent.", actor)
        return int(cur.lastrowid)


def consent(actor: Any, referral_id: int, given: bool) -> dict:
    """The person consents to (or declines) the referral."""
    me = _who(actor)
    with lr.write() as conn:
        ref = _referral(conn, referral_id)
        if me != ref['user_id']:
            raise PermissionError("Only the person referred can give consent")
        if ref['status'] != 'awaiting_consent':
            raise ValueError("Consent has already been answered")
        conn.execute("UPDATE staff_oh_referrals SET consent_given = ?, consent_at = ?, "
                     "status = ?, updated_at = ? WHERE referral_id = ?",
                     (int(bool(given)), lr.now(), 'referred' if given else 'declined',
                      lr.now(), referral_id))
        access.audit(conn, actor, 'oh_consent', me, 'staff_oh_referrals', referral_id,
                     {'given': bool(given)})
        lr.mail(ref['referred_by'], "Occupational health referral: consent "
                + ("given" if given else "declined"),
                f"{access.display_name(me, conn)} has {'given' if given else 'declined'} "
                "consent to the occupational health referral.", actor)
        return _referral(conn, referral_id)


def book_oh(actor: Any, referral_id: int, provider: str, appointment_date: str) -> dict:
    """HR books the appointment."""
    access.require(actor, 'hr', "Only HR can book occupational health")
    with lr.write() as conn:
        ref = _referral(conn, referral_id)
        if ref['status'] not in ('referred', 'appointment_booked'):
            raise ValueError("The referral needs the person's consent first")
        day = lr.as_date(appointment_date)
        conn.execute("UPDATE staff_oh_referrals SET provider = ?, appointment_date = ?, "
                     "status = 'appointment_booked', updated_at = ? WHERE referral_id = ?",
                     (provider, day.isoformat(), lr.now(), referral_id))
        access.audit(conn, actor, 'oh_booked', ref['user_id'], 'staff_oh_referrals', referral_id)
        lr.mail(ref['user_id'], "Occupational health appointment",
                f"Your occupational health appointment with {provider} is on {day.isoformat()}.",
                actor)
        return _referral(conn, referral_id)


def record_oh_report(actor: Any, referral_id: int, fitness: str,
                     adjustments: Optional[str] = None, outcome: Optional[str] = None,
                     review_date: Optional[str] = None) -> dict:
    """HR records the OH report: fitness and adjustments (shared with the
    manager) and the outcome (medical; HR and the person only)."""
    access.require(actor, 'hr', "Only HR can record an occupational health report")
    if fitness not in OH_FITNESS:
        raise ValueError(f"Fitness must be one of {', '.join(OH_FITNESS)}")
    with lr.write() as conn:
        ref = _referral(conn, referral_id)
        if ref['status'] in ('awaiting_consent', 'declined', 'closed'):
            raise ValueError("There is no consented referral to report on")
        conn.execute("UPDATE staff_oh_referrals SET fitness = ?, adjustments = ?, outcome = ?, "
                     "review_date = ?, report_received_at = ?, status = 'report_received', "
                     "updated_at = ? WHERE referral_id = ?",
                     (fitness, adjustments, outcome,
                      lr.as_date(review_date).isoformat() if review_date else None,
                      lr.now(), lr.now(), referral_id))
        access.audit(conn, actor, 'oh_report', ref['user_id'], 'staff_oh_referrals', referral_id,
                     {'fitness': fitness})
        lr.mail(ref['referred_by'], "Occupational health report received",
                f"The occupational health report for {access.display_name(ref['user_id'], conn)}"
                f" has been received: {fitness.replace('_', ' ')}. Recommended adjustments are "
                "in Staff HR > Leave > Absence.", actor)
        return _referral(conn, referral_id)


def close_referral(actor: Any, referral_id: int) -> bool:
    access.require(actor, 'hr', "Only HR can close an occupational health referral")
    with lr.write() as conn:
        ref = _referral(conn, referral_id)
        conn.execute("UPDATE staff_oh_referrals SET status = 'closed', closed_by = ?, "
                     "closed_at = ?, updated_at = ? WHERE referral_id = ?",
                     (access.username_of(actor), lr.now(), lr.now(), referral_id))
        access.audit(conn, actor, 'oh_closed', ref['user_id'], 'staff_oh_referrals', referral_id)
        return True


def referrals(actor: Any, username: Optional[str] = None, open_only: bool = False) -> list:
    with get_connection() as conn:
        lr.ensure(conn)
        sql, params = "SELECT * FROM staff_oh_referrals WHERE 1 = 1", []
        if username:
            key = access.staff_key(username, conn) or username
            access.require_view_person(actor, key, conn, "this person's referrals")
            sql += " AND user_id = ?"
            params.append(key)
        if open_only:
            sql += " AND status NOT IN ('closed', 'declined')"
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY referred_at DESC", params)]
        if not username:
            rows = access.filter_people(rows, actor, conn=conn)
        out = []
        for r in rows:
            r = _redact(r, _MEDICAL_OH, sees_medical(actor, r['user_id'], conn))
            r['name'] = access.display_name(r['user_id'], conn)
            out.append(r)
        return out


# ── what needs doing ────────────────────────────────────────────────────


def due_actions(actor: Any, on: Optional[date] = None) -> list:
    """For the people ``actor`` sees: fit notes overdue, return-to-work
    interviews to hold, consents awaited, triggers to review."""
    on = on or lr.today()
    out = []
    with get_connection() as conn:
        lr.ensure(conn)
        settings = lr.settings(conn)
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM staff_absence_episodes WHERE status != 'cancelled'")]
        rows = access.filter_people(rows, actor, conn=conn)
        me = access.username_of(actor)
        for ep in rows:
            name = access.display_name(ep['user_id'], conn)
            start = lr.as_date(ep['start_date'])
            last = lr.as_date(ep['end_date']) or on
            noted = conn.execute("SELECT MAX(to_date) FROM staff_fit_notes WHERE episode_id = ?",
                                 (ep['episode_id'],)).fetchone()[0]
            covered_to = lr.as_date(noted) if noted else \
                start + timedelta(days=int(settings['self_cert_days']) - 1)
            if last > covered_to:
                out.append({'kind': 'fit_note', 'user_id': ep['user_id'], 'name': name,
                            'episode_id': ep['episode_id'],
                            'detail': f"Fit note needed from {(covered_to + timedelta(days=1))}"})
            has_rtw = conn.execute("SELECT 1 FROM staff_rtw_interviews WHERE episode_id = ?",
                                   (ep['episode_id'],)).fetchone()
            if ep['status'] == 'closed' and not has_rtw and ep['user_id'] != me:
                due = lr.as_date(ep['end_date']) + timedelta(days=int(settings['rtw_due_days']))
                out.append({'kind': 'rtw', 'user_id': ep['user_id'], 'name': name,
                            'episode_id': ep['episode_id'],
                            'detail': f"Return-to-work interview due by {due.isoformat()}"
                                      + (" (overdue)" if due < on else "")})
        for ref in conn.execute("SELECT * FROM staff_oh_referrals WHERE status = "
                                "'awaiting_consent'").fetchall():
            if ref['user_id'] == me:
                out.append({'kind': 'oh_consent', 'user_id': me, 'name': 'You',
                            'referral_id': ref['referral_id'],
                            'detail': 'Occupational health referral awaits your consent'})
    out += [{'kind': 'trigger', 'user_id': a['user_id'], 'name': a['name'],
             'alert_id': a['alert_id'],
             'detail': f"{a['trigger_kind']} trigger ({a['value']:g} / {a['threshold']:g})"}
            for a in alerts(actor)]
    return out


def run_daily(on: Optional[date] = None) -> dict:
    """Scheduler job: keep open absences' bookings running to today, raise
    trigger alerts, remind about fit notes and return-to-work interviews."""
    on = on or lr.today()
    reminded = 0
    with lr.write() as conn:
        settings = lr.settings(conn)
        for ep in [dict(r) for r in conn.execute(
                "SELECT * FROM staff_absence_episodes WHERE status = 'open'")]:
            lr.update_linked(conn, ep['leave_request_id'], ep['start_date'],
                             max(lr.as_date(ep['start_date']), on))
            conn.execute("UPDATE staff_absence_episodes SET working_days = ? WHERE episode_id = ?",
                         (_days(conn, ep['user_id'], ep['start_date'], on,
                                bool(ep['first_day_half'])), ep['episode_id']))
            noted = conn.execute("SELECT MAX(to_date) FROM staff_fit_notes WHERE episode_id = ?",
                                 (ep['episode_id'],)).fetchone()[0]
            covered = lr.as_date(noted) if noted else lr.as_date(ep['start_date']) + \
                timedelta(days=int(settings['self_cert_days']) - 1)
            if on > covered and lr.remind_once(conn, f"fit_note:{ep['episode_id']}:{covered}",
                                               ep['user_id']):
                lr.mail(ep['user_id'], "A fit note is needed",
                        "Your absence now runs beyond the period you can self-certify. Please "
                        "send a fit note from your doctor to your line manager or HR.")
                reminded += 1
        for ep in [dict(r) for r in conn.execute(
                "SELECT e.* FROM staff_absence_episodes e LEFT JOIN staff_rtw_interviews r "
                "ON r.episode_id = e.episode_id WHERE e.status = 'closed' AND r.rtw_id IS NULL "
                "AND e.end_date >= ?", ((on - timedelta(days=60)).isoformat(),))]:
            due = lr.as_date(ep['end_date']) + timedelta(days=int(settings['rtw_due_days']))
            if on <= lr.as_date(ep['end_date']):
                continue
            for manager in access.approvers_for(ep['user_id'], conn):
                if lr.remind_once(conn, f"rtw:{ep['episode_id']}", manager):
                    lr.mail(manager, "Return-to-work interview due",
                            f"Please hold a return-to-work interview with "
                            f"{access.display_name(ep['user_id'], conn)} (absence ended "
                            f"{ep['end_date']}) by {due.isoformat()}.")
                    reminded += 1
    return {'alerts': raise_alerts(on), 'reminders': reminded}


__all__ = [
    'REASONS', 'CERTIFICATION', 'ADJUSTMENTS', 'OH_FITNESS', 'ALERT_STATUSES', 'sees_medical',
    'record', 'close', 'update', 'cancel', 'add_fit_note', 'record_rtw', 'confirm_rtw',
    'episode', 'episodes', 'stats', 'triggers_hit', 'raise_alerts', 'alerts', 'review_alert',
    'refer', 'consent', 'book_oh', 'record_oh_report', 'close_referral', 'referrals',
    'due_actions', 'run_daily',
]
