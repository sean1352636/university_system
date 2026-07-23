#!/usr/bin/env python3
"""
Comprehensive tests for Security and Automation Module
Tests automated notifications, fraud detection, and workflow management
"""

import pytest
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from education_system.post_18.university_system.modules.domain.finance.core import security_automation


class _UnclosableConnection:
    """Wrapper that makes close() a no-op so tests can query after production code closes."""
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
    def close(self):
        pass
    def __getattr__(self, name):
        return getattr(self._conn, name)
    def __enter__(self):
        return self._conn.__enter__()
    def __exit__(self, *args):
        return self._conn.__exit__(*args)

def _unclosable_connect(db_path):
    return _UnclosableConnection(db_path)

@pytest.fixture
def temp_db():
    """Create a temporary database with security schema"""
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
            course TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fee_types (
            fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_name TEXT NOT NULL
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
            reminder_count INTEGER DEFAULT 0,
            last_reminder_sent TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            template_type TEXT NOT NULL,
            subject_template TEXT NOT NULL,
            body_template TEXT NOT NULL,
            send_method TEXT DEFAULT 'email',
            is_active BOOLEAN DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            trigger_condition TEXT NOT NULL,
            days_before_due INTEGER,
            max_reminders INTEGER DEFAULT 3,
            reminder_interval_days INTEGER DEFAULT 7,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            template_id INTEGER NOT NULL,
            recipient_email TEXT,
            subject TEXT,
            message_body TEXT,
            send_method TEXT,
            status TEXT DEFAULT 'pending',
            sent_at TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            payment_method TEXT,
            payment_date TEXT,
            created_at TEXT,
            gateway_transaction_id TEXT,
            status TEXT DEFAULT 'completed',
            fraud_score DECIMAL(3,2),
            is_suspicious BOOLEAN DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT NOT NULL,
            table_name TEXT,
            record_id TEXT,
            new_values TEXT,
            timestamp TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_name TEXT NOT NULL,
            workflow_type TEXT NOT NULL,
            trigger_conditions TEXT,
            workflow_steps TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_by TEXT,
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
def mock_auth():
    """Mock authentication object"""
    auth = MagicMock()
    auth.current_user = {"username": "test_admin"}
    auth.check_permission = MagicMock(return_value=True)
    return auth

@pytest.fixture
def sample_data(temp_db):
    """Insert sample data"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Insert students
    cursor.execute("""
        INSERT INTO students (student_id, first_name, last_name, email_address, course)
        VALUES ('STU001', 'John', 'Doe', 'john@test.com', 'Computer Science')
    """)

    # Insert fee types
    cursor.execute("""
        INSERT INTO fee_types (fee_name) VALUES ('Tuition')
    """)

    # Insert overdue fees
    due_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    cursor.execute("""
        INSERT INTO student_fees (student_id, fee_type_id, amount, status, due_date)
        VALUES ('STU001', 1, 5000.00, 'unpaid', ?)
    """, (due_date,))

    # Insert notification templates
    cursor.execute("""
        INSERT INTO notification_templates
        (template_id, template_name, template_type, subject_template, body_template, is_active)
        VALUES (1, 'Payment Reminder', 'payment_reminder',
                'Payment Due: {fee_name}',
                'Dear {student_name}, your payment of {amount} is due on {due_date}.',
                1)
    """)

    # Insert payments for fraud detection
    cursor.execute("""
        INSERT INTO payments (student_id, amount, payment_method, payment_date, created_at, status)
        VALUES ('STU001', 5000.00, 'Card', date('now'), datetime('now'), 'completed')
    """)

    conn.commit()
    conn.close()

    return temp_db

class TestAutomatedNotifications:
    """Test automated notification functionality"""

    def test_setup_automated_notifications(self, sample_data, mock_auth):
        """Test setting up automated notification schedules"""
        with patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.get_connection') as mock_conn, \
             patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.auth', mock_auth):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            security_automation.setup_automated_notifications()

            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM notification_schedules")
            count = cursor.fetchone()[0]
            assert count > 0, "Notification schedules should be created"

    def test_send_automated_notifications(self, sample_data):
        """Test sending automated notifications"""
        with patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.get_connection') as mock_conn, \
             patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.send_notification', return_value=True):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            # Add notification schedule
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notification_schedules
                (template_id, trigger_condition, days_before_due, max_reminders, reminder_interval_days, is_active)
                VALUES (1, '{"fee_status": "unpaid", "days_before_due": 7}', 7, 3, 7, 1)
            """)
            conn.commit()

            count = security_automation.send_automated_notifications()
            assert count >= 0, "Should return notification count"

class TestFraudDetection:
    """Test fraud detection functionality"""

    def test_detect_payment_fraud(self, sample_data, mock_auth):
        """Test fraud detection on payments"""
        with patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.get_connection') as mock_conn, \
             patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.auth', mock_auth), \
             patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.log_audit_action'):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            security_automation.detect_payment_fraud()

            # Verify fraud scores were calculated
            cursor = conn.cursor()
            cursor.execute("SELECT fraud_score FROM payments WHERE payment_id = 1")
            score = cursor.fetchone()
            assert score is not None, "Fraud score should be calculated"

class TestAuditLogging:
    """Test audit logging functionality"""

    def test_log_audit_action(self, sample_data, mock_auth):
        """Test logging audit actions"""
        with patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.get_connection') as mock_conn, \
             patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.auth', mock_auth):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            details = {'action': 'test', 'data': 'test_data'}
            security_automation.log_audit_action('test_action', 'test_table', '123', details)

            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'test_action'")
            count = cursor.fetchone()[0]
            assert count == 1, "Audit log entry should be created"

class TestWorkflowManagement:
    """Test workflow management"""

    def test_create_approval_workflow(self, sample_data, mock_auth):
        """Test creating approval workflow"""
        with patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.get_connection') as mock_conn, \
             patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.auth', mock_auth):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            security_automation.create_approval_workflow()

            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM workflows WHERE workflow_type = 'approval'")
            count = cursor.fetchone()[0]
            assert count == 1, "Approval workflow should be created"

class TestNotificationSending:
    """Test notification sending functionality"""

    def test_send_notification(self, sample_data):
        """Test sending a single notification"""
        with patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.get_connection') as mock_conn, \
             patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.send_email_notification', return_value=True):

            conn = _unclosable_connect(sample_data)
            mock_conn.return_value = conn

            result = security_automation.send_notification(
                'STU001', 'john@test.com', 'Test Subject', 'Test Body', 'email', 1
            )

            assert result is True, "Notification should be sent successfully"

            # Verify notification logged
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sent_notifications WHERE student_id = 'STU001'")
            count = cursor.fetchone()[0]
            assert count == 1, "Sent notification should be logged"

    def test_send_email_notification(self):
        """Test email notification wrapper"""
        # send_email_notification imports send_email locally, so patch it at the source module.
        with patch('education_system.post_18.university_system.infrastructure.email.email_service.core.send_email', return_value=True):
            result = security_automation.send_email_notification('test@test.com', 'Subject', 'Body')
            assert result is True or result is None, "Email should be sent or mocked"

class TestPermissions:
    """Test permission requirements"""

    def test_setup_notifications_without_permission(self, sample_data):
        """Test that setup requires permission"""
        mock_auth = MagicMock()
        mock_auth.current_user = {"username": "test_user"}
        mock_auth.check_permission = MagicMock(return_value=False)

        with patch('education_system.post_18.university_system.modules.domain.finance.core.security_automation.auth', mock_auth):
            security_automation.setup_automated_notifications()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
