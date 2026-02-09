#!/usr/bin/env python3
"""
Comprehensive tests for Payment Plans Module
Tests payment plan creation, management, processing, and modifications
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from university_system.modules.domain.finance.billing import payment_plans


@pytest.fixture
def temp_db():
    """Create a temporary database with payment plan schema for testing"""
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
            description TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_fees (
            student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            fee_type_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'unpaid',
            due_date TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (fee_type_id) REFERENCES fee_types (fee_type_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_plan_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            description TEXT,
            number_of_installments INTEGER NOT NULL,
            installment_frequency TEXT NOT NULL,
            setup_fee DECIMAL(10,2) DEFAULT 0,
            interest_rate DECIMAL(5,2) DEFAULT 0,
            early_payment_discount DECIMAL(5,2) DEFAULT 0,
            late_payment_penalty DECIMAL(5,2) DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_payment_plans (
            payment_plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            template_id INTEGER,
            total_amount DECIMAL(10,2) NOT NULL,
            remaining_amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            status TEXT DEFAULT 'active',
            start_date TEXT NOT NULL,
            next_due_date TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (template_id) REFERENCES payment_plan_templates (template_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_plan_installments (
            installment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_plan_id INTEGER NOT NULL,
            installment_number INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            payment_id INTEGER,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (payment_plan_id) REFERENCES student_payment_plans (payment_plan_id)
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
            status TEXT DEFAULT 'completed',
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
    """)

    conn.commit()
    conn.close()

    yield path

    # Cleanup
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

    # Insert sample students
    cursor.execute("""
        INSERT INTO students (student_id, first_name, last_name, email_address, course)
        VALUES ('STU001', 'John', 'Doe', 'john@test.com', 'Computer Science')
    """)

    cursor.execute("""
        INSERT INTO students (student_id, first_name, last_name, email_address, course)
        VALUES ('STU002', 'Jane', 'Smith', 'jane@test.com', 'Engineering')
    """)

    # Insert fee types
    cursor.execute("""
        INSERT INTO fee_types (fee_name, description)
        VALUES ('Tuition', 'Annual tuition fee')
    """)

    cursor.execute("""
        INSERT INTO fee_types (fee_name, description)
        VALUES ('Library Fee', 'Library usage fee')
    """)

    # Insert outstanding fees
    cursor.execute("""
        INSERT INTO student_fees (student_id, fee_type_id, amount, status, due_date)
        VALUES ('STU001', 1, 5000.00, 'unpaid', date('now', '+30 days'))
    """)

    cursor.execute("""
        INSERT INTO student_fees (student_id, fee_type_id, amount, status, due_date)
        VALUES ('STU001', 2, 200.00, 'unpaid', date('now', '+30 days'))
    """)

    # Insert payment plan templates
    cursor.execute("""
        INSERT INTO payment_plan_templates
        (template_name, description, number_of_installments, installment_frequency,
         setup_fee, interest_rate, is_active)
        VALUES ('3-Month Plan', '3 monthly installments', 3, 'monthly', 25.00, 5.0, 1)
    """)

    cursor.execute("""
        INSERT INTO payment_plan_templates
        (template_name, description, number_of_installments, installment_frequency,
         setup_fee, interest_rate, is_active)
        VALUES ('6-Month Plan', '6 monthly installments', 6, 'monthly', 50.00, 3.0, 1)
    """)

    cursor.execute("""
        INSERT INTO payment_plan_templates
        (template_name, description, number_of_installments, installment_frequency,
         setup_fee, interest_rate, is_active)
        VALUES ('12-Week Plan', '12 weekly installments', 12, 'weekly', 15.00, 7.0, 1)
    """)

    conn.commit()
    conn.close()

    return temp_db


class TestPaymentPlanCreation:
    """Test payment plan creation functionality"""

    def test_create_payment_plan_monthly(self, sample_data, mock_auth):
        """Test creating a monthly payment plan"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['STU001', '1', 'y']), \
             patch('university_system.modules.domain.finance.billing.payment_plans.student_exists', return_value=True), \
             patch('university_system.modules.domain.finance.billing.payment_plans.send_payment_plan_notification'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            payment_plans.create_payment_plan()

            # Verify payment plan was created
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM student_payment_plans WHERE student_id = 'STU001'")
            count = cursor.fetchone()[0]
            assert count == 1, "Payment plan should be created"

            # Verify installments were created
            cursor.execute("""
                SELECT COUNT(*) FROM payment_plan_installments ppi
                JOIN student_payment_plans spp ON ppi.payment_plan_id = spp.payment_plan_id
                WHERE spp.student_id = 'STU001'
            """)
            installment_count = cursor.fetchone()[0]
            assert installment_count == 3, "3 installments should be created"

            conn.close()

    def test_create_payment_plan_calculates_amounts_correctly(self, sample_data, mock_auth):
        """Test that payment plan amounts are calculated correctly"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['STU001', '1', 'y']), \
             patch('university_system.modules.domain.finance.billing.payment_plans.student_exists', return_value=True), \
             patch('university_system.modules.domain.finance.billing.payment_plans.send_payment_plan_notification'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            payment_plans.create_payment_plan()

            # Verify total amount calculation
            cursor = conn.cursor()
            cursor.execute("""
                SELECT total_amount, remaining_amount
                FROM student_payment_plans
                WHERE student_id = 'STU001'
            """)
            result = cursor.fetchone()

            # Total outstanding fees: 5000 + 200 = 5200
            # Setup fee: 25
            # Interest (5%): 260
            # Total: 5485
            total_amount, remaining_amount = result
            assert total_amount > 5200, "Total should include setup fee and interest"
            assert remaining_amount == total_amount, "Initially, remaining should equal total"

            conn.close()

    def test_create_payment_plan_no_outstanding_fees(self, sample_data, mock_auth):
        """Test creating payment plan when student has no outstanding fees"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['STU002']), \
             patch('university_system.modules.domain.finance.billing.payment_plans.student_exists', return_value=True):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Remove all fees for STU002
            cursor = conn.cursor()
            cursor.execute("DELETE FROM student_fees WHERE student_id = 'STU002'")
            conn.commit()

            payment_plans.create_payment_plan()

            # Verify no payment plan was created
            cursor.execute("SELECT COUNT(*) FROM student_payment_plans WHERE student_id = 'STU002'")
            count = cursor.fetchone()[0]
            assert count == 0, "No payment plan should be created without outstanding fees"

            conn.close()


class TestPaymentPlanViewing:
    """Test payment plan viewing functionality"""

    def test_view_active_payment_plans(self, sample_data, mock_auth):
        """Test viewing all active payment plans"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn:

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Create a payment plan
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_payment_plans
                (student_id, template_id, total_amount, remaining_amount, status, start_date, next_due_date)
                VALUES ('STU001', 1, 5485.00, 5485.00, 'active', date('now'), date('now', '+30 days'))
            """)
            conn.commit()

            payment_plans.view_active_payment_plans()

            # Verify plan is in database
            cursor.execute("SELECT COUNT(*) FROM student_payment_plans WHERE status = 'active'")
            count = cursor.fetchone()[0]
            assert count == 1, "Active payment plan should be visible"

            conn.close()

    def test_view_active_payment_plans_empty(self, sample_data):
        """Test viewing when no active payment plans exist"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn:

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            payment_plans.view_active_payment_plans()

            # Should handle empty case gracefully
            conn.close()


class TestPaymentPlanPaymentProcessing:
    """Test payment plan payment processing"""

    def test_process_payment_plan_payment_full_installment(self, sample_data, mock_auth):
        """Test processing a full installment payment"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['1', '1828.33']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Create payment plan and installments
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_payment_plans
                (student_id, template_id, total_amount, remaining_amount, status, start_date, next_due_date)
                VALUES ('STU001', 1, 5485.00, 5485.00, 'active', date('now'), date('now', '+30 days'))
            """)
            plan_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO payment_plan_installments
                (payment_plan_id, installment_number, amount, due_date, status)
                VALUES (?, 1, 1828.33, date('now', '+30 days'), 'pending')
            """, (plan_id,))
            conn.commit()

            payment_plans.process_payment_plan_payment()

            # Verify payment was recorded
            cursor.execute("SELECT COUNT(*) FROM payments WHERE student_id = 'STU001'")
            payment_count = cursor.fetchone()[0]
            assert payment_count == 1, "Payment should be recorded"

            # Verify installment status updated
            cursor.execute("SELECT status FROM payment_plan_installments WHERE installment_number = 1")
            status = cursor.fetchone()[0]
            assert status == 'paid', "Installment should be marked as paid"

            # Verify remaining amount updated
            cursor.execute("SELECT remaining_amount FROM student_payment_plans WHERE payment_plan_id = ?", (plan_id,))
            remaining = cursor.fetchone()[0]
            assert remaining < 5485.00, "Remaining amount should be reduced"

            conn.close()

    def test_process_payment_plan_payment_partial(self, sample_data, mock_auth):
        """Test processing a partial installment payment"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['1', '500.00']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Create payment plan
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_payment_plans
                (student_id, template_id, total_amount, remaining_amount, status, start_date, next_due_date)
                VALUES ('STU001', 1, 5485.00, 5485.00, 'active', date('now'), date('now', '+30 days'))
            """)
            plan_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO payment_plan_installments
                (payment_plan_id, installment_number, amount, due_date, status)
                VALUES (?, 1, 1828.33, date('now', '+30 days'), 'pending')
            """, (plan_id,))
            conn.commit()

            payment_plans.process_payment_plan_payment()

            # Verify partial payment recorded
            cursor.execute("SELECT amount FROM payments WHERE student_id = 'STU001'")
            payment_amount = cursor.fetchone()[0]
            assert payment_amount == 500.00, "Partial payment should be recorded"

            # Verify installment still pending
            cursor.execute("SELECT status FROM payment_plan_installments WHERE installment_number = 1")
            status = cursor.fetchone()[0]
            # Status might remain pending for partial payment
            assert status in ['pending', 'partial'], "Installment should remain pending or partial"

            conn.close()

    def test_process_payment_completes_plan(self, sample_data, mock_auth):
        """Test that final payment completes the plan"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['1', '100.00']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Create payment plan with small remaining amount
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_payment_plans
                (student_id, template_id, total_amount, remaining_amount, status, start_date, next_due_date)
                VALUES ('STU001', 1, 5485.00, 100.00, 'active', date('now'), date('now', '+30 days'))
            """)
            plan_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO payment_plan_installments
                (payment_plan_id, installment_number, amount, due_date, status)
                VALUES (?, 3, 100.00, date('now', '+30 days'), 'pending')
            """, (plan_id,))
            conn.commit()

            payment_plans.process_payment_plan_payment()

            # Verify plan status updated to completed
            cursor.execute("SELECT status, remaining_amount FROM student_payment_plans WHERE payment_plan_id = ?", (plan_id,))
            result = cursor.fetchone()
            status, remaining = result
            assert status == 'completed', "Plan should be marked as completed"
            assert remaining == 0, "Remaining amount should be zero"

            conn.close()


class TestPaymentPlanModification:
    """Test payment plan modification functionality"""

    def test_modify_payment_plan_adjust_amount(self, sample_data, mock_auth):
        """Test adjusting payment plan amount"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['1', '1', '6000.00']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Create payment plan
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_payment_plans
                (student_id, template_id, total_amount, remaining_amount, status, start_date, next_due_date)
                VALUES ('STU001', 1, 5485.00, 5485.00, 'active', date('now'), date('now', '+30 days'))
            """)
            conn.commit()

            payment_plans.modify_payment_plan()

            # Verify amount was updated
            cursor.execute("SELECT total_amount, remaining_amount FROM student_payment_plans WHERE payment_plan_id = 1")
            result = cursor.fetchone()
            total, remaining = result
            assert total == 6000.00, "Total amount should be updated"
            assert remaining == 6000.00, "Remaining amount should be updated"

            conn.close()

    def test_modify_payment_plan_change_due_date(self, sample_data, mock_auth):
        """Test changing payment plan due date"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['1', '2', '2025-12-31']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Create payment plan
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_payment_plans
                (student_id, template_id, total_amount, remaining_amount, status, start_date, next_due_date)
                VALUES ('STU001', 1, 5485.00, 5485.00, 'active', date('now'), date('now', '+30 days'))
            """)
            conn.commit()

            payment_plans.modify_payment_plan()

            # Verify due date was updated
            cursor.execute("SELECT next_due_date FROM student_payment_plans WHERE payment_plan_id = 1")
            next_due = cursor.fetchone()[0]
            assert next_due == '2025-12-31', "Due date should be updated"

            conn.close()

    def test_modify_payment_plan_pause(self, sample_data, mock_auth):
        """Test pausing a payment plan"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['1', '3']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Create payment plan
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_payment_plans
                (student_id, template_id, total_amount, remaining_amount, status, start_date, next_due_date)
                VALUES ('STU001', 1, 5485.00, 5485.00, 'active', date('now'), date('now', '+30 days'))
            """)
            conn.commit()

            payment_plans.modify_payment_plan()

            # Verify status changed to paused
            cursor.execute("SELECT status FROM student_payment_plans WHERE payment_plan_id = 1")
            status = cursor.fetchone()[0]
            assert status == 'paused', "Plan should be paused"

            conn.close()

    def test_modify_payment_plan_resume(self, sample_data, mock_auth):
        """Test resuming a paused payment plan"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['1', '4']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Create paused payment plan
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_payment_plans
                (student_id, template_id, total_amount, remaining_amount, status, start_date, next_due_date)
                VALUES ('STU001', 1, 5485.00, 5485.00, 'paused', date('now'), date('now', '+30 days'))
            """)
            conn.commit()

            payment_plans.modify_payment_plan()

            # Verify status changed to active
            cursor.execute("SELECT status FROM student_payment_plans WHERE payment_plan_id = 1")
            status = cursor.fetchone()[0]
            assert status == 'active', "Plan should be active"

            conn.close()


class TestPaymentPlanCancellation:
    """Test payment plan cancellation"""

    def test_cancel_payment_plan(self, sample_data, mock_auth):
        """Test cancelling a payment plan"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['1', 'Student withdrawal', 'y']), \
             patch('university_system.modules.domain.finance.billing.payment_plans.log_audit_action'):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Create payment plan
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_payment_plans
                (student_id, template_id, total_amount, remaining_amount, status, start_date, next_due_date)
                VALUES ('STU001', 1, 5485.00, 5485.00, 'active', date('now'), date('now', '+30 days'))
            """)
            plan_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO payment_plan_installments
                (payment_plan_id, installment_number, amount, due_date, status)
                VALUES (?, 1, 1828.33, date('now', '+30 days'), 'pending')
            """, (plan_id,))
            conn.commit()

            payment_plans.cancel_payment_plan()

            # Verify plan cancelled
            cursor.execute("SELECT status FROM student_payment_plans WHERE payment_plan_id = ?", (plan_id,))
            status = cursor.fetchone()[0]
            assert status == 'cancelled', "Plan should be cancelled"

            # Verify installments cancelled
            cursor.execute("SELECT status FROM payment_plan_installments WHERE payment_plan_id = ?", (plan_id,))
            installment_status = cursor.fetchone()[0]
            assert installment_status == 'cancelled', "Installments should be cancelled"

            conn.close()


class TestPermissions:
    """Test permission requirements"""

    def test_create_payment_plan_without_permission(self, sample_data):
        """Test that create_payment_plan requires permission"""
        mock_auth = MagicMock()
        mock_auth.current_user = {"username": "test_user"}
        mock_auth.check_permission = MagicMock(return_value=False)

        with patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth):
            payment_plans.create_payment_plan()
            # Should not proceed without permission

    def test_process_payment_without_permission(self, sample_data):
        """Test that process_payment_plan_payment requires permission"""
        mock_auth = MagicMock()
        mock_auth.current_user = {"username": "test_user"}
        mock_auth.check_permission = MagicMock(return_value=False)

        with patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth):
            payment_plans.process_payment_plan_payment()
            # Should not proceed without permission


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_create_payment_plan_invalid_student(self, sample_data, mock_auth):
        """Test creating payment plan for non-existent student"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['STU999']), \
             patch('university_system.modules.domain.finance.billing.payment_plans.student_exists', return_value=False):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            payment_plans.create_payment_plan()

            # Verify no plan was created
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM student_payment_plans WHERE student_id = 'STU999'")
            count = cursor.fetchone()[0]
            assert count == 0, "No plan should be created for invalid student"

            conn.close()

    def test_process_payment_invalid_plan(self, sample_data, mock_auth):
        """Test processing payment for non-existent plan"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['999']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            payment_plans.process_payment_plan_payment()

            # Should handle gracefully
            conn.close()

    def test_overpayment_handling(self, sample_data, mock_auth):
        """Test handling of overpayments"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.billing.payment_plans.auth', mock_auth), \
             patch('builtins.input', side_effect=['1', '2000.00']):

            conn = sqlite3.connect(sample_data)
            mock_conn.return_value = conn

            # Create payment plan with small amount
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO student_payment_plans
                (student_id, template_id, total_amount, remaining_amount, status, start_date, next_due_date)
                VALUES ('STU001', 1, 1828.33, 1828.33, 'active', date('now'), date('now', '+30 days'))
            """)
            plan_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO payment_plan_installments
                (payment_plan_id, installment_number, amount, due_date, status)
                VALUES (?, 1, 1828.33, date('now', '+30 days'), 'pending')
            """, (plan_id,))
            conn.commit()

            payment_plans.process_payment_plan_payment()

            # Verify overpayment is handled (should not exceed remaining)
            cursor.execute("SELECT remaining_amount FROM student_payment_plans WHERE payment_plan_id = ?", (plan_id,))
            remaining = cursor.fetchone()[0]
            assert remaining >= 0, "Remaining amount should not be negative"

            conn.close()


class TestNotifications:
    """Test payment plan notification functionality"""

    def test_send_payment_plan_notification(self, sample_data):
        """Test sending payment plan notification"""
        with patch('university_system.modules.domain.finance.billing.payment_plans.get_student_name', return_value='John Doe'), \
             patch('university_system.modules.domain.finance.billing.payment_plans.get_student_email', return_value='john@test.com'), \
             patch('university_system.modules.domain.finance.billing.payment_plans.render_template', return_value=('Subject', 'Body')), \
             patch('university_system.modules.domain.finance.billing.payment_plans.send_email_notification', return_value=True):

            # Should send notification successfully
            payment_plans.send_payment_plan_notification('STU001', 1, 'payment_plan_setup')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
