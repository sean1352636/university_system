#!/usr/bin/env python3
"""
Comprehensive tests for Financial Aid Module
Tests aid application approval, aid types, loan tracking, and aid effectiveness
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from university_system.modules.domain.finance.core import aid


@pytest.fixture
def temp_db():
    """Create a temporary database with financial aid schema"""
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
        CREATE TABLE IF NOT EXISTS financial_aid_types (
            aid_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            aid_name TEXT NOT NULL,
            aid_category TEXT,
            description TEXT,
            max_amount DECIMAL(10,2),
            eligibility_criteria TEXT,
            is_renewable BOOLEAN DEFAULT 0,
            requires_repayment BOOLEAN DEFAULT 0,
            interest_rate DECIMAL(5,2),
            grace_period_months INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_financial_aid (
            aid_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            aid_type_id INTEGER NOT NULL,
            awarded_amount DECIMAL(10,2) NOT NULL,
            disbursed_amount DECIMAL(10,2) DEFAULT 0,
            remaining_amount DECIMAL(10,2) NOT NULL,
            status TEXT DEFAULT 'pending',
            application_date TEXT,
            approval_date TEXT,
            approved_by TEXT,
            repayment_start_date TEXT,
            monthly_payment_amount DECIMAL(10,2),
            total_repaid DECIMAL(10,2) DEFAULT 0,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (aid_type_id) REFERENCES financial_aid_types (aid_type_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            payment_method TEXT,
            payment_date TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TEXT,
            status TEXT DEFAULT 'completed'
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
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_allocations (
            allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id INTEGER NOT NULL,
            student_fee_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fee_types (
            fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_name TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collection_cases (
            case_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            total_debt DECIMAL(10,2) NOT NULL,
            case_status TEXT DEFAULT 'new',
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
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
def sample_data(temp_db):
    """Insert sample data for testing"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Insert students
    cursor.execute("""
        INSERT INTO students (student_id, first_name, last_name, email_address, course, status)
        VALUES ('STU001', 'John', 'Doe', 'john@test.com', 'Computer Science', 'active')
    """)

    cursor.execute("""
        INSERT INTO students (student_id, first_name, last_name, email_address, course, status)
        VALUES ('STU002', 'Jane', 'Smith', 'jane@test.com', 'Engineering', 'active')
    """)

    # Insert aid types
    cursor.execute("""
        INSERT INTO financial_aid_types
        (aid_name, aid_category, max_amount, requires_repayment, interest_rate, is_active)
        VALUES ('Merit Scholarship', 'grant', 5000.00, 0, 0, 1)
    """)

    cursor.execute("""
        INSERT INTO financial_aid_types
        (aid_name, aid_category, max_amount, requires_repayment, interest_rate, is_active)
        VALUES ('Student Loan', 'loan', 10000.00, 1, 3.5, 1)
    """)

    cursor.execute("""
        INSERT INTO financial_aid_types
        (aid_name, aid_category, max_amount, requires_repayment, is_active)
        VALUES ('Emergency Grant', 'emergency', 1000.00, 0, 1)
    """)

    # Insert pending aid applications
    cursor.execute("""
        INSERT INTO student_financial_aid
        (student_id, aid_type_id, awarded_amount, remaining_amount, status, application_date, notes)
        VALUES ('STU001', 1, 5000.00, 5000.00, 'pending', date('now'), 'Merit-based application')
    """)

    cursor.execute("""
        INSERT INTO student_financial_aid
        (student_id, aid_type_id, awarded_amount, remaining_amount, status, application_date, notes)
        VALUES ('STU002', 2, 8000.00, 8000.00, 'pending', date('now'), 'Student loan application')
    """)

    # Insert approved aid
    cursor.execute("""
        INSERT INTO student_financial_aid
        (student_id, aid_type_id, awarded_amount, disbursed_amount, remaining_amount,
         status, application_date, approval_date, repayment_start_date, monthly_payment_amount)
        VALUES ('STU001', 2, 10000.00, 10000.00, 10000.00, 'disbursed',
                date('now', '-6 months'), date('now', '-5 months'), date('now', '+6 months'), 200.00)
    """)

    # Insert fee types
    cursor.execute("INSERT INTO fee_types (fee_name) VALUES ('Tuition')")

    # Insert student fees
    cursor.execute("""
        INSERT INTO student_fees (student_id, fee_type_id, amount, status, due_date)
        VALUES ('STU001', 1, 5000.00, 'unpaid', date('now', '+30 days'))
    """)

    # Insert collection case
    cursor.execute("""
        INSERT INTO collection_cases (student_id, total_debt, case_status)
        VALUES ('STU002', 1000.00, 'new')
    """)

    conn.commit()
    conn.close()

    return temp_db


class TestAidApplicationApproval:
    """Test aid application approval functionality"""

    def test_approve_full_amount(self, sample_data):
        """Test approving aid application for full amount"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn, \
             patch('builtins.input', side_effect=['1', '1']), \
             patch('university_system.modules.domain.finance.finance_misc.aid.get_current_user', return_value={'username': 'admin'}), \
             patch('university_system.modules.domain.finance.finance_misc.aid.log_audit_action'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.approve_reject_aid_application()

            cursor = conn.cursor()
            cursor.execute("SELECT status FROM student_financial_aid WHERE aid_id = 1")
            status = cursor.fetchone()[0]
            assert status == 'approved', "Aid should be approved"

            conn.close()

    def test_approve_partial_amount(self, sample_data):
        """Test approving aid application for partial amount"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn, \
             patch('builtins.input', side_effect=['1', '2', '3000.00']), \
             patch('university_system.modules.domain.finance.finance_misc.aid.get_current_user', return_value={'username': 'admin'}), \
             patch('university_system.modules.domain.finance.finance_misc.aid.log_audit_action'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.approve_reject_aid_application()

            cursor = conn.cursor()
            cursor.execute("SELECT awarded_amount, status FROM student_financial_aid WHERE aid_id = 1")
            result = cursor.fetchone()
            amount, status = result
            assert status == 'approved', "Aid should be approved"
            assert amount == 3000.00, "Awarded amount should be partial"

            conn.close()

    def test_reject_application(self, sample_data):
        """Test rejecting aid application"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn, \
             patch('builtins.input', side_effect=['1', '3', 'Insufficient documentation']), \
             patch('university_system.modules.domain.finance.finance_misc.aid.get_current_user', return_value={'username': 'admin'}), \
             patch('university_system.modules.domain.finance.finance_misc.aid.log_audit_action'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.approve_reject_aid_application()

            cursor = conn.cursor()
            cursor.execute("SELECT status, notes FROM student_financial_aid WHERE aid_id = 1")
            result = cursor.fetchone()
            status, notes = result
            assert status == 'rejected', "Aid should be rejected"
            assert 'REJECTED' in notes, "Rejection reason should be in notes"

            conn.close()


class TestAidTypeManagement:
    """Test aid type management"""

    def test_view_aid_types(self, sample_data):
        """Test viewing aid types"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn:

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.view_aid_types()

            conn.close()

    def test_create_aid_type(self, sample_data):
        """Test creating a new aid type"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn, \
             patch('builtins.input', side_effect=[
                 'Work Study Program', '3', 'Part-time work opportunity', '5000',
                 'Enrolled students', 'y', 'n'
             ]):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.create_aid_type()

            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM financial_aid_types WHERE aid_name = 'Work Study Program'")
            count = cursor.fetchone()[0]
            assert count == 1, "Aid type should be created"

            conn.close()

    def test_deactivate_aid_type(self, sample_data):
        """Test deactivating an aid type"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn, \
             patch('builtins.input', side_effect=['1', 'y']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.deactivate_aid_type()

            cursor = conn.cursor()
            cursor.execute("SELECT is_active FROM financial_aid_types WHERE aid_type_id = 1")
            is_active = cursor.fetchone()[0]
            assert is_active == 0, "Aid type should be deactivated"

            conn.close()


class TestLoanTracking:
    """Test loan repayment tracking"""

    def test_track_loan_repayments(self, sample_data):
        """Test tracking loan repayments"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn:

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.track_loan_repayments()

            # Should display loans without errors
            conn.close()

    def test_process_loan_payment(self, sample_data):
        """Test processing a loan payment"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn, \
             patch('builtins.input', side_effect=['200.00']), \
             patch('university_system.modules.domain.finance.finance_misc.aid.get_current_user', return_value={'username': 'admin'}):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Get loans first
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sfa.aid_id, sfa.student_id, s.first_name, s.last_name,
                       fat.aid_name, sfa.awarded_amount, sfa.disbursed_amount,
                       sfa.repayment_start_date, sfa.monthly_payment_amount, sfa.total_repaid
                FROM student_financial_aid sfa
                JOIN students s ON sfa.student_id = s.student_id
                JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                WHERE fat.requires_repayment = 1 AND sfa.status = 'disbursed'
            """)
            loans = cursor.fetchall()

            if loans:
                aid.process_loan_payment(loans)

                # Verify payment recorded
                cursor.execute("SELECT COUNT(*) FROM payments WHERE notes LIKE '%Loan repayment%'")
                count = cursor.fetchone()[0]
                assert count > 0, "Loan payment should be recorded"

            conn.close()


class TestAidReporting:
    """Test aid reporting functionality"""

    def test_aid_distribution_summary(self, sample_data):
        """Test aid distribution summary report"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn:

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.aid_distribution_summary()

            # Should display summary without errors
            conn.close()

    def test_aid_by_academic_year(self, sample_data):
        """Test aid by academic year report"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn, \
             patch('builtins.input', side_effect=['2024-2025']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.aid_by_academic_year()

            conn.close()

    def test_aid_effectiveness_analysis(self, sample_data):
        """Test aid effectiveness analysis"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn:

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.aid_effectiveness_analysis()

            # Should display analysis without errors
            conn.close()


class TestAidApplication:
    """Test aid application to fees"""

    def test_apply_aid_to_fees(self, sample_data):
        """Test applying aid directly to student fees"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.finance_misc.aid.get_current_user', return_value={'username': 'admin'}):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.apply_aid_to_fees('STU001', 3000.00, 1)

            # Verify payment created
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM payments WHERE student_id = 'STU001' AND payment_method = 'Financial Aid'")
            count = cursor.fetchone()[0]
            assert count > 0, "Aid payment should be created"

            # Verify fee status updated
            cursor.execute("SELECT status FROM student_fees WHERE student_id = 'STU001'")
            status = cursor.fetchone()[0]
            assert status in ['paid', 'partial'], "Fee status should be updated"

            conn.close()


class TestPaymentArrangement:
    """Test payment arrangement creation"""

    def test_create_payment_arrangement(self, sample_data):
        """Test creating payment arrangement for collection case"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn, \
             patch('builtins.input', side_effect=[
                 'STU002', '500.00', '3', '6', '2025-12-01',
                 'Payment on 1st of each month'
             ]), \
             patch('university_system.modules.domain.finance.finance_misc.aid.student_exists', return_value=True), \
             patch('university_system.modules.domain.finance.finance_misc.aid.get_student_name', return_value='Jane Smith'), \
             patch('university_system.modules.domain.finance.finance_misc.aid.get_current_user', return_value={'username': 'admin'}), \
             patch('university_system.modules.domain.finance.finance_misc.aid.send_arrangement_confirmation'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.create_payment_arrangement()

            # Verify collection case updated
            cursor = conn.cursor()
            cursor.execute("SELECT case_status, notes FROM collection_cases WHERE student_id = 'STU002'")
            result = cursor.fetchone()
            status, notes = result
            assert status == 'in_progress', "Case status should be updated"
            assert 'PAYMENT ARRANGEMENT' in notes, "Arrangement should be in notes"

            conn.close()


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_approve_aid_no_pending_applications(self, temp_db):
        """Test approving when no pending applications exist"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn:

            conn = sqlite3.connect(temp_db)
            mock_conn.return_value = conn

            # Setup minimal schema
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT)")
            cursor.execute("CREATE TABLE financial_aid_types (aid_type_id INTEGER PRIMARY KEY, aid_name TEXT, aid_category TEXT)")
            cursor.execute("""
                CREATE TABLE student_financial_aid (
                    aid_id INTEGER PRIMARY KEY, student_id TEXT, aid_type_id INTEGER,
                    awarded_amount DECIMAL(10,2), status TEXT, application_date TEXT, notes TEXT
                )
            """)
            conn.commit()

            aid.approve_reject_aid_application()

            # Should handle empty case gracefully
            conn.close()

    def test_deactivate_nonexistent_aid_type(self, sample_data):
        """Test deactivating non-existent aid type"""
        with patch('university_system.modules.domain.finance.finance_misc.aid.get_connection') as mock_conn, \
             patch('builtins.input', side_effect=['999']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            aid.deactivate_aid_type()

            # Should handle gracefully
            conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
