"""Period state machine: open → closed → locked.

- close_period: 'open' → 'closed'. Posting into the period is rejected.
  Admins can later reopen via reopen_period.
- lock_period: 'closed' or 'open' → 'locked'. Stronger close (e.g. after
  external audit). Cannot be reversed; only superseding journals in a
  later period can correct errors.
- reopen_period: 'closed' → 'open'. Refused for 'locked'.
"""

from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection


class PeriodStateError(Exception):
    """Raised when a period transition is not allowed."""


def _read_status(cur, period_id):
    cur.execute("SELECT status FROM gl_periods WHERE period_id = ?", (period_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"period_id {period_id} not found")
    return row[0]


def close_period(period_id, closed_by):
    conn = get_connection()
    try:
        cur = conn.cursor()
        status = _read_status(cur, period_id)
        if status != 'open':
            raise PeriodStateError(
                f"Cannot close period {period_id} — current status is '{status}'"
            )
        cur.execute(
            "UPDATE gl_periods SET status = 'closed', closed_at = ?, closed_by = ? "
            "WHERE period_id = ?",
            (datetime.now().isoformat(), closed_by, period_id),
        )
        conn.commit()
    finally:
        conn.close()


def lock_period(period_id, locked_by):
    conn = get_connection()
    try:
        cur = conn.cursor()
        status = _read_status(cur, period_id)
        if status == 'locked':
            return  # already locked, no-op
        cur.execute(
            "UPDATE gl_periods SET status = 'locked', closed_at = ?, closed_by = ? "
            "WHERE period_id = ?",
            (datetime.now().isoformat(), locked_by, period_id),
        )
        conn.commit()
    finally:
        conn.close()


def reopen_period(period_id):
    """Reopen a 'closed' period. Refuses 'locked' periods."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        status = _read_status(cur, period_id)
        if status == 'locked':
            raise PeriodStateError(f"Period {period_id} is locked and cannot be reopened")
        if status == 'open':
            return  # no-op
        cur.execute(
            "UPDATE gl_periods SET status = 'open', closed_at = NULL, closed_by = NULL "
            "WHERE period_id = ?",
            (period_id,),
        )
        conn.commit()
    finally:
        conn.close()


def list_periods(fiscal_year=None):
    """Return all periods (or just one fiscal year) ordered by start_date.

    Each row is a dict with: period_id, fiscal_year, period_no, start_date,
    end_date, status, closed_at, closed_by, journal_count.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT p.period_id, p.fiscal_year, p.period_no, p.start_date,
                   p.end_date, p.status, p.closed_at, p.closed_by,
                   COALESCE((SELECT COUNT(*) FROM gl_journals
                             WHERE period_id = p.period_id), 0) AS journal_count
            FROM gl_periods p
        """
        params = ()
        if fiscal_year is not None:
            sql += " WHERE p.fiscal_year = ?"
            params = (fiscal_year,)
        sql += " ORDER BY p.start_date"
        cur.execute(sql, params)
        return [
            {
                'period_id': r[0], 'fiscal_year': r[1], 'period_no': r[2],
                'start_date': r[3], 'end_date': r[4], 'status': r[5],
                'closed_at': r[6], 'closed_by': r[7], 'journal_count': r[8],
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()
