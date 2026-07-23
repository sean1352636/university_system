"""GL test suite — schema, posting, period state, trial balance, backfill.

Each test gets an isolated SQLite file via the `gl_db` fixture so tests
don't pollute the dev DB or each other.
"""

import sqlite3
import pytest
from datetime import date

from education_system.post_18.university_system.infrastructure.database import db as db_module
from education_system.post_18.university_system.modules.domain.finance.ledger import (
    init_ledger, post_payment, post_refund, post_fee_assignment, post_payroll_run,
    backfill, trial_balance, close_period, lock_period, reopen_period,
    JournalUnbalancedError, PeriodClosedError, AccountNotFoundError,
)
from education_system.post_18.university_system.modules.domain.finance.ledger.posting import _post_journal
from education_system.post_18.university_system.modules.domain.finance.ledger.periods import PeriodStateError


@pytest.fixture
def gl_db(tmp_path, monkeypatch):
    """Point the DB layer at a fresh temp file, init the ledger, and seed
    minimal operational tables that posting functions read from.
    """
    db_path = str(tmp_path / "ledger_test.db")
    monkeypatch.setattr(db_module, 'DEFAULT_DB_PATH', db_path)

    # Seed operational tables that posting functions query
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, amount DECIMAL(10,2), payment_date TEXT,
            source_type TEXT, payment_method TEXT, notes TEXT, status TEXT,
            vat_rate TEXT, vat_amount REAL, payment_type TEXT
        );
        CREATE TABLE unified_refunds (
            refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, amount DECIMAL(10,2), refund_date TEXT,
            source_type TEXT, refund_method TEXT, notes TEXT, status TEXT,
            requested_by TEXT, approved_by TEXT, processed_by TEXT,
            vat_rate TEXT, vat_amount REAL
        );
        CREATE TABLE fee_types (
            fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_name TEXT
        );
        CREATE TABLE student_fees (
            student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, fee_type_id INTEGER, amount DECIMAL(10,2),
            currency TEXT, status TEXT, due_date TEXT, created_at TEXT
        );
        CREATE TABLE payroll_periods (
            period_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, period_type TEXT, start_date TEXT, end_date TEXT,
            payment_date TEXT, status TEXT
        );
        CREATE TABLE payroll_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_id INTEGER, user_id TEXT,
            basic_salary REAL, overtime_pay REAL, allowances_total REAL,
            gross_pay REAL, tax_deduction REAL, ni_deduction REAL,
            pension_deduction REAL, net_pay REAL
        );
        INSERT INTO fee_types (fee_type_id, fee_name) VALUES (1, 'Tuition Home/EU'), (2, 'Accommodation');
    """)
    conn.commit()
    conn.close()

    init_ledger()
    return db_path


# ---------------------------------------------------------------------------
# Schema / seed
# ---------------------------------------------------------------------------

class TestSchemaSeed:
    def test_init_creates_all_tables(self, gl_db):
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        names = {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert {'gl_entities', 'gl_accounts', 'gl_periods',
                'gl_journals', 'gl_journal_lines'} <= names

    def test_default_entity_seeded(self, gl_db):
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        cur.execute("SELECT entity_code FROM gl_entities")
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 'UNI'

    def test_chart_seeded_with_required_codes(self, gl_db):
        conn = sqlite3.connect(gl_db)
        codes = {r[0] for r in conn.execute(
            "SELECT account_code FROM gl_accounts"
        ).fetchall()}
        # Codes that posting rules depend on
        for required in ('1010', '1110', '1120', '1130', '2500',
                         '4000', '4001', '4010', '4310', '4340', '4350', '4360'):
            assert required in codes, f"Missing required account {required}"

    def test_periods_cover_full_fiscal_year(self, gl_db):
        conn = sqlite3.connect(gl_db)
        rows = conn.execute(
            "SELECT period_no, fiscal_year FROM gl_periods ORDER BY period_no"
        ).fetchall()
        assert [r[0] for r in rows] == list(range(1, 13))
        assert len({r[1] for r in rows}) == 1  # all in same FY

    def test_init_is_idempotent(self, gl_db):
        # Re-running shouldn't duplicate
        init_ledger()
        init_ledger()
        conn = sqlite3.connect(gl_db)
        assert conn.execute("SELECT COUNT(*) FROM gl_entities").fetchone()[0] == 1
        # Chart row count is fixed by SORP_CHART
        from education_system.post_18.university_system.modules.domain.finance.ledger.seed import SORP_CHART
        assert conn.execute("SELECT COUNT(*) FROM gl_accounts").fetchone()[0] == len(SORP_CHART)


# ---------------------------------------------------------------------------
# Posting — payments
# ---------------------------------------------------------------------------

class TestPostPayment:
    def _seed_payment(self, gl_db, **kw):
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payments (student_id, amount, payment_date, source_type, "
            "payment_method, notes, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kw.get('student_id', 'S001'), kw.get('amount', 100.00),
             kw.get('payment_date', date.today().isoformat()),
             kw.get('source_type', 'general'),
             kw.get('payment_method', 'card'),
             kw.get('notes'), 'completed'),
        )
        pid = cur.lastrowid
        conn.commit()
        conn.close()
        return pid

    def test_creates_balanced_journal(self, gl_db):
        pid = self._seed_payment(gl_db, amount=250.00)
        jid = post_payment(pid)

        conn = sqlite3.connect(gl_db)
        # Two lines, balanced
        rows = conn.execute(
            "SELECT debit, credit FROM gl_journal_lines WHERE journal_id = ?", (jid,)
        ).fetchall()
        assert len(rows) == 2
        assert sum(float(r[0]) for r in rows) == sum(float(r[1]) for r in rows) == 250.00

    def test_credits_correct_revenue_for_source_type(self, gl_db):
        pid = self._seed_payment(gl_db, amount=50.00, source_type='club')
        jid = post_payment(pid)
        conn = sqlite3.connect(gl_db)
        # Find the credit line's account code
        row = conn.execute(
            "SELECT a.account_code FROM gl_journal_lines l "
            "JOIN gl_accounts a ON a.account_id = l.account_id "
            "WHERE l.journal_id = ? AND l.credit > 0", (jid,)
        ).fetchone()
        assert row[0] == '4340'  # Club / Membership Income

    def test_topup_credits_liability_not_revenue(self, gl_db):
        pid = self._seed_payment(gl_db, amount=20.00, source_type='bank_topup')
        jid = post_payment(pid)
        conn = sqlite3.connect(gl_db)
        row = conn.execute(
            "SELECT a.account_code FROM gl_journal_lines l "
            "JOIN gl_accounts a ON a.account_id = l.account_id "
            "WHERE l.journal_id = ? AND l.credit > 0", (jid,)
        ).fetchone()
        assert row[0] == '2500'  # Student Account Liability — top-ups aren't revenue

    def test_idempotent(self, gl_db):
        pid = self._seed_payment(gl_db)
        jid_1 = post_payment(pid)
        jid_2 = post_payment(pid)
        assert jid_1 == jid_2
        conn = sqlite3.connect(gl_db)
        assert conn.execute(
            "SELECT COUNT(*) FROM gl_journals WHERE source_type='payment' AND source_id=?",
            (pid,)).fetchone()[0] == 1


# ---------------------------------------------------------------------------
# Posting — refunds
# ---------------------------------------------------------------------------

class TestPostRefund:
    def test_refund_reverses_revenue(self, gl_db):
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO unified_refunds (student_id, amount, refund_date, source_type, "
            "refund_method, status, requested_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ('S001', 75.00, date.today().isoformat(), 'general', 'card', 'approved', 'admin'),
        )
        rid = cur.lastrowid
        conn.commit()
        conn.close()

        jid = post_refund(rid)
        conn = sqlite3.connect(gl_db)
        debit_row = conn.execute(
            "SELECT a.account_code FROM gl_journal_lines l "
            "JOIN gl_accounts a ON a.account_id = l.account_id "
            "WHERE l.journal_id = ? AND l.debit > 0", (jid,)
        ).fetchone()
        credit_row = conn.execute(
            "SELECT a.account_code FROM gl_journal_lines l "
            "JOIN gl_accounts a ON a.account_id = l.account_id "
            "WHERE l.journal_id = ? AND l.credit > 0", (jid,)
        ).fetchone()
        # Refund: Dr revenue, Cr cash — opposite of payment
        assert debit_row[0] == '4000'   # Tuition (Home/EU) — reversed
        assert credit_row[0] == '1010'  # Cash


# ---------------------------------------------------------------------------
# Posting — fee assignments
# ---------------------------------------------------------------------------

class TestPostFeeAssignment:
    def test_creates_ar_and_revenue(self, gl_db):
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO student_fees (student_id, fee_type_id, amount, status, due_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ('S001', 1, 9000.00, 'pending', '2025-09-01', '2025-08-15'),
        )
        sfid = cur.lastrowid
        conn.commit()
        conn.close()

        jid = post_fee_assignment(sfid)
        conn = sqlite3.connect(gl_db)
        debit_row = conn.execute(
            "SELECT a.account_code, l.debit FROM gl_journal_lines l "
            "JOIN gl_accounts a ON a.account_id = l.account_id "
            "WHERE l.journal_id = ? AND l.debit > 0", (jid,)
        ).fetchone()
        assert debit_row[0] == '1110'  # AR — Tuition (Home/EU)
        assert float(debit_row[1]) == 9000.00


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_unbalanced_journal_rejected(self, gl_db):
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        with pytest.raises(JournalUnbalancedError):
            _post_journal(
                conn, entity_id=1, journal_date=date.today().isoformat(),
                description='bad', source_type='manual', source_id=999,
                posted_by='test',
                lines=[
                    {'account_code': '1010', 'debit': 100.00},
                    {'account_code': '4000', 'credit': 50.00},  # mismatched
                ],
            )

    def test_single_line_journal_rejected(self, gl_db):
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        with pytest.raises(JournalUnbalancedError):
            _post_journal(
                conn, entity_id=1, journal_date=date.today().isoformat(),
                description='bad', source_type='manual', source_id=998,
                posted_by='test',
                lines=[{'account_code': '1010', 'debit': 100.00}],
            )

    def test_unknown_account_rejected(self, gl_db):
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        with pytest.raises(AccountNotFoundError):
            _post_journal(
                conn, entity_id=1, journal_date=date.today().isoformat(),
                description='bad', source_type='manual', source_id=997,
                posted_by='test',
                lines=[
                    {'account_code': '9999', 'debit': 50.00},
                    {'account_code': '4000', 'credit': 50.00},
                ],
            )


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------

class TestPeriods:
    def _today_period_id(self, gl_db):
        conn = sqlite3.connect(gl_db)
        today = date.today().isoformat()
        row = conn.execute(
            "SELECT period_id FROM gl_periods WHERE start_date <= ? AND end_date >= ?",
            (today, today),
        ).fetchone()
        return row[0] if row else None

    def test_close_blocks_posting(self, gl_db):
        pid_period = self._today_period_id(gl_db)
        if pid_period is None:
            pytest.skip("Today's date isn't covered by seeded periods")

        # Close current period
        close_period(pid_period, closed_by='admin')

        # Try to post a payment dated today — should fail
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payments (student_id, amount, payment_date, source_type, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ('S001', 10.00, date.today().isoformat(), 'general', 'completed'),
        )
        pay_id = cur.lastrowid
        conn.commit()
        conn.close()

        with pytest.raises(PeriodClosedError):
            post_payment(pay_id)

    def test_reopen_after_close(self, gl_db):
        pid_period = self._today_period_id(gl_db)
        if pid_period is None:
            pytest.skip("Today's date isn't covered by seeded periods")
        close_period(pid_period, closed_by='admin')
        reopen_period(pid_period)
        # Should now post fine
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payments (student_id, amount, payment_date, source_type, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ('S001', 20.00, date.today().isoformat(), 'general', 'completed'),
        )
        pay_id = cur.lastrowid
        conn.commit()
        conn.close()
        post_payment(pay_id)  # should not raise

    def test_lock_cannot_be_reopened(self, gl_db):
        pid_period = self._today_period_id(gl_db)
        if pid_period is None:
            pytest.skip("Today's date isn't covered by seeded periods")
        lock_period(pid_period, locked_by='auditor')
        with pytest.raises(PeriodStateError):
            reopen_period(pid_period)


# ---------------------------------------------------------------------------
# Trial balance
# ---------------------------------------------------------------------------

class TestTrialBalance:
    def test_balanced_after_payments(self, gl_db):
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        for amt in (100.00, 250.00, 75.50):
            cur.execute(
                "INSERT INTO payments (student_id, amount, payment_date, source_type, status) "
                "VALUES (?, ?, ?, ?, ?)",
                ('S001', amt, date.today().isoformat(), 'general', 'completed'),
            )
        conn.commit()
        # Post all
        ids = [r[0] for r in cur.execute("SELECT payment_id FROM payments").fetchall()]
        conn.close()
        for pid in ids:
            post_payment(pid)

        rows = trial_balance()
        total_dr = sum(r['debit_total'] for r in rows)
        total_cr = sum(r['credit_total'] for r in rows)
        assert abs(total_dr - total_cr) < 0.01
        assert total_dr == pytest.approx(425.50)


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

class TestBackfill:
    def test_backfill_idempotent(self, gl_db):
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payments (student_id, amount, payment_date, source_type, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ('S001', 100.00, date.today().isoformat(), 'general', 'completed'),
        )
        cur.execute(
            "INSERT INTO unified_refunds (student_id, amount, refund_date, source_type, status, requested_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ('S001', 30.00, date.today().isoformat(), 'general', 'approved', 'admin'),
        )
        conn.commit()
        conn.close()

        s1 = backfill()
        assert s1['posted'] == 2  # 1 payment + 1 refund
        assert len(s1['errors']) == 0

        # Second run: idempotent — UNIQUE constraint blocks reposting
        s2 = backfill()
        # Errors will contain UNIQUE-constraint failures, posted will be 0 effective
        # (the wrapper counts attempts as "posted" only if no exception, so re-runs
        # surface as errors). Verify journal count didn't grow.
        conn = sqlite3.connect(gl_db)
        n = conn.execute("SELECT COUNT(*) FROM gl_journals").fetchone()[0]
        assert n == 2


# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------

class TestPostPayrollRun:
    def _seed_period(self, gl_db, *, payment_date=None, name='2026-04 Salaries'):
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payroll_periods (name, period_type, start_date, end_date, "
            "payment_date, status) VALUES (?, 'monthly', '2026-04-01', '2026-04-30', ?, 'completed')",
            (name, payment_date or date.today().isoformat()),
        )
        period_id = cur.lastrowid
        conn.commit()
        conn.close()
        return period_id

    def _seed_records(self, gl_db, period_id, rows):
        """rows is a list of (gross, net) tuples."""
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        for i, (gross, net) in enumerate(rows):
            cur.execute(
                "INSERT INTO payroll_records (period_id, user_id, basic_salary, gross_pay, net_pay) "
                "VALUES (?, ?, ?, ?, ?)",
                (period_id, f"U{i:03d}", gross, gross, net),
            )
        conn.commit()
        conn.close()

    def test_creates_balanced_3_line_journal(self, gl_db):
        period_id = self._seed_period(gl_db)
        # 3 employees: gross 3000 each, net 2400 each → total gross 9000, net 7200, deductions 1800
        self._seed_records(gl_db, period_id, [(3000.0, 2400.0)] * 3)

        jid = post_payroll_run(period_id)

        conn = sqlite3.connect(gl_db)
        # Lines should be Dr 5000 9000, Cr 1010 7200, Cr 2100 1800
        rows = conn.execute(
            """SELECT a.account_code, l.debit, l.credit
               FROM gl_journal_lines l JOIN gl_accounts a ON a.account_id = l.account_id
               WHERE l.journal_id = ?
               ORDER BY a.account_code""",
            (jid,),
        ).fetchall()
        rows = [(c, float(d or 0), float(cr or 0)) for c, d, cr in rows]
        assert ('1010', 0.0, 7200.0) in rows
        assert ('2100', 0.0, 1800.0) in rows
        assert ('5000', 9000.0, 0.0) in rows
        # Balanced
        assert sum(r[1] for r in rows) == sum(r[2] for r in rows) == 9000.0

    def test_no_deductions_skips_ap_credit(self, gl_db):
        # Edge case: gross == net (no deductions). Journal should be 2 lines, not 3.
        period_id = self._seed_period(gl_db, name='No-deductions period')
        self._seed_records(gl_db, period_id, [(1000.0, 1000.0)])

        jid = post_payroll_run(period_id)
        conn = sqlite3.connect(gl_db)
        n_lines = conn.execute(
            "SELECT COUNT(*) FROM gl_journal_lines WHERE journal_id = ?", (jid,),
        ).fetchone()[0]
        assert n_lines == 2  # Dr Staff Costs, Cr Cash only

    def test_idempotent(self, gl_db):
        period_id = self._seed_period(gl_db, name='Idempotency test')
        self._seed_records(gl_db, period_id, [(2000.0, 1700.0)])
        j1 = post_payroll_run(period_id)
        j2 = post_payroll_run(period_id)
        assert j1 == j2
        conn = sqlite3.connect(gl_db)
        n = conn.execute(
            "SELECT COUNT(*) FROM gl_journals WHERE source_type = 'payroll_run' AND source_id = ?",
            (period_id,),
        ).fetchone()[0]
        assert n == 1

    def test_empty_period_rejected(self, gl_db):
        period_id = self._seed_period(gl_db, name='Empty period')
        # No payroll_records inserted
        with pytest.raises(ValueError, match="no records"):
            post_payroll_run(period_id)

    def test_net_exceeds_gross_rejected(self, gl_db):
        period_id = self._seed_period(gl_db, name='Bad period')
        # net > gross is a calculation error; should refuse to post
        self._seed_records(gl_db, period_id, [(1000.0, 1100.0)])
        with pytest.raises(ValueError, match="net.*>.*gross"):
            post_payroll_run(period_id)


# ---------------------------------------------------------------------------
# VAT
# ---------------------------------------------------------------------------

class TestVATPayments:
    def _seed_payment(self, gl_db, **kw):
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payments (student_id, amount, payment_date, source_type, "
            "payment_method, status, vat_rate, vat_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (kw.get('student_id', 'S001'), kw.get('amount', 120.00),
             kw.get('payment_date', date.today().isoformat()),
             kw.get('source_type', 'restaurant'),
             kw.get('payment_method', 'card'),
             'completed',
             kw.get('vat_rate'), kw.get('vat_amount')),
        )
        pid = cur.lastrowid
        conn.commit()
        conn.close()
        return pid

    def test_standard_rated_source_splits_vat(self, gl_db):
        # £120 gross at 20% VAT → £100 net + £20 VAT
        pid = self._seed_payment(gl_db, source_type='restaurant', amount=120.00)
        jid = post_payment(pid)

        conn = sqlite3.connect(gl_db)
        rows = conn.execute(
            """SELECT a.account_code, l.debit, l.credit
               FROM gl_journal_lines l JOIN gl_accounts a ON a.account_id = l.account_id
               WHERE l.journal_id = ? ORDER BY a.account_code""",
            (jid,),
        ).fetchall()
        rows = [(c, float(d or 0), float(cr or 0)) for c, d, cr in rows]
        assert ('1010', 120.00, 0.0) in rows   # Cash gross
        assert ('2200', 0.0,    20.00) in rows # VAT Output
        # Revenue line at NET (100). Account is whatever maps from 'restaurant'.
        revenue_line = [r for r in rows if r[0] not in ('1010', '2200')]
        assert len(revenue_line) == 1
        assert revenue_line[0][2] == 100.00
        # Balanced
        assert sum(r[1] for r in rows) == sum(r[2] for r in rows) == 120.00

    def test_exempt_source_keeps_2_line_journal(self, gl_db):
        # Tuition is exempt → 2-line journal, no VAT split
        pid = self._seed_payment(gl_db, source_type='tuition', amount=100.00)
        jid = post_payment(pid)
        conn = sqlite3.connect(gl_db)
        n = conn.execute("SELECT COUNT(*) FROM gl_journal_lines WHERE journal_id = ?",
                         (jid,)).fetchone()[0]
        assert n == 2  # Cash + Revenue, no VAT

    def test_zero_rated_source_keeps_2_line_journal(self, gl_db):
        # Train (passenger transport) is zero-rated → no VAT line
        pid = self._seed_payment(gl_db, source_type='train', amount=10.00)
        jid = post_payment(pid)
        conn = sqlite3.connect(gl_db)
        n = conn.execute("SELECT COUNT(*) FROM gl_journal_lines WHERE journal_id = ?",
                         (jid,)).fetchone()[0]
        assert n == 2

    def test_explicit_vat_amount_overrides_default(self, gl_db):
        # £100 with explicit £15 VAT (not the standard-rate 16.67)
        pid = self._seed_payment(gl_db, source_type='restaurant',
                                 amount=100.00, vat_rate='reduced', vat_amount=5.00)
        jid = post_payment(pid)
        conn = sqlite3.connect(gl_db)
        vat = conn.execute(
            "SELECT credit FROM gl_journal_lines l "
            "JOIN gl_accounts a ON a.account_id = l.account_id "
            "WHERE l.journal_id = ? AND a.account_code = '2200'",
            (jid,),
        ).fetchone()
        assert float(vat[0]) == 5.00

    def test_topup_never_splits_vat(self, gl_db):
        # bank_topup must always be 2-line (Dr Cash, Cr Liability) — never VAT
        pid = self._seed_payment(gl_db, source_type='bank_topup', amount=50.00,
                                 vat_rate='standard')  # ignored on top-ups
        jid = post_payment(pid)
        conn = sqlite3.connect(gl_db)
        rows = conn.execute(
            "SELECT a.account_code FROM gl_journal_lines l "
            "JOIN gl_accounts a ON a.account_id = l.account_id "
            "WHERE l.journal_id = ?", (jid,),
        ).fetchall()
        codes = {r[0] for r in rows}
        assert codes == {'1010', '2500'}  # Cash + Student Account Liability only


class TestVATRefunds:
    def _seed_refund(self, gl_db, **kw):
        conn = sqlite3.connect(gl_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO unified_refunds (student_id, amount, refund_date, source_type, "
            "refund_method, status, requested_by, vat_rate, vat_amount) "
            "VALUES (?, ?, ?, ?, ?, 'processed', 'admin', ?, ?)",
            (kw.get('student_id', 'S001'), kw.get('amount', 60.00),
             kw.get('refund_date', date.today().isoformat()),
             kw.get('source_type', 'restaurant'),
             kw.get('refund_method', 'card'),
             kw.get('vat_rate'), kw.get('vat_amount')),
        )
        rid = cur.lastrowid
        conn.commit()
        conn.close()
        return rid

    def test_standard_refund_reverses_vat(self, gl_db):
        # £60 gross refund at 20% → £50 net (Dr Revenue), £10 VAT (Dr 2200), £60 Cr Cash
        rid = self._seed_refund(gl_db, source_type='restaurant', amount=60.00)
        jid = post_refund(rid)
        conn = sqlite3.connect(gl_db)
        rows = conn.execute(
            """SELECT a.account_code, l.debit, l.credit
               FROM gl_journal_lines l JOIN gl_accounts a ON a.account_id = l.account_id
               WHERE l.journal_id = ?""",
            (jid,),
        ).fetchall()
        rows = [(c, float(d or 0), float(cr or 0)) for c, d, cr in rows]
        # VAT Output is debited (reversing the previous output)
        vat_line = [r for r in rows if r[0] == '2200']
        assert vat_line and vat_line[0][1] == 10.00 and vat_line[0][2] == 0.0
        # Cash credited at gross
        cash_line = [r for r in rows if r[0] == '1010']
        assert cash_line[0][2] == 60.00
        # Balanced
        assert sum(r[1] for r in rows) == sum(r[2] for r in rows) == 60.00

    def test_exempt_refund_keeps_2_line_journal(self, gl_db):
        rid = self._seed_refund(gl_db, source_type='tuition', amount=50.00)
        jid = post_refund(rid)
        conn = sqlite3.connect(gl_db)
        n = conn.execute("SELECT COUNT(*) FROM gl_journal_lines WHERE journal_id = ?",
                         (jid,)).fetchone()[0]
        assert n == 2
