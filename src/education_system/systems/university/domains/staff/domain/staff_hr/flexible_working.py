"""Statutory flexible working requests (a day-one right).

* Anyone may ask from their first day; at most ``fw_requests_per_year``
  statutory requests in any 12 months (a withdrawn one still counts), and
  one at a time.
* The request goes to whoever approves for them (``access.approvers_for``:
  their line manager, else HR); anyone who may approve for them
  (``access.can_approve_for``) can decide it.
* A request may not be turned down without consulting the person first
  (a meeting); a refusal must give one of the eight statutory business
  reasons (:data:`REFUSAL_REASONS`).
* The decision — including any appeal — is due within
  ``fw_decision_months`` (2) of the request unless both sides agree to an
  extension.
* An approval may be a trial; an approval records the contract variation
  and, when the request gives the new working days / hours, updates the
  working pattern from the start date (which feeds leave entitlements).
* The person may appeal a refusal; someone other than the original
  decision-maker who may approve for them (or HR) decides it.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Iterable, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr import leave_rules as lr
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

CHANGE_TYPES = ('hours', 'times', 'location', 'compressed hours', 'job share', 'annualised hours',
                'term-time working', 'other')
REFUSAL_REASONS = (
    'the burden of additional costs',
    'a detrimental effect on ability to meet customer demand',
    'inability to reorganise work among existing staff',
    'inability to recruit additional staff',
    'a detrimental impact on quality',
    'a detrimental impact on performance',
    'insufficiency of work during the periods the employee proposes to work',
    'planned structural changes',
)
LIVE = ('submitted', 'meeting_scheduled', 'appealed')
OUTCOMES = ('approved', 'approved_trial', 'rejected')


def _row(conn, fw_id: int) -> dict:
    row = conn.execute("SELECT * FROM staff_flexible_working_requests WHERE fw_id = ?",
                       (fw_id,)).fetchone()
    if not row:
        raise ValueError("No such flexible working request")
    return dict(row)


def _deadline(row: dict) -> date:
    return lr.as_date(row['extended_to']) or lr.as_date(row['decision_due'])


def _shape(conn, row: dict) -> dict:
    row = dict(row)
    row['name'] = access.display_name(row['user_id'], conn)
    due = _deadline(row)
    row['deadline'] = due.isoformat() if due else None
    row['overdue'] = bool(due and row['status'] in LIVE and due < lr.today())
    return row


def submit(actor: Any, requested_pattern: str, *, change_type: str = 'hours',
           current_pattern: Optional[str] = None, requested_start: Optional[str] = None,
           requested_days: Optional[Iterable[int]] = None,
           requested_hours: Optional[float] = None, temporary_until: Optional[str] = None,
           effect_notes: Optional[str] = None) -> int:
    """The person makes a statutory request."""
    me = access.require_user(actor)['username']
    if not (requested_pattern or '').strip():
        raise ValueError("Describe the working pattern you are asking for")
    if change_type not in CHANGE_TYPES:
        raise ValueError(f"Change type must be one of {', '.join(CHANGE_TYPES)}")
    days = sorted({int(d) for d in requested_days}) if requested_days else None
    if days is not None and (not days or any(d < 0 or d > 6 for d in days)):
        raise ValueError("Working days are 0 (Monday) to 6 (Sunday)")
    if requested_hours is not None and float(requested_hours) <= 0:
        raise ValueError("Hours must be more than 0")
    with lr.write() as conn:
        settings = lr.settings(conn)
        if conn.execute("SELECT 1 FROM staff_flexible_working_requests WHERE user_id = ? AND "
                        f"status IN ({', '.join('?' * len(LIVE))})",
                        (me, *LIVE)).fetchone():
            raise ValueError("You already have a flexible working request being considered")
        since = lr.add_months(lr.today(), -12).isoformat()
        made = conn.execute("SELECT COUNT(*) FROM staff_flexible_working_requests WHERE "
                            "user_id = ? AND substr(submitted_at, 1, 10) > ?",
                            (me, since)).fetchone()[0]
        if made >= int(settings['fw_requests_per_year']):
            raise ValueError(f"Only {settings['fw_requests_per_year']} statutory requests can be "
                             "made in any 12 months")
        approvers = access.approvers_for(me, conn)
        if current_pattern is None:
            p = lr.pattern_of(me, conn)
            current_pattern = (', '.join(lr.WEEKDAYS[d] for d in p['work_days']) +
                               (f"; {p['hours']:g} hours" if p['hours'] else '') +
                               f"; FTE {p['fte']:g}")
        due = lr.add_months(lr.today(), int(settings['fw_decision_months']))
        cur = conn.execute(
            "INSERT INTO staff_flexible_working_requests (user_id, submitted_at, change_type, "
            "current_pattern, requested_pattern, requested_days, requested_hours, requested_start, "
            "temporary_until, effect_notes, approver, decision_due) VALUES (?, ?, ?, ?, ?, ?, ?, "
            "?, ?, ?, ?, ?)",
            (me, lr.now(), change_type, current_pattern, requested_pattern.strip(),
             ','.join(str(d) for d in days) if days else None, requested_hours,
             lr.as_date(requested_start).isoformat() if requested_start else None,
             lr.as_date(temporary_until).isoformat() if temporary_until else None,
             effect_notes, approvers[0] if approvers else None, due.isoformat()))
        fw_id = int(cur.lastrowid)
        access.audit(conn, actor, 'flexible_working_requested', me,
                     'staff_flexible_working_requests', fw_id)
        for person in approvers:
            lr.mail(person, f"Flexible working request from {access.display_name(me, conn)}",
                    f"{access.display_name(me, conn)} has made a statutory flexible working "
                    f"request. You must consult them before any refusal and decide by "
                    f"{due.isoformat()}. See Staff HR > Leave > Flexible Working.", actor)
        return fw_id


def _require_decider(actor: Any, row: dict, conn) -> None:
    if not access.can_approve_for(actor, row['user_id'], conn):
        raise PermissionError("Only someone who approves for this person can decide the request")


def schedule_meeting(actor: Any, fw_id: int, meeting_date: str) -> dict:
    with lr.write() as conn:
        row = _row(conn, fw_id)
        _require_decider(actor, row, conn)
        if row['status'] not in ('submitted', 'meeting_scheduled'):
            raise ValueError("The request is not awaiting a decision")
        day = lr.as_date(meeting_date)
        conn.execute("UPDATE staff_flexible_working_requests SET meeting_date = ?, status = "
                     "'meeting_scheduled', updated_at = ? WHERE fw_id = ?",
                     (day.isoformat(), lr.now(), fw_id))
        access.audit(conn, actor, 'flexible_working_meeting', row['user_id'],
                     'staff_flexible_working_requests', fw_id, {'date': day.isoformat()})
        lr.mail(row['user_id'], "Flexible working request: meeting",
                f"A meeting to discuss your flexible working request is arranged for "
                f"{day.isoformat()}. You may bring a colleague or trade union representative.",
                actor)
        return _shape(conn, _row(conn, fw_id))


def record_consultation(actor: Any, fw_id: int, notes: str) -> dict:
    """Record the consultation (meeting notes) — needed before a refusal."""
    if not (notes or '').strip():
        raise ValueError("Record what was discussed")
    with lr.write() as conn:
        row = _row(conn, fw_id)
        _require_decider(actor, row, conn)
        conn.execute("UPDATE staff_flexible_working_requests SET meeting_notes = ?, "
                     "consulted = 1, meeting_date = COALESCE(meeting_date, ?), updated_at = ? "
                     "WHERE fw_id = ?", (notes.strip(), lr.today().isoformat(), lr.now(), fw_id))
        access.audit(conn, actor, 'flexible_working_consulted', row['user_id'],
                     'staff_flexible_working_requests', fw_id)
        return _shape(conn, _row(conn, fw_id))


def extend(actor: Any, fw_id: int, new_deadline: str, agreed_note: str) -> dict:
    """Both sides agree a later decision date."""
    if not (agreed_note or '').strip():
        raise ValueError("Record that the person agreed the extension")
    with lr.write() as conn:
        row = _row(conn, fw_id)
        _require_decider(actor, row, conn)
        day = lr.as_date(new_deadline)
        if day <= _deadline(row):
            raise ValueError("An extension must be later than the current deadline")
        conn.execute("UPDATE staff_flexible_working_requests SET extended_to = ?, decision_notes "
                     "= TRIM(COALESCE(decision_notes, '') || ' ' || ?), updated_at = ? "
                     "WHERE fw_id = ?",
                     (day.isoformat(), f"Extension agreed: {agreed_note.strip()}", lr.now(), fw_id))
        access.audit(conn, actor, 'flexible_working_extended', row['user_id'],
                     'staff_flexible_working_requests', fw_id, {'to': day.isoformat()})
        return _shape(conn, _row(conn, fw_id))


def _vary(conn, actor: Any, row: dict, variation: str) -> None:
    conn.execute("UPDATE staff_flexible_working_requests SET contract_variation = ?, "
                 "varied_at = ? WHERE fw_id = ?", (variation, lr.now(), row['fw_id']))
    if row['requested_days'] or row['requested_hours']:
        days = [int(d) for d in (row['requested_days'] or '').split(',') if d.strip().isdigit()]
        current = lr.pattern_of(row['user_id'], conn)
        fte = None
        if row['requested_hours']:
            fte = min(1.0, float(row['requested_hours']) / float(lr.setting('full_time_hours',
                                                                            conn)))
        lr.set_pattern(actor, row['user_id'], days or current['work_days'],
                       hours_per_week=row['requested_hours'], fte=fte,
                       effective_from=row['requested_start'], source='flexible_working',
                       conn=conn)


def decide(actor: Any, fw_id: int, outcome: str, *, notes: Optional[str] = None,
           refusal_reason: Optional[str] = None, trial_end: Optional[str] = None,
           contract_variation: Optional[str] = None) -> dict:
    """Approve (outright or as a trial) or refuse."""
    if outcome not in OUTCOMES:
        raise ValueError(f"Outcome must be one of {', '.join(OUTCOMES)}")
    with lr.write() as conn:
        row = _row(conn, fw_id)
        _require_decider(actor, row, conn)
        if row['status'] not in ('submitted', 'meeting_scheduled'):
            raise ValueError("The request is not awaiting a decision")
        if outcome == 'rejected':
            if refusal_reason not in REFUSAL_REASONS:
                raise ValueError("A refusal must give one of the statutory business reasons")
            if not row['consulted']:
                raise ValueError("Consult the person (record the meeting) before refusing")
            if not (notes or '').strip():
                raise ValueError("Explain why the reason applies")
        if outcome == 'approved_trial' and not trial_end:
            raise ValueError("Give the trial end date")
        conn.execute("UPDATE staff_flexible_working_requests SET status = ?, decision_by = ?, "
                     "decided_at = ?, decision_notes = TRIM(COALESCE(decision_notes, '') || ' ' "
                     "|| ?), rejection_reason = ?, trial_end = ?, updated_at = ? WHERE fw_id = ?",
                     (outcome, access.username_of(actor), lr.now(), notes or '',
                      refusal_reason if outcome == 'rejected' else None,
                      lr.as_date(trial_end).isoformat() if trial_end else None, lr.now(), fw_id))
        if outcome != 'rejected':
            _vary(conn, actor, row, contract_variation or
                  f"Working pattern varied to: {row['requested_pattern']}"
                  + (f" from {row['requested_start']}" if row['requested_start'] else '')
                  + (f" until {row['temporary_until']}" if row['temporary_until'] else '')
                  + (f" (trial to {trial_end})" if outcome == 'approved_trial' else ''))
        access.audit(conn, actor, 'flexible_working_decided', row['user_id'],
                     'staff_flexible_working_requests', fw_id, {'outcome': outcome})
        text = {'approved': 'approved', 'approved_trial': 'approved for a trial period',
                'rejected': f"refused ({refusal_reason})"}[outcome]
        lr.mail(row['user_id'], "Your flexible working request",
                f"Your flexible working request has been {text}."
                + (" You may appeal within 14 days in Staff HR > Leave > Flexible Working."
                   if outcome == 'rejected' else ''), actor)
        return _shape(conn, _row(conn, fw_id))


def withdraw(actor: Any, fw_id: int) -> bool:
    with lr.write() as conn:
        row = _row(conn, fw_id)
        if access.username_of(actor) != row['user_id']:
            raise PermissionError("Only the person who asked can withdraw the request")
        if row['status'] not in LIVE:
            raise ValueError("The request has already been decided")
        conn.execute("UPDATE staff_flexible_working_requests SET status = 'withdrawn', "
                     "updated_at = ? WHERE fw_id = ?", (lr.now(), fw_id))
        access.audit(conn, actor, 'flexible_working_withdrawn', row['user_id'],
                     'staff_flexible_working_requests', fw_id)
        return True


def appeal(actor: Any, fw_id: int, grounds: str) -> dict:
    if not (grounds or '').strip():
        raise ValueError("Give the grounds for the appeal")
    with lr.write() as conn:
        row = _row(conn, fw_id)
        if access.username_of(actor) != row['user_id']:
            raise PermissionError("Only the person who asked can appeal")
        if row['status'] != 'rejected':
            raise ValueError("Only a refused request can be appealed")
        conn.execute("UPDATE staff_flexible_working_requests SET status = 'appealed', "
                     "appeal_grounds = ?, appealed_at = ?, updated_at = ? WHERE fw_id = ?",
                     (grounds.strip(), lr.now(), lr.now(), fw_id))
        access.audit(conn, actor, 'flexible_working_appealed', row['user_id'],
                     'staff_flexible_working_requests', fw_id)
        for person in set(lr.hr_people(conn)) | set(access.management_chain(row['user_id'],
                                                                           conn)[1:2]):
            lr.mail(person, "Flexible working appeal",
                    f"{access.display_name(row['user_id'], conn)} has appealed the refusal of "
                    f"their flexible working request; it must be decided by "
                    f"{_deadline(row).isoformat()}.", actor)
        return _shape(conn, _row(conn, fw_id))


def decide_appeal(actor: Any, fw_id: int, upheld: bool, notes: str,
                  contract_variation: Optional[str] = None) -> dict:
    """Someone other than the original decision-maker decides the appeal."""
    if not (notes or '').strip():
        raise ValueError("Record the reasons for the appeal decision")
    with lr.write() as conn:
        row = _row(conn, fw_id)
        if row['status'] != 'appealed':
            raise ValueError("There is no appeal to decide")
        _require_decider(actor, row, conn)
        if access.username_of(actor) == row['decision_by']:
            raise PermissionError("The appeal must be heard by someone other than the person "
                                  "who refused the request")
        conn.execute("UPDATE staff_flexible_working_requests SET status = ?, appeal_decided_by "
                     "= ?, appeal_decided_at = ?, appeal_notes = ?, updated_at = ? WHERE fw_id = ?",
                     ('appeal_upheld' if upheld else 'appeal_dismissed',
                      access.username_of(actor), lr.now(), notes.strip(), lr.now(), fw_id))
        if upheld:
            _vary(conn, actor, row, contract_variation or
                  f"Working pattern varied on appeal to: {row['requested_pattern']}")
        access.audit(conn, actor, 'flexible_working_appeal_decided', row['user_id'],
                     'staff_flexible_working_requests', fw_id, {'upheld': upheld})
        lr.mail(row['user_id'], "Your flexible working appeal",
                f"Your appeal has been {'upheld' if upheld else 'dismissed'}.", actor)
        return _shape(conn, _row(conn, fw_id))


def requests(actor: Any, username: Optional[str] = None, to_decide: bool = False) -> list:
    """One person's requests, everyone's ``actor`` sees, or (``to_decide``)
    the live requests ``actor`` may decide."""
    with get_connection() as conn:
        lr.ensure(conn)
        sql, params = "SELECT * FROM staff_flexible_working_requests WHERE 1 = 1", []
        if username:
            key = access.staff_key(username, conn) or username
            access.require_view_person(actor, key, conn, "this person's requests")
            sql += " AND user_id = ?"
            params.append(key)
        if to_decide:
            sql += f" AND status IN ({', '.join('?' * len(LIVE))})"
            params.extend(LIVE)
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY submitted_at DESC", params)]
        if to_decide:
            rows = [r for r in rows if access.can_approve_for(actor, r['user_id'], conn)]
        elif not username:
            rows = access.filter_people(rows, actor, conn=conn)
        return [_shape(conn, r) for r in rows]


def request(actor: Any, fw_id: int) -> dict:
    with get_connection() as conn:
        lr.ensure(conn)
        row = _row(conn, fw_id)
        access.require_view_person(actor, row['user_id'], conn, "this request")
        return _shape(conn, row)


def run_daily(on: Optional[date] = None) -> dict:
    """Scheduler job: remind the decider two weeks before the deadline and
    when it has passed; tell people their trial is ending."""
    on = on or lr.today()
    sent = 0
    with lr.write() as conn:
        for row in [dict(r) for r in conn.execute(
                "SELECT * FROM staff_flexible_working_requests WHERE status IN "
                f"({', '.join('?' * len(LIVE))})", LIVE)]:
            due = _deadline(row)
            if due - on > timedelta(days=14):
                continue
            stage = 'overdue' if due < on else 'soon'
            people = access.approvers_for(row['user_id'], conn) if row['status'] != 'appealed' \
                else lr.hr_people(conn)
            for person in people:
                if lr.remind_once(conn, f"fw:{row['fw_id']}:{stage}:{due}", person):
                    lr.mail(person, "Flexible working decision "
                            + ("overdue" if stage == 'overdue' else "due soon"),
                            f"The flexible working request from "
                            f"{access.display_name(row['user_id'], conn)} must be decided by "
                            f"{due.isoformat()}" + (" — the deadline has passed." if
                                                    stage == 'overdue' else "."))
                    sent += 1
        for row in [dict(r) for r in conn.execute(
                "SELECT * FROM staff_flexible_working_requests WHERE status = 'approved_trial' "
                "AND trial_end BETWEEN ? AND ?",
                (on.isoformat(), (on + timedelta(days=14)).isoformat()))]:
            for person in {row['user_id'], *access.approvers_for(row['user_id'], conn)}:
                if lr.remind_once(conn, f"fw_trial:{row['fw_id']}", person):
                    lr.mail(person, "Flexible working trial ending",
                            f"The flexible working trial for "
                            f"{access.display_name(row['user_id'], conn)} ends on "
                            f"{row['trial_end']}; please review it.")
                    sent += 1
    return {'reminders': sent}


__all__ = [
    'CHANGE_TYPES', 'REFUSAL_REASONS', 'LIVE', 'OUTCOMES', 'submit', 'schedule_meeting',
    'record_consultation', 'extend', 'decide', 'withdraw', 'appeal', 'decide_appeal',
    'requests', 'request', 'run_daily',
]
