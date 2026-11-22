"""Invoices, payments, funding claims, childcare vouchers and fee discounts.

Split out of ``database.py``, which imports every name here and keeps
``connect``/``init_db``. Import from ``database``, not from here.
"""

from __future__ import annotations


# ── Finance ──────────────────────────────────────────────────────────────────

# ``invoices`` = fee invoices raised to a child's account. ``total_amount`` is
# the net of gross fees less funded-hours deduction and any discount; the paid
# balance is derived from ``payments`` rows referencing the invoice.
_INVOICES_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id       TEXT PRIMARY KEY,
    pupil_id         TEXT NOT NULL,
    period           TEXT,
    issue_date       TEXT,
    due_date         TEXT,
    hours_billed     REAL,
    hourly_rate      REAL,
    gross_amount     REAL NOT NULL DEFAULT 0,
    funded_deduction REAL NOT NULL DEFAULT 0,
    discount_amount  REAL NOT NULL DEFAULT 0,
    total_amount     REAL NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'draft',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_invoices_pupil  ON invoices(pupil_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
"""

# ``payments`` = money received, optionally allocated to an invoice. Methods
# include the voucher / Tax-Free Childcare schemes registered in
# ``childcare_vouchers``.
_PAYMENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    payment_id   TEXT PRIMARY KEY,
    pupil_id     TEXT NOT NULL,
    invoice_id   TEXT,
    amount       REAL NOT NULL DEFAULT 0,
    method       TEXT,
    payment_date TEXT,
    reference    TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_payments_pupil   ON payments(pupil_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
"""

# ``funding_claims`` = claims to the local authority for funded entitlement
# hours. ``claim_amount`` = funded_hours/week × weeks × hourly_rate.
_FUNDING_CLAIMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS funding_claims (
    claim_id       TEXT PRIMARY KEY,
    pupil_id       TEXT,
    funding_period TEXT,
    entitlement    TEXT,
    funded_hours   REAL,
    weeks          REAL,
    hourly_rate    REAL,
    claim_amount   REAL NOT NULL DEFAULT 0,
    headcount_date TEXT,
    status         TEXT NOT NULL DEFAULT 'draft',
    submitted_date TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_funding_claims_status ON funding_claims(status);
"""

# ``childcare_vouchers`` = registered Tax-Free Childcare / employer-voucher
# arrangements per child (the standing arrangement; actual receipts are logged
# as ``payments`` with the matching method).
_VOUCHERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS childcare_vouchers (
    voucher_id      TEXT PRIMARY KEY,
    pupil_id        TEXT NOT NULL,
    scheme          TEXT,
    provider        TEXT,
    account_ref     TEXT,
    expected_amount REAL,
    status          TEXT NOT NULL DEFAULT 'active',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vouchers_pupil ON childcare_vouchers(pupil_id);
"""

# ``fee_discounts`` = discount arrangements (sibling, staff, bursary) applied to
# a child's fees. Either a percentage or a fixed monthly amount.
_DISCOUNTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS fee_discounts (
    discount_id   TEXT PRIMARY KEY,
    pupil_id      TEXT NOT NULL,
    discount_type TEXT,
    percentage    REAL,
    fixed_amount  REAL,
    reason        TEXT,
    start_date    TEXT,
    end_date      TEXT,
    status        TEXT NOT NULL DEFAULT 'active',
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_discounts_pupil ON fee_discounts(pupil_id);
"""
