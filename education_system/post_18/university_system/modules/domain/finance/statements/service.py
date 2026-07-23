"""Statement-run service.

`run_statements_batch(period_end, generated_by, period_start=None)` produces
one `student_statements` row per student that has any `student_fees` row
dated on or before `period_end`. Each row carries:

  opening_balance     — AR position immediately before period_start
  charges_in_period   — Σ fees with created_at in [period_start, period_end]
  payments_in_period  — Σ payment allocations with payment_date in window
  refunds_in_period   — Σ refunds with refund_date in window (best-effort:
                         joined by student_id since unified_refunds doesn't
                         always link back to a specific fee)
  closing_balance     — AR position as of period_end

The math:
    closing  = total_charges_to_date − total_paid_to_date
    opening  = closing − charges_in_period + payments_in_period + refunds_in_period

`period_start` defaults to "the beginning of time" so a first-ever run
treats everything as in-period (opening = 0).
"""

from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import get_connection


def run_statements_batch(period_end, generated_by='admin', period_start=None):
    """Generate a fresh run of statements covering through `period_end`.

    Returns dict {run_id, total_students, total_with_balance}.
    """
    period_end = str(period_end)[:10]
    period_start = (str(period_start)[:10] if period_start else '0000-01-01')

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Create run header
        cur.execute(
            "INSERT INTO statement_runs (period_start, period_end, generated_by, status) "
            "VALUES (?, ?, ?, 'completed')",
            (period_start, period_end, generated_by),
        )
        run_id = cur.lastrowid

        # All students with any fee row dated on or before period_end
        cur.execute(
            """SELECT DISTINCT student_id
               FROM student_fees
               WHERE substr(COALESCE(created_at, due_date), 1, 10) <= ?
               ORDER BY student_id""",
            (period_end,),
        )
        student_ids = [r[0] for r in cur.fetchall()]

        n_total = 0
        n_with_balance = 0

        for sid in student_ids:
            charges_total = _scalar(cur,
                """SELECT COALESCE(SUM(amount), 0) FROM student_fees
                   WHERE student_id = ?
                   AND substr(COALESCE(created_at, due_date), 1, 10) <= ?""",
                (sid, period_end))

            paid_total = _scalar(cur,
                """SELECT COALESCE(SUM(pa.amount), 0)
                   FROM payment_allocations pa
                   JOIN student_fees sf ON sf.student_fee_id = pa.student_fee_id
                   JOIN payments p      ON p.payment_id      = pa.payment_id
                   WHERE sf.student_id = ?
                   AND substr(COALESCE(p.payment_date, p.created_at), 1, 10) <= ?""",
                (sid, period_end))

            charges_in_period = _scalar(cur,
                """SELECT COALESCE(SUM(amount), 0) FROM student_fees
                   WHERE student_id = ?
                   AND substr(COALESCE(created_at, due_date), 1, 10) BETWEEN ? AND ?""",
                (sid, period_start, period_end))

            payments_in_period = _scalar(cur,
                """SELECT COALESCE(SUM(pa.amount), 0)
                   FROM payment_allocations pa
                   JOIN student_fees sf ON sf.student_fee_id = pa.student_fee_id
                   JOIN payments p      ON p.payment_id      = pa.payment_id
                   WHERE sf.student_id = ?
                   AND substr(COALESCE(p.payment_date, p.created_at), 1, 10) BETWEEN ? AND ?""",
                (sid, period_start, period_end))

            # Refunds: best-effort by student_id (no fee linkage)
            refunds_in_period = _scalar(cur,
                """SELECT COALESCE(SUM(amount), 0) FROM unified_refunds
                   WHERE student_id = ?
                   AND substr(COALESCE(refund_date, created_at), 1, 10)
                   BETWEEN ? AND ?
                   AND COALESCE(status, '') IN ('processed', 'completed')""",
                (sid, period_start, period_end))

            closing = float(charges_total) - float(paid_total)
            opening = closing - float(charges_in_period) \
                              + float(payments_in_period) \
                              + float(refunds_in_period)

            cur.execute(
                """INSERT INTO student_statements
                   (run_id, student_id, period_start, period_end,
                    opening_balance, charges_in_period, payments_in_period,
                    refunds_in_period, closing_balance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, sid, period_start, period_end,
                 opening, float(charges_in_period), float(payments_in_period),
                 float(refunds_in_period), closing),
            )

            n_total += 1
            if abs(closing) >= 0.01:
                n_with_balance += 1

        cur.execute(
            "UPDATE statement_runs SET total_students = ?, total_with_balance = ? "
            "WHERE run_id = ?",
            (n_total, n_with_balance, run_id),
        )
        conn.commit()
        return {
            'run_id': run_id,
            'total_students': n_total,
            'total_with_balance': n_with_balance,
        }
    finally:
        conn.close()


def _scalar(cur, sql, params):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else 0


def list_runs(limit=50):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT run_id, period_start, period_end, generated_at,
                      generated_by, status, total_students, total_with_balance
               FROM statement_runs ORDER BY run_id DESC LIMIT ?""",
            (limit,),
        )
        return [
            {
                'run_id': r[0], 'period_start': r[1], 'period_end': r[2],
                'generated_at': r[3], 'generated_by': r[4],
                'status': r[5], 'total_students': r[6],
                'total_with_balance': r[7],
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def list_statements(run_id, only_with_balance=False):
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = ("SELECT statement_id, student_id, opening_balance, "
               "charges_in_period, payments_in_period, refunds_in_period, "
               "closing_balance FROM student_statements WHERE run_id = ?")
        params = [run_id]
        if only_with_balance:
            sql += " AND ABS(closing_balance) >= 0.01"
        sql += " ORDER BY closing_balance DESC, student_id"
        cur.execute(sql, params)
        return [
            {
                'statement_id': r[0], 'student_id': r[1],
                'opening_balance': r[2], 'charges_in_period': r[3],
                'payments_in_period': r[4], 'refunds_in_period': r[5],
                'closing_balance': r[6],
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def get_statement(run_id, student_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT statement_id, run_id, student_id, period_start, period_end,
                      opening_balance, charges_in_period, payments_in_period,
                      refunds_in_period, closing_balance
               FROM student_statements
               WHERE run_id = ? AND student_id = ?""",
            (run_id, student_id),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            'statement_id': r[0], 'run_id': r[1], 'student_id': r[2],
            'period_start': r[3], 'period_end': r[4],
            'opening_balance': r[5], 'charges_in_period': r[6],
            'payments_in_period': r[7], 'refunds_in_period': r[8],
            'closing_balance': r[9],
        }
    finally:
        conn.close()
