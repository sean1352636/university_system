"""Bank reconciliation tests."""

import csv
import sqlite3
import pytest
from datetime import date, timedelta

from education_system.university_system.infrastructure.database import db as db_module
from education_system.university_system.modules.domain.finance.bank_rec import (
    init_bank_rec, import_csv, auto_match_statement,
    manual_match, unmatch, discard, list_statements, list_lines,
)


@pytest.fixture
def br_db(tmp_path, monkeypatch):
    """Fresh DB with bank_rec schema and minimal payments/unified_refunds tables
    so the auto-matcher has something to look at."""
    db_path = str(tmp_path / "br_test.db")
    monkeypatch.setattr(db_module, 'DEFAULT_DB_PATH', db_path)

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, amount DECIMAL(10,2), payment_date TEXT,
            transaction_id TEXT, payment_reference TEXT, notes TEXT, status TEXT
        );
        CREATE TABLE unified_refunds (
            refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, amount DECIMAL(10,2), refund_date TEXT,
            refund_reference TEXT, notes TEXT, status TEXT
        );
    """)
    conn.commit()
    conn.close()
    init_bank_rec()
    return db_path


def _write_csv(tmp_path, rows):
    p = tmp_path / "stmt.csv"
    with open(p, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['date', 'amount', 'description', 'reference'])
        w.writerows(rows)
    return str(p)


class TestImport:
    def test_basic_import(self, br_db, tmp_path):
        path = _write_csv(tmp_path, [
            ('2026-04-01', '100.00', 'Card payment',  'PAY-001'),
            ('2026-04-02', '-25.50', 'Refund',         'REF-001'),
            ('2026-04-03', '50.00',  'Bank transfer',  ''),
        ])
        result = import_csv(path, account_name='Operating', imported_by='admin')
        assert result['lines_imported'] == 3
        assert result['errors'] == []

        lines = list_lines(result['statement_id'])
        assert len(lines) == 3
        assert lines[0]['amount'] == 100.0
        assert lines[1]['amount'] == -25.5

    def test_amount_currency_symbol_stripped(self, br_db, tmp_path):
        path = _write_csv(tmp_path, [
            ('2026-04-01', '£1,234.56', 'with quid', ''),
        ])
        result = import_csv(path, account_name='Op')
        assert result['lines_imported'] == 1
        assert list_lines(result['statement_id'])[0]['amount'] == 1234.56

    def test_missing_required_column(self, br_db, tmp_path):
        p = tmp_path / "bad.csv"
        with open(p, 'w', newline='', encoding='utf-8') as fh:
            fh.write("description,reference\nfoo,bar\n")
        result = import_csv(str(p), account_name='Op')
        assert result['lines_imported'] == 0
        assert any('date' in e or 'amount' in e for e in result['errors'])


class TestAutoMatch:
    def _seed_payment(self, br_db, *, amount, payment_date, ref=None):
        conn = sqlite3.connect(br_db)
        cur = conn.execute(
            "INSERT INTO payments (student_id, amount, payment_date, "
            "payment_reference, status) VALUES ('S001', ?, ?, ?, 'completed')",
            (amount, payment_date, ref),
        )
        pid = cur.lastrowid
        conn.commit()
        conn.close()
        return pid

    def _seed_refund(self, br_db, *, amount, refund_date, ref=None):
        conn = sqlite3.connect(br_db)
        cur = conn.execute(
            "INSERT INTO unified_refunds (student_id, amount, refund_date, "
            "refund_reference, status) VALUES ('S001', ?, ?, ?, 'processed')",
            (amount, refund_date, ref),
        )
        rid = cur.lastrowid
        conn.commit()
        conn.close()
        return rid

    def test_unique_match(self, br_db, tmp_path):
        # One unmatched line, one matching payment → match
        pid = self._seed_payment(br_db, amount=100.00, payment_date='2026-04-01')
        path = _write_csv(tmp_path, [('2026-04-01', '100.00', 'card', '')])
        sid = import_csv(path, account_name='Op')['statement_id']

        result = auto_match_statement(sid)
        assert result['matched'] == 1
        assert result['ambiguous'] == 0

        line = list_lines(sid)[0]
        assert line['status'] == 'matched_auto'
        assert line['matched_payment_id'] == pid

    def test_ambiguous_left_for_review(self, br_db, tmp_path):
        # Two payments at the same amount and date → ambiguous (no match)
        self._seed_payment(br_db, amount=50.00, payment_date='2026-04-05')
        self._seed_payment(br_db, amount=50.00, payment_date='2026-04-05')
        path = _write_csv(tmp_path, [('2026-04-05', '50.00', 'card', '')])
        sid = import_csv(path, account_name='Op')['statement_id']

        result = auto_match_statement(sid)
        assert result['matched'] == 0
        assert result['ambiguous'] == 1
        assert list_lines(sid)[0]['status'] == 'unmatched'

    def test_reference_breaks_tie(self, br_db, tmp_path):
        # Two amount-matching candidates; one's reference matches the bank line
        self._seed_payment(br_db, amount=50.00, payment_date='2026-04-05', ref='PAY-A')
        pid_b = self._seed_payment(br_db, amount=50.00, payment_date='2026-04-05', ref='PAY-B')
        path = _write_csv(tmp_path, [('2026-04-05', '50.00', 'card', 'PAY-B')])
        sid = import_csv(path, account_name='Op')['statement_id']

        result = auto_match_statement(sid)
        assert result['matched'] == 1
        line = list_lines(sid)[0]
        assert line['matched_payment_id'] == pid_b

    def test_refund_matched_via_negative_amount(self, br_db, tmp_path):
        rid = self._seed_refund(br_db, amount=30.00, refund_date='2026-04-10')
        path = _write_csv(tmp_path, [('2026-04-10', '-30.00', 'refund out', '')])
        sid = import_csv(path, account_name='Op')['statement_id']

        result = auto_match_statement(sid)
        assert result['matched'] == 1
        line = list_lines(sid)[0]
        assert line['matched_refund_id'] == rid

    def test_payment_outside_window_not_matched(self, br_db, tmp_path):
        self._seed_payment(br_db, amount=100.00, payment_date='2026-04-01')
        # Bank line dated 2 weeks later — outside the default ±3 day window
        path = _write_csv(tmp_path, [('2026-04-15', '100.00', '', '')])
        sid = import_csv(path, account_name='Op')['statement_id']
        result = auto_match_statement(sid)
        assert result['matched'] == 0
        assert list_lines(sid)[0]['status'] == 'unmatched'


class TestManualOps:
    def test_manual_match_then_unmatch(self, br_db, tmp_path):
        path = _write_csv(tmp_path, [('2026-04-01', '75.00', '', '')])
        sid = import_csv(path, account_name='Op')['statement_id']
        line_id = list_lines(sid)[0]['line_id']

        manual_match(line_id, payment_id=999, by='alice')
        line = list_lines(sid)[0]
        assert line['status'] == 'matched_manual'
        assert line['matched_payment_id'] == 999
        assert line['matched_by'] == 'alice'

        unmatch(line_id)
        line = list_lines(sid)[0]
        assert line['status'] == 'unmatched'
        assert line['matched_payment_id'] is None

    def test_manual_match_requires_one_target(self, br_db, tmp_path):
        path = _write_csv(tmp_path, [('2026-04-01', '75.00', '', '')])
        sid = import_csv(path, account_name='Op')['statement_id']
        line_id = list_lines(sid)[0]['line_id']
        with pytest.raises(ValueError):
            manual_match(line_id)  # neither
        with pytest.raises(ValueError):
            manual_match(line_id, payment_id=1, refund_id=2)  # both

    def test_discard(self, br_db, tmp_path):
        # Bank fee that doesn't correspond to anything operational
        path = _write_csv(tmp_path, [('2026-04-01', '-2.50', 'monthly fee', '')])
        sid = import_csv(path, account_name='Op')['statement_id']
        line_id = list_lines(sid)[0]['line_id']
        discard(line_id, reason='monthly bank fee', by='admin')
        line = list_lines(sid)[0]
        assert line['status'] == 'discarded'

    def test_already_matched_payment_not_re_matched(self, br_db, tmp_path):
        # If a payment is already matched to one bank line, another bank line
        # with the same amount/date should not pick it up.
        conn = sqlite3.connect(br_db)
        conn.execute(
            "INSERT INTO payments (student_id, amount, payment_date, status) "
            "VALUES ('S', 40.00, '2026-04-01', 'completed')"
        )
        conn.commit()
        conn.close()

        path = _write_csv(tmp_path, [
            ('2026-04-01', '40.00', 'first', ''),
            ('2026-04-01', '40.00', 'second', ''),
        ])
        sid = import_csv(path, account_name='Op')['statement_id']
        result = auto_match_statement(sid)
        # Only one line gets the payment; the other stays unmatched.
        assert result['matched'] == 1
        statuses = [r['status'] for r in list_lines(sid)]
        assert sorted(statuses) == ['matched_auto', 'unmatched']
