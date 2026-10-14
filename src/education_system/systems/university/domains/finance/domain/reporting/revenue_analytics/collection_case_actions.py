"""Actions on a single collection case: notices, resolution, arrangements.

Non-interactive — every value arrives as an argument and the result comes back
as data. The Finance GUI Collections tab and the Finance CLI Collections menu
both call these, so the two interfaces cannot drift apart.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.domains.finance.domain.core.security_automation import (
    log_audit_action,
)
from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics.collections import (
    _current_username,
    get_case,
    set_case_status,
)

logger = logging.getLogger(__name__)

#: The notice types the GUI offers, in escalation order.
NOTICE_TYPES = ('first_notice', 'second_notice', 'final_notice', 'legal_notice', 'payment_demand')

#: Payment schedules an arrangement can describe (see :func:`describe_schedule`).
SCHEDULE_KINDS = ('single', 'weekly', 'monthly', 'custom')

DEFAULT_NOTICE_SUBJECT = "Payment Overdue Notice"

_DEFAULT_NOTICE_MESSAGE = (
    "Dear Student,\n\n"
    "This is a collection notice regarding your outstanding balance of £{total_debt:.2f}.\n\n"
    "We have attempted to contact you regarding this matter. Please make arrangements "
    "to settle this debt as soon as possible to avoid further collection action.\n\n"
    "You can contact our finance department to discuss payment options or payment plans.\n\n"
    "If you have already made payment, please disregard this notice and contact us "
    "with proof of payment.\n\n"
    "Best regards,\nFinance Department"
)


def default_notice_message(total_debt):
    """The notice body the GUI pre-fills for a case with ``total_debt``."""
    return _DEFAULT_NOTICE_MESSAGE.format(total_debt=float(total_debt or 0))


def student_contact(student_id):
    """Return ``(full_name, email)`` for a student, or ``(None, None)``."""
    try:
        conn = get_connection()
        try:
            row = conn.execute(
                'SELECT first_name, last_name, email_address FROM students WHERE student_id = ?',
                (student_id,),
            ).fetchone()
        finally:
            conn.close()
    except Exception:
        logger.debug("student lookup failed for %s", student_id, exc_info=True)
        return None, None
    if not row:
        return None, None
    return f"{row['first_name'] or ''} {row['last_name'] or ''}".strip(), row['email_address']


def _send_email(recipient, subject, body):
    """Send through the university email service; ``False`` when it refuses."""
    from education_system.systems.university.infrastructure.email import send_email
    try:
        return send_email(recipient_email=recipient, subject=subject, body=body)
    except Exception:
        logger.warning("Collection email to %s failed", recipient, exc_info=True)
        return False


def build_notice_html(case_id, total_debt, message):
    """Wrap a plain-text notice in the HTML layout the GUI sends."""
    return (
        '<html><body>'
        '<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">'
        '<h2 style="color: #d9534f;">Collection Notice</h2>'
        f'<p><strong>Case ID:</strong> {case_id}</p>'
        f'<p><strong>Outstanding Amount:</strong> £{float(total_debt or 0):.2f}</p>'
        '<hr>'
        f'<div style="white-space: pre-wrap;">{message}</div>'
        '<hr>'
        '<p style="font-size: 12px; color: #666;">'
        'This is an automated notice from the University Finance Department.</p>'
        '</div></body></html>'
    )


def _notices_table_exists(conn):
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='collection_notices'"
    ).fetchone() is not None


def send_case_notice(case_id, notice_type, subject=None, message=None, sent_by=None):
    """Email a collection notice for ``case_id`` and record it on the case.

    Returns a summary dict. Raises ValueError for a missing case, an unknown
    notice type or a student without an email address, and RuntimeError when
    the email service refuses the message.
    """
    if notice_type not in NOTICE_TYPES:
        raise ValueError(
            f"Invalid notice type '{notice_type}'. Expected one of: {', '.join(NOTICE_TYPES)}")
    case = get_case(case_id)
    if case is None:
        raise ValueError(f"Collection case {case_id} not found")
    email = case.get('email_address')
    if not email:
        raise ValueError(f"No email address on file for student {case['student_id']}")

    subject = (subject or DEFAULT_NOTICE_SUBJECT).strip()
    message = (message or default_notice_message(case['total_debt'])).strip()
    if not subject or not message:
        raise ValueError("Subject and message are both required")

    if _send_email(email, subject, build_notice_html(case_id, case['total_debt'], message)) is False:
        raise RuntimeError(f"Email could not be sent to {email}")

    username = _current_username(sent_by)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with transaction() as conn:
        if _notices_table_exists(conn):
            conn.execute('''
            INSERT INTO collection_notices
            (case_id, student_id, notice_type, subject, message, sent_by, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (case_id, case['student_id'], notice_type, subject, message, username, now))
        conn.execute('''
        UPDATE collection_cases
        SET notes = COALESCE(notes, '') || ?, updated_at = ?
        WHERE case_id = ?
        ''', (f'\nNotice sent: {notice_type} on {now}', now, case_id))

    log_audit_action('send_collection_notice', 'collection_cases', str(case_id), {
        'notice_type': notice_type, 'email': email, 'sent_by': username,
    })
    return {'case_id': case_id, 'student_id': case['student_id'],
            'email': email, 'notice_type': notice_type}


def resolution_email_body(student_name, case_id, total_debt, amount_collected):
    """The plain-text email the GUI sends when a case is resolved."""
    remaining = float(total_debt or 0) - float(amount_collected or 0)
    if remaining <= 0:
        status_text = "Your account balance has been fully settled."
    else:
        status_text = (f"Remaining balance: £{remaining:.2f}. "
                       "Please contact the finance department for any queries.")
    return (
        f"Dear {student_name},\n\n"
        f"This is to inform you that collection case #{case_id} has been resolved.\n\n"
        f"Original Debt: £{float(total_debt or 0):.2f}\n"
        f"Amount Collected: £{float(amount_collected or 0):.2f}\n"
        f"{status_text}\n\n"
        "If you have any questions, please contact the Finance Department.\n\n"
        "Best regards,\nFinance Department"
    )


def resolve_case(case_id, amount_collected, notify=True, notes='', updated_by=None):
    """Mark a case resolved with the amount recovered, optionally emailing the student.

    Returns the :func:`set_case_status` summary plus ``emailed`` and
    ``remaining``. Raises ValueError for a missing case or negative amount.
    """
    case = get_case(case_id)
    if case is None:
        raise ValueError(f"Collection case {case_id} not found")
    amount_collected = float(amount_collected)
    result = set_case_status(case_id, 'resolved', notes or 'Resolved',
                             amount_collected, updated_by)

    emailed = False
    email = case.get('email_address')
    if notify and email:
        display_name = (f"{case.get('first_name') or ''} {case.get('last_name') or ''}".strip()
                        or case['student_id'])
        body = resolution_email_body(display_name, case_id, case['total_debt'], amount_collected)
        emailed = _send_email(email, f"Collection Case #{case_id} - Resolved", body) is not False

    result['emailed'] = emailed
    result['remaining'] = float(case['total_debt'] or 0) - amount_collected
    return result


def describe_schedule(kind, amount, start_date='', periods=None, custom=''):
    """Render the schedule text stored on a payment arrangement.

    ``kind`` is one of :data:`SCHEDULE_KINDS`; ``periods`` is the number of
    weekly/monthly payments. Raises ValueError for an invalid combination.
    """
    amount = float(amount)
    if kind == 'single':
        if not start_date:
            raise ValueError("A payment date is required")
        return f"Single payment of £{amount:.2f} due on {start_date}"
    if kind in ('weekly', 'monthly'):
        if not periods or int(periods) < 1:
            raise ValueError("Number of payments must be at least 1")
        if not start_date:
            raise ValueError("A start date is required")
        periods = int(periods)
        unit = 'weeks' if kind == 'weekly' else 'months'
        return (f"£{amount / periods:.2f} {kind} for {periods} {unit} "
                f"starting {start_date}")
    if kind == 'custom':
        if not custom.strip():
            raise ValueError("Custom schedule details are required")
        return custom.strip()
    raise ValueError(f"Unknown schedule kind '{kind}'")


def active_case_for_student(student_id):
    """The student's most recent open case as a dict, or ``None``."""
    conn = get_connection()
    try:
        row = conn.execute('''
        SELECT case_id, total_debt, case_status
        FROM collection_cases
        WHERE student_id = ? AND case_status NOT IN ('resolved', 'closed')
        ORDER BY created_at DESC
        LIMIT 1
        ''', (student_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def record_payment_arrangement(student_id, arrangement_amount, schedule_info,
                               terms='', arranged_by=None, notify=True):
    """Attach a payment arrangement to the student's open collection case.

    Mirrors the interactive ``aid.create_payment_arrangement``: the case moves
    to ``in_progress``, the schedule and terms are appended to its notes, and
    the student is sent a confirmation. Raises ValueError when there is no
    open case or the amount is outside ``(0, total_debt]``.
    """
    case = active_case_for_student(student_id)
    if case is None:
        raise ValueError(f"No active collection case found for student {student_id}")
    arrangement_amount = float(arrangement_amount)
    if arrangement_amount <= 0 or arrangement_amount > float(case['total_debt'] or 0):
        raise ValueError(
            f"Arrangement amount must be between 0 and £{float(case['total_debt'] or 0):.2f}")
    schedule_info = (schedule_info or '').strip()
    if not schedule_info:
        raise ValueError("Schedule details are required")

    username = _current_username(arranged_by)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    arrangement_notes = (f"PAYMENT ARRANGEMENT: {schedule_info}. Terms: {terms}. "
                         f"Arranged by: {username}")
    with transaction() as conn:
        conn.execute('''
        UPDATE collection_cases
        SET case_status = 'in_progress',
            notes = COALESCE(notes, '') || ' | ' || ?,
            updated_at = ?
        WHERE case_id = ?
        ''', (arrangement_notes, now, case['case_id']))

    log_audit_action('create_payment_arrangement', 'collection_cases', str(case['case_id']), {
        'student_id': student_id, 'amount': arrangement_amount,
        'schedule': schedule_info, 'arranged_by': username,
    })

    if notify:
        from education_system.systems.university.domains.finance.domain.core.communications import (
            send_arrangement_confirmation,
        )
        send_arrangement_confirmation(student_id, case['case_id'], schedule_info)

    return {'case_id': case['case_id'], 'student_id': student_id,
            'amount': arrangement_amount, 'schedule_info': schedule_info}


def list_audit_entries(start_date, end_date, table_name=None, limit=1000):
    """Audit-log rows between two dates (inclusive), newest first."""
    sql = '''
    SELECT log_id, user_id, action, table_name, record_id, new_values, timestamp
    FROM audit_log
    WHERE date(timestamp) BETWEEN ? AND ?
    '''
    params = [start_date, end_date]
    if table_name:
        sql += ' AND table_name = ?'
        params.append(table_name)
    sql += ' ORDER BY timestamp DESC LIMIT ?'
    params.append(int(limit))
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
