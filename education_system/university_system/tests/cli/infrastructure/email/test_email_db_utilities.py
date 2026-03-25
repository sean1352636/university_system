"""
Comprehensive test suite for infrastructure/email/email_db_utilities.py
Tests database operations, connection management, threading, and initialization with proper mocking
"""

import sys
import os
import tempfile
import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import threading
import time
from unittest.mock import Mock, patch, MagicMock, call, PropertyMock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from education_system.university_system.infrastructure.email import email_db_utilities

class TestModuleConstants:
    """Test suite for module-level constants and configuration"""

    def test_use_auth_db_flag_exists(self):
        """Test that USE_AUTH_DB flag exists"""
        assert hasattr(email_db_utilities, 'USE_AUTH_DB')
        assert isinstance(email_db_utilities.USE_AUTH_DB, bool)

    def test_main_dir_exists(self):
        """Test that MAIN_DIR constant exists"""
        assert hasattr(email_db_utilities, 'MAIN_DIR')
        assert isinstance(email_db_utilities.MAIN_DIR, str)

    def test_project_root_exists(self):
        """Test that PROJECT_ROOT constant exists"""
        assert hasattr(email_db_utilities, 'PROJECT_ROOT')

    def test_db_path_exists(self):
        """Test that DB_PATH constant exists"""
        assert hasattr(email_db_utilities, 'DB_PATH')
        assert isinstance(email_db_utilities.DB_PATH, str)

    def test_db_ready_flag_exists(self):
        """Test that _DB_READY flag exists"""
        assert hasattr(email_db_utilities, '_DB_READY')
        assert isinstance(email_db_utilities._DB_READY, bool)

class TestEnsureDbDirectory:
    """Test suite for ensure_db_directory() function"""

    @patch('education_system.university_system.modules.shared.constants.paths.DB_DIR')
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_ensure_db_directory_creates_new(self, mock_log, mock_makedirs, mock_exists, mock_db_dir):
        """Test ensure_db_directory creates directory when missing"""
        mock_db_dir.__fspath__ = Mock(return_value='/path/to/db')
        mock_exists.return_value = False

        result = email_db_utilities.ensure_db_directory()

        mock_makedirs.assert_called_once_with('/path/to/db', exist_ok=True)
        assert result == '/path/to/db'
        mock_log.assert_called_once()

    @patch('education_system.university_system.modules.shared.constants.paths.DB_DIR')
    @patch('os.path.exists')
    @patch('os.makedirs')
    def test_ensure_db_directory_exists_already(self, mock_makedirs, mock_exists, mock_db_dir):
        """Test ensure_db_directory when directory exists"""
        mock_db_dir.__fspath__ = Mock(return_value='/path/to/db')
        mock_exists.return_value = True

        result = email_db_utilities.ensure_db_directory()

        mock_makedirs.assert_not_called()
        assert result == '/path/to/db'

class TestEnsureParentDir:
    """Test suite for ensure_parent_dir() function"""

    @patch('os.makedirs')
    @patch('os.path.dirname')
    def test_ensure_parent_dir_creates_directory(self, mock_dirname, mock_makedirs):
        """Test ensure_parent_dir creates parent directory"""
        mock_dirname.return_value = '/path/to'

        email_db_utilities.ensure_parent_dir('/path/to/file.db')

        mock_makedirs.assert_called_once_with('/path/to', exist_ok=True)

    @patch('os.makedirs')
    @patch('os.path.dirname')
    def test_ensure_parent_dir_no_parent(self, mock_dirname, mock_makedirs):
        """Test ensure_parent_dir handles file with no parent directory"""
        mock_dirname.return_value = ''

        email_db_utilities.ensure_parent_dir('file.db')

        mock_makedirs.assert_not_called()

class TestGetUnifiedConnection:
    """Test suite for get_unified_connection() function"""

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.USE_AUTH_DB', True)
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.auth_get_connection')
    def test_get_unified_connection_uses_auth_db(self, mock_auth_conn):
        """Test get_unified_connection uses auth DB when available"""
        mock_conn = MagicMock()
        mock_auth_conn.return_value = mock_conn

        result = email_db_utilities.get_unified_connection()

        assert result == mock_conn
        mock_auth_conn.assert_called_once()

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.USE_AUTH_DB', True)
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.auth_get_connection')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.sqlite3.connect')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_get_unified_connection_fallback_on_auth_error(self, mock_log, mock_connect, mock_auth_conn):
        """Test get_unified_connection falls back to direct connection on auth error"""
        mock_auth_conn.side_effect = Exception("Auth DB error")
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = email_db_utilities.get_unified_connection()

        assert result == mock_conn
        mock_connect.assert_called_once()
        # Should log warning about fallback
        warning_calls = [call for call in mock_log.call_args_list if call[0][0] == 'warning']
        assert len(warning_calls) > 0

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.USE_AUTH_DB', False)
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.sqlite3.connect')
    def test_get_unified_connection_direct_when_auth_disabled(self, mock_connect):
        """Test get_unified_connection uses direct connection when auth disabled"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = email_db_utilities.get_unified_connection()

        assert result == mock_conn
        mock_connect.assert_called_once_with(email_db_utilities.DB_PATH, timeout=30.0)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.USE_AUTH_DB', False)
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.sqlite3.connect')
    def test_get_unified_connection_sets_row_factory(self, mock_connect):
        """Test get_unified_connection sets row_factory"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = email_db_utilities.get_unified_connection()

        assert result.row_factory == sqlite3.Row

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.USE_AUTH_DB', False)
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.sqlite3.connect')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_get_unified_connection_handles_connection_error(self, mock_log, mock_connect):
        """Test get_unified_connection handles connection errors"""
        mock_connect.side_effect = sqlite3.Error("Connection failed")

        with pytest.raises(sqlite3.Error):
            email_db_utilities.get_unified_connection()

        # Should log error
        error_calls = [call for call in mock_log.call_args_list if call[0][0] == 'error']
        assert len(error_calls) > 0

class TestSimpleDBManager:
    """Test suite for SimpleDBManager class"""

    def test_simple_db_manager_init_default_path(self):
        """Test SimpleDBManager initializes with default DB path"""
        with patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir'):
            manager = email_db_utilities.SimpleDBManager()

            assert manager.db_path == email_db_utilities.DB_PATH
            assert hasattr(manager, '_lock')
            # RLock is not directly comparable, check it's a lock object
            assert hasattr(manager._lock, 'acquire')
            assert hasattr(manager._lock, 'release')

    def test_simple_db_manager_init_custom_path(self):
        """Test SimpleDBManager initializes with custom DB path"""
        custom_path = '/custom/path/db.sqlite'

        with patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir'):
            manager = email_db_utilities.SimpleDBManager(db_path=custom_path)

            assert manager.db_path == custom_path

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir')
    def test_simple_db_manager_ensures_parent_dir(self, mock_ensure_parent):
        """Test SimpleDBManager ensures parent directory exists"""
        test_path = '/test/path/db.sqlite'

        manager = email_db_utilities.SimpleDBManager(db_path=test_path)

        mock_ensure_parent.assert_called_once_with(test_path)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_unified_connection')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir')
    def test_simple_db_manager_get_connection_success(self, mock_ensure, mock_get_conn):
        """Test SimpleDBManager.get_connection yields cursor"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        manager = email_db_utilities.SimpleDBManager()

        with manager.get_connection() as cursor:
            assert cursor == mock_cursor

        # Should execute PRAGMA statements
        assert mock_conn.execute.call_count >= 3

        # Should commit at the end
        mock_conn.commit.assert_called_once()

        # Should close connection
        mock_conn.close.assert_called_once()

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_unified_connection')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir')
    def test_simple_db_manager_get_connection_pragma_settings(self, mock_ensure, mock_get_conn):
        """Test SimpleDBManager.get_connection sets proper PRAGMA settings"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        manager = email_db_utilities.SimpleDBManager()

        with manager.get_connection() as cursor:
            pass

        # Verify PRAGMA calls
        pragma_calls = [str(call) for call in mock_conn.execute.call_args_list]
        assert any('WAL' in str(call) for call in pragma_calls)
        assert any('NORMAL' in str(call) for call in pragma_calls)
        assert any('busy_timeout' in str(call) for call in pragma_calls)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_unified_connection')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir')
    def test_simple_db_manager_get_connection_rollback_on_error(self, mock_ensure, mock_get_conn):
        """Test SimpleDBManager.get_connection rolls back on error"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        manager = email_db_utilities.SimpleDBManager()

        with pytest.raises(Exception):
            with manager.get_connection() as cursor:
                raise Exception("Test error")

        # Should rollback instead of commit
        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_unified_connection')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir')
    def test_simple_db_manager_get_connection_closes_on_error(self, mock_ensure, mock_get_conn):
        """Test SimpleDBManager.get_connection closes connection on error"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        manager = email_db_utilities.SimpleDBManager()

        with pytest.raises(Exception):
            with manager.get_connection() as cursor:
                raise Exception("Test error")

        # Should still close connection
        mock_conn.close.assert_called_once()

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_unified_connection')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir')
    def test_simple_db_manager_get_connection_lock_timeout(self, mock_ensure, mock_get_conn):
        """Test SimpleDBManager.get_connection raises error on lock timeout"""
        manager = email_db_utilities.SimpleDBManager()

        # Replace the lock with a mock lock (RLock acquire is read-only)
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = False
        manager._lock = mock_lock

        with pytest.raises(sqlite3.OperationalError, match="Could not acquire database lock"):
            with manager.get_connection(timeout=1):
                pass

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_unified_connection')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir')
    def test_simple_db_manager_thread_safety(self, mock_ensure, mock_get_conn):
        """Test SimpleDBManager is thread-safe (uses RLock)"""
        manager = email_db_utilities.SimpleDBManager()

        # Check that _lock has RLock methods (acquire and release)
        assert hasattr(manager._lock, 'acquire')
        assert hasattr(manager._lock, 'release')
        # Verify it's reentrant by acquiring twice from same thread
        assert manager._lock.acquire(blocking=False)
        assert manager._lock.acquire(blocking=False)
        manager._lock.release()
        manager._lock.release()

class TestGetDbManager:
    """Test suite for get_db_manager() function"""

    def test_get_db_manager_returns_singleton(self):
        """Test get_db_manager returns same instance (singleton pattern)"""
        # Reset the global manager
        with patch('education_system.university_system.infrastructure.email.email_db_utilities._db_manager', None):
            with patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir'):
                manager1 = email_db_utilities.get_db_manager()
                manager2 = email_db_utilities.get_db_manager()

                assert manager1 is manager2

    def test_get_db_manager_thread_safe(self):
        """Test get_db_manager is thread-safe"""
        # Reset the global manager
        email_db_utilities._db_manager = None

        managers = []

        def get_manager():
            with patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir'):
                managers.append(email_db_utilities.get_db_manager())

        threads = [threading.Thread(target=get_manager) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All managers should be the same instance
        assert all(m is managers[0] for m in managers)

    def test_get_db_manager_creates_manager(self):
        """Test get_db_manager creates SimpleDBManager instance"""
        # Reset the global manager
        with patch('education_system.university_system.infrastructure.email.email_db_utilities._db_manager', None):
            with patch('education_system.university_system.infrastructure.email.email_db_utilities.ensure_parent_dir'):
                manager = email_db_utilities.get_db_manager()

                assert isinstance(manager, email_db_utilities.SimpleDBManager)

class TestExecuteDbOperation:
    """Test suite for execute_db_operation() function"""

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_db_manager')
    def test_execute_db_operation_success(self, mock_get_manager):
        """Test execute_db_operation executes function successfully"""
        mock_manager = MagicMock()
        mock_cursor = MagicMock()
        mock_manager.get_connection.return_value.__enter__.return_value = mock_cursor
        mock_get_manager.return_value = mock_manager

        def test_operation(cursor):
            return "success"

        result = email_db_utilities.execute_db_operation(test_operation)

        assert result == "success"

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_db_manager')
    def test_execute_db_operation_with_args(self, mock_get_manager):
        """Test execute_db_operation passes args to operation"""
        mock_manager = MagicMock()
        mock_cursor = MagicMock()
        mock_manager.get_connection.return_value.__enter__.return_value = mock_cursor
        mock_get_manager.return_value = mock_manager

        def test_operation(cursor, arg1, arg2):
            return arg1 + arg2

        result = email_db_utilities.execute_db_operation(test_operation, 10, 20)

        assert result == 30

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_db_manager')
    def test_execute_db_operation_with_kwargs(self, mock_get_manager):
        """Test execute_db_operation passes kwargs to operation"""
        mock_manager = MagicMock()
        mock_cursor = MagicMock()
        mock_manager.get_connection.return_value.__enter__.return_value = mock_cursor
        mock_get_manager.return_value = mock_manager

        def test_operation(cursor, value=0):
            return value * 2

        result = email_db_utilities.execute_db_operation(test_operation, value=15)

        assert result == 30

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_db_manager')
    @patch('time.sleep')
    def test_execute_db_operation_retries_on_lock(self, mock_sleep, mock_get_manager):
        """Test execute_db_operation retries on database lock"""
        mock_manager = MagicMock()
        mock_cursor = MagicMock()

        # First two attempts fail with locked error, third succeeds
        call_count = [0]

        def get_connection_side_effect():
            call_count[0] += 1
            if call_count[0] < 3:
                raise sqlite3.OperationalError("database is locked")
            return MagicMock(__enter__=lambda self: mock_cursor, __exit__=lambda *args: None)

        mock_manager.get_connection.side_effect = get_connection_side_effect
        mock_get_manager.return_value = mock_manager

        def test_operation(cursor):
            return "success"

        result = email_db_utilities.execute_db_operation(test_operation, max_retries=3)

        assert result == "success"
        assert call_count[0] == 3
        # Should have slept twice (after first two failures)
        assert mock_sleep.call_count == 2

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_db_manager')
    @patch('time.sleep')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.logger')
    def test_execute_db_operation_max_retries_exceeded(self, mock_logger, mock_sleep, mock_get_manager):
        """Test execute_db_operation raises error after max retries"""
        mock_manager = MagicMock()
        mock_manager.get_connection.side_effect = sqlite3.OperationalError("database is locked")
        mock_get_manager.return_value = mock_manager

        def test_operation(cursor):
            return "success"

        with pytest.raises(sqlite3.OperationalError):
            email_db_utilities.execute_db_operation(test_operation, max_retries=3)

        # Should have tried 3 times
        assert mock_manager.get_connection.call_count == 3
        # Should have slept 2 times (not after last attempt)
        assert mock_sleep.call_count == 2

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_db_manager')
    @patch('time.sleep')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.logger')
    def test_execute_db_operation_exponential_backoff(self, mock_logger, mock_sleep, mock_get_manager):
        """Test execute_db_operation uses exponential backoff"""
        mock_manager = MagicMock()
        mock_manager.get_connection.side_effect = sqlite3.OperationalError("database is locked")
        mock_get_manager.return_value = mock_manager

        def test_operation(cursor):
            return "success"

        try:
            email_db_utilities.execute_db_operation(test_operation, max_retries=3)
        except (OSError, IOError):
            pass

        # Check that sleep times increase (exponential backoff with random component)
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        # First sleep should be around 1 second (2^0 + random)
        # Second sleep should be around 2 seconds (2^1 + random)
        assert len(sleep_calls) == 2
        assert sleep_calls[0] < sleep_calls[1]  # Exponential increase

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_db_manager')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.logger')
    def test_execute_db_operation_non_lock_error_no_retry(self, mock_logger, mock_get_manager):
        """Test execute_db_operation doesn't retry on non-lock errors"""
        mock_manager = MagicMock()
        mock_cursor = MagicMock()
        mock_manager.get_connection.return_value.__enter__.return_value = mock_cursor
        mock_get_manager.return_value = mock_manager

        def test_operation(cursor):
            raise sqlite3.IntegrityError("UNIQUE constraint failed")

        with pytest.raises(sqlite3.IntegrityError):
            email_db_utilities.execute_db_operation(test_operation, max_retries=3)

        # Should only try once (no retries for non-lock errors)
        assert mock_manager.get_connection.call_count == 1

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.get_db_manager')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.logger')
    def test_execute_db_operation_logs_info_on_lock(self, mock_logger, mock_get_manager):
        """Test execute_db_operation logs info (not warning) on lock retry"""
        mock_manager = MagicMock()

        call_count = [0]

        def get_connection_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                raise sqlite3.OperationalError("database is locked")
            return MagicMock(__enter__=lambda self: MagicMock(), __exit__=lambda *args: None)

        mock_manager.get_connection.side_effect = get_connection_side_effect
        mock_get_manager.return_value = mock_manager

        with patch('time.sleep'):
            email_db_utilities.execute_db_operation(lambda cursor: None, max_retries=3)

        # Should log at INFO level, not WARNING
        info_calls = [call for call in mock_logger.info.call_args_list if 'locked' in str(call)]
        assert len(info_calls) > 0

class TestSafeDbOperation:
    """Test suite for safe_db_operation() function"""

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    def test_safe_db_operation_calls_execute(self, mock_execute):
        """Test safe_db_operation calls execute_db_operation"""
        mock_execute.return_value = "result"

        def test_op(cursor):
            return "test"

        result = email_db_utilities.safe_db_operation(test_op, arg1="value")

        mock_execute.assert_called_once()
        assert result == "result"

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    def test_safe_db_operation_passes_args(self, mock_execute):
        """Test safe_db_operation passes arguments correctly"""
        def test_op(cursor, val):
            return val

        email_db_utilities.safe_db_operation(test_op, 42)

        # Verify execute_db_operation was called with correct args
        call_args = mock_execute.call_args
        assert call_args[0][0] == test_op
        assert call_args[0][1] == 42

class TestInitializeEmailDb:
    """Test suite for initialize_email_db() function"""

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_initialize_email_db_success(self, mock_log, mock_execute):
        """Test initialize_email_db creates all tables successfully"""
        mock_execute.return_value = True

        result = email_db_utilities.initialize_email_db()

        assert result is True
        mock_execute.assert_called_once()
        # Should log success
        info_calls = [call for call in mock_log.call_args_list if call[0][0] == 'info']
        assert any('successfully' in str(call) for call in info_calls)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_initialize_email_db_creates_stored_emails_table(self, mock_log, mock_execute):
        """Test initialize_email_db creates stored_emails table"""
        captured_func = None

        def capture_func(func):
            nonlocal captured_func
            captured_func = func
            return True

        mock_execute.side_effect = capture_func

        email_db_utilities.initialize_email_db()

        # Execute the captured function with a mock cursor
        mock_cursor = MagicMock()
        if captured_func:
            captured_func(mock_cursor)

        # Check that stored_emails table was created
        create_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('stored_emails' in call for call in create_calls)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_initialize_email_db_creates_email_log_table(self, mock_log, mock_execute):
        """Test initialize_email_db creates email_log table"""
        captured_func = None

        def capture_func(func):
            nonlocal captured_func
            captured_func = func
            return True

        mock_execute.side_effect = capture_func

        email_db_utilities.initialize_email_db()

        mock_cursor = MagicMock()
        if captured_func:
            captured_func(mock_cursor)

        create_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('email_log' in call for call in create_calls)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_initialize_email_db_creates_messages_table(self, mock_log, mock_execute):
        """Test initialize_email_db creates messages table"""
        captured_func = None

        def capture_func(func):
            nonlocal captured_func
            captured_func = func
            return True

        mock_execute.side_effect = capture_func

        email_db_utilities.initialize_email_db()

        mock_cursor = MagicMock()
        if captured_func:
            captured_func(mock_cursor)

        create_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('messages' in call and 'CREATE TABLE' in call for call in create_calls)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_initialize_email_db_creates_email_metrics_table(self, mock_log, mock_execute):
        """Test initialize_email_db creates email_metrics table"""
        captured_func = None

        def capture_func(func):
            nonlocal captured_func
            captured_func = func
            return True

        mock_execute.side_effect = capture_func

        email_db_utilities.initialize_email_db()

        mock_cursor = MagicMock()
        if captured_func:
            captured_func(mock_cursor)

        create_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('email_metrics' in call for call in create_calls)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_initialize_email_db_creates_scheduled_emails_table(self, mock_log, mock_execute):
        """Test initialize_email_db creates scheduled_emails table"""
        captured_func = None

        def capture_func(func):
            nonlocal captured_func
            captured_func = func
            return True

        mock_execute.side_effect = capture_func

        email_db_utilities.initialize_email_db()

        mock_cursor = MagicMock()
        # Mock table_info to simulate table doesn't exist
        mock_cursor.fetchone.return_value = None

        if captured_func:
            captured_func(mock_cursor)

        create_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('scheduled_emails' in call for call in create_calls)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_initialize_email_db_creates_indexes(self, mock_log, mock_execute):
        """Test initialize_email_db creates indexes"""
        captured_func = None

        def capture_func(func):
            nonlocal captured_func
            captured_func = func
            return True

        mock_execute.side_effect = capture_func

        email_db_utilities.initialize_email_db()

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        if captured_func:
            captured_func(mock_cursor)

        create_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        # Check for index creation
        assert any('CREATE INDEX' in call for call in create_calls)

class TestMigrateEmailLogTable:
    """Test suite for migrate_email_log_table() function"""

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_migrate_email_log_table_adds_missing_columns(self, mock_log, mock_execute):
        """Test migrate_email_log_table adds missing columns"""
        captured_func = None

        def capture_func(func):
            nonlocal captured_func
            captured_func = func
            return True

        mock_execute.side_effect = capture_func

        result = email_db_utilities.migrate_email_log_table()

        assert result is True

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_migrate_email_log_table_handles_existing_columns(self, mock_log, mock_execute):
        """Test migrate_email_log_table handles already-existing columns"""
        captured_func = None

        def capture_func(func):
            nonlocal captured_func
            captured_func = func
            return True

        mock_execute.side_effect = capture_func

        email_db_utilities.migrate_email_log_table()

        # Should not raise error if columns already exist
        mock_cursor = MagicMock()
        # Simulate all columns exist
        mock_cursor.fetchall.return_value = [
            (0, 'sender_email', 'TEXT', 0, None, 0),
            (1, 'sender_name', 'TEXT', 0, None, 0),
            (2, 'cc_recipients', 'TEXT', 0, None, 0),
            (3, 'bcc_recipients', 'TEXT', 0, None, 0),
            (4, 'attachment_info', 'TEXT', 0, None, 0),
            (5, 'template_name', 'TEXT', 0, None, 0),
            (6, 'template_vars', 'TEXT', 0, None, 0),
        ]

        if captured_func:
            result = captured_func(mock_cursor)
            assert result is True

class TestOptimizeDatabase:
    """Test suite for optimize_database() function"""

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_optimize_database_success(self, mock_log, mock_execute):
        """Test optimize_database runs successfully"""
        mock_execute.return_value = True

        result = email_db_utilities.optimize_database()

        assert result is True
        mock_execute.assert_called_once()
        # Should log success
        info_calls = [call for call in mock_log.call_args_list if call[0][0] == 'info']
        assert any('optimization completed' in str(call).lower() for call in info_calls)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_optimize_database_runs_pragma_optimize(self, mock_log, mock_execute):
        """Test optimize_database runs PRAGMA optimize"""
        captured_func = None

        def capture_func(func):
            nonlocal captured_func
            captured_func = func
            return True

        mock_execute.side_effect = capture_func

        email_db_utilities.optimize_database()

        mock_cursor = MagicMock()
        if captured_func:
            captured_func(mock_cursor)

        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('PRAGMA optimize' in call for call in execute_calls)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_optimize_database_runs_wal_checkpoint(self, mock_log, mock_execute):
        """Test optimize_database runs WAL checkpoint"""
        captured_func = None

        def capture_func(func):
            nonlocal captured_func
            captured_func = func
            return True

        mock_execute.side_effect = capture_func

        email_db_utilities.optimize_database()

        mock_cursor = MagicMock()
        if captured_func:
            captured_func(mock_cursor)

        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('wal_checkpoint' in call for call in execute_calls)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_optimize_database_runs_analyze(self, mock_log, mock_execute):
        """Test optimize_database runs ANALYZE"""
        captured_func = None

        def capture_func(func):
            nonlocal captured_func
            captured_func = func
            return True

        mock_execute.side_effect = capture_func

        email_db_utilities.optimize_database()

        mock_cursor = MagicMock()
        if captured_func:
            captured_func(mock_cursor)

        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('ANALYZE' in call for call in execute_calls)

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.log_event')
    def test_optimize_database_handles_error(self, mock_log, mock_execute):
        """Test optimize_database handles errors gracefully"""
        mock_execute.side_effect = Exception("Optimization error")

        result = email_db_utilities.optimize_database()

        assert result is False
        # Should log error
        error_calls = [call for call in mock_log.call_args_list if call[0][0] == 'error']
        assert len(error_calls) > 0

class TestScheduleDatabaseMaintenance:
    """Test suite for schedule_database_maintenance() function"""

    def test_schedule_database_maintenance_schedules_job(self):
        """Test schedule_database_maintenance schedules daily job"""
        # Import schedule inside the test
        import schedule as schedule_module

        with patch.object(schedule_module, 'every') as mock_every:
            mock_day = MagicMock()
            mock_at = MagicMock()

            mock_every.return_value = mock_every
            mock_every.day = mock_day
            mock_day.at.return_value = mock_at

            email_db_utilities.schedule_database_maintenance()

            mock_every.assert_called_once()
            mock_day.at.assert_called_once_with("02:00")

class TestHelperFunctions:
    """Test suite for internal helper functions"""

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    def test_get_or_create_sender_id_existing_user(self, mock_execute):
        """Test _get_or_create_sender_id returns existing user ID"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (123,)

        result = email_db_utilities._get_or_create_sender_id(
            mock_cursor,
            'user@example.com',
            'John Doe',
            '2024-01-01 00:00:00'
        )

        assert result == 123

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    def test_get_or_create_sender_id_creates_system_user(self, mock_execute):
        """Test _get_or_create_sender_id creates system user when needed"""
        mock_cursor = MagicMock()
        # First call (find user): None, Second call (find system user): None
        mock_cursor.fetchone.side_effect = [None, None]
        mock_cursor.lastrowid = 456

        result = email_db_utilities._get_or_create_sender_id(
            mock_cursor,
            'noreply@example.com',
            'No Reply',
            '2024-01-01 00:00:00'
        )

        assert result == 456
        # Should have created a new user
        insert_calls = [call for call in mock_cursor.execute.call_args_list if 'INSERT INTO users' in str(call)]
        assert len(insert_calls) > 0

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    def test_get_or_create_sender_id_returns_existing_system_user(self, mock_execute):
        """Test _get_or_create_sender_id returns existing system user"""
        mock_cursor = MagicMock()
        # First call (find real user): None, Second call (find system user): found
        mock_cursor.fetchone.side_effect = [None, (789,)]

        result = email_db_utilities._get_or_create_sender_id(
            mock_cursor,
            'system@example.com',
            'System',
            '2024-01-01 00:00:00'
        )

        assert result == 789

class TestDbReadyInitialization:
    """Test suite for _ensure_db_ready() and _sync_inbox_messages()"""

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.initialize_email_db')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities._sync_inbox_messages')
    def test_ensure_db_ready_initializes_once(self, mock_sync, mock_init):
        """Test _ensure_db_ready only initializes once"""
        # Reset the _DB_READY flag
        email_db_utilities._DB_READY = False

        email_db_utilities._ensure_db_ready()
        email_db_utilities._ensure_db_ready()

        # Should only initialize once
        mock_init.assert_called_once()
        mock_sync.assert_called_once()

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.initialize_email_db')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities._sync_inbox_messages')
    def test_ensure_db_ready_handles_init_error(self, mock_sync, mock_init):
        """Test _ensure_db_ready handles initialization errors"""
        email_db_utilities._DB_READY = False
        mock_init.side_effect = Exception("Init error")

        with pytest.raises(Exception, match="Init error"):
            email_db_utilities._ensure_db_ready()

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.logger')
    def test_sync_inbox_messages_no_missing_messages(self, mock_logger, mock_execute):
        """Test _sync_inbox_messages handles no missing messages"""
        mock_execute.return_value = 0

        result = email_db_utilities._sync_inbox_messages()

        assert result == 0

    @patch('education_system.university_system.infrastructure.email.email_db_utilities.execute_db_operation')
    @patch('education_system.university_system.infrastructure.email.email_db_utilities.logger')
    def test_sync_inbox_messages_handles_error(self, mock_logger, mock_execute):
        """Test _sync_inbox_messages handles errors gracefully"""
        mock_execute.side_effect = Exception("Sync error")

        result = email_db_utilities._sync_inbox_messages()

        # Should not raise, just return 0
        assert result == 0
        # Should log warning
        assert mock_logger.warning.called

class TestModuleIntegration:
    """Test suite for module-level integration"""

    def test_module_imports(self):
        """Test that all necessary imports are available"""
        assert hasattr(email_db_utilities, 'sqlite3')
        assert hasattr(email_db_utilities, 'threading')
        assert hasattr(email_db_utilities, 'time')
        assert hasattr(email_db_utilities, 'contextlib')

    def test_all_public_functions_exist(self):
        """Test that all public functions are accessible"""
        expected_functions = [
            'ensure_db_directory',
            'ensure_parent_dir',
            'get_unified_connection',
            'get_db_manager',
            'execute_db_operation',
            'safe_db_operation',
            'initialize_email_db',
            'migrate_email_log_table',
            'optimize_database',
            'schedule_database_maintenance'
        ]

        for func_name in expected_functions:
            assert hasattr(email_db_utilities, func_name)
            assert callable(getattr(email_db_utilities, func_name))

    def test_simple_db_manager_class_exists(self):
        """Test that SimpleDBManager class is accessible"""
        assert hasattr(email_db_utilities, 'SimpleDBManager')
        assert isinstance(email_db_utilities.SimpleDBManager, type)

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '--cov=university_system.infrastructure.email.email_db_utilities', '--cov-report=term-missing'])
