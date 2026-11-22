"""The daily Staff HR reminders: e-mail plus an in-app notice to the person,
their line manager and HR, each reminder once (``staff_hr_reminder_log``).

* contracts ending in 90 and in 30 days;
* probation reviews due within 30 days, and once more when overdue;
* onboarding tasks past their due date;
* right-to-work follow-up dates within 60 and 14 days (time-limited
  permission, visas) and DBS re-check dates within 30 days
  (``staff_hr_pre_employment_checks``; before the hire, HR only);
* staff documents expiring within 30 days
  (``EmployeeManager.get_expiring_documents``).

Certifications are not here: ``services/bus/jobs/certification_expiry``
already sweeps them (run by the same daily job).

A key names the thing *and* its date (``contract_end:12:2027-03-31:30``),
so a contract that is extended earns fresh reminders. The notices for one
person in one run are gathered into one message per kind. The log and the
in-app notices are written together; the e-mails follow the commit.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from typing import Any, Iterable, Optional

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.infrastructure.database import (
    staff_hr_ddl,
)
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

CONTRACT_THRESHOLDS = (30, 90)
PROBATION_DAYS = 30
RTW_THRESHOLDS = (14, 60)
DBS_DAYS = 30
DOCUMENT_DAYS = 30

TITLES = {
    'contract_end': "Contracts ending",
    'probation': "Probation reviews due",
    'onboarding': "Onboarding tasks overdue",
    'right_to_work': "Right-to-work follow-ups due",
    'dbs': "DBS re-checks due",
    'document': "Staff documents expiring",
}

__all__ = ['run', 'collect', 'hr_recipients', 'recipients_for', 'TITLES']


def _today(now) -> date:
    if now is None:
        return date.today()
    return now if isinstance(now, date) and not hasattr(now, 'hour') else now.date()


def _days(day: Optional[str], today: date) -> Optional[int]:
    try:
        return (date.fromisoformat(str(day)[:10]) - today).days
    except (TypeError, ValueError):
        return None


def _threshold(days_left: int, thresholds: Iterable[int]) -> Optional[int]:
    for limit in sorted(thresholds):
        if days_left <= limit:
            return limit
    return None


def hr_recipients(conn) -> list:
    """HR administrators and officers; the administrators when none is named."""
    try:
        rows = conn.execute("SELECT DISTINCT username FROM staff_hr_roles "
                            "WHERE role IN ('hr_admin', 'hr_officer') ORDER BY username").fetchall()
    except Exception:
        rows = []
    people = [r[0] for r in rows]
    if not people:
        people = [r[0] for r in conn.execute(
            "SELECT username FROM users WHERE LOWER(role) IN ('admin', 'administrator') "
            "AND COALESCE(service_account, 0) = 0 ORDER BY id").fetchall()]
    return people


def recipients_for(conn, username: Optional[str], hr: list, *, person: bool = True) -> list:
    """The person, their line manager and HR (no one twice)."""
    out: list = []
    if username and person:
        out.append(username)
    if username:
        chain = access.management_chain(username, conn)
        if chain:
            out.append(chain[0])
    out.extend(hr)
    return list(dict.fromkeys(p for p in out if p))


def _name(conn, username: Optional[str]) -> str:
    if not username:
        return 'an applicant'
    return f"{access.display_name(username, conn)} ({username})"


# ── what is due ─────────────────────────────────────────────────────────


def _contracts(conn, today: date) -> list:
    from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.contract_manager import (
        ContractManager,
    )
    items = []
    for c in ContractManager.get_expiring_contracts(days_ahead=max(CONTRACT_THRESHOLDS)):
        left = _days(c.get('end_date'), today)
        limit = _threshold(left, CONTRACT_THRESHOLDS) if left is not None else None
        if limit is None:
            continue
        items.append({'kind': 'contract_end', 'subject': c.get('user_id'),
                      'key': f"contract_end:{c['contract_id']}:{c['end_date']}:{limit}",
                      'line': f"{_name(conn, c.get('user_id'))}: "
                              f"{c.get('job_title') or 'contract'} ends on {c['end_date']} "
                              f"({left} days)"})
    return items


def _probation(conn, today: date) -> list:
    rows = conn.execute(
        "SELECT contract_id, user_id, probation_end_date, job_title FROM staff_contracts c "
        "WHERE status = 'active' AND probation_end_date IS NOT NULL "
        "AND probation_end_date != '' AND probation_end_date <= ? "
        # decided already: a final review passed or failed
        "AND NOT EXISTS (SELECT 1 FROM probation_reviews r WHERE r.contract_id = c.contract_id "
        "AND r.review_type = 'final' AND r.outcome IN ('pass', 'fail'))",
        ((today + timedelta(days=PROBATION_DAYS)).isoformat(),)).fetchall()
    items = []
    for r in rows:
        left = _days(r['probation_end_date'], today)
        if left is None:
            continue
        stage = 'overdue' if left < 0 else 'due'
        when = (f"was due on {r['probation_end_date']}" if left < 0
                else f"is due by {r['probation_end_date']} ({left} days)")
        items.append({'kind': 'probation', 'subject': r['user_id'],
                      'key': f"probation:{r['contract_id']}:{r['probation_end_date']}:{stage}",
                      'line': f"{_name(conn, r['user_id'])}: probation review {when}"})
    return items


def _onboarding(conn, today: date) -> list:
    from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.onboarding_manager import (
        OnboardingManager,
    )
    items = []
    for t in OnboardingManager.get_overdue_tasks():
        who = access.staff_key(t.get('user_id'), conn) or t.get('user_id')
        items.append({'kind': 'onboarding', 'subject': who,
                      'key': f"onboarding:{t['progress_id']}:{t.get('due_date')}",
                      'line': f"{_name(conn, who)}: '{t.get('title') or 'task'}' was due on "
                              f"{t.get('due_date')}"
                              + (f" (assigned to {t['assigned_to']})"
                                 if t.get('assigned_to') else '')})
    return items


def _checks(conn, today: date) -> list:
    items = []
    rtw_until = (today + timedelta(days=max(RTW_THRESHOLDS))).isoformat()
    for r in conn.execute(
            "SELECT c.check_id, c.staff_username, c.follow_up_date, c.document_type, "
            "a.applicant_name FROM staff_hr_pre_employment_checks c "
            "LEFT JOIN staff_recruitment_applications a ON a.application_id = c.application_id "
            "WHERE c.check_type = 'right_to_work' AND c.status = 'cleared' "
            "AND c.follow_up_date IS NOT NULL AND c.follow_up_date != '' "
            "AND c.follow_up_date <= ?", (rtw_until,)).fetchall():
        left = _days(r['follow_up_date'], today)
        if left is None:
            continue
        limit = _threshold(left, RTW_THRESHOLDS)
        who = _name(conn, r['staff_username']) if r['staff_username'] \
            else (r['applicant_name'] or 'an applicant')
        items.append({'kind': 'right_to_work', 'subject': r['staff_username'],
                      'key': f"rtw:{r['check_id']}:{r['follow_up_date']}:{limit}",
                      'line': f"{who}: right-to-work follow-up "
                              + (f"overdue since {r['follow_up_date']}" if left < 0
                                 else f"due {r['follow_up_date']} ({left} days)")})
    for r in conn.execute(
            "SELECT c.check_id, c.staff_username, c.recheck_date, c.dbs_level, "
            "a.applicant_name FROM staff_hr_pre_employment_checks c "
            "LEFT JOIN staff_recruitment_applications a ON a.application_id = c.application_id "
            "WHERE c.check_type = 'dbs' AND c.status = 'cleared' "
            "AND c.recheck_date IS NOT NULL AND c.recheck_date != '' AND c.recheck_date <= ?",
            ((today + timedelta(days=DBS_DAYS)).isoformat(),)).fetchall():
        left = _days(r['recheck_date'], today)
        if left is None:
            continue
        who = _name(conn, r['staff_username']) if r['staff_username'] \
            else (r['applicant_name'] or 'an applicant')
        items.append({'kind': 'dbs', 'subject': r['staff_username'],
                      'key': f"dbs:{r['check_id']}:{r['recheck_date']}",
                      'line': f"{who}: {(r['dbs_level'] or '').replace('_', ' ')} DBS re-check "
                              + (f"overdue since {r['recheck_date']}" if left < 0
                                 else f"due {r['recheck_date']} ({left} days)")})
    return items


def _documents(conn, today: date) -> list:
    from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.employee_manager import (
        EmployeeManager,
    )
    items = []
    for d in EmployeeManager.get_expiring_documents(DOCUMENT_DAYS):
        doc_id = d.get('document_id') or d.get('id')
        owner = access.staff_key(d.get('owner_id'), conn) or d.get('owner_id')
        left = _days(d.get('expiry_date'), today)
        items.append({'kind': 'document', 'subject': owner,
                      'key': f"document:{doc_id}:{d.get('expiry_date')}",
                      'line': f"{_name(conn, owner)}: "
                              f"{d.get('document_name') or d.get('document_type') or 'document'} "
                              f"expires on {d.get('expiry_date')}"
                              + (f" ({left} days)" if left is not None else '')})
    return items


SOURCES = (
    ('contract_end', _contracts),
    ('probation', _probation),
    ('onboarding', _onboarding),
    ('checks', _checks),
    ('document', _documents),
)


def collect(now=None, conn=None) -> list:
    """Every reminder due today (sent or not)."""
    today = _today(now)
    own = conn is None
    c = conn or get_connection()
    try:
        staff_hr_ddl.apply_to_connection(c)
        items: list = []
        for name, source in SOURCES:
            try:
                items.extend(source(c, today))
            except Exception:
                logger.exception("Staff HR reminders: %s not collected", name)
        return items
    finally:
        if own:
            c.close()


# ── sending ─────────────────────────────────────────────────────────────


def _send_mail(address: str, subject: str, body: str, to_ref: str) -> bool:
    try:
        from education_system.systems.university.infrastructure.email.email_manager import (
            send_email,
        )
        return send_email(address, subject, body, to_ref=to_ref, in_app_copy=False,
                          category='staff_hr_reminder') in ('sent to outbox', 'already sent')
    except Exception:
        logger.warning("Staff HR reminder e-mail %s not sent", to_ref, exc_info=True)
        return False


def run(now=None) -> dict:
    """Send every reminder not yet sent. Returns counts per kind plus
    ``recipients`` / ``emails``."""
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    today = _today(now)
    conn = get_connection()
    outbox: list = []
    counts: dict = {kind: 0 for kind in TITLES}
    try:
        items = collect(today, conn)
        hr = hr_recipients(conn)
        sent = {(r[0], r[1]) for r in conn.execute(
            "SELECT reminder_key, recipient FROM staff_hr_reminder_log").fetchall()}
        # recipient -> kind -> [item]
        pending: dict = {}
        for item in items:
            person = bool(item['subject']) and bool(conn.execute(
                "SELECT 1 FROM users WHERE username = ?", (item['subject'],)).fetchone())
            for who in recipients_for(conn, item['subject'], hr, person=person):
                if (item['key'], who) in sent:
                    continue
                pending.setdefault(who, {}).setdefault(item['kind'], []).append(item)
        for who, kinds in pending.items():
            for kind, group in kinds.items():
                subject = f"Staff HR reminder: {TITLES[kind]}"
                body = (f"{TITLES[kind]}:\n\n"
                        + "\n".join(f"- {i['line']}" for i in group)
                        + "\n\nOpen Staff HR to act on these.")
                deliver_inbox_message_on(conn, who, subject, body)
                for i in group:
                    conn.execute("INSERT OR IGNORE INTO staff_hr_reminder_log (reminder_key, "
                                 "recipient, kind, subject_username) VALUES (?, ?, ?, ?)",
                                 (i['key'], who, kind, i['subject']))
                    sent.add((i['key'], who))
                    counts[kind] += 1
                address = access.email_of(who, conn)
                if address:
                    digest = hashlib.sha1("|".join(sorted(i['key'] for i in group)).encode(),
                                          usedforsecurity=False).hexdigest()[:16]
                    ref = f"staff_hr:reminder:{who}:{kind}:{digest}"
                    outbox.append((address, subject, body, ref))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    emails = sum(1 for args in outbox if _send_mail(*args))
    return {**counts, 'recipients': len(pending), 'emails': emails}
