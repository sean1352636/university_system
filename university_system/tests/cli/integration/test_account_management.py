#!/usr/bin/env python3
"""
Comprehensive tests for Account Management Module
Tests fee assignment, payment recording, invoices, refunds, and credits
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from university_system.modules.domain.finance.core import account_management

@pytest.fixture
def temp_db():
    """Create a temporary database with account management schema"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Create required tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email_address TEXT,
            course TEXT,
            enrollment_date TEXT,
            status TEXT DEFAULT 'active'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fee_types (
            fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_name TEXT NOT NULL,
            description TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_fees (
            student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            fee_type_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            status TEXT DEFAULT 'unpaid',
            due_date TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (fee_type_id) REFERENCES fee_types (fee_type_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            payment_method TEXT,
            payment_date TEXT,
            transaction_id TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TEXT,
            status TEXT DEFAULT 'completed',
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_allocations (
            allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            student_fee_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            created_at TEXT,
            FOREIGN KEY (payment_id) REFERENCES payments (payment_id),
            FOREIGN KEY (student_fee_id) REFERENCES student_fees (student_fee_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_credits (
            credit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            credit_amount DECIMAL(10,2) NOT NULL,
            remaining_amount DECIMAL(10,2) NOT NULL,
            credit_source TEXT,
            description TEXT,
            status TEXT DEFAULT 'active',
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS refunds (
            refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            original_payment_id INTEGER,
            refund_amount DECIMAL(10,2) NOT NULL,
            refund_reason TEXT NOT NULL,
            refund_type TEXT NOT NULL,
            refund_method TEXT,
            status TEXT DEFAULT 'pending',
            requested_by TEXT,
            request_date TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (original_payment_id) REFERENCES payments (payment_id)
        )
    """)

    conn.commit()
    conn.close()

    yield path

    try:
        os.unlink(path)
    except (OSError, IOError):
        pass

@pytest.fixture
def mock_auth():
    """Mock authentication object"""
    auth = MagicMock()
    auth.current_user = {"username": "test_admin"}
    auth.check_permission = MagicMock(return_value=True)
    return auth

@pytest.fixture
def sample_data(temp_db):
    """Insert sample data for testing"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Insert students
    cursor.execute("""
        INSERT INTO students (student_id, first_name, last_name, email_address, course)
        VALUES ('STU001', 'John', 'Doe', 'john@test.com', 'Computer Science')
    """)

    # Insert fee types
    cursor.execute("""
        INSERT INTO fee_types (fee_name, description)
        VALUES ('Tuition', 'Annual tuition fee'), ('Library', 'Library fee')
    """)

    # Insert unpaid fees
    cursor.execute("""
        INSERT INTO student_fees (student_id, fee_type_id, amount, status, due_date)
        VALUES ('STU001', 1, 5000.00, 'unpaid', date('now', '+30 days'))
    """)

    cursor.execute("""
        INSERT INTO student_fees (student_id, fee_type_id, amount, status, due_date)
        VALUES ('STU001', 2, 200.00, 'unpaid', date('now', '+60 days'))
    """)

    conn.commit()
    conn.close()

    return temp_db

class TestFeeAssignment:
    """Test fee assignment functionality"""

    def test_assign_fee_to_student(self, sample_data, mock_auth):
        """Test assigning a fee to a student"""
        with patch('university_system.modules.domain.finance.core.account_management.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.core.account_management.auth', mock_auth), \
             patch('builtins.input', side_effect=['STU001', '1', '1000.00', '2025-12-31']), \
             patch('university_system.modules.domain.finance.core.account_management.student_exists', return_value=True), \
             patch('university_system.modules.domain.finance.core.account_management.get_student_name', return_value='John Doe'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            account_management.assign_fees_to_student()

            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM student_fees WHERE amount = 1000.00")
            count = cursor.fetchone()[0]
            assert count == 1, "Fee should be assigned"

            conn.close()

class TestPaymentRecording:
    """Test payment recording functionality"""

    def test_record_payment(self, sample_data, mock_auth):
        """Test recording a payment"""
        with patch('university_system.modules.domain.finance.core.account_management.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.core.account_management.auth', mock_auth), \
             patch('builtins.input', side_effect=['STU001', '5000.00', 'Card', '', '', '']), \
             patch('university_system.modules.domain.finance.core.account_management.student_exists', return_value=True), \
             patch('university_system.modules.domain.finance.core.account_management.get_student_name', return_value='John Doe'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            account_management.record_payment()

            cursor = conn.cursor()
            cursor.execute("SELECT amount, payment_method FROM payments WHERE student_id = 'STU001'")
            result = cursor.fetchone()
            assert result is not None, "Payment should be recorded"
            assert result[0] == 5000.00, "Payment amount should match"
            assert result[1] == 'Card', "Payment method should match"

            conn.close()

    def test_payment_allocation_to_fees(self, sample_data, mock_auth):
        """Test that payment is allocated to outstanding fees"""
        with patch('university_system.modules.domain.finance.core.account_management.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.core.account_management.auth', mock_auth), \
             patch('builtins.input', side_effect=['STU001', '3000.00', 'Card', '', '', '']), \
             patch('university_system.modules.domain.finance.core.account_management.student_exists', return_value=True), \
             patch('university_system.modules.domain.finance.core.account_management.get_student_name', return_value='John Doe'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            account_management.record_payment()

            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM payment_allocations")
            count = cursor.fetchone()[0]
            assert count > 0, "Payment should be allocated to fees"

            # Check fee status updated
            cursor.execute("SELECT status FROM student_fees WHERE student_fee_id = 1")
            status = cursor.fetchone()[0]
            assert status in ['paid', 'partial'], "Fee status should be updated"

            conn.close()

    def test_overpayment_creates_credit(self, sample_data, mock_auth):
        """Test that overpayment creates a credit"""
        with patch('university_system.modules.domain.finance.core.account_management.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.core.account_management.auth', mock_auth), \
             patch('builtins.input', side_effect=['STU001', '10000.00', 'Card', '', '', '']), \
             patch('university_system.modules.domain.finance.core.account_management.student_exists', return_value=True), \
             patch('university_system.modules.domain.finance.core.account_management.get_student_name', return_value='John Doe'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            account_management.record_payment()

            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM student_credits WHERE student_id = 'STU001'")
            count = cursor.fetchone()[0]
            assert count > 0, "Credit should be created for overpayment"

            conn.close()

class TestInvoiceGeneration:
    """Test invoice generation functionality"""

    def test_generate_invoice(self, sample_data, mock_auth):
        """Test generating an invoice"""
        with patch('university_system.modules.domain.finance.core.account_management.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.core.account_management.auth', mock_auth), \
             patch('builtins.input', side_effect=['STU001']), \
             patch('university_system.modules.domain.finance.core.account_management.student_exists', return_value=True), \
             patch('university_system.modules.domain.finance.core.account_management.send_email_notification'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            account_management.generate_invoice()

            # Verify invoice was generated (file created)
            conn.close()

class TestRefundProcessing:
    """Test refund processing functionality"""

    def test_process_refund(self, sample_data, mock_auth):
        """Test processing a refund"""
        with patch('university_system.modules.domain.finance.core.account_management.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.core.account_management.auth', mock_auth), \
             patch('builtins.input', side_effect=['STU001', '1', '1', '1', '500.00', 'Overpayment', '1', 'y']), \
             patch('university_system.modules.domain.finance.core.account_management.student_exists', return_value=True), \
             patch('university_system.modules.domain.finance.core.account_management.get_student_name', return_value='John Doe'), \
             patch('university_system.modules.domain.finance.core.account_management.log_audit_action'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Create a payment first
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payments (student_id, amount, payment_method, payment_date, created_by, created_at, status)
                VALUES ('STU001', 1000.00, 'Card', date('now'), 'admin', datetime('now'), 'completed')
            """)
            conn.commit()

            account_management.process_refund()

            cursor.execute("SELECT COUNT(*) FROM refunds WHERE student_id = 'STU001'")
            count = cursor.fetchone()[0]
            assert count == 1, "Refund should be created"

            conn.close()

class TestFinancialStatements:
    """Test financial statement functionality"""

    def test_view_student_financial_statement(self, sample_data):
        """Test viewing student financial statement"""
        with patch('university_system.modules.domain.finance.core.account_management.get_connection') as mock_conn, \
             patch('builtins.input', side_effect=['STU001']), \
             patch('university_system.modules.domain.finance.core.account_management.student_exists', return_value=True):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            account_management.view_student_financial_statement()

            # Should display statement without errors
            conn.close()

class TestCreditManagement:
    """Test student credit management"""

    def test_manage_student_credits(self, sample_data, mock_auth):
        """Test managing student credits"""
        with patch('university_system.modules.domain.finance.core.account_management.auth', mock_auth), \
             patch('builtins.input', side_effect=['5']):

            account_management.manage_student_credits()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
