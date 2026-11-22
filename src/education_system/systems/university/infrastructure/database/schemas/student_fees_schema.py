"""Student tuition finance: fee-status assessments, programme tuition rates,
tuition charges made at registration, the withdrawal / interruption
fee-liability schedule and its adjustments, sponsors (organisations,
purchase orders, agreements, invoices, payments) and the registration
hold overrides. One area audit trail (``tuition_audit``) and the area's
named-capability grants (``finance_capability_grants``).

Applied by :func:`apply_to_connection` from
``finance/domain/tuition`` and ``services/bus/finance_bus``. Additive and
idempotent; foreign keys only point at tables created here.
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS tuition_audit (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        at TEXT NOT NULL DEFAULT (datetime('now')),
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        entity TEXT NOT NULL,
        entity_id TEXT,
        student_id TEXT,
        detail_json TEXT NOT NULL DEFAULT '{}'
    )""",
    "CREATE INDEX IF NOT EXISTS ix_tuition_audit_student ON tuition_audit (student_id, at)",
    """CREATE TABLE IF NOT EXISTS finance_capability_grants (
        username TEXT NOT NULL,
        capability TEXT NOT NULL,
        granted_by TEXT NOT NULL,
        granted_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (username, capability)
    )""",
    """CREATE TABLE IF NOT EXISTS finance_hold_overrides (
        override_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        academic_year TEXT NOT NULL,
        context TEXT NOT NULL,
        hold_ids TEXT NOT NULL,
        reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
        authorised_by TEXT NOT NULL,
        authorised_role TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_finance_hold_overrides_student ON "
    "finance_hold_overrides (student_id, academic_year)",
    """CREATE TABLE IF NOT EXISTS fee_status_assessments (
        assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        academic_year TEXT NOT NULL,
        nationality TEXT,
        residence_json TEXT NOT NULL DEFAULT '[]',
        immigration_status TEXT,
        evidence_json TEXT NOT NULL DEFAULT '[]',
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'submitted'
            CHECK (status IN ('submitted', 'decided', 'superseded')),
        submitted_by TEXT NOT NULL,
        submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
        category TEXT,
        fee_basis TEXT CHECK (fee_basis IS NULL OR fee_basis IN
            ('home', 'islands', 'international')),
        decision_reason TEXT,
        decided_by TEXT,
        decided_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_fee_status_assessments_student ON "
    "fee_status_assessments (student_id, status)",
    """CREATE TABLE IF NOT EXISTS programme_tuition_rates (
        rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
        programme_code TEXT NOT NULL,
        academic_year TEXT NOT NULL,
        fee_basis TEXT NOT NULL CHECK (fee_basis IN ('home', 'islands', 'international')),
        mode_of_study TEXT NOT NULL DEFAULT 'full-time',
        fte REAL CHECK (fte IS NULL OR (fte > 0 AND fte <= 1)),
        annual_fee REAL NOT NULL CHECK (annual_fee >= 0),
        currency TEXT NOT NULL DEFAULT 'GBP',
        due_date TEXT,
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (programme_code, academic_year, fee_basis, mode_of_study, fte)
    )""",
    """CREATE TABLE IF NOT EXISTS sponsors (
        sponsor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        contact_name TEXT,
        contact_email TEXT,
        contact_phone TEXT,
        billing_address TEXT,
        vat_number TEXT,
        payment_terms_days INTEGER NOT NULL DEFAULT 30,
        active INTEGER NOT NULL DEFAULT 1,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS sponsor_purchase_orders (
        po_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sponsor_id INTEGER NOT NULL REFERENCES sponsors(sponsor_id),
        po_number TEXT NOT NULL,
        academic_year TEXT,
        amount_limit REAL,
        valid_to TEXT,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (sponsor_id, po_number)
    )""",
    """CREATE TABLE IF NOT EXISTS sponsorship_agreements (
        agreement_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sponsor_id INTEGER NOT NULL REFERENCES sponsors(sponsor_id),
        student_id TEXT NOT NULL,
        basis TEXT NOT NULL CHECK (basis IN ('percent', 'amount')),
        value REAL NOT NULL CHECK (value > 0),
        start_year INTEGER NOT NULL,
        end_year INTEGER NOT NULL,
        cap_amount REAL,
        po_id INTEGER REFERENCES sponsor_purchase_orders(po_id),
        source TEXT NOT NULL DEFAULT 'manual',
        source_ref TEXT,
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'ended', 'cancelled')),
        notes TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        CHECK (end_year >= start_year),
        CHECK (basis = 'amount' OR value <= 100)
    )""",
    "CREATE INDEX IF NOT EXISTS ix_sponsorship_agreements_student ON "
    "sponsorship_agreements (student_id, status)",
    """CREATE TABLE IF NOT EXISTS sponsor_invoices (
        invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT UNIQUE,
        sponsor_id INTEGER NOT NULL REFERENCES sponsors(sponsor_id),
        academic_year TEXT NOT NULL,
        po_number TEXT,
        status TEXT NOT NULL DEFAULT 'draft'
            CHECK (status IN ('draft', 'issued', 'paid', 'cancelled')),
        issued_at TEXT,
        issued_by TEXT,
        due_date TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS sponsor_invoice_lines (
        line_id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL REFERENCES sponsor_invoices(invoice_id),
        student_id TEXT,
        agreement_id INTEGER REFERENCES sponsorship_agreements(agreement_id),
        tuition_charge_id INTEGER,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS sponsor_payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sponsor_id INTEGER NOT NULL REFERENCES sponsors(sponsor_id),
        amount REAL NOT NULL CHECK (amount > 0),
        received_on TEXT NOT NULL,
        method TEXT,
        reference TEXT,
        recorded_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS sponsor_payment_allocations (
        allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_id INTEGER NOT NULL REFERENCES sponsor_payments(payment_id),
        invoice_id INTEGER NOT NULL REFERENCES sponsor_invoices(invoice_id),
        amount REAL NOT NULL CHECK (amount > 0),
        allocated_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS tuition_charges (
        charge_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        academic_year TEXT NOT NULL,
        programme_code TEXT,
        fee_basis TEXT,
        basis_source TEXT,
        mode_of_study TEXT,
        fte REAL,
        rate_source TEXT,
        gross_amount REAL NOT NULL DEFAULT 0,
        sponsor_amount REAL NOT NULL DEFAULT 0,
        student_amount REAL NOT NULL DEFAULT 0,
        student_fee_id INTEGER,
        agreement_id INTEGER REFERENCES sponsorship_agreements(agreement_id),
        sponsor_line_id INTEGER REFERENCES sponsor_invoice_lines(line_id),
        status TEXT NOT NULL DEFAULT 'charged' CHECK (status IN
            ('charged', 'adjusted', 'no_rate', 'no_fee_status', 'no_fee_type')),
        note TEXT,
        charged_by TEXT,
        charged_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (student_id, academic_year)
    )""",
    """CREATE TABLE IF NOT EXISTS fee_liability_schedule (
        academic_year TEXT NOT NULL DEFAULT '*',
        term_number INTEGER NOT NULL CHECK (term_number BETWEEN 0 AND 6),
        liable_percent REAL NOT NULL CHECK (liable_percent BETWEEN 0 AND 100),
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (academic_year, term_number)
    )""",
    """CREATE TABLE IF NOT EXISTS fee_liability_adjustments (
        adjustment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        history_id INTEGER UNIQUE,
        action TEXT NOT NULL,
        academic_year TEXT,
        effective_date TEXT,
        term_number INTEGER,
        liable_percent REAL,
        charge_id INTEGER REFERENCES tuition_charges(charge_id),
        gross_amount REAL NOT NULL DEFAULT 0,
        student_credit REAL NOT NULL DEFAULT 0,
        sponsor_credit REAL NOT NULL DEFAULT 0,
        fee_reduced_by REAL NOT NULL DEFAULT 0,
        student_refund_id INTEGER,
        sponsor_refund_id INTEGER,
        sponsor_line_id INTEGER REFERENCES sponsor_invoice_lines(line_id),
        status TEXT NOT NULL CHECK (status IN
            ('applied', 'needs_review', 'no_tuition', 'reversed')),
        note TEXT,
        applied_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        reversed_at TEXT
    )""",
)


def apply(execute) -> None:
    for ddl in TABLES:
        execute(ddl)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file. Inside a caller's open
    transaction it applies without committing or caching."""
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        return
    busy = conn.in_transaction
    apply(conn.execute)
    if busy:
        return
    conn.commit()
    if key:
        _APPLIED.add(key)
