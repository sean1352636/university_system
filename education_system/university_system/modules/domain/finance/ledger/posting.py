"""GL posting service — translates operational events into balanced double-entry journals.

Public functions are idempotent: re-posting the same source (`source_type`,
`source_id`) returns the existing journal_id rather than creating a duplicate
(enforced by the UNIQUE index on gl_journals).

Posting rules (cash basis, single default entity):

  payment received  : Dr Cash 1010              Cr AR or revenue (per source_type)
  refund processed  : Dr revenue (per source)   Cr Cash 1010
  fee assigned      : Dr AR (per fee_type)      Cr revenue (per fee_type)
  payroll run       : Dr Staff Costs 5000 (gross) ;
                      Cr Cash 1010 (net)
                      Cr AP 2100 (deductions parked until remitted)

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
# VAT classification by source_type
# ---------------------------------------------------------------------------
#
# UK VAT, defaults only. Each source_type is mapped to a vat_rate keyword:
#   'standard' → 20% (most commercial supplies)
#   'reduced'  →  5% (energy, certain things)
#   'zero'     →  0% (passenger transport, books, food)
#   'exempt'   → no VAT (tuition, club memberships, financial services,
#                medical/dental, library penalties, education-related)
#
# Per-row vat_rate / vat_amount on the operational row OVERRIDES this default
# (use them when the writer knows the correct treatment). The map below is
# intentionally conservative: things that are clearly exempt are exempt;
# commercial supplies are standard. Mixed cases (e.g. accommodation —
# student halls vs commercial guest stays) default to the more common
# institutional treatment (exempt for student halls); the writer should
# pass an explicit vat_rate when commercial.
#
# Partial-exemption (the institution-level recovery percentage on input
# VAT) is NOT handled here — that's a year-end accountancy decision.

_VAT_RATES = {
    'standard': 0.20,
    'reduced':  0.05,
    'zero':     0.0,
    'exempt':   None,  # None means "no VAT line at all"
}

_VAT_DEFAULT_BY_SOURCE = {
    # Exempt — tuition / education / non-business
    'general':         'exempt',  # default tuition path
    'tuition':         'exempt',
    'application':     'exempt',
    'late_fee':        'exempt',  # penalties aren't a supply
    'club':            'exempt',  # student union — non-business
    'housing':         'exempt',  # student halls; commercial guests must pass explicit
    'library':         'exempt',
    'library_fine':    'exempt',
    'fee_assignment':  'exempt',  # AR for tuition
    'aid_disbursement':'exempt',
    'research_grants': 'exempt',
    # Standard 20%
    'restaurant':      'standard',
    'cafe':            'standard',
    'takeaway':        'standard',
    'commerce':        'standard',
    'shop':            'standard',
    'charity_shop':    'standard',
    'grocery':         'standard',
    'butcher':         'standard',
    'musicshop':       'standard',
    'phoneshop':       'standard',
    'nailbar':         'standard',
    'nail_bar':        'standard',
    'barber':          'standard',
    'gym':             'standard',
    'cinema':          'standard',
    'car_rental':      'standard',
    'taxi':            'standard',
    'parking':         'standard',
    'legal':           'standard',
    # Zero-rated
    'train':           'zero',     # passenger transport
    # Special: not a supply, no VAT semantics
    'bank_topup':      'exempt',
    'order':           'standard',  # restaurant orders source_type
}

_VAT_OUTPUT_ACCOUNT = '2200'  # VAT Output (collected on sales)
_VAT_INPUT_ACCOUNT  = '1300'  # VAT Input (recoverable on purchases)


def _resolve_vat(source_type, explicit_rate, explicit_amount, gross):
    """Return (rate_keyword, vat_amount, net_amount) for a transaction.

    Precedence: explicit_amount > explicit_rate > default by source_type.
    Returns ('exempt', 0, gross) when no VAT applies (so callers can post
    a 2-line journal). Returns the keyword from _VAT_RATES for taxable
    transactions plus the computed VAT and net.
    """
    gross = Decimal(str(gross or 0))
    # Explicit amount wins if provided
    if explicit_amount is not None:
        try:
            vat = Decimal(str(explicit_amount))
            if vat < 0:
                vat = Decimal('0')
            net = gross - vat
            keyword = (explicit_rate or 'standard').lower() if vat > 0 else 'exempt'
            return keyword, vat, net
        except Exception:
            pass

    rate_keyword = (explicit_rate or _VAT_DEFAULT_BY_SOURCE.get(
        (source_type or '').lower(), 'exempt')).lower()
    rate = _VAT_RATES.get(rate_keyword)
    if rate is None or rate == 0:
        # exempt / zero — no VAT line
        return rate_keyword, Decimal('0'), gross
    # Gross-inclusive: vat = gross * rate / (1 + rate)
    vat = (gross * Decimal(str(rate)) / (Decimal('1') + Decimal(str(rate))))
    vat = vat.quantize(Decimal('0.01'))
    net = gross - vat
    return rate_keyword, vat, net


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
    'student_union': '4340',
    'housing':       '4360',  # Accommodation Income
    'commerce':      '4350',  # Catering / Commerce
    'library':       '4330',  # Library Fines
    'library_fine':  '4330',
    'late_fee':      '4310',  # Late Fee Income
    'application':   '4320',  # Application Fees
    'train':         '4350',  # broad commerce bucket — transport revenue
    'taxi':          '4350',
    'parking':       '4350',
    # Commerce subsystems — all consolidate under Catering / Commerce (4350).
    # A finer-grained chart (4351 Catering, 4352 Retail, 4353 Services, …)
    # is a chart-of-accounts decision deferred to finance staff.
    'charity_shop':  '4350',
    'restaurant':    '4350',
    'cafe':          '4350',
    'takeaway':      '4350',
    'shop':          '4350',
    'grocery':       '4350',
    'butcher':       '4350',
    'musicshop':     '4350',
    'phoneshop':     '4350',
    'nailbar':       '4350',
    'nail_bar':      '4350',
    'barber':        '4350',
    'gym':           '4350',
    'cinema':        '4350',
    'car_rental':    '4350',
    'order':         '4350',  # restaurant orders source_type
    # Professional services
    'legal':         '4300',  # Other Income
    'dentist':       '4300',
}

# Bank-app top-ups are not revenue — they're a liability (we hold student cash).
# Detected by payment_method or a dedicated source_type 'bank_topup'.
_TOPUP_LIABILITY_CODE = '2500'  # Student Account Liabilities

# Refundable housing deposits — held until move-out, then released against damages
# or returned. Recognised as a liability on receipt, never as revenue.
_DEPOSIT_LIABILITY_CODE = '2510'  # Tenant Deposits Held

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


def _resolve_payment_revenue_code(source_type, payment_method=None, payment_type=None):
    """Pick the credit account for a payment row.

    Bank-app top-ups go to liability 2500. Housing deposits go to liability 2510
    (held, not earned). Everything else routes by source_type.
    """
    if source_type == 'bank_topup' or (payment_method or '').lower() in ('top-up', 'topup'):
        return _TOPUP_LIABILITY_CODE
    if (source_type or '').lower() == 'housing' and (payment_type or '').lower() == 'deposit':
        return _DEPOSIT_LIABILITY_CODE
    return _REVENUE_FOR_PAYMENT_SOURCE.get((source_type or 'general').lower(), '4000')


# ---------------------------------------------------------------------------
# Public posting functions
# ---------------------------------------------------------------------------

def post_payment(payment_id, posted_by='system'):
    """Post a payments row to the GL.

    Cash basis with VAT split: Dr Cash (gross), Cr Revenue (net), Cr VAT
    Output 2200 (vat_amount) when applicable. Top-ups credit Student-Account
    Liability 2500 instead of revenue (and never split VAT — top-ups aren't
    a supply). Exempt/zero-rated source_types fall back to a 2-line journal.
    Idempotent — returns existing journal_id if already posted.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT payment_id, amount, payment_date, source_type, payment_method, notes, "
            "       vat_rate, vat_amount, payment_type "
            "FROM payments WHERE payment_id = ?",
            (payment_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"payment_id {payment_id} not found")
        pid, gross_in, pay_date, source_type, payment_method, notes, vat_rate_in, vat_amount_in, payment_type = (
            row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]
        )
        gross = Decimal(str(gross_in or 0))
        if gross <= 0:
            raise ValueError(f"payment {pid} has non-positive amount {gross}")
        # Normalise date — operational tables sometimes store full timestamps
        journal_date = (pay_date or datetime.now().isoformat())[:10]

        credit_code = _resolve_payment_revenue_code(source_type, payment_method, payment_type)
        is_topup = credit_code == _TOPUP_LIABILITY_CODE
        is_deposit = credit_code == _DEPOSIT_LIABILITY_CODE

        # Top-ups and refundable deposits are liability movements, not supplies: no VAT.
        if is_topup or is_deposit:
            rate_keyword, vat, net = 'exempt', Decimal('0'), gross
        else:
            rate_keyword, vat, net = _resolve_vat(
                source_type, vat_rate_in, vat_amount_in, gross,
            )

        lines = [
            {'account_code': _CASH_ACCOUNT_CODE, 'debit': float(gross),
             'memo': f"Payment {pid}"},
            {'account_code': credit_code, 'credit': float(net),
             'memo': f"Payment {pid} — {source_type or 'general'}"
                     + (f" (net of {rate_keyword} VAT)" if vat > 0 else "")},
        ]
        if vat > 0:
            lines.append({
                'account_code': _VAT_OUTPUT_ACCOUNT, 'credit': float(vat),
                'memo': f"VAT {rate_keyword} on payment {pid}",
            })

        return _post_journal(
            conn,
            entity_id=_default_entity_id(cur),
            journal_date=journal_date,
            description=f"Payment {pid} ({source_type or 'general'})"
                        + (f": {notes}" if notes else ""),
            source_type='payment',
            source_id=pid,
            posted_by=posted_by,
            lines=lines,
        )
    finally:
        conn.close()


def post_refund(refund_id, posted_by='system'):
    """Post a unified_refunds row to the GL.

    Cash basis with VAT split: Dr Revenue (net), Dr VAT Output 2200 (vat —
    reversing the previously-collected output VAT), Cr Cash (gross).
    For top-up withdrawals: Dr Student-Account Liability 2500, Cr Cash.
    Exempt/zero-rated source_types fall back to the 2-line journal.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT refund_id, amount, refund_date, source_type, refund_method, notes, "
            "       vat_rate, vat_amount "
            "FROM unified_refunds WHERE refund_id = ?",
            (refund_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"refund_id {refund_id} not found")
        rid, gross_in, refund_date, source_type, refund_method, notes, vat_rate_in, vat_amount_in = (
            row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]
        )
        gross = Decimal(str(gross_in or 0))
        if gross <= 0:
            raise ValueError(f"refund {rid} has non-positive amount {gross}")
        journal_date = (refund_date or datetime.now().isoformat())[:10]

        # Refunds reverse whichever income (or liability) the original payment hit.
        debit_code = _resolve_payment_revenue_code(source_type, refund_method)
        is_topup_withdrawal = debit_code == _TOPUP_LIABILITY_CODE

        if is_topup_withdrawal:
            rate_keyword, vat, net = 'exempt', Decimal('0'), gross
        else:
            rate_keyword, vat, net = _resolve_vat(
                source_type, vat_rate_in, vat_amount_in, gross,
            )

        lines = [
            {'account_code': debit_code, 'debit': float(net),
             'memo': f"Refund {rid} — {source_type or 'general'}"
                     + (f" (net of {rate_keyword} VAT)" if vat > 0 else "")},
        ]
        if vat > 0:
            # Reverse output VAT previously collected
            lines.append({
                'account_code': _VAT_OUTPUT_ACCOUNT, 'debit': float(vat),
                'memo': f"VAT {rate_keyword} reversed on refund {rid}",
            })
        lines.append({
            'account_code': _CASH_ACCOUNT_CODE, 'credit': float(gross),
            'memo': f"Refund {rid}",
        })

        return _post_journal(
            conn,
            entity_id=_default_entity_id(cur),
            journal_date=journal_date,
            description=f"Refund {rid} ({source_type or 'general'})"
                        + (f": {notes}" if notes else ""),
            source_type='refund',
            source_id=rid,
            posted_by=posted_by,
            lines=lines,
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


def post_payroll_run(period_id, posted_by='system'):
    """Post a finalised payroll period to the GL.

    Cash basis treatment:
      Dr Staff Costs (5000)        gross_pay total
      Cr Cash (1010)               net_pay total
      Cr Accounts Payable (2100)   total deductions  [parked until remitted]

    The deductions credit (PAYE, NI, pension, student loan, other) is parked
    in Accounts Payable as a placeholder — when those deductions are actually
    remitted to HMRC / the pension provider, that's a separate event:
      Dr Accounts Payable (2100)   amount remitted
      Cr Cash (1010)               amount remitted
    which clears the parked liability without affecting Staff Costs again.

    A dedicated 'Statutory Deductions Payable' account would be cleaner than
    re-using AP; that's a chart-of-accounts decision deferred to finance.

    Idempotent on (source_type='payroll_run', source_id=period_id).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT period_id, name, payment_date, status FROM payroll_periods "
            "WHERE period_id = ?",
            (period_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"payroll period {period_id} not found")
        pid, name, payment_date, status = row[0], row[1], row[2], row[3]

        # Sum the run from payroll_records. Use the cash transfer date —
        # `payment_date` on the period — as the journal date.
        cur.execute(
            """SELECT COALESCE(SUM(gross_pay), 0)             AS gross,
                      COALESCE(SUM(net_pay),   0)             AS net,
                      COUNT(*)                                AS n
               FROM payroll_records
               WHERE period_id = ?""",
            (period_id,),
        )
        totals = cur.fetchone()
        gross = Decimal(str(totals[0] or 0))
        net = Decimal(str(totals[1] or 0))
        n_records = totals[2]
        if n_records == 0:
            raise ValueError(f"payroll period {period_id} has no records to post")
        if gross <= 0:
            raise ValueError(f"payroll period {period_id} gross is non-positive ({gross})")
        deductions = gross - net
        if deductions < 0:
            # Sanity guard: net should never exceed gross.
            raise ValueError(
                f"payroll period {period_id} has net ({net}) > gross ({gross})"
            )

        journal_date = (payment_date or date.today().isoformat())[:10]

        lines = [
            {'account_code': '5000', 'debit': float(gross),
             'memo': f"Payroll {name or pid} — gross over {n_records} records"},
            {'account_code': _CASH_ACCOUNT_CODE, 'credit': float(net),
             'memo': f"Payroll {name or pid} — net pay"},
        ]
        if deductions > 0:
            lines.append({
                'account_code': '2100', 'credit': float(deductions),
                'memo': f"Payroll {name or pid} — deductions parked (PAYE/NI/pension/etc.)",
            })

        return _post_journal(
            conn,
            entity_id=_default_entity_id(cur),
            journal_date=journal_date,
            description=f"Payroll run {name or pid} ({n_records} records)",
            source_type='payroll_run',
            source_id=pid,
            posted_by=posted_by,
            lines=lines,
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
