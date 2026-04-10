"""
Tests for university_system/modules/core/services/restaurant_misc/audit.py
"""
from __future__ import annotations

import json
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from io import StringIO
from unittest import mock

import pytest

from education_system.university_system.modules.domain.commerce.services.restaurant.operations import audit

@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    conn = mock.MagicMock(spec=sqlite3.Connection)
    cursor = mock.MagicMock(spec=sqlite3.Cursor)
    conn.cursor.return_value = cursor
    return conn, cursor

class TestLogAuditAction:
    """Tests for log_audit_action function"""

    def test_log_audit_action_success(self, mock_db_connection):
        """Test successful audit action logging"""
        conn, cursor = mock_db_connection

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            audit.log_audit_action(
                user_id='USER001',
                action='CREATE',
                table_name='menu_items',
                record_id='ITEM001',
                old_values={'name': 'Old Name'},
                new_values={'name': 'New Name'}
            )

            cursor.execute.assert_called_once()
            call_args = cursor.execute.call_args[0]
            assert 'INSERT INTO restaurant_audit_logs' in call_args[0]
            assert call_args[1][0].startswith('AUDIT')  # audit_id
            assert call_args[1][1] == 'USER001'  # user_id
            assert call_args[1][2] == 'CREATE'  # action
            assert call_args[1][3] == 'menu_items'  # table_name
            assert call_args[1][4] == 'ITEM001'  # record_id
            assert json.loads(call_args[1][5]) == {'name': 'Old Name'}  # old_values
            assert json.loads(call_args[1][6]) == {'name': 'New Name'}  # new_values

            conn.commit.assert_called_once()
            conn.close.assert_called_once()

    def test_log_audit_action_with_none_values(self, mock_db_connection):
        """Test audit logging with None values"""
        conn, cursor = mock_db_connection

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            audit.log_audit_action(
                user_id='USER001',
                action='DELETE',
                table_name='menu_items',
                record_id='ITEM001',
                old_values=None,
                new_values=None
            )

            call_args = cursor.execute.call_args[0]
            assert call_args[1][5] is None  # old_values
            assert call_args[1][6] is None  # new_values

    def test_log_audit_action_no_connection(self):
        """Test audit logging when database connection fails"""
        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=None):
            # Should not raise exception
            audit.log_audit_action(
                user_id='USER001',
                action='CREATE',
                table_name='menu_items'
            )

    def test_log_audit_action_database_error(self, mock_db_connection):
        """Test audit logging when database error occurs"""
        conn, cursor = mock_db_connection
        cursor.execute.side_effect = sqlite3.Error("Database error")

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.logging.error') as mock_log:
                audit.log_audit_action(
                    user_id='USER001',
                    action='CREATE'
                )
                mock_log.assert_called_once()

class TestViewUserActivityLogs:
    """Tests for view_user_activity_logs function"""

    def test_view_user_activity_logs_all_recent(self, mock_db_connection):
        """Test viewing all recent activity logs"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('AUDIT001', 'USER001', 'CREATE', 'menu_items', 'ITEM001', None, None, '2025-01-15 10:00:00', None, None),
            ('AUDIT002', 'USER002', 'UPDATE', 'orders', 'ORD001', None, None, '2025-01-15 11:00:00', None, None)
        ]

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='1'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    audit.view_user_activity_logs()

                    output = fake_out.getvalue()
                    assert 'USER ACTIVITY LOGS' in output
                    assert 'Total logs: 2' in output

            cursor.execute.assert_called_once()
            assert 'LIMIT 100' in cursor.execute.call_args[0][0]
            conn.close.assert_called_once()

    def test_view_user_activity_logs_by_user(self, mock_db_connection):
        """Test viewing activity logs filtered by user"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('AUDIT001', 'USER001', 'CREATE', 'menu_items', 'ITEM001', None, None, '2025-01-15 10:00:00', None, None)
        ]

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['2', 'USER001']):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    audit.view_user_activity_logs()

                    output = fake_out.getvalue()
                    assert 'USER ACTIVITY LOGS' in output

            assert 'WHERE user_id = ?' in cursor.execute.call_args[0][0]
            assert cursor.execute.call_args[0][1] == ('USER001',)

    def test_view_user_activity_logs_by_action(self, mock_db_connection):
        """Test viewing activity logs filtered by action"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['3', 'CREATE']):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    audit.view_user_activity_logs()

                    output = fake_out.getvalue()
                    assert 'No activity logs found' in output

    def test_view_user_activity_logs_today(self, mock_db_connection):
        """Test viewing today's activity logs"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []
        today = datetime.now().strftime('%Y-%m-%d')

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='4'):
                with mock.patch('sys.stdout', new=StringIO()):
                    audit.view_user_activity_logs()

            assert 'WHERE DATE(timestamp) = ?' in cursor.execute.call_args[0][0]
            assert cursor.execute.call_args[0][1] == (today,)

    def test_view_user_activity_logs_database_error(self, mock_db_connection):
        """Test viewing activity logs when database error occurs"""
        conn, cursor = mock_db_connection
        cursor.execute.side_effect = Exception("Database error")

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='1'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.logging.error'):
                        audit.view_user_activity_logs()

                        output = fake_out.getvalue()
                        assert 'An error occurred' in output

class TestViewAuditLogs:
    """Tests for view_audit_logs function"""

    def test_view_audit_logs_recent(self, mock_db_connection):
        """Test viewing recent audit logs"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = [
            ('AUDIT001', 'USER001', 'CREATE', 'menu_items', 'ITEM001', None, None, '2025-01-15 10:00:00', '192.168.1.1', 'Mozilla'),
            ('AUDIT002', 'USER002', 'UPDATE', 'orders', 'ORD001', None, None, '2025-01-15 11:00:00', '192.168.1.2', 'Chrome')
        ]

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='1'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    audit.view_audit_logs()

                    output = fake_out.getvalue()
                    assert 'AUDIT LOGS' in output
                    assert 'Total logs: 2' in output
                    assert '192.168.1.1' in output

            assert 'LIMIT 50' in cursor.execute.call_args[0][0]

    def test_view_audit_logs_by_user(self, mock_db_connection):
        """Test viewing audit logs filtered by user"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['2', 'USER001']):
                with mock.patch('sys.stdout', new=StringIO()):
                    audit.view_audit_logs()

            assert 'WHERE user_id = ?' in cursor.execute.call_args[0][0]
            assert cursor.execute.call_args[0][1] == ('USER001',)

    def test_view_audit_logs_by_action(self, mock_db_connection):
        """Test viewing audit logs filtered by action"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['3', 'DELETE']):
                with mock.patch('sys.stdout', new=StringIO()):
                    audit.view_audit_logs()

            assert 'WHERE action = ?' in cursor.execute.call_args[0][0]

    def test_view_audit_logs_by_table(self, mock_db_connection):
        """Test viewing audit logs filtered by table"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['4', 'menu_items']):
                with mock.patch('sys.stdout', new=StringIO()):
                    audit.view_audit_logs()

            assert 'WHERE table_name = ?' in cursor.execute.call_args[0][0]

    def test_view_audit_logs_today(self, mock_db_connection):
        """Test viewing today's audit logs"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []
        today = datetime.now().strftime('%Y-%m-%d')

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='5'):
                with mock.patch('sys.stdout', new=StringIO()):
                    audit.view_audit_logs()

            assert 'WHERE DATE(timestamp) = ?' in cursor.execute.call_args[0][0]
            assert cursor.execute.call_args[0][1] == (today,)

    def test_view_audit_logs_date_range(self, mock_db_connection):
        """Test viewing audit logs by date range"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', side_effect=['6', '2025-01-01', '2025-01-31']):
                with mock.patch('sys.stdout', new=StringIO()):
                    audit.view_audit_logs()

            assert 'WHERE DATE(timestamp) BETWEEN ? AND ?' in cursor.execute.call_args[0][0]
            assert cursor.execute.call_args[0][1] == ('2025-01-01', '2025-01-31')

    def test_view_audit_logs_no_results(self, mock_db_connection):
        """Test viewing audit logs when no results found"""
        conn, cursor = mock_db_connection
        cursor.fetchall.return_value = []

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='1'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    audit.view_audit_logs()

                    output = fake_out.getvalue()
                    assert 'No audit logs found' in output

    def test_view_audit_logs_exception(self, mock_db_connection):
        """Test viewing audit logs when exception occurs"""
        conn, cursor = mock_db_connection
        cursor.fetchall.side_effect = Exception("Test error")

        with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.get_db_connection', return_value=conn):
            with mock.patch('builtins.input', return_value='1'):
                with mock.patch('sys.stdout', new=StringIO()) as fake_out:
                    with mock.patch('education_system.university_system.modules.core.services.restaurant_misc.audit.logging.error') as mock_log:
                        audit.view_audit_logs()

                        output = fake_out.getvalue()
                        assert 'An error occurred' in output
                        mock_log.assert_called_once()
