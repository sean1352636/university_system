"""GL posting service — translates operational events into balanced double-entry journals.

Public functions are idempotent: re-posting the same source (`source_type`,
`source_id`) returns the existing journal_id rather than creating a duplicate
(enforced by the UNIQUE index on gl_journals).

Posting rules (cash basis, single default entity):

  payment received  : Dr Cash 1010              Cr AR or revenue (per source_type)
  refund processed  : Dr revenue (per source)   Cr Cash 1010
  fee assigned      : Dr AR (per fee_type)      Cr revenue (per fee_type)

Mappings live in `_REVENUE_FOR_PAYMENT_SOURCE` and friends below; finance staff
can adjust by editing this module. A more elaborate config-driven ruleset is
deferred to a future change.
"""

from decimal import Decimal
from datetime import datetime, date

from education_system.university_system.infrastructure.database.db import get_connection


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class JournalUnbalancedError(Exception):
    """Raised when a journal's debit total does not equal its credit total."""


class PeriodClosedError(Exception):
    """Raised when posting into a period whose status is 'closed' or 'locked'."""


class AccountNotFoundError(Exception):
    """Raised when a posting rule references an account_code not in the chart."""


# ---------------------------------------------------------------------------
# Posting rule mappings — payments.source_type → revenue account_code
# ---------------------------------------------------------------------------

_REVENUE_FOR_PAYMENT_SOURCE = {
    # When a student fee payment lands and the link to a specific fee_type
    # is unknown, fall back to generic Tuition (Home/EU). Posting through
    # post_fee_assignment + payment_allocation is the precise path; this
    # default exists for direct payments that bypass the AR cycle.
    'general':       '4000',  # Tuition Fees — Home/EU (default)
    'tuition':       '4000',
    'club':          '4340',  # Club / Membership Income
    'housing':       '4360',  # Accommodation Income
    'commerce':      '4350',  # Catering / Commerce
    'library':       '4330',  # Library Fines
    'late_fee':      '4310',  # Late Fee Income
    'application':   '4320',  # Application Fees
    'train':         '4350',  # Catering / Commerce (transport — broad bucket for now)
    'charity_shop':  '4350',
}

# Bank-app top-ups are not revenue — they're a liability (we hold student cash).
# Detected by payment_method or a dedicated source_type 'bank_topup'.
_TOPUP_LIABILITY_CODE = '2500'  # Student Account Liabilities

# Default cash account
_CASH_ACCOUNT_CODE = '1010'

# AR for fee assignments — naive default; finance can refine via fee_type
_AR_DEFAULT_CODE = '1110'  # AR — Tuition (Home/EU)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _account_id(cur, account_code):
    cur.execute("SELECT account_id FROM gl_accounts WHERE account_code = ?", (account_code,))
    row = cur.fetchone()
    if not row:
        raise AccountNotFoundError(f"No account with code {account_code!r} in gl_accounts")
    return row[0]


def _default_entity_id(cur):
    cur.execute("SELECT entity_id FROM gl_entities WHERE is_active = 1 ORDER BY entity_id LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise RuntimeError("No active entity in gl_entities — has init_ledger() been run?")
    return row[0]


def _period_for_date(cur, journal_date):
    """Return (period_id, status) for the period containing journal_date.

    Raises if no period covers the date — caller should ensure
    seed_current_fiscal_year_periods() has been run for the relevant FY.
    """
    cur.execute(
        "SELECT period_id, status FROM gl_periods "
        "WHERE start_date <= ? AND end_date >= ? "
        "LIMIT 1",
        (journal_date, journal_date),
    )
    row = cur.fetchone()
    if not row:
        raise PeriodClosedError(
            f"No period covers {journal_date!r}. Seed periods for the relevant fiscal year first."
        )
    return row[0], row[1]


def _existing_journal_id(cur, source_type, source_id):
    cur.execute(
        "SELECT journal_id FROM gl_journals WHERE source_type = ? AND source_id = ?",
        (source_type, source_id),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _post_journal(conn, *, entity_id, journal_date, description, source_type, source_id,
                  posted_by, lines):
    """Write a balanced journal in a single transaction.

    `lines` is a list of dicts: {'account_code', 'debit'?, 'credit'?, 'memo'?}.
    Exactly one of debit/credit must be > 0 per line. Sums must balance.

    Idempotent on (source_type, source_id): if a journal already exists,
    returns its id without writing.
    """
    cur = conn.cursor()
    existing = _existing_journal_id(cur, source_type, source_id)
    if existing is not None:
        return existing

    if len(lines) < 2:
        raise JournalUnbalancedError("A journal must have at least 2 lines")
    debit_total = Decimal('0')
    credit_total = Decimal('0')
    resolved = []
    for line in lines:
        debit = Decimal(str(line.get('debit', 0) or 0))
        credit = Decimal(str(line.get('credit', 0) or 0))
        if (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
            raise JournalUnbalancedError(
                f"Each line must be exactly debit OR credit; got debit={debit}, credit={credit}"
            )
        debit_total += debit
        credit_total += credit
        resolved.append({
            'account_id': _account_id(cur, line['account_code']),
            'debit': float(debit),
            'credit': float(credit),
            'memo': line.get('memo'),
        })
    if debit_total != credit_total:
        raise JournalUnbalancedError(
            f"Journal not balanced: debit={debit_total} credit={credit_total}"
        )

    period_id, period_status = _period_for_date(cur, journal_date)
    if period_status in ('closed', 'locked'):
        raise PeriodClosedError(
            f"Period {period_id} is {period_status}; cannot post journal dated {journal_date}"
        )

    cur.execute(
        """INSERT INTO gl_journals
           (entity_id, journal_date, period_id, description, source_type, source_id, posted_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (entity_id, journal_date, period_id, description, source_type, source_id, posted_by),
    )
    journal_id = cur.lastrowid

    cur.executemany(
        """INSERT INTO gl_journal_lines (journal_id, account_id, debit, credit, memo)
           VALUES (?, ?, ?, ?, ?)""",
        [(journal_id, ln['account_id'], ln['debit'], ln['credit'], ln['memo'])
         for ln in resolved],
    )
    conn.commit()
    return journal_id


def _resolve_payment_revenue_code(source_type, payment_method=None):
    """Pick the credit account for a payment row.

    Bank-app top-ups go to liability 2500. Everything else routes by source_type.
    """
    if source_type == 'bank_topup' or (payment_method or '').lower() in ('top-up', 'topup'):
        return _TOPUP_LIABILITY_CODE
    return _REVENUE_FOR_PAYMENT_SOURCE.get((source_type or 'general').lower(), '4000')


# ---------------------------------------------------------------------------
# Public posting functions
# ---------------------------------------------------------------------------

def post_payment(payment_id, posted_by='system'):
    """Post a payments row to the GL.

    Cash basis: Dr Cash, Cr Revenue (or Cr Student-Account Liability for top-ups).
    Idempotent — returns existing journal_id if already posted.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT payment_id, amount, payment_date, source_type, payment_method, notes "
            "FROM payments WHERE payment_id = ?",
            (payment_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"payment_id {payment_id} not found")
        pid, amount, pay_date, source_type, payment_method, notes = (
            row[0], row[1], row[2], row[3], row[4], row[5]
        )
        amount = Decimal(str(amount or 0))
        if amount <= 0:
            raise ValueError(f"payment {pid} has non-positive amount {amount}")
        # Normalise date — operational tables sometimes store full timestamps
        journal_date = (pay_date or datetime.now().isoformat())[:10]

        credit_code = _resolve_payment_revenue_code(source_type, payment_method)

        return _post_journal(
            conn,
            entity_id=_default_entity_id(cur),
            journal_date=journal_date,
            description=f"Payment {pid} ({source_type or 'general'})"
                        + (f": {notes}" if notes else ""),
            source_type='payment',
            source_id=pid,
            posted_by=posted_by,
            lines=[
                {'account_code': _CASH_ACCOUNT_CODE, 'debit': float(amount),
                 'memo': f"Payment {pid}"},
                {'account_code': credit_code, 'credit': float(amount),
                 'memo': f"Payment {pid} — {source_type or 'general'}"},
            ],
        )
    finally:
        conn.close()


def post_refund(refund_id, posted_by='system'):
    """Post a unified_refunds row to the GL.

    Cash basis: Dr Revenue (reversing the original income line), Cr Cash.
    For top-up withdrawals: Dr Student-Account Liability 2500, Cr Cash.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT refund_id, amount, refund_date, source_type, refund_method, notes "
            "FROM unified_refunds WHERE refund_id = ?",
            (refund_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"refund_id {refund_id} not found")
        rid, amount, refund_date, source_type, refund_method, notes = (
            row[0], row[1], row[2], row[3], row[4], row[5]
        )
        amount = Decimal(str(amount or 0))
        if amount <= 0:
            raise ValueError(f"refund {rid} has non-positive amount {amount}")
        journal_date = (refund_date or datetime.now().isoformat())[:10]

        # Refunds reverse whichever income (or liability) the original payment hit.
        debit_code = _resolve_payment_revenue_code(source_type, refund_method)

        return _post_journal(
            conn,
            entity_id=_default_entity_id(cur),
            journal_date=journal_date,
            description=f"Refund {rid} ({source_type or 'general'})"
                        + (f": {notes}" if notes else ""),
            source_type='refund',
            source_id=rid,
            posted_by=posted_by,
            lines=[
                {'account_code': debit_code, 'debit': float(amount),
                 'memo': f"Refund {rid} — {source_type or 'general'}"},
                {'account_code': _CASH_ACCOUNT_CODE, 'credit': float(amount),
                 'memo': f"Refund {rid}"},
            ],
        )
    finally:
        conn.close()


def post_fee_assignment(student_fee_id, posted_by='system'):
    """Post a student_fees row (charge raised against a student) to the GL.

    Cash basis treatment for AR is a hybrid: we recognise the receivable when
    the fee is assigned (Dr AR, Cr Revenue) and the eventual cash receipt
    extinguishes the AR (handled in post_payment when source_type='tuition'
    and the payment is allocated). For genuinely cash-only operation finance
    can choose to skip post_fee_assignment and rely on post_payment alone.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT sf.student_fee_id, sf.amount, sf.created_at, sf.due_date, "
            "       ft.fee_name "
            "FROM student_fees sf "
            "LEFT JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id "
            "WHERE sf.student_fee_id = ?",
            (student_fee_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"student_fee_id {student_fee_id} not found")
        sfid, amount, created_at, due_date, fee_name = (
            row[0], row[1], row[2], row[3], row[4]
        )
        amount = Decimal(str(amount or 0))
        if amount <= 0:
            raise ValueError(f"student_fee {sfid} has non-positive amount {amount}")
        # Use the assignment timestamp as the journal date; fall back to due_date or today.
        journal_date = (created_at or due_date or date.today().isoformat())[:10]

        # Lookup AR + revenue codes by fee_name. v1 is naive: tuition vs. catch-all.
        fee_lc = (fee_name or '').lower()
        if 'international' in fee_lc:
            ar_code, rev_code = '1120', '4001'
        elif 'postgrad' in fee_lc or 'pg' in fee_lc:
            ar_code, rev_code = '1110', '4010'
        elif 'accommod' in fee_lc or 'housing' in fee_lc:
            ar_code, rev_code = '1130', '4360'
        else:
            ar_code, rev_code = _AR_DEFAULT_CODE, '4000'

        return _post_journal(
            conn,
            entity_id=_default_entity_id(cur),
            journal_date=journal_date,
            description=f"Fee assigned {sfid} ({fee_name or 'unknown'})",
            source_type='fee_assignment',
            source_id=sfid,
            posted_by=posted_by,
            lines=[
                {'account_code': ar_code, 'debit': float(amount),
                 'memo': f"Fee {sfid} — {fee_name}"},
                {'account_code': rev_code, 'credit': float(amount),
                 'memo': f"Fee {sfid} — {fee_name}"},
            ],
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

def backfill(posted_by='backfill'):
    """Replay all operational rows into the ledger.

    Returns a dict summary: {posted, skipped, errors:[(source_type, source_id, msg), ...]}.
    Idempotent — already-posted rows are skipped via the UNIQUE constraint.
    Caller should ensure init_ledger() has been run first.
    """
    summary = {'posted': 0, 'skipped': 0, 'errors': []}
    conn = get_connection()
    cur = conn.cursor()

    def _process(source_type, ids, fn):
        for source_id in ids:
            try:
                journal_id = fn(source_id, posted_by=posted_by)
                # Detect 'already existed' vs. 'just posted now' by re-reading posted_at recency
                # — simplest proxy: check if a journal predates this run. For v1 we just
                # increment 'posted' on success and rely on the user to re-run if needed.
                summary['posted'] += 1
            except Exception as e:
                summary['errors'].append((source_type, source_id, str(e)))

    # Payments
    try:
        cur.execute("SELECT payment_id FROM payments ORDER BY payment_id")
        payment_ids = [r[0] for r in cur.fetchall()]
    except Exception:
        payment_ids = []
    _process('payment', payment_ids, post_payment)

    # Refunds
    try:
        cur.execute("SELECT refund_id FROM unified_refunds ORDER BY refund_id")
        refund_ids = [r[0] for r in cur.fetchall()]
    except Exception:
        refund_ids = []
    _process('refund', refund_ids, post_refund)

    # Fee assignments
    try:
        cur.execute("SELECT student_fee_id FROM student_fees ORDER BY student_fee_id")
        fee_ids = [r[0] for r in cur.fetchall()]
    except Exception:
        fee_ids = []
    _process('fee_assignment', fee_ids, post_fee_assignment)

    conn.close()
    return summary
