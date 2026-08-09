"""
Tests for student-to-student money transfers in finance_integration.py.

Covers transfer_student_finance_funds: balance movement, the two ledger
legs sharing a reference number, validation failures, recipient resolution
by username, and dispatch of the sender receipt email + recipient
notification. All tests run against a temporary database.
"""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3

DB_PATCH = 'education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH'
FI = 'education_system.systems.university.infrastructure.utils.finance_integration'


@pytest.fixture
def temp_db():
    """Temporary database with two funded student accounts."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_finance.db')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE students (
        student_id TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        email_address TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        email TEXT,
        role TEXT,
        student_id TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE student_finance_accounts (
        account_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        balance DECIMAL(10,2) DEFAULT 0.00,
        currency TEXT DEFAULT 'GBP',
        account_status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL,
        student_id TEXT,
        account_id INTEGER,
        transaction_type TEXT,
        amount DECIMAL(10,2),
        balance_before DECIMAL(10,2),
        balance_after DECIMAL(10,2),
        currency TEXT DEFAULT 'GBP',
        payment_method TEXT,
        reference_type TEXT,
        reference_id TEXT,
        reference_number TEXT,
        description TEXT,
        status TEXT DEFAULT 'completed',
        processed_by TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT
    )
    ''')

    cursor.execute(
        "INSERT INTO students VALUES ('S100', 'Alice', 'Smith', 'alice@uni.test')")
    cursor.execute(
        "INSERT INTO students VALUES ('S200', 'Bob', 'Jones', 'bob@uni.test')")
    cursor.execute(
        "INSERT INTO users (username, first_name, last_name, email, role, student_id) "
        "VALUES ('S100', 'Alice', 'Smith', 'alice@uni.test', 'student', 'S100')")
    cursor.execute(
        "INSERT INTO users (username, first_name, last_name, email, role, student_id) "
        "VALUES ('bobby', 'Bob', 'Jones', 'bob@uni.test', 'student', 'S200')")
    cursor.execute(
        "INSERT INTO users (username, first_name, last_name, email, role, student_id) "
        "VALUES ('charlie', 'Charlie', 'Brown', 'charlie@uni.test', 'staff', NULL)")
    cursor.execute(
        "INSERT INTO student_finance_accounts (student_id, balance) VALUES ('S100', 100.00)")
    cursor.execute(
        "INSERT INTO student_finance_accounts (student_id, balance) VALUES ('S200', 5.00)")

    conn.commit()
    conn.close()

    yield db_path

    shutil.rmtree(temp_dir, ignore_errors=True)


def _transfer(**kwargs):
    """Run a transfer with messaging mocked out; returns (result, email_mock, notif_mock)."""
    from education_system.systems.university.infrastructure.utils import finance_integration

    params = {
        'from_student_id': 'S100',
        'to_student_id': 'S200',
        'amount': 25.0,
        'reference': 'Meal out',
    }
    params.update(kwargs)

    with patch(f'{FI}.send_transfer_receipt_email', return_value=True) as m_email, \
         patch(f'{FI}.send_transfer_received_notification', return_value=True) as m_notif:
        result = finance_integration.transfer_student_finance_funds(**params)
    return result, m_email, m_notif


def _balances(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        'SELECT student_id, balance FROM student_finance_accounts').fetchall()
    conn.close()
    return dict(rows)


def _ledger_rows(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute('''
        SELECT student_id, transaction_type, amount, balance_before, balance_after,
               reference_type, reference_id, reference_number, description, processed_by
        FROM transactions ORDER BY transaction_id
    ''').fetchall()
    conn.close()
    return rows


class TestTransferMovesMoney:

    def test_successful_transfer_moves_balances(self, temp_db):
        with patch(DB_PATCH, temp_db):
            result, _, _ = _transfer()

        assert result['success'] is True
        assert result['new_balance'] == 75.00
        assert result['recipient_name'] == 'Bob Jones'
        assert result['reference_number'].startswith('TRF-')

        balances = _balances(temp_db)
        assert balances['S100'] == 75.00
        assert balances['S200'] == 30.00

    def test_ledger_legs_share_reference_number(self, temp_db):
        with patch(DB_PATCH, temp_db):
            result, _, _ = _transfer(reference='Money owed')

        rows = _ledger_rows(temp_db)
        assert len(rows) == 2
        out_row = next(r for r in rows if r[1] == 'transfer_out')
        in_row = next(r for r in rows if r[1] == 'transfer_in')

        assert out_row[0] == 'S100'
        assert in_row[0] == 'S200'
        assert out_row[2] == in_row[2] == 25.0
        assert (out_row[3], out_row[4]) == (100.0, 75.0)
        assert (in_row[3], in_row[4]) == (5.0, 30.0)
        # Both legs carry the p2p marker, the counterparty, and one shared reference number
        assert out_row[5] == in_row[5] == 'p2p_transfer'
        assert out_row[6] == 'S200'
        assert in_row[6] == 'S100'
        assert out_row[7] == in_row[7] == result['reference_number']
        assert 'Money owed' in out_row[8]
        assert 'Money owed' in in_row[8]
        assert out_row[9] == 'S100'

    def test_recipient_resolved_by_username(self, temp_db):
        """A recipient given by username lands on their student_id-keyed account."""
        with patch(DB_PATCH, temp_db):
            result, _, _ = _transfer(to_student_id='bobby')

        assert result['success'] is True
        balances = _balances(temp_db)
        assert balances['S200'] == 30.00
        assert 'bobby' not in balances

    def test_recipient_without_student_id_keyed_by_username(self, temp_db):
        """A user with no student_id gets an account keyed by their username."""
        with patch(DB_PATCH, temp_db):
            result, _, _ = _transfer(to_student_id='charlie')

        assert result['success'] is True
        assert _balances(temp_db)['charlie'] == 25.00


class TestTransferValidation:

    def test_insufficient_balance_rejected(self, temp_db):
        with patch(DB_PATCH, temp_db):
            result, _, _ = _transfer(amount=100.01)

        assert result['success'] is False
        assert 'Insufficient balance' in result['message']
        balances = _balances(temp_db)
        assert balances['S100'] == 100.00
        assert balances['S200'] == 5.00
        assert _ledger_rows(temp_db) == []

    @pytest.mark.parametrize('amount', [0, -5, 'abc', None, float('nan'), float('inf')])
    def test_invalid_amount_rejected(self, temp_db, amount):
        with patch(DB_PATCH, temp_db):
            result, _, _ = _transfer(amount=amount)

        assert result['success'] is False
        assert _ledger_rows(temp_db) == []

    def test_missing_reference_rejected(self, temp_db):
        with patch(DB_PATCH, temp_db):
            result, _, _ = _transfer(reference='   ')

        assert result['success'] is False
        assert 'reference is required' in result['message'].lower()
        assert _ledger_rows(temp_db) == []

    def test_self_transfer_rejected(self, temp_db):
        with patch(DB_PATCH, temp_db):
            result, _, _ = _transfer(to_student_id='S100')

        assert result['success'] is False
        assert 'yourself' in result['message']

    def test_self_transfer_via_username_alias_rejected(self, temp_db):
        """Sending to your own username still counts as a self-transfer."""
        with patch(DB_PATCH, temp_db):
            result, _, _ = _transfer(from_student_id='S200', to_student_id='bobby')

        assert result['success'] is False
        assert 'yourself' in result['message']

    def test_unknown_recipient_rejected(self, temp_db):
        with patch(DB_PATCH, temp_db):
            result, _, _ = _transfer(to_student_id='NOBODY')

        assert result['success'] is False
        assert 'not found' in result['message'].lower()
        assert _ledger_rows(temp_db) == []


class TestTransferMessaging:

    def test_receipt_email_and_notification_dispatched(self, temp_db):
        with patch(DB_PATCH, temp_db):
            result, m_email, m_notif = _transfer()

        assert result['email_sent'] is True
        assert result['notification_sent'] is True

        m_email.assert_called_once()
        email_kwargs = m_email.call_args.kwargs
        assert email_kwargs['student_id'] == 'S100'
        assert email_kwargs['recipient_id'] == 'S200'
        assert email_kwargs['recipient_name'] == 'Bob Jones'
        assert email_kwargs['amount'] == 25.0
        assert email_kwargs['reference'] == 'Meal out'
        assert email_kwargs['reference_number'] == result['reference_number']
        assert email_kwargs['balance_before'] == 100.0
        assert email_kwargs['balance_after'] == 75.0

        m_notif.assert_called_once()
        notif_kwargs = m_notif.call_args.kwargs
        assert notif_kwargs['recipient_id'] == 'S200'
        assert notif_kwargs['sender_id'] == 'S100'
        assert notif_kwargs['sender_name'] == 'Alice Smith'
        assert notif_kwargs['amount'] == 25.0
        assert notif_kwargs['reference'] == 'Meal out'

    def test_messaging_failures_do_not_fail_the_transfer(self, temp_db):
        from education_system.systems.university.infrastructure.utils import finance_integration

        with patch(DB_PATCH, temp_db), \
             patch(f'{FI}.send_transfer_receipt_email', return_value=False), \
             patch(f'{FI}.send_transfer_received_notification', return_value=False):
            result = finance_integration.transfer_student_finance_funds(
                from_student_id='S100', to_student_id='S200',
                amount=10.0, reference='Meal out')

        assert result['success'] is True
        assert result['email_sent'] is False
        assert result['notification_sent'] is False
        assert _balances(temp_db)['S200'] == 15.00


class TestTransferTemplates:
    """The JSON email templates ship with the code and must stay renderable."""

    @pytest.mark.parametrize('template_name', [
        'p2p_transfer_sent_receipt',
        'p2p_transfer_received_notification',
    ])
    def test_template_placeholders_are_declared(self, template_name):
        import json
        import re

        from education_system.paths import UNIVERSITY_EMAIL_TEMPLATES_DIR

        path = (UNIVERSITY_EMAIL_TEMPLATES_DIR / 'finance_commerce' / 'finance'
                / f'{template_name}.json')
        data = json.loads(path.read_text(encoding='utf-8'))

        assert data['template_id'] == template_name
        assert data['subject']
        assert 'body' in data or 'body_html' in data

        declared = set(data['variables'])
        brace_re = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
        used = set()
        for key in ('subject', 'body', 'body_text', 'body_html'):
            if key in data:
                used |= set(brace_re.findall(data[key]))
        assert used == declared
