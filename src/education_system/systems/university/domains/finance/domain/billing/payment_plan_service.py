"""Payment plan records — list, schedule, edit, delete.

Non-interactive counterpart to the menu-driven functions in
``billing.payment_plans``. The Finance GUI Payment Plans tab and the Finance
CLI Payment Plans menu both call these, so a plan created in one is exactly
what the other shows.

A plan is a ``student_payment_plans`` row; its schedule is the set of
``payment_plan_installments`` rows that reference it.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.domains.finance.domain.core.students import (
    student_exists,
)

#: Installment frequency -> days between installments.
FREQUENCIES = {'weekly': 7, 'biweekly': 14, 'monthly': 30, 'quarterly': 90}

#: Statuses a plan can be moved to by hand (``completed`` is set by payments).
PLAN_STATUSES = ('active', 'paused', 'completed', 'defaulted', 'cancelled')

_DATE_FMT = '%Y-%m-%d'
_TS_FMT = '%Y-%m-%d %H:%M:%S'


def _parse_date(value, label):
    try:
        return datetime.strptime(value, _DATE_FMT)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a date in YYYY-MM-DD form") from None


def list_payment_plans(status=None, limit=500):
    """Plans newest first, with template details and the student's name."""
    sql = '''
    SELECT spp.payment_plan_id AS plan_id, spp.student_id,
           s.first_name, s.last_name,
           spp.total_amount, spp.remaining_amount, spp.status, spp.start_date,
           spp.next_due_date, spp.notes,
           ppt.template_name,
           COALESCE(ppt.number_of_installments,
                    (SELECT COUNT(*) FROM payment_plan_installments ppi
                     WHERE ppi.payment_plan_id = spp.payment_plan_id)) AS installments,
           ppt.installment_frequency AS frequency
    FROM student_payment_plans spp
    LEFT JOIN students s ON spp.student_id = s.student_id
    LEFT JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
    '''
    params = []
    if status:
        sql += ' WHERE spp.status = ?'
        params.append(status)
    sql += ' ORDER BY spp.created_at DESC, spp.payment_plan_id DESC LIMIT ?'
    params.append(int(limit))
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_payment_plan(plan_id):
    """One plan as a dict (same columns as :func:`list_payment_plans`), or ``None``."""
    conn = get_connection()
    try:
        row = conn.execute('''
        SELECT spp.payment_plan_id AS plan_id, spp.student_id,
               s.first_name, s.last_name,
               spp.total_amount, spp.remaining_amount, spp.status, spp.start_date,
               spp.next_due_date, spp.notes, spp.created_at, spp.updated_at,
               ppt.template_name, ppt.installment_frequency AS frequency
        FROM student_payment_plans spp
        LEFT JOIN students s ON spp.student_id = s.student_id
        LEFT JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
        WHERE spp.payment_plan_id = ?
        ''', (plan_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_installments(plan_id):
    """A plan's installments in schedule order."""
    conn = get_connection()
    try:
        rows = conn.execute('''
        SELECT installment_id, installment_number, amount, due_date, status,
               payment_id, late_fee_amount
        FROM payment_plan_installments
        WHERE payment_plan_id = ?
        ORDER BY installment_number
        ''', (plan_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_scheduled_plan(student_id, total_amount, installments, frequency='monthly',
                          start_date=None, notes=''):
    """Create an active plan with an equal-installment schedule.

    The first installment falls one period after ``start_date`` (today by
    default). Returns ``{'plan_id', 'installment_amount', 'first_due',
    'last_due'}``. Raises ValueError on bad input.
    """
    student_id = str(student_id).strip()
    if not student_id or not student_exists(student_id):
        raise ValueError(f"Student with ID {student_id!r} does not exist")
    total_amount = float(total_amount)
    if total_amount <= 0:
        raise ValueError("Total amount must be greater than zero")
    installments = int(installments)
    if installments < 1:
        raise ValueError("Number of installments must be at least 1")
    if frequency not in FREQUENCIES:
        raise ValueError(
            f"Invalid frequency '{frequency}'. Expected one of: {', '.join(FREQUENCIES)}")

    start = _parse_date(start_date, "Start date") if start_date else datetime.now()
    step = timedelta(days=FREQUENCIES[frequency])
    ts = datetime.now().strftime(_TS_FMT)
    installment_amount = round(total_amount / installments, 2)
    due_dates = [start + step * (i + 1) for i in range(installments)]

    with transaction() as conn:
        cursor = conn.execute('''
        INSERT INTO student_payment_plans
        (student_id, total_amount, remaining_amount, status, start_date,
         next_due_date, notes, created_at, updated_at)
        VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?)
        ''', (student_id, total_amount, total_amount, start.strftime(_DATE_FMT),
              due_dates[0].strftime(_DATE_FMT), notes or None, ts, ts))
        plan_id = cursor.lastrowid
        conn.executemany('''
        INSERT INTO payment_plan_installments
        (payment_plan_id, installment_number, amount, due_date, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'pending', ?, ?)
        ''', [(plan_id, i + 1, installment_amount, due.strftime(_DATE_FMT), ts, ts)
              for i, due in enumerate(due_dates)])

    return {'plan_id': plan_id, 'installment_amount': installment_amount,
            'first_due': due_dates[0].strftime(_DATE_FMT),
            'last_due': due_dates[-1].strftime(_DATE_FMT)}


def update_payment_plan(plan_id, total_amount=None, next_due_date=None, status=None, notes=None):
    """Edit a plan in place; ``None`` leaves a field alone. Returns the new row.

    Changing ``total_amount`` re-bases ``remaining_amount`` by the same delta
    (never below zero). ``notes`` are appended, not replaced. Raises
    ValueError for a missing plan, a bad date, or an unknown status.
    """
    plan = get_payment_plan(plan_id)
    if plan is None:
        raise ValueError(f"Payment plan {plan_id} not found")

    sets, params = [], []
    if total_amount is not None:
        total_amount = float(total_amount)
        if total_amount <= 0:
            raise ValueError("Total amount must be greater than zero")
        delta = total_amount - float(plan['total_amount'] or 0)
        remaining = max(0.0, float(plan['remaining_amount'] or 0) + delta)
        sets += ['total_amount = ?', 'remaining_amount = ?']
        params += [total_amount, remaining]
    if next_due_date is not None:
        _parse_date(next_due_date, "Next due date")
        sets.append('next_due_date = ?')
        params.append(next_due_date)
    if status is not None:
        if status not in PLAN_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Expected one of: {', '.join(PLAN_STATUSES)}")
        sets.append('status = ?')
        params.append(status)
    if notes:
        sets.append("notes = COALESCE(notes, '') || ' | ' || ?")
        params.append(notes.strip())
    if not sets:
        return plan

    sets.append('updated_at = ?')
    params.append(datetime.now().strftime(_TS_FMT))
    params.append(plan_id)
    with transaction() as conn:
        conn.execute(
            f"UPDATE student_payment_plans SET {', '.join(sets)} WHERE payment_plan_id = ?",
            params,
        )
    return get_payment_plan(plan_id)


def delete_payment_plan(plan_id):
    """Delete a plan and its schedule. Refuses once any installment is paid.

    A plan with payment history should be cancelled (``update_payment_plan``
    with ``status='cancelled'``) so the payments keep their reference.
    Returns the deleted plan. Raises ValueError.
    """
    plan = get_payment_plan(plan_id)
    if plan is None:
        raise ValueError(f"Payment plan {plan_id} not found")
    with transaction() as conn:
        paid = conn.execute('''
        SELECT COUNT(*) FROM payment_plan_installments
        WHERE payment_plan_id = ? AND (status = 'paid' OR payment_id IS NOT NULL)
        ''', (plan_id,)).fetchone()[0]
        if paid:
            raise ValueError(
                f"Payment plan {plan_id} has {paid} paid installment(s); cancel it instead")
        conn.execute('DELETE FROM payment_plan_installments WHERE payment_plan_id = ?', (plan_id,))
        conn.execute('DELETE FROM student_payment_plans WHERE payment_plan_id = ?', (plan_id,))
    return plan
