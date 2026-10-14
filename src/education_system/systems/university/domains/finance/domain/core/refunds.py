"""Refund records in ``unified_refunds`` — list, filter, approve/reject, export.

Non-interactive counterpart to the menu-driven ``account_management.process_refund``
(which raises a refund request). The Finance GUI Refunds tab, the transaction
manager's refund dialog and the Finance CLI Refunds menu all call these.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)

logger = logging.getLogger(__name__)

REFUND_STATUSES = ('pending', 'approved', 'rejected', 'processed', 'completed', 'cancelled')

#: Statuses at which money actually leaves — these post to the ledger.
CASH_OUT_STATUSES = ('processed', 'completed')

#: Column order shared by the table view and the CSV export.
EXPORT_COLUMNS = ('ID', 'Reference', 'Source Type', 'Department', 'Amount', 'Method',
                  'Date', 'Reference ID', 'Status', 'Processed By', 'Notes')

_ROW_KEYS = ('refund_id', 'refund_reference', 'source_type', 'department', 'amount',
             'refund_method', 'refund_date', 'reference_id', 'status', 'processed_by', 'notes')

_SEARCH_FIELDS = ('refund_reference', 'department', 'source_type', 'reference_id',
                  'processed_by', 'notes', 'student_id')

_BASE_SELECT = '''
SELECT refund_id, refund_reference, source_type,
       COALESCE(department, source_type) AS department,
       amount, refund_method, refund_date, reference_id,
       COALESCE(status, 'pending') AS status,
       COALESCE(processed_by, approved_by, requested_by) AS processed_by,
       notes, student_id, refund_type, reason, requested_by, approved_by,
       request_date, approval_date, currency
FROM unified_refunds
'''


def refunds_table_exists():
    """Whether ``unified_refunds`` has been created in this database."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='unified_refunds'"
        ).fetchone() is not None
    finally:
        conn.close()


def list_refunds(search=None, status=None, limit=None):
    """Refunds newest first, filtered by a free-text search and/or a status.

    ``status`` of ``None`` or ``'all'`` returns every status. The search is a
    case-insensitive substring match across reference, department, source,
    reference id, processed-by, notes and student id.
    """
    if not refunds_table_exists():
        return []
    where, params = [], []
    if search:
        term = f'%{search.lower()}%'
        where.append('(' + ' OR '.join(
            f"LOWER(COALESCE({field}, '')) LIKE ?" for field in _SEARCH_FIELDS) + ')')
        params.extend([term] * len(_SEARCH_FIELDS))
    if status and status != 'all':
        where.append("COALESCE(status, 'pending') = ?")
        params.append(status)
    sql = _BASE_SELECT
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY refund_id DESC'
    if limit:
        sql += ' LIMIT ?'
        params.append(int(limit))
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_refund(refund_id):
    """One refund as a dict, or ``None``."""
    conn = get_connection()
    try:
        row = conn.execute(_BASE_SELECT + ' WHERE refund_id = ?', (refund_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def refund_totals(rows):
    """``(count, total_amount)`` for a list of refund dicts."""
    return len(rows), round(sum(float(r.get('amount') or 0) for r in rows), 2)


def export_row(refund):
    """A refund dict as the tuple of display values in :data:`EXPORT_COLUMNS` order."""
    values = []
    for key in _ROW_KEYS:
        value = refund.get(key)
        if key == 'amount':
            value = f"£{float(value or 0):.2f}"
        values.append('' if value is None else value)
    return tuple(values)


def export_refunds_csv(rows, path):
    """Write refund dicts to ``path`` as CSV with :data:`EXPORT_COLUMNS`; returns ``path``."""
    with open(path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(EXPORT_COLUMNS)
        for refund in rows:
            writer.writerow(export_row(refund))
    return path


def _notify_ledger(refund_id, username):
    try:
        from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
        notify_ledger('refund', refund_id, posted_by=username)
    except Exception:
        logger.exception("ledger hook failed for refund %s", refund_id)


def set_refund_status(refund_ids, new_status, username='system', only_pending=False):
    """Move one or more refunds to ``new_status``.

    ``approved`` stamps the approver and date; ``processed``/``completed``
    stamp the processor and refund date and post to the ledger; other
    statuses change the status alone. With ``only_pending`` (the Refunds
    tab's approve/reject buttons) rows not currently pending are skipped.

    Returns ``{'updated': [ids], 'skipped': [(id, current_status)]}``.
    Raises ValueError for an unknown status.
    """
    if new_status not in REFUND_STATUSES:
        raise ValueError(
            f"Invalid refund status '{new_status}'. Expected one of: {', '.join(REFUND_STATUSES)}")
    if isinstance(refund_ids, (int, str)):
        refund_ids = [refund_ids]
    username = username or 'system'
    today = datetime.now().strftime('%Y-%m-%d')
    updated, skipped = [], []

    with transaction() as conn:
        for refund_id in refund_ids:
            row = conn.execute(
                "SELECT COALESCE(status, 'pending') AS status FROM unified_refunds "
                "WHERE refund_id = ?", (refund_id,),
            ).fetchone()
            if row is None:
                skipped.append((refund_id, 'missing'))
                continue
            if only_pending and row['status'] != 'pending':
                skipped.append((refund_id, row['status']))
                continue
            if new_status == 'approved':
                conn.execute('''
                UPDATE unified_refunds
                SET status = ?, approved_by = ?, approval_date = ?
                WHERE refund_id = ?
                ''', (new_status, username, today, refund_id))
            elif new_status in CASH_OUT_STATUSES:
                conn.execute('''
                UPDATE unified_refunds
                SET status = ?, processed_by = ?, refund_date = ?
                WHERE refund_id = ?
                ''', (new_status, username, today, refund_id))
            else:
                conn.execute('UPDATE unified_refunds SET status = ? WHERE refund_id = ?',
                             (new_status, refund_id))
            updated.append(refund_id)

    if new_status in CASH_OUT_STATUSES:
        for refund_id in updated:
            _notify_ledger(refund_id, username)
    return {'updated': updated, 'skipped': skipped}


# --------------------------------------------------------------------------- #
# Student notification (lifted from the transaction manager's refund dialog)
# --------------------------------------------------------------------------- #
REFUND_EMAIL_TEMPLATES = {
    'created': 'finance/refund_created',
    'status_update': 'finance/refund_status_update',
}


def _lookup_student(student_id):
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT first_name, last_name, email_address FROM students WHERE student_id = ?',
            (student_id,),
        ).fetchone()
    finally:
        conn.close()
    if row:
        return f"{row[0] or ''} {row[1] or ''}".strip(), row[2]
    return None, None


def send_refund_email(*, kind, student_id, refund_id, amount, refund_type='',
                      refund_method='', status='pending', reason='', request_date=''):
    """Email the student about a refund. ``kind`` is ``created`` or ``status_update``.

    Templates and their ``enabled`` flag live in
    ``templates/email/finance/refund_{kind}.json``. Returns True when sent;
    never raises.
    """
    try:
        from education_system.systems.university.infrastructure.email import send_email
        from education_system.systems.university.infrastructure.email.template_utils import (
            load_template,
            render_template,
        )
        template_name = REFUND_EMAIL_TEMPLATES.get(kind)
        if not template_name:
            return False
        template_data = load_template(template_name)
        if not template_data or not template_data.get('enabled', True):
            return False
        student_name, student_email = _lookup_student(student_id)
        if not student_email:
            return False
        fmt = {
            'student_name': student_name or 'Student',
            'refund_id': refund_id,
            'amount': f"{float(amount or 0):,.2f}",
            'refund_type': refund_type or '',
            'refund_method': refund_method or '',
            'status': status or '',
            'status_label': (status or '').capitalize(),
            'reason': reason or '',
            'request_date': request_date or datetime.now().strftime('%Y-%m-%d'),
        }
        subject, body = render_template(template_name, fmt)
        if not subject or not body:
            return False
        cc = None
        if template_data.get('send_copy_to_finance') and template_data.get('finance_email'):
            cc = [template_data['finance_email']]
        return bool(send_email(recipient_email=student_email, subject=subject, body=body, cc=cc))
    except Exception:
        logger.warning("Refund email for %s failed", refund_id, exc_info=True)
        return False
