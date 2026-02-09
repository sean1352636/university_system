"""
Comprehensive tests for restaurant maintenance module.

Tests cover:
- Database cleanup operations
- Log file management
- System counter resets
- Index rebuilding
- System health checks
- Cache clearing
- Database optimization
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import pytest


class TestMaintenanceModule(unittest.TestCase):
    """Test suite for maintenance.py module"""

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

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.get_db_connection')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.log_audit_action')
    def test_database_cleanup(self, mock_log_audit, mock_ctx, mock_get_conn):
        """Test database cleanup operation"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import database_cleanup

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user
        self.mock_cursor.rowcount = 10

        # Execute
        database_cleanup()

        # Verify database operations
        assert self.mock_cursor.execute.call_count >= 3
        self.mock_conn.commit.assert_called_once()
        self.mock_conn.close.assert_called_once()

        # Verify audit log was called
        mock_log_audit.assert_called_once()
        call_args = mock_log_audit.call_args
        assert call_args[0][0] == 'TEST_USER_001'
        assert call_args[0][1] == 'DATABASE_CLEANUP'

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.os.listdir')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.os.path.exists')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.os.path.getmtime')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.os.path.getsize')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.os.remove')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.get_log_file')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.log_audit_action')
    def test_clear_old_logs(self, mock_log_audit, mock_ctx, mock_get_log_file,
                           mock_remove, mock_getsize, mock_getmtime,
                           mock_exists, mock_listdir):
        """Test clearing old log files"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import clear_old_logs

        # Setup mocks
        mock_ctx.auth.current_user = self.mock_user
        mock_get_log_file.return_value = '/tmp/logs/restaurant_system.log'
        mock_exists.return_value = True
        mock_listdir.return_value = ['old_log.log', 'new_log.log', 'other.txt']

        # Old file timestamp (35 days ago)
        old_timestamp = (datetime.now() - timedelta(days=35)).timestamp()
        new_timestamp = datetime.now().timestamp()

        mock_getmtime.side_effect = [old_timestamp, new_timestamp]
        mock_getsize.return_value = 1024 * 1024  # 1 MB

        # Execute
        clear_old_logs()

        # Verify only old log was removed
        mock_remove.assert_called_once()
        assert 'old_log.log' in str(mock_remove.call_args)

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.get_db_connection')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.log_audit_action')
    @patch('builtins.input', return_value='y')
    def test_reset_system_counters(self, mock_input, mock_log_audit, mock_ctx, mock_get_conn):
        """Test resetting system counters"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import reset_system_counters

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user

        # Execute
        reset_system_counters()

        # Verify database operations
        assert self.mock_cursor.execute.call_count >= 2
        self.mock_conn.commit.assert_called_once()
        self.mock_conn.close.assert_called_once()

        # Verify audit log
        mock_log_audit.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.get_db_connection')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.log_audit_action')
    def test_rebuild_indexes(self, mock_log_audit, mock_ctx, mock_get_conn):
        """Test rebuilding database indexes"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import rebuild_indexes

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user

        # Execute
        rebuild_indexes()

        # Verify multiple index operations
        assert self.mock_cursor.execute.call_count > 10  # Multiple DROP/CREATE calls
        self.mock_conn.commit.assert_called_once()
        self.mock_conn.close.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.get_db_connection')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.os.path.getsize')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.DATABASE_FILE', '/tmp/test.db')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.log_audit_action')
    def test_system_health_check(self, mock_log_audit, mock_getsize, mock_ctx, mock_get_conn):
        """Test system health check"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import system_health_check

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user
        mock_getsize.return_value = 10 * 1024 * 1024  # 10 MB

        # Mock database responses
        self.mock_cursor.fetchone.side_effect = [
            ('ok',),  # integrity check
            (100,),   # menu_items count
            (50,),    # restaurant_orders count
            (200,),   # restaurant_customers count
            (25,),    # restaurant_tables count
            (15,),    # restaurant_staff count
            (300,),   # restaurant_inventory count
            (10,),    # restaurant_suppliers count
            (0,),     # orphaned orders
            (0,),     # orphaned items
            (5,),     # system settings count
        ]

        # Execute
        system_health_check()

        # Verify multiple checks were performed
        assert self.mock_cursor.execute.call_count >= 10
        self.mock_conn.close.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.os.listdir')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.os.remove')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.log_audit_action')
    def test_clear_cache(self, mock_log_audit, mock_ctx, mock_remove, mock_listdir):
        """Test cache clearing"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import clear_cache

        # Setup mocks
        mock_ctx.auth.current_user = self.mock_user
        mock_listdir.return_value = ['file1.tmp', 'temp_file.txt', 'regular.txt']

        # Execute
        clear_cache()

        # Verify temp files were removed
        assert mock_remove.call_count == 2  # Only .tmp and temp_ files

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    @patch('builtins.input', return_value='7')
    @patch('builtins.print')
    def test_system_maintenance_menu_return(self, mock_print, mock_input, mock_ctx):
        """Test system maintenance menu - return option"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import system_maintenance

        # Setup mocks
        mock_ctx.auth.current_user = self.mock_user
        mock_ctx.auth.check_permission.return_value = True

        # Execute
        system_maintenance()

        # Should complete without error
        assert mock_input.call_count == 1

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    @patch('builtins.input', return_value='1')
    @patch('builtins.print')
    def test_system_maintenance_no_auth(self, mock_print, mock_input, mock_ctx):
        """Test system maintenance without authentication"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import system_maintenance

        # Setup mocks - no current user
        mock_ctx.auth = None

        # Execute
        system_maintenance()

        # Should print error message
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('must be logged in' in str(call).lower() for call in print_calls)

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    @patch('builtins.print')
    def test_system_maintenance_no_permission(self, mock_print, mock_ctx):
        """Test system maintenance without permission"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import system_maintenance

        # Setup mocks
        mock_ctx.auth.current_user = self.mock_user
        mock_ctx.auth.check_permission.return_value = False

        # Execute
        system_maintenance()

        # Should print permission error
        print_calls = [str(call) for call in mock_print.call_args_list]
        assert any('permission' in str(call).lower() for call in print_calls)

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.get_db_connection')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.log_audit_action')
    def test_update_statistics(self, mock_log_audit, mock_ctx, mock_get_conn):
        """Test database statistics update"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import update_statistics

        # Setup mocks
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user

        # Execute
        update_statistics()

        # Verify ANALYZE was called
        calls = [str(call) for call in self.mock_cursor.execute.call_args_list]
        assert any('ANALYZE' in str(call) for call in calls)
        self.mock_conn.commit.assert_called_once()

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.get_db_connection')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.log_audit_action')
    def test_defragment_database(self, mock_log_audit, mock_ctx, mock_get_conn):
        """Test database defragmentation"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import defragment_database

        # Setup mocks
        self.mock_conn.isolation_level = None
        mock_get_conn.return_value = self.mock_conn
        mock_ctx.auth.current_user = self.mock_user

        # Execute
        defragment_database()

        # Verify VACUUM was called
        calls = [str(call) for call in self.mock_conn.execute.call_args_list]
        assert any('VACUUM' in str(call) for call in calls)

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.get_db_connection')
    def test_database_cleanup_error_handling(self, mock_get_conn):
        """Test database cleanup error handling"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import database_cleanup

        # Setup mock to raise exception
        mock_get_conn.side_effect = Exception("Database connection error")

        # Execute - should not raise
        database_cleanup()

        # Should handle gracefully
        mock_get_conn.assert_called_once()


class TestMaintenanceIntegration(unittest.TestCase):
    """Integration tests for maintenance operations"""

    @patch('university_system.modules.core.services.restaurant_misc.maintenance.get_db_connection')
    @patch('university_system.modules.core.services.restaurant_misc.maintenance.ctx')
    def test_full_maintenance_workflow(self, mock_ctx, mock_get_conn):
        """Test full maintenance workflow"""
        from university_system.modules.domain.commerce.services.restaurant.operations.maintenance import (
            database_cleanup,
            rebuild_indexes,
            update_statistics
        )

        # Setup mocks
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_ctx.auth.current_user = {'id': 'TEST_USER'}

        # Execute maintenance workflow
        database_cleanup()
        rebuild_indexes()
        update_statistics()

        # Verify all operations completed
        assert mock_get_conn.call_count == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
