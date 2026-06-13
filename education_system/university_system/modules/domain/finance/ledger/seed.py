"""Seed default entity, simplified UK SORP chart of accounts, and current FY periods.

Each helper takes an open connection and is idempotent. The chart structure
mirrors UK HE/FE Statement of Recommended Practice categories at a level
sufficient to post the platform's existing operational events. Finance staff
can rename, restructure, or extend after init — account_code is text and
parent_account_id supports hierarchy.
"""

from datetime import date, timedelta
from calendar import monthrange


DEFAULT_ENTITY = ('UNI', 'University (Default Entity)')


# (code, name, type, parent_code or None)
# Codes follow a 4-digit convention with type-driven leading digit:
#   1xxx assets, 2xxx liabilities, 3xxx equity, 4xxx income, 5xxx expense
SORP_CHART = [
    # ---- ASSETS ----
    ('1000', 'Cash & Bank',                    'asset',     None),
    ('1010', 'Bank — Operating Account',       'asset',     '1000'),
    ('1020', 'Bank — Reserve Account',         'asset',     '1000'),
    ('1100', 'Accounts Receivable',            'asset',     None),
    ('1110', 'AR — Tuition (Home/EU)',         'asset',     '1100'),
    ('1120', 'AR — Tuition (International)',   'asset',     '1100'),
    ('1130', 'AR — Accommodation',             'asset',     '1100'),
    ('1140', 'AR — Other',                     'asset',     '1100'),
    ('1300', 'VAT Input (Recoverable)',        'asset',     None),

    # ---- LIABILITIES ----
    ('2100', 'Accounts Payable',               'liability', None),
    ('2200', 'VAT Output',                     'liability', None),
    ('2300', 'Deferred Income',                'liability', None),  # reserved; unused on cash basis
    ('2500', 'Student Account Liabilities',    'liability', None),  # student bank-app top-ups not yet spent
    ('2510', 'Tenant Deposits Held',           'liability', None),  # refundable housing deposits — released against damages or returned at move-out
    ('2400', 'Long-term Loans',                'liability', None),

    # ---- EQUITY ----
    ('3000', 'Reserves',                       'equity',    None),
    ('3100', 'Retained Surplus',               'equity',    None),

    # ---- INCOME ----
    ('4000', 'Tuition Fees — Home/EU',         'revenue',   None),
    ('4001', 'Tuition Fees — International',   'revenue',   None),
    ('4010', 'Tuition Fees — Postgraduate',    'revenue',   None),
    ('4100', 'Funding Body Grants',            'revenue',   None),
    ('4200', 'Research Grants & Contracts',    'revenue',   None),
    ('4300', 'Other Income',                   'revenue',   None),
    ('4310', 'Late Fee Income',                'revenue',   '4300'),
    ('4320', 'Application Fees',               'revenue',   '4300'),
    ('4330', 'Library Fines',                  'revenue',   '4300'),
    ('4340', 'Club / Membership Income',       'revenue',   '4300'),
    ('4350', 'Catering / Commerce',            'revenue',   '4300'),
    ('4360', 'Accommodation Income',           'revenue',   '4300'),

    # ---- EXPENSE ----
    ('5000', 'Staff Costs',                    'expense',   None),
    ('5010', 'Salaries — Academic',            'expense',   '5000'),
    ('5020', 'Salaries — Admin',               'expense',   '5000'),
    ('5030', 'Pensions & NI',                  'expense',   '5000'),
    ('5100', 'Premises Costs',                 'expense',   None),
    ('5200', 'Bursaries & Scholarships',       'expense',   None),
    ('5300', 'Bad Debt Write-off',             'expense',   None),
    ('5400', 'Other Operating Expenses',       'expense',   None),
]


def seed_default_entity(conn):
    """Insert the default entity if no entities exist yet."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM gl_entities")
    if cur.fetchone()[0] > 0:
        return
    cur.execute(
        "INSERT INTO gl_entities (entity_code, entity_name) VALUES (?, ?)",
        DEFAULT_ENTITY,
    )


def seed_chart_of_accounts(conn):
    """Insert the SORP chart. Skips any account_code that already exists."""
    cur = conn.cursor()

    # First pass: insert root accounts (parent_code is None) so children find them.
    code_to_id = {}
    cur.execute("SELECT account_code, account_id FROM gl_accounts")
    for code, aid in cur.fetchall():
        code_to_id[code] = aid

    for code, name, atype, parent_code in SORP_CHART:
        if code in code_to_id:
            continue
        if parent_code is None:
            cur.execute(
                "INSERT INTO gl_accounts (account_code, account_name, account_type, parent_account_id) "
                "VALUES (?, ?, ?, NULL)",
                (code, name, atype),
            )
            code_to_id[code] = cur.lastrowid

    # Second pass: insert children, resolving parent_id from the map.
    for code, name, atype, parent_code in SORP_CHART:
        if code in code_to_id:
            continue
        parent_id = code_to_id.get(parent_code) if parent_code else None
        cur.execute(
            "INSERT INTO gl_accounts (account_code, account_name, account_type, parent_account_id) "
            "VALUES (?, ?, ?, ?)",
            (code, name, atype, parent_id),
        )
        code_to_id[code] = cur.lastrowid


def _uk_he_fiscal_year_for(d: date):
    """Map a calendar date to a UK HE fiscal year (1 Aug → 31 Jul).

    A date on 2025-08-01 belongs to FY 2026 (the year it ends in).
    A date on 2025-07-31 belongs to FY 2025.
    """
    return d.year + 1 if d.month >= 8 else d.year


def _periods_for_fiscal_year(fy: int):
    """Yield (period_no, start_date, end_date) for a UK HE fiscal year FY=fy.

    Period 1 = August of (fy-1), period 12 = July of fy.
    """
    for period_no in range(1, 13):
        if period_no <= 5:           # Aug (1), Sep (2), Oct (3), Nov (4), Dec (5)
            month = period_no + 7
            year = fy - 1
        else:                        # Jan..Jul = period 6..12
            month = period_no - 5
            year = fy
        days = monthrange(year, month)[1]
        start = date(year, month, 1).isoformat()
        end = date(year, month, days).isoformat()
        yield period_no, start, end


def seed_current_fiscal_year_periods(conn, today=None):
    """Ensure 12 monthly periods exist for the fiscal year containing today.

    Idempotent — UNIQUE(fiscal_year, period_no) means re-running silently
    skips already-seeded periods.
    """
    today = today or date.today()
    fy = _uk_he_fiscal_year_for(today)
    cur = conn.cursor()
    for period_no, start, end in _periods_for_fiscal_year(fy):
        cur.execute(
            "INSERT OR IGNORE INTO gl_periods (fiscal_year, period_no, start_date, end_date, status) "
            "VALUES (?, ?, ?, ?, 'open')",
            (fy, period_no, start, end),
        )
