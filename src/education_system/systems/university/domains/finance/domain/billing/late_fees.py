"""Late fee records — list, apply, waive, and the flat overdue sweep.

Non-interactive counterpart to ``billing.fee_structure.calculate_late_fees``
(which applies each fee type's configured late-fee rule) and ``waive_late_fee``
(which prompts for a student). The Finance GUI Late Fees tab and the Finance
CLI Late Fees menu both call these.
"""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.domains.finance.domain.core.security_automation import (
    log_audit_action,
)

CALCULATION_METHODS = ('fixed', 'percentage', 'daily')

#: Flat rate the GUI's "Calculate Overdue" sweep charges on an overdue fee.
DEFAULT_OVERDUE_RATE = 0.05

_TS_FMT = '%Y-%m-%d %H:%M:%S'


def list_late_fees(limit=500, include_waived=True):
    """Late fees newest first, with the owning student and fee amount."""
    sql = '''
    SELECT lf.late_fee_id, lf.student_fee_id, sf.student_id, sf.amount AS fee_amount,
           lf.late_fee_amount, lf.days_overdue, lf.calculation_method, lf.applied_date,
           lf.waived, lf.waived_by, lf.waived_date, lf.waiver_reason
    FROM late_fees lf
    LEFT JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
    '''
    if not include_waived:
        sql += ' WHERE COALESCE(lf.waived, 0) = 0'
    sql += ' ORDER BY lf.applied_date DESC, lf.late_fee_id DESC LIMIT ?'
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, (int(limit),)).fetchall()]
    finally:
        conn.close()


def get_late_fee(late_fee_id):
    """One late fee as a dict (same columns as :func:`list_late_fees`), or ``None``."""
    conn = get_connection()
    try:
        row = conn.execute('''
        SELECT lf.late_fee_id, lf.student_fee_id, sf.student_id, sf.amount AS fee_amount,
               lf.late_fee_amount, lf.days_overdue, lf.calculation_method, lf.applied_date,
               lf.waived, lf.waived_by, lf.waived_date, lf.waiver_reason
        FROM late_fees lf
        LEFT JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
        WHERE lf.late_fee_id = ?
        ''', (late_fee_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def apply_late_fee(student_fee_id, amount, method='fixed', days_overdue=0):
    """Record a late fee against a student fee and return the new id.

    Raises ValueError for an unknown student fee, a non-positive amount, an
    unknown method, or negative days.
    """
    amount = float(amount)
    if amount <= 0:
        raise ValueError("Late fee amount must be greater than zero")
    if method not in CALCULATION_METHODS:
        raise ValueError(
            f"Invalid calculation method '{method}'. "
            f"Expected one of: {', '.join(CALCULATION_METHODS)}")
    days_overdue = int(days_overdue)
    if days_overdue < 0:
        raise ValueError("Days overdue cannot be negative")

    now = datetime.now()
    with transaction() as conn:
        exists = conn.execute(
            'SELECT 1 FROM student_fees WHERE student_fee_id = ?', (student_fee_id,)
        ).fetchone()
        if not exists:
            raise ValueError(f"Student fee {student_fee_id} not found")
        cursor = conn.execute('''
        INSERT INTO late_fees
        (student_fee_id, late_fee_amount, calculation_method, days_overdue,
         applied_date, waived, created_at)
        VALUES (?, ?, ?, ?, ?, 0, ?)
        ''', (student_fee_id, amount, method, days_overdue,
              now.strftime('%Y-%m-%d'), now.strftime(_TS_FMT)))
        return cursor.lastrowid


def waive_late_fee_by_id(late_fee_id, reason, waived_by='system'):
    """Waive one late fee with a reason; returns the updated row.

    Raises ValueError for a missing fee, an already-waived fee, or no reason.
    """
    reason = (reason or '').strip()
    if not reason:
        raise ValueError("A waiver reason is required")
    fee = get_late_fee(late_fee_id)
    if fee is None:
        raise ValueError(f"Late fee {late_fee_id} not found")
    if fee['waived']:
        raise ValueError(f"Late fee {late_fee_id} is already waived")

    now = datetime.now().strftime(_TS_FMT)
    with transaction() as conn:
        conn.execute('''
        UPDATE late_fees
        SET waived = 1, waiver_reason = ?, waived_date = ?, waived_by = ?
        WHERE late_fee_id = ?
        ''', (reason, now, waived_by or 'system', late_fee_id))

    log_audit_action('waive_late_fee', 'late_fees', str(late_fee_id), {
        'student_id': fee.get('student_id'),
        'amount_waived': float(fee['late_fee_amount'] or 0),
        'reason': reason,
        'waived_by': waived_by or 'system',
    })
    return get_late_fee(late_fee_id)


def list_overdue_fees_without_late_fee():
    """Unpaid, past-due student fees that carry no late fee yet."""
    conn = get_connection()
    try:
        rows = conn.execute('''
        SELECT sf.student_fee_id, sf.student_id, sf.amount, sf.due_date,
               CAST(julianday('now') - julianday(sf.due_date) AS INTEGER) AS days_overdue
        FROM student_fees sf
        WHERE sf.status = 'unpaid'
          AND sf.due_date IS NOT NULL
          AND sf.due_date < date('now')
          AND NOT EXISTS (
              SELECT 1 FROM late_fees lf WHERE lf.student_fee_id = sf.student_fee_id
          )
        ORDER BY sf.due_date
        ''').fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def apply_overdue_late_fees(rate=DEFAULT_OVERDUE_RATE):
    """Charge ``rate`` of the fee amount on every overdue fee without a late fee.

    This is the GUI's "Calculate Overdue" sweep. Returns
    ``{'applied': count, 'total': amount}``. Raises ValueError for a rate
    outside ``(0, 1]``.
    """
    rate = float(rate)
    if not 0 < rate <= 1:
        raise ValueError("Rate must be a fraction between 0 and 1")
    now = datetime.now()
    applied, total = 0, 0.0
    with transaction() as conn:
        overdue = conn.execute('''
        SELECT sf.student_fee_id, sf.amount,
               julianday('now') - julianday(sf.due_date) AS days_overdue
        FROM student_fees sf
        WHERE sf.status = 'unpaid'
          AND sf.due_date IS NOT NULL
          AND sf.due_date < date('now')
          AND NOT EXISTS (
              SELECT 1 FROM late_fees lf WHERE lf.student_fee_id = sf.student_fee_id
          )
        ''').fetchall()
        for fee_id, amount, days_overdue in overdue:
            if not days_overdue or days_overdue <= 0:
                continue
            late_fee_amount = round(float(amount or 0) * rate, 2)
            if late_fee_amount <= 0:
                continue
            conn.execute('''
            INSERT INTO late_fees
            (student_fee_id, late_fee_amount, calculation_method, days_overdue,
             applied_date, waived, created_at)
            VALUES (?, ?, 'percentage', ?, ?, 0, ?)
            ''', (fee_id, late_fee_amount, int(days_overdue),
                  now.strftime('%Y-%m-%d'), now.strftime(_TS_FMT)))
            applied += 1
            total += late_fee_amount
    return {'applied': applied, 'total': round(total, 2)}
