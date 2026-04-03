"""
Comprehensive test suite for finance_integration.py

Tests all functionality in university_system/modules/shared/utils/finance_integration.py including:
- record_payment_to_finance
- record_refund_to_finance
- record_revenue_to_finance
- get_student_financial_summary
- get_finance_report_by_source
- Database integration
- Transaction recording
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_finance.db')

    # Create database with required tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create payments table
    cursor.execute('''
    CREATE TABLE payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        amount REAL,
        currency TEXT,
        payment_method TEXT,
        transaction_id TEXT,
        payment_date TEXT,
        status TEXT,
        notes TEXT,
        created_by TEXT,
        created_at TEXT
    )
    ''')

    # Create unified_refunds table (matches _ensure_finance_tables_exist schema)
    cursor.execute('''
    CREATE TABLE unified_refunds (
        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        refund_reference TEXT,
        source_type TEXT NOT NULL DEFAULT 'general',
        department TEXT,
        reference_id TEXT,
        reference_type TEXT,
        amount DECIMAL(10,2) NOT NULL,
        refund_type TEXT,
        refund_method TEXT,
        reason TEXT,
        status TEXT DEFAULT 'pending',
        refund_date TEXT,
        request_date TEXT,
        approval_date TEXT,
        requested_by TEXT,
        approved_by TEXT,
        processed_by TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create students table (for testing purposes)
    cursor.execute('''
    CREATE TABLE students (
        student_id TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        email_address TEXT
    )
    ''')

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

class TestFinanceIntegrationImports:
    """Test finance_integration module imports"""

    def test_module_imports_successfully(self):
        """Test that finance_integration module can be imported"""
        try:
            from education_system.university_system.modules.shared.utils import finance_integration
            assert finance_integration is not None
        except ImportError as e:
            pytest.fail(f"Failed to import finance_integration: {e}")

    def test_all_functions_exist(self):
        """Test that all expected functions are defined"""
        from education_system.university_system.modules.shared.utils import finance_integration

        assert hasattr(finance_integration, 'record_payment_to_finance')
        assert hasattr(finance_integration, 'record_refund_to_finance')
        assert hasattr(finance_integration, 'record_revenue_to_finance')
        assert hasattr(finance_integration, 'get_student_financial_summary')
        assert hasattr(finance_integration, 'get_finance_report_by_source')

class TestRecordPaymentToFinance:
    """Test record_payment_to_finance function"""

    def test_record_payment_to_finance_exists(self):
        """Test that function exists and is callable"""
        from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance

        assert callable(record_payment_to_finance)

    def test_record_payment_basic(self, temp_db):
        """Test recording a basic payment"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            payment_id = finance_integration.record_payment_to_finance(
                student_id='S001',
                amount=250.00,
                payment_method='Credit Card',
                transaction_source='Library',
                transaction_ref='FINE-12345'
            )

            assert payment_id is not None
            assert isinstance(payment_id, int)

            # Verify payment was recorded
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM payments WHERE payment_id = ?', (payment_id,))
            payment = cursor.fetchone()
            conn.close()

            assert payment is not None
            assert payment[1] == 'S001'  # student_id
            assert payment[2] == 250.00  # amount

    def test_record_payment_with_all_parameters(self, temp_db):
        """Test recording payment with all optional parameters"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            payment_id = finance_integration.record_payment_to_finance(
                student_id='S002',
                amount=500.50,
                payment_method='Bank Transfer',
                transaction_source='Housing',
                transaction_ref='RENT-2024-01',
                currency='USD',
                status='pending',
                notes='First semester rent',
                created_by='admin123',
                payment_date='2025-01-15 10:30:00'
            )

            assert payment_id is not None

            # Verify all fields were recorded
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM payments WHERE payment_id = ?', (payment_id,))
            payment = cursor.fetchone()
            conn.close()

            assert payment[1] == 'S002'  # student_id
            assert payment[2] == 500.50  # amount
            assert payment[3] == 'USD'  # currency
            assert payment[4] == 'Bank Transfer'  # payment_method
            assert payment[6] == '2025-01-15 10:30:00'  # payment_date
            assert payment[7] == 'pending'  # status

    def test_record_payment_creates_transaction_id(self, temp_db):
        """Test that transaction_id is properly formatted"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            payment_id = finance_integration.record_payment_to_finance(
                student_id='S003',
                amount=100.00,
                payment_method='Cash',
                transaction_source='Shop',
                transaction_ref='SALE-789'
            )

            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT transaction_id FROM payments WHERE payment_id = ?', (payment_id,))
            transaction_id = cursor.fetchone()[0]
            conn.close()

            assert transaction_id == 'Shop-SALE-789'

    def test_record_payment_creates_notes(self, temp_db):
        """Test that notes are properly formatted with source and ref"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            payment_id = finance_integration.record_payment_to_finance(
                student_id='S004',
                amount=75.00,
                payment_method='Credit Card',
                transaction_source='Restaurant',
                transaction_ref='ORDER-456',
                notes='Lunch order'
            )

            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT notes FROM payments WHERE payment_id = ?', (payment_id,))
            notes = cursor.fetchone()[0]
            conn.close()

            assert '[Restaurant]' in notes
            assert 'ORDER-456' in notes
            assert 'Lunch order' in notes

    def test_record_payment_handles_database_error(self, temp_db):
        """Test that database errors are handled gracefully"""
        from education_system.university_system.modules.shared.utils import finance_integration

        # Use non-existent database path
        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', '/nonexistent/db.db'):
            payment_id = finance_integration.record_payment_to_finance(
                student_id='S005',
                amount=100.00,
                payment_method='Cash',
                transaction_source='Test',
                transaction_ref='TEST-123'
            )

            assert payment_id is None

    def test_record_payment_rounds_amount(self, temp_db):
        """Test that amount is rounded to 2 decimal places"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            payment_id = finance_integration.record_payment_to_finance(
                student_id='S006',
                amount=123.456789,
                payment_method='Cash',
                transaction_source='Test',
                transaction_ref='TEST-456'
            )

            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT amount FROM payments WHERE payment_id = ?', (payment_id,))
            amount = cursor.fetchone()[0]
            conn.close()

            assert amount == 123.46

class TestRecordRefundToFinance:
    """Test record_refund_to_finance function"""

    def test_record_refund_to_finance_exists(self):
        """Test that function exists and is callable"""
        from education_system.university_system.modules.shared.utils.finance_integration import record_refund_to_finance

        assert callable(record_refund_to_finance)

    def test_record_refund_basic(self, temp_db):
        """Test recording a basic refund"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            refund_id = finance_integration.record_refund_to_finance(
                student_id='S001',
                refund_amount=50.00,
                original_payment_id=1,
                refund_reason='Overpayment',
                refund_type='partial',
                transaction_source='Library',
                transaction_ref='REFUND-123'
            )

            assert refund_id is not None
            assert isinstance(refund_id, int)

            # Verify refund was recorded
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM unified_refunds WHERE refund_id = ?', (refund_id,))
            refund = cursor.fetchone()
            conn.close()

            assert refund is not None
            assert refund[1] == 'S001'  # student_id
            assert refund[7] == 50.00  # amount

    def test_record_refund_with_all_parameters(self, temp_db):
        """Test recording refund with all parameters"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            refund_id = finance_integration.record_refund_to_finance(
                student_id='S002',
                refund_amount=100.00,
                original_payment_id=5,
                refund_reason='Course withdrawal',
                refund_type='full',
                transaction_source='Finance',
                transaction_ref='REFUND-456',
                refund_method='bank_transfer',
                currency='USD',
                requested_by='student',
                notes='Withdrew from course'
            )

            assert refund_id is not None

            # Verify all fields
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM unified_refunds WHERE refund_id = ?', (refund_id,))
            refund = cursor.fetchone()
            conn.close()

            assert refund[1] == 'S002'  # student_id
            assert refund[5] == '5'  # reference_id (original_payment_id)
            assert refund[4] == 'Finance'  # department (transaction_source)
            assert refund[10] == 'Course withdrawal'  # reason

    def test_record_refund_auto_processes(self, temp_db):
        """Test that refund is auto-approved and processed"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            refund_id = finance_integration.record_refund_to_finance(
                student_id='S003',
                refund_amount=25.00,
                original_payment_id=None,
                refund_reason='Test',
                refund_type='partial',
                transaction_source='Test',
                transaction_ref='TEST-789'
            )

            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT status, processed_by FROM unified_refunds WHERE refund_id = ?', (refund_id,))
            status, processed_by = cursor.fetchone()
            conn.close()

            assert status == 'processed'
            assert processed_by == 'System'

    def test_record_refund_handles_error(self, temp_db):
        """Test that refund handles database errors"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', '/nonexistent/db.db'):
            refund_id = finance_integration.record_refund_to_finance(
                student_id='S004',
                refund_amount=50.00,
                original_payment_id=1,
                refund_reason='Test',
                refund_type='full',
                transaction_source='Test',
                transaction_ref='TEST-ERROR'
            )

            assert refund_id is None

class TestRecordRevenueToFinance:
    """Test record_revenue_to_finance function"""

    def test_record_revenue_to_finance_exists(self):
        """Test that function exists and is callable"""
        from education_system.university_system.modules.shared.utils.finance_integration import record_revenue_to_finance

        assert callable(record_revenue_to_finance)

    def test_record_revenue_basic(self, temp_db):
        """Test recording basic revenue"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            payment_id = finance_integration.record_revenue_to_finance(
                student_id='EXTERNAL',
                amount=1000.00,
                revenue_category='Donation',
                transaction_source='Alumni',
                transaction_ref='DONATION-123'
            )

            assert payment_id is not None

            # Verify revenue was recorded
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT notes FROM payments WHERE payment_id = ?', (payment_id,))
            notes = cursor.fetchone()[0]
            conn.close()

            assert 'Revenue - Donation' in notes

    def test_record_revenue_with_notes(self, temp_db):
        """Test recording revenue with additional notes"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            payment_id = finance_integration.record_revenue_to_finance(
                student_id='S001',
                amount=500.00,
                revenue_category='Sale',
                transaction_source='Shop',
                transaction_ref='SALE-456',
                notes='Book sale'
            )

            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('SELECT notes FROM payments WHERE payment_id = ?', (payment_id,))
            notes = cursor.fetchone()[0]
            conn.close()

            assert 'Revenue - Sale' in notes
            assert 'Book sale' in notes

class TestGetStudentFinancialSummary:
    """Test get_student_financial_summary function"""

    def test_get_student_financial_summary_exists(self):
        """Test that function exists and is callable"""
        from education_system.university_system.modules.shared.utils.finance_integration import get_student_financial_summary

        assert callable(get_student_financial_summary)

    def test_get_financial_summary_empty(self, temp_db):
        """Test getting summary for student with no transactions"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            summary = finance_integration.get_student_financial_summary('S999')

            assert summary['student_id'] == 'S999'
            assert summary['total_payments'] == 0
            assert summary['total_paid'] == 0.0
            assert summary['total_refunds'] == 0
            assert summary['total_refunded'] == 0.0
            assert summary['net_paid'] == 0.0

    def test_get_financial_summary_with_payments(self, temp_db):
        """Test getting summary with payments"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            # Add payments
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO payments (student_id, amount, status, notes, payment_date, currency, payment_method, transaction_id, created_by, created_at)
            VALUES ('S001', 100.00, 'completed', '[Library] Ref: FINE-1', '2025-01-01', 'GBP', 'Cash', 'LIB-1', 'admin', '2025-01-01')
            ''')
            cursor.execute('''
            INSERT INTO payments (student_id, amount, status, notes, payment_date, currency, payment_method, transaction_id, created_by, created_at)
            VALUES ('S001', 200.00, 'completed', '[Housing] Ref: RENT-1', '2025-01-02', 'GBP', 'Card', 'HOUS-1', 'admin', '2025-01-02')
            ''')
            conn.commit()
            conn.close()

            summary = finance_integration.get_student_financial_summary('S001')

            assert summary['student_id'] == 'S001'
            assert summary['total_payments'] == 2
            assert summary['total_paid'] == 300.00
            assert summary['net_paid'] == 300.00

    def test_get_financial_summary_with_refunds(self, temp_db):
        """Test getting summary with refunds"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            # Add payments and refunds
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO payments (student_id, amount, status, notes, payment_date, currency, payment_method, transaction_id, created_by, created_at)
            VALUES ('S002', 500.00, 'completed', '[Test] Ref: PAY-1', '2025-01-01', 'GBP', 'Cash', 'TEST-1', 'admin', '2025-01-01')
            ''')
            cursor.execute('''
            INSERT INTO unified_refunds (student_id, refund_reference, source_type, department, amount, refund_type, refund_method, reason, status, refund_date, request_date, processed_by, notes, created_at)
            VALUES ('S002', 'TEST-REF-1', 'general', 'Test', 100.00, 'partial', 'cash', 'Overpayment', 'processed', '2025-01-02', '2025-01-02', 'admin', 'Test refund', '2025-01-02')
            ''')
            conn.commit()
            conn.close()

            summary = finance_integration.get_student_financial_summary('S002')

            assert summary['total_paid'] == 500.00
            assert summary['total_refunded'] == 100.00
            assert summary['net_paid'] == 400.00

    def test_get_financial_summary_by_source(self, temp_db):
        """Test getting summary broken down by source"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            # Add payments from different sources
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO payments (student_id, amount, status, notes, payment_date, currency, payment_method, transaction_id, created_by, created_at)
            VALUES ('S003', 100.00, 'completed', '[Library] Ref: FINE-1', '2025-01-01', 'GBP', 'Cash', 'LIB-1', 'admin', '2025-01-01')
            ''')
            cursor.execute('''
            INSERT INTO payments (student_id, amount, status, notes, payment_date, currency, payment_method, transaction_id, created_by, created_at)
            VALUES ('S003', 200.00, 'completed', '[Library] Ref: FINE-2', '2025-01-02', 'GBP', 'Card', 'LIB-2', 'admin', '2025-01-02')
            ''')
            cursor.execute('''
            INSERT INTO payments (student_id, amount, status, notes, payment_date, currency, payment_method, transaction_id, created_by, created_at)
            VALUES ('S003', 300.00, 'completed', '[Housing] Ref: RENT-1', '2025-01-03', 'GBP', 'Bank', 'HOUS-1', 'admin', '2025-01-03')
            ''')
            conn.commit()
            conn.close()

            summary = finance_integration.get_student_financial_summary('S003')

            assert 'Library' in summary['payments_by_source']
            assert 'Housing' in summary['payments_by_source']
            assert summary['payments_by_source']['Library']['count'] == 2
            assert summary['payments_by_source']['Library']['amount'] == 300.00
            assert summary['payments_by_source']['Housing']['count'] == 1
            assert summary['payments_by_source']['Housing']['amount'] == 300.00

    def test_get_financial_summary_handles_error(self, temp_db):
        """Test that summary handles database errors"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', '/nonexistent/db.db'):
            summary = finance_integration.get_student_financial_summary('S001')

            assert summary == {}

class TestGetFinanceReportBySource:
    """Test get_finance_report_by_source function"""

    def test_get_finance_report_by_source_exists(self):
        """Test that function exists and is callable"""
        from education_system.university_system.modules.shared.utils.finance_integration import get_finance_report_by_source

        assert callable(get_finance_report_by_source)

    def test_get_report_basic(self, temp_db):
        """Test getting basic report for a source"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            # Add payments
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO payments (student_id, amount, status, notes, payment_date, currency, payment_method, transaction_id, created_by, created_at)
            VALUES ('S001', 100.00, 'completed', '[Library] Ref: FINE-1', '2025-01-15', 'GBP', 'Cash', 'LIB-1', 'admin', '2025-01-15')
            ''')
            cursor.execute('''
            INSERT INTO payments (student_id, amount, status, notes, payment_date, currency, payment_method, transaction_id, created_by, created_at)
            VALUES ('S002', 50.00, 'completed', '[Library] Ref: FINE-2', '2025-01-16', 'GBP', 'Card', 'LIB-2', 'admin', '2025-01-16')
            ''')
            conn.commit()
            conn.close()

            report = finance_integration.get_finance_report_by_source('Library')

            assert report['source'] == 'Library'
            assert report['transaction_count'] == 2
            assert report['total_revenue'] == 150.00
            assert report['average_transaction'] == 75.00
            assert report['min_transaction'] == 50.00
            assert report['max_transaction'] == 100.00

    def test_get_report_with_date_filter(self, temp_db):
        """Test getting report with date filters"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            # Add payments
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO payments (student_id, amount, status, notes, payment_date, currency, payment_method, transaction_id, created_by, created_at)
            VALUES ('S001', 100.00, 'completed', '[Shop] Ref: SALE-1', '2025-01-10', 'GBP', 'Cash', 'SHOP-1', 'admin', '2025-01-10')
            ''')
            cursor.execute('''
            INSERT INTO payments (student_id, amount, status, notes, payment_date, currency, payment_method, transaction_id, created_by, created_at)
            VALUES ('S002', 200.00, 'completed', '[Shop] Ref: SALE-2', '2025-01-20', 'GBP', 'Card', 'SHOP-2', 'admin', '2025-01-20')
            ''')
            cursor.execute('''
            INSERT INTO payments (student_id, amount, status, notes, payment_date, currency, payment_method, transaction_id, created_by, created_at)
            VALUES ('S003', 300.00, 'completed', '[Shop] Ref: SALE-3', '2025-01-30', 'GBP', 'Bank', 'SHOP-3', 'admin', '2025-01-30')
            ''')
            conn.commit()
            conn.close()

            # Get report for January 15-25
            report = finance_integration.get_finance_report_by_source(
                'Shop',
                start_date='2025-01-15',
                end_date='2025-01-25'
            )

            assert report['transaction_count'] == 1
            assert report['total_revenue'] == 200.00
            assert report['start_date'] == '2025-01-15'
            assert report['end_date'] == '2025-01-25'

    def test_get_report_empty_source(self, temp_db):
        """Test getting report for source with no transactions"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            report = finance_integration.get_finance_report_by_source('NonexistentSource')

            assert report['source'] == 'NonexistentSource'
            assert report['transaction_count'] == 0
            assert report['total_revenue'] == 0.00

    def test_get_report_handles_error(self, temp_db):
        """Test that report handles database errors"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', '/nonexistent/db.db'):
            report = finance_integration.get_finance_report_by_source('Library')

            assert report == {}

class TestModuleConstants:
    """Test module-level constants and imports"""

    def test_module_has_logger(self):
        """Test that module has logger configured"""
        from education_system.university_system.modules.shared.utils import finance_integration

        assert hasattr(finance_integration, 'logger')

    def test_module_imports_paths(self):
        """Test that module imports paths correctly"""
        from education_system.university_system.modules.shared.utils import finance_integration

        assert hasattr(finance_integration, 'paths')

class TestIntegration:
    """Integration tests for finance integration"""

    def test_complete_payment_lifecycle(self, temp_db):
        """Test complete payment lifecycle: payment -> refund"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            # Record payment
            payment_id = finance_integration.record_payment_to_finance(
                student_id='S100',
                amount=500.00,
                payment_method='Credit Card',
                transaction_source='Housing',
                transaction_ref='RENT-100'
            )

            assert payment_id is not None

            # Record refund
            refund_id = finance_integration.record_refund_to_finance(
                student_id='S100',
                refund_amount=100.00,
                original_payment_id=payment_id,
                refund_reason='Overpayment',
                refund_type='partial',
                transaction_source='Housing',
                transaction_ref='REFUND-100'
            )

            assert refund_id is not None

            # Get summary
            summary = finance_integration.get_student_financial_summary('S100')

            assert summary['total_paid'] == 500.00
            assert summary['total_refunded'] == 100.00
            assert summary['net_paid'] == 400.00

    def test_multiple_sources_integration(self, temp_db):
        """Test tracking payments from multiple sources"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            # Library payment
            finance_integration.record_payment_to_finance(
                student_id='S200',
                amount=25.00,
                payment_method='Cash',
                transaction_source='Library',
                transaction_ref='FINE-200'
            )

            # Housing payment
            finance_integration.record_payment_to_finance(
                student_id='S200',
                amount=500.00,
                payment_method='Bank Transfer',
                transaction_source='Housing',
                transaction_ref='RENT-200'
            )

            # Shop payment
            finance_integration.record_payment_to_finance(
                student_id='S200',
                amount=50.00,
                payment_method='Credit Card',
                transaction_source='Shop',
                transaction_ref='PURCHASE-200'
            )

            # Get summary
            summary = finance_integration.get_student_financial_summary('S200')

            assert summary['total_paid'] == 575.00
            assert len(summary['payments_by_source']) == 3
            assert 'Library' in summary['payments_by_source']
            assert 'Housing' in summary['payments_by_source']
            assert 'Shop' in summary['payments_by_source']

    def test_revenue_tracking_integration(self, temp_db):
        """Test revenue tracking integration"""
        from education_system.university_system.modules.shared.utils import finance_integration

        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            # Record revenue
            finance_integration.record_revenue_to_finance(
                student_id='EXTERNAL',
                amount=5000.00,
                revenue_category='Donation',
                transaction_source='Alumni',
                transaction_ref='DONATION-300'
            )

            # Get report
            report = finance_integration.get_finance_report_by_source('Alumni')

            assert report['transaction_count'] == 1
            assert report['total_revenue'] == 5000.00

class TestModuleDocumentation:
    """Test module documentation"""

    def test_module_has_docstring(self):
        """Test that module has documentation"""
        from education_system.university_system.modules.shared.utils import finance_integration

        assert finance_integration.__doc__ is not None
        assert 'finance' in finance_integration.__doc__.lower()

    def test_functions_have_docstrings(self):
        """Test that all public functions have documentation"""
        from education_system.university_system.modules.shared.utils import finance_integration

        functions = [
            'record_payment_to_finance',
            'record_refund_to_finance',
            'record_revenue_to_finance',
            'get_student_financial_summary',
            'get_finance_report_by_source'
        ]

        for func_name in functions:
            func = getattr(finance_integration, func_name)
            assert func.__doc__ is not None, f"{func_name} should have docstring"

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
