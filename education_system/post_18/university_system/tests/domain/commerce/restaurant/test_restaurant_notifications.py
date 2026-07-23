"""
Comprehensive tests for restaurant notifications module.

Tests cover:
- Viewing notifications with various filters
- Creating notifications
- Marking notifications as read
- Clearing old notifications
- Notification management workflow
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, call, patch

import pytest


class TestNotificationsModule(unittest.TestCase):
    """Test suite for notifications.py module"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.mock_conn.__enter__ = Mock(return_value=self.mock_conn)
        self.mock_conn.__exit__ = Mock(return_value=False)

        # Mock auth user
        self.mock_user = {
            'id': 'TEST_USER_001',
            'username': 'test_admin',
            'role': 'admin'
        }

        # Sample notification data
        self.sample_notifications = [
            ('NOT001', 'USER001', 'System', 'Server Maintenance', '2024-01-15 10:00:00',
             None, 'High', 'System', 1),
            ('NOT002', 'USER002', 'Alert', 'Order Update', '2024-01-15 11:00:00',
             '2024-01-15 12:00:00', 'Normal', 'Orders', 0),
            ('NOT003', None, 'Info', 'New Feature Available', '2024-01-15 12:00:00',
             None, 'Low', 'Features', 0),
        ]

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('builtins.input', side_effect=['1'])  # All notifications
    def test_view_notifications_all(self, mock_input, mock_get_conn):
        """Test viewing all notifications"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import view_notifications

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = self.sample_notifications

        # Execute
        view_notifications()

        # Verify query was executed
        self.mock_cursor.execute.assert_called_once()
        sql_call = str(self.mock_cursor.execute.call_args)
        assert 'restaurant_notifications' in sql_call
        assert 'LIMIT 50' in sql_call

        self.mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('builtins.input', side_effect=['2'])  # Unread notifications
    def test_view_notifications_unread(self, mock_input, mock_get_conn):
        """Test viewing unread notifications"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import view_notifications

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        unread_notifications = [n for n in self.sample_notifications if n[5] is None]
        self.mock_cursor.fetchall.return_value = unread_notifications

        # Execute
        view_notifications()

        # Verify WHERE clause for unread
        sql_call = str(self.mock_cursor.execute.call_args)
        assert 'read_date IS NULL' in sql_call

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('builtins.input', side_effect=['3', 'High'])  # By priority
    def test_view_notifications_by_priority(self, mock_input, mock_get_conn):
        """Test viewing notifications by priority"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import view_notifications

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        high_priority = [n for n in self.sample_notifications if n[6] == 'High']
        self.mock_cursor.fetchall.return_value = high_priority

        # Execute
        view_notifications()

        # Verify priority filter
        execute_calls = self.mock_cursor.execute.call_args_list
        assert len(execute_calls) == 1
        assert 'priority = ?' in str(execute_calls[0])
        assert 'High' in str(execute_calls[0])

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('builtins.input', side_effect=['4', 'Orders'])  # By category
    def test_view_notifications_by_category(self, mock_input, mock_get_conn):
        """Test viewing notifications by category"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import view_notifications

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        orders_notifs = [n for n in self.sample_notifications if n[7] == 'Orders']
        self.mock_cursor.fetchall.return_value = orders_notifs

        # Execute
        view_notifications()

        # Verify category filter
        execute_calls = self.mock_cursor.execute.call_args_list
        assert 'category = ?' in str(execute_calls[0])

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('builtins.input')
    def test_view_notifications_empty(self, mock_input, mock_get_conn):
        """Test viewing notifications when none exist"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import view_notifications

        # Setup mocks
        mock_input.side_effect = ['1']
        mock_get_conn.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []

        # Execute
        view_notifications()

        # Verify appropriate handling
        self.mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.backup_before_operation')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.log_audit_action')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.datetime')
    @patch('builtins.input')
    def test_create_notification_system_wide(self, mock_input, mock_datetime, mock_log_audit,
                                            mock_backup, mock_ctx, mock_get_conn):
        """Test creating a system-wide notification"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import create_notification

        # Setup mocks
        mock_input.side_effect = [
            'all',                    # user_id
            '1',                      # type: System
            'Server Maintenance',     # title
            'System will be down',    # message
            '3',                      # priority: High
            'System',                 # category
            'y'                       # action_required
        ]
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user

        # Mock datetime
        mock_now = datetime(2024, 1, 15, 10, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.strftime = datetime.strftime

        # Execute
        create_notification()

        # Verify backup was called
        mock_backup.assert_called_once_with('create_notification')

        # Verify INSERT was called
        insert_calls = [call for call in self.mock_cursor.execute.call_args_list
                       if 'INSERT' in str(call)]
        assert len(insert_calls) == 1

        # Verify audit log
        mock_log_audit.assert_called_once()
        audit_args = mock_log_audit.call_args[0]
        assert audit_args[0] == 'TEST_USER_001'
        assert audit_args[1] == 'CREATE_NOTIFICATION'

        self.mock_conn.commit.assert_called_once()
        self.mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.backup_before_operation')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.log_audit_action')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.datetime')
    @patch('builtins.input')
    def test_create_notification_specific_user(self, mock_input, mock_datetime, mock_log_audit,
                                               mock_backup, mock_ctx, mock_get_conn):
        """Test creating a notification for specific user"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import create_notification

        # Setup mocks
        mock_input.side_effect = [
            'USER123',                # user_id
            '2',                      # type: Alert
            'Order Ready',            # title
            'Your order is ready',    # message
            '2',                      # priority: Normal
            'Orders',                 # category
            'n'                       # action_required
        ]
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
        mock_datetime.strftime = datetime.strftime

        # Execute
        create_notification()

        # Verify user_id was set correctly (not None)
        insert_call = str(self.mock_cursor.execute.call_args_list[-1])
        assert 'USER123' in insert_call or "'USER123'" in insert_call

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    @patch('builtins.input')
    def test_create_notification_no_auth(self, mock_input, mock_ctx):
        """Test creating notification without authentication"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import create_notification

        # Setup mocks - no auth
        mock_ctx.auth = None

        # Execute
        create_notification()

        # Should return early without input
        mock_input.assert_not_called()

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.backup_before_operation')
    @patch('builtins.input')
    def test_create_notification_missing_title(self, mock_input, mock_backup, mock_ctx, mock_get_conn):
        """Test creating notification with missing title"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import create_notification

        # Setup mocks
        mock_input.side_effect = [
            'USER123',  # user_id
            '1',        # type
            '',         # title (empty)
        ]
        mock_ctx.auth.current_user = self.mock_user

        # Execute
        create_notification()

        # Should not reach INSERT
        self.mock_cursor.execute.assert_not_called()

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.log_audit_action')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.datetime')
    @patch('builtins.input', return_value='NOT001')
    def test_mark_notification_read(self, mock_input, mock_datetime, mock_log_audit,
                                   mock_ctx, mock_get_conn):
        """Test marking notification as read"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import mark_notification_read

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
        mock_datetime.strftime = datetime.strftime

        # Mock notification exists and is unread
        unread_notification = list(self.sample_notifications[0])
        unread_notification[5] = None  # read_date is None
        self.mock_cursor.fetchone.return_value = tuple(unread_notification)

        # Execute
        mark_notification_read()

        # Verify UPDATE was called
        update_calls = [call for call in self.mock_cursor.execute.call_args_list
                       if 'UPDATE' in str(call)]
        assert len(update_calls) == 1
        assert 'read_date' in str(update_calls[0])

        self.mock_conn.commit.assert_called_once()
        mock_log_audit.assert_called_once()

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    @patch('builtins.input', return_value='NOT999')
    def test_mark_notification_read_not_found(self, mock_input, mock_ctx, mock_get_conn):
        """Test marking non-existent notification as read"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import mark_notification_read

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user
        self.mock_cursor.fetchone.return_value = None

        # Execute
        mark_notification_read()

        # Should not commit
        self.mock_conn.commit.assert_not_called()
        self.mock_conn.close.assert_called_once()

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    @patch('builtins.input', return_value='NOT002')
    def test_mark_notification_already_read(self, mock_input, mock_ctx, mock_get_conn):
        """Test marking already-read notification"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import mark_notification_read

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user
        # Notification with read_date already set
        self.mock_cursor.fetchone.return_value = self.sample_notifications[1]

        # Execute
        mark_notification_read()

        # Should not update
        update_calls = [call for call in self.mock_cursor.execute.call_args_list
                       if 'UPDATE' in str(call)]
        assert len(update_calls) == 0

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.backup_before_operation')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.log_audit_action')
    @patch('builtins.input', side_effect=['1'])  # Clear read notifications older than 30 days
    def test_clear_old_notifications_option1(self, mock_input, mock_log_audit, mock_backup,
                                            mock_ctx, mock_get_conn):
        """Test clearing read notifications older than 30 days"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import clear_old_notifications

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user
        mock_ctx.auth.check_permission.return_value = True
        self.mock_cursor.rowcount = 15

        # Execute
        clear_old_notifications()

        # Verify DELETE was called
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list
                       if 'DELETE' in str(call)]
        assert len(delete_calls) == 1
        assert 'read_date IS NOT NULL' in str(delete_calls[0])

        self.mock_conn.commit.assert_called_once()

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.backup_before_operation')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.log_audit_action')
    @patch('builtins.input', side_effect=['2'])  # Clear all older than 90 days
    def test_clear_old_notifications_option2(self, mock_input, mock_log_audit, mock_backup,
                                            mock_ctx, mock_get_conn):
        """Test clearing all notifications older than 90 days"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import clear_old_notifications

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user
        mock_ctx.auth.check_permission.return_value = True
        self.mock_cursor.rowcount = 25

        # Execute
        clear_old_notifications()

        # Verify DELETE with 90 day cutoff
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list
                       if 'DELETE' in str(call)]
        assert len(delete_calls) == 1

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.backup_before_operation')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.log_audit_action')
    @patch('builtins.input', side_effect=['3', 'Low'])  # Clear by priority
    def test_clear_old_notifications_by_priority(self, mock_input, mock_log_audit, mock_backup,
                                                 mock_ctx, mock_get_conn):
        """Test clearing notifications by priority"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import clear_old_notifications

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user
        mock_ctx.auth.check_permission.return_value = True
        self.mock_cursor.rowcount = 5

        # Execute
        clear_old_notifications()

        # Verify DELETE with priority filter
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list
                       if 'DELETE' in str(call)]
        assert len(delete_calls) == 1
        assert 'priority = ?' in str(delete_calls[0])

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    def test_clear_old_notifications_no_permission(self, mock_ctx):
        """Test clearing notifications without admin permission"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import clear_old_notifications

        # Setup mocks
        mock_ctx.auth.current_user = self.mock_user
        mock_ctx.auth.check_permission.return_value = False

        # Execute
        clear_old_notifications()

        # Should exit early

    @patch('builtins.input', return_value='5')
    @patch('builtins.print')
    def test_manage_notifications_return(self, mock_print, mock_input):
        """Test manage notifications menu - return option"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import manage_notifications

        # Execute
        manage_notifications()

        # Should return without error
        assert mock_input.call_count == 1


class TestNotificationsIntegration(unittest.TestCase):
    """Integration tests for notification operations"""

    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.get_db_connection')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.ctx')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.backup_before_operation')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.log_audit_action')
    @patch('education_system.post_18.university_system.modules.core.services.restaurant_misc.notifications.datetime')
    def test_create_and_mark_read_workflow(self, mock_datetime, mock_log_audit, mock_backup,
                                          mock_ctx, mock_get_conn):
        """Test creating and marking notification as read"""
        from education_system.post_18.university_system.modules.domain.commerce.services.restaurant.operations.notifications import (
            create_notification,
            mark_notification_read
        )

        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_ctx.auth.current_user = {'id': 'TEST_USER'}
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
        mock_datetime.strftime = datetime.strftime

        # Create notification
        with patch('builtins.input', side_effect=[
            'USER123', '1', 'Test', 'Test message', '1', '', 'n'
        ]):
            create_notification()

        # Verify creation
        assert mock_cursor.execute.called

        # Mark as read
        mock_cursor.fetchone.return_value = ('NOT001', 'USER123', 'Info', 'Test',
                                             '2024-01-15 10:00:00', None, 'Low', 'Test', 0)
        with patch('builtins.input', return_value='NOT001'):
            mark_notification_read()

        # Verify both operations completed
        assert mock_log_audit.call_count >= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
