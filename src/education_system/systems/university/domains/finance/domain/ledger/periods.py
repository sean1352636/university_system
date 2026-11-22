"""Period state machine: open → closed → locked.

- close_period: 'open' → 'closed'. Posting into the period is rejected.
  Admins can later reopen via reopen_period.
- lock_period: 'closed' or 'open' → 'locked'. Stronger close (e.g. after
  external audit). Cannot be reversed; only superseding journals in a
  later period can correct errors.
- reopen_period: 'closed' → 'open'. Refused for 'locked'.

Fiscal years (UK HE, 1 Aug – 31 Jul, named by the year they end in):

- ensure_periods_for(conn, date): the automatic roll-forward used by
  posting — opens the twelve periods of the date's fiscal year only when it
  is the current or next year (by today's date) and no later year exists.
- open_fiscal_year(fy, opened_by): finance opens any other year on purpose
  (an older year for a late correction, or a year further ahead). A year
  whose periods already exist is left as it is — closed and locked periods
  are never reopened this way.
"""

import logging
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


def ensure_periods_for(conn, journal_date, today=None) -> bool:
    """Open the fiscal year containing ``journal_date`` if the ledger may do
    so on its own. Returns True when periods were created. Does not commit
    (the caller's transaction posts the journal and commits both)."""
    from datetime import date
    from education_system.systems.university.domains.finance.domain.ledger import seed
    try:
        fy = seed.fiscal_year_for(journal_date)
    except ValueError:
        return False
    current = seed.fiscal_year_for(today or date.today())
    if fy not in (current, current + 1):
        return False
    latest = conn.execute("SELECT MAX(fiscal_year) FROM gl_periods").fetchone()[0]
    if latest is not None and fy < latest:
        return False          # a gap before a later year: open it deliberately
    created = seed.seed_fiscal_year_periods(conn, fy)
    if created:
        logging.getLogger(__name__).info("Ledger opened fiscal year %s (%s periods) for a "
                                         "journal dated %s", fy, created, journal_date)
    return bool(created)


def open_fiscal_year(fiscal_year, opened_by):
    """Open the twelve periods of ``fiscal_year`` (finance staff). Returns
    the number of periods created (0 when the year already exists)."""
    from education_system.systems.university.domains.finance.domain.ledger import seed
    try:
        fy = int(fiscal_year)
    except (TypeError, ValueError):
        raise ValueError("Give the fiscal year as the year it ends in, e.g. 2027") from None
    if not 2000 <= fy <= 2100:
        raise ValueError("That fiscal year is out of range")
    if not str(opened_by or "").strip():
        raise ValueError("Say who is opening the year")
    conn = get_connection()
    try:
        created = seed.seed_fiscal_year_periods(conn, fy)
        conn.commit()
    finally:
        conn.close()
    logging.getLogger(__name__).info("Fiscal year %s opened by %s (%s periods created)",
                                     fy, opened_by, created)
    return created


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
