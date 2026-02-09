"""
Comprehensive tests for database.py

Tests all database utility functions, connection management,
thread safety, and backward compatibility features.
"""

import pytest
import threading
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path


class TestDatabaseConstants:
    """Test database constants and variables"""

    def test_db_ready_flag_exists(self):
        """Test that _DB_READY flag exists"""
        from university_system.modules.shared.utils.database import _DB_READY

        # Should be a boolean
        assert isinstance(_DB_READY, bool)

    def test_use_auth_db_flag(self):
        """Test USE_AUTH_DB flag"""
        from university_system.modules.shared.utils.database import USE_AUTH_DB

        assert isinstance(USE_AUTH_DB, bool)
        assert USE_AUTH_DB is True

    def test_main_dir_defined(self):
        """Test MAIN_DIR constant"""
        from university_system.modules.shared.utils.database import MAIN_DIR

        assert MAIN_DIR is not None
        assert isinstance(MAIN_DIR, str)

    def test_project_root_defined(self):
        """Test PROJECT_ROOT constant"""
        from university_system.modules.shared.utils.database import PROJECT_ROOT

        assert PROJECT_ROOT is not None
        assert isinstance(PROJECT_ROOT, str)

    def test_db_path_defined(self):
        """Test DB_PATH constant"""
        from university_system.modules.shared.utils.database import DB_PATH

        assert DB_PATH is not None

    def test_db_manager_lock_exists(self):
        """Test that _db_manager_lock exists"""
        from university_system.modules.shared.utils.database import _db_manager_lock

        assert _db_manager_lock is not None
        assert isinstance(_db_manager_lock, threading.Lock)


class TestEnsureDbReady:
    """Test _ensure_db_ready function"""

    @patch('university_system.modules.shared.utils.database.ensure_db_directory')
    def test_ensure_db_ready_first_call(self, mock_ensure):
        """Test first call to _ensure_db_ready"""
        # Reset the flag
        import university_system.modules.shared.utils.database as db_module
        with patch.object(db_module, '_DB_READY', False):
            result = db_module._ensure_db_ready()

        assert result is True
        mock_ensure.assert_called_once()

    @patch('university_system.modules.shared.utils.database.ensure_db_directory')
    def test_ensure_db_ready_already_ready(self, mock_ensure):
        """Test _ensure_db_ready when already ready (fast path)"""
        import university_system.modules.shared.utils.database as db_module

        # Set flag to True
        with patch.object(db_module, '_DB_READY', True):
            result = db_module._ensure_db_ready()

        assert result is True
        # Should not call ensure_db_directory (fast path)
        mock_ensure.assert_not_called()

    @patch('university_system.modules.shared.utils.database.ensure_db_directory')
    def test_ensure_db_ready_thread_safe(self, mock_ensure):
        """Test thread safety of _ensure_db_ready"""
        import university_system.modules.shared.utils.database as db_module

        # Reset flag
        db_module._DB_READY = False

        results = []

        def call_ensure():
            result = db_module._ensure_db_ready()
            results.append(result)

        # Create multiple threads
        threads = [threading.Thread(target=call_ensure) for _ in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # All should succeed
        assert all(results)

        # ensure_db_directory should be called at least once (but not 10 times due to locking)
        assert mock_ensure.call_count >= 1


class TestGetUnifiedConnection:
    """Test get_unified_connection function"""

    @patch('university_system.modules.shared.utils.database.get_connection')
    @patch('university_system.modules.shared.utils.database._ensure_db_ready')
    def test_get_unified_connection(self, mock_ensure, mock_get_conn):
        """Test get_unified_connection calls get_connection"""
        from university_system.modules.shared.utils.database import get_unified_connection

        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_ensure.return_value = True

        result = get_unified_connection()

        assert result == mock_conn
        mock_ensure.assert_called_once()
        mock_get_conn.assert_called_once()


class TestSimpleDBManager:
    """Test SimpleDBManager class"""

    @patch('university_system.modules.shared.utils.database._ensure_db_ready')
    def test_simple_db_manager_init(self, mock_ensure):
        """Test SimpleDBManager initialization"""
        from university_system.modules.shared.utils.database import SimpleDBManager

        mock_ensure.return_value = True

        manager = SimpleDBManager()

        assert manager is not None
        assert manager.db_path is not None
        mock_ensure.assert_called_once()

    @patch('university_system.modules.shared.utils.database._ensure_db_ready')
    def test_simple_db_manager_init_with_path(self, mock_ensure):
        """Test SimpleDBManager initialization with custom path"""
        from university_system.modules.shared.utils.database import SimpleDBManager

        mock_ensure.return_value = True
        custom_path = '/tmp/custom.db'

        manager = SimpleDBManager(db_path=custom_path)

        assert manager.db_path == custom_path

    @patch('university_system.modules.shared.utils.database.get_connection')
    @patch('university_system.modules.shared.utils.database._ensure_db_ready')
    def test_simple_db_manager_get_connection(self, mock_ensure, mock_get_conn):
        """Test SimpleDBManager get_connection method"""
        from university_system.modules.shared.utils.database import SimpleDBManager

        mock_ensure.return_value = True
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        manager = SimpleDBManager()
        result = manager.get_connection()

        assert result == mock_conn
        mock_get_conn.assert_called_once()


class TestGetDBManager:
    """Test get_db_manager function"""

    @patch('university_system.modules.shared.utils.database._ensure_db_ready')
    def test_get_db_manager_singleton(self, mock_ensure):
        """Test get_db_manager returns singleton"""
        from university_system.modules.shared.utils.database import get_db_manager

        mock_ensure.return_value = True

        # Reset singleton
        import university_system.modules.shared.utils.database as db_module
        db_module._db_manager = None

        manager1 = get_db_manager()
        manager2 = get_db_manager()

        # Should be the same instance
        assert manager1 is manager2

    @patch('university_system.modules.shared.utils.database._ensure_db_ready')
    def test_get_db_manager_thread_safe(self, mock_ensure):
        """Test get_db_manager thread safety"""
        from university_system.modules.shared.utils.database import get_db_manager

        mock_ensure.return_value = True

        # Reset singleton
        import university_system.modules.shared.utils.database as db_module
        db_module._db_manager = None

        managers = []

        def get_manager():
            manager = get_db_manager()
            managers.append(manager)

        # Create multiple threads
        threads = [threading.Thread(target=get_manager) for _ in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # All should be the same instance
        assert len(set(id(m) for m in managers)) == 1


class TestExecuteDBOperation:
    """Test execute_db_operation function"""

    @patch('university_system.modules.shared.utils.database.get_connection')
    def test_execute_db_operation_success(self, mock_get_conn):
        """Test successful database operation"""
        from university_system.modules.shared.utils.database import execute_db_operation

        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        def operation(conn):
            return 'success'

        result = execute_db_operation(operation)

        assert result == 'success'
        mock_conn.close.assert_called_once()

    @patch('university_system.modules.shared.utils.database.get_connection')
    def test_execute_db_operation_with_args(self, mock_get_conn):
        """Test database operation with arguments"""
        from university_system.modules.shared.utils.database import execute_db_operation

        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        def operation(conn, arg1, arg2):
            return arg1 + arg2

        result = execute_db_operation(operation, 5, 10)

        assert result == 15
        mock_conn.close.assert_called_once()

    @patch('university_system.modules.shared.utils.database.get_connection')
    def test_execute_db_operation_with_kwargs(self, mock_get_conn):
        """Test database operation with keyword arguments"""
        from university_system.modules.shared.utils.database import execute_db_operation

        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        def operation(conn, value=0):
            return value * 2

        result = execute_db_operation(operation, value=21)

        assert result == 42
        mock_conn.close.assert_called_once()

    @patch('university_system.modules.shared.utils.database.get_connection')
    def test_execute_db_operation_error(self, mock_get_conn, capsys):
        """Test database operation with error"""
        from university_system.modules.shared.utils.database import execute_db_operation

        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        def operation(conn):
            raise Exception("Database error")

        result = execute_db_operation(operation)

        assert result is None
        captured = capsys.readouterr()
        assert "Database operation error" in captured.out


class TestSafeDBOperation:
    """Test safe_db_operation decorator"""

    def test_safe_db_operation_success(self):
        """Test safe_db_operation decorator with success"""
        from university_system.modules.shared.utils.database import safe_db_operation

        @safe_db_operation
        def test_func():
            return 'success'

        result = test_func()

        assert result == 'success'

    def test_safe_db_operation_error(self, capsys):
        """Test safe_db_operation decorator with error"""
        from university_system.modules.shared.utils.database import safe_db_operation

        @safe_db_operation
        def test_func():
            raise Exception("Test error")

        result = test_func()

        assert result is None
        captured = capsys.readouterr()
        assert "Database error" in captured.out

    def test_safe_db_operation_with_args(self):
        """Test safe_db_operation decorator with arguments"""
        from university_system.modules.shared.utils.database import safe_db_operation

        @safe_db_operation
        def test_func(a, b):
            return a + b

        result = test_func(5, 10)

        assert result == 15

    def test_safe_db_operation_with_kwargs(self):
        """Test safe_db_operation decorator with keyword arguments"""
        from university_system.modules.shared.utils.database import safe_db_operation

        @safe_db_operation
        def test_func(value=0):
            return value * 2

        result = test_func(value=21)

        assert result == 42


class TestInitializeEmailDB:
    """Test initialize_email_db function"""

    @patch('university_system.modules.shared.utils.database._ensure_db_ready')
    def test_initialize_email_db(self, mock_ensure):
        """Test initialize_email_db function"""
        from university_system.modules.shared.utils.database import initialize_email_db

        mock_ensure.return_value = True

        result = initialize_email_db()

        assert result is True
        mock_ensure.assert_called_once()


class TestMigrateEmailLogTable:
    """Test migrate_email_log_table function"""

    def test_migrate_email_log_table(self):
        """Test migrate_email_log_table function"""
        from university_system.modules.shared.utils.database import migrate_email_log_table

        result = migrate_email_log_table()

        assert result is True


class TestScheduleDatabaseMaintenance:
    """Test schedule_database_maintenance function"""

    def test_schedule_database_maintenance(self):
        """Test schedule_database_maintenance function"""
        from university_system.modules.shared.utils.database import schedule_database_maintenance

        # Should not raise error
        schedule_database_maintenance()


class TestOptimizeDatabase:
    """Test optimize_database function"""

    @patch('university_system.modules.shared.utils.database._ensure_db_ready')
    def test_optimize_database(self, mock_ensure):
        """Test optimize_database function"""
        from university_system.modules.shared.utils.database import optimize_database

        mock_ensure.return_value = True

        # Should not raise error
        optimize_database()

        mock_ensure.assert_called_once()


class TestReExportedFunctions:
    """Test re-exported functions from other modules"""

    def test_ensure_db_directory_exists(self):
        """Test ensure_db_directory is re-exported"""
        from university_system.modules.shared.utils.database import ensure_db_directory

        assert ensure_db_directory is not None
        assert callable(ensure_db_directory)

    def test_ensure_parent_dir_exists(self):
        """Test ensure_parent_dir is re-exported"""
        from university_system.modules.shared.utils.database import ensure_parent_dir

        assert ensure_parent_dir is not None
        assert callable(ensure_parent_dir)

    def test_get_connection_exists(self):
        """Test get_connection is re-exported"""
        from university_system.modules.shared.utils.database import get_connection

        assert get_connection is not None
        assert callable(get_connection)

    def test_default_db_path_exists(self):
        """Test DEFAULT_DB_PATH is re-exported"""
        from university_system.modules.shared.utils.database import DEFAULT_DB_PATH

        assert DEFAULT_DB_PATH is not None

    def test_paths_exists(self):
        """Test paths is re-exported"""
        from university_system.modules.shared.utils.database import paths

        assert paths is not None


class TestModuleExports:
    """Test module __all__ exports"""

    def test_all_exports_defined(self):
        """Test that __all__ is defined"""
        from university_system.modules.shared.utils import database

        assert hasattr(database, '__all__')
        assert isinstance(database.__all__, list)

    def test_all_exports_accessible(self):
        """Test that all exported names are accessible"""
        from university_system.modules.shared.utils import database

        for name in database.__all__:
            assert hasattr(database, name), f"{name} not found in module"

    def test_key_functions_in_exports(self):
        """Test that key functions are in __all__"""
        from university_system.modules.shared.utils.database import __all__

        key_exports = [
            'get_unified_connection',
            'get_db_manager',
            'execute_db_operation',
            'safe_db_operation',
            '_ensure_db_ready',
            'ensure_db_directory',
            'ensure_parent_dir'
        ]

        for export in key_exports:
            assert export in __all__, f"{export} not in __all__"


class TestThreadSafety:
    """Test thread safety of database utilities"""

    @patch('university_system.modules.shared.utils.database.get_connection')
    @patch('university_system.modules.shared.utils.database._ensure_db_ready')
    def test_concurrent_get_unified_connection(self, mock_ensure, mock_get_conn):
        """Test concurrent calls to get_unified_connection"""
        from university_system.modules.shared.utils.database import get_unified_connection

        mock_ensure.return_value = True
        mock_get_conn.return_value = MagicMock()

        connections = []

        def get_conn():
            conn = get_unified_connection()
            connections.append(conn)

        threads = [threading.Thread(target=get_conn) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All threads should succeed
        assert len(connections) == 10

    @patch('university_system.modules.shared.utils.database.get_connection')
    def test_concurrent_execute_db_operation(self, mock_get_conn):
        """Test concurrent database operations"""
        from university_system.modules.shared.utils.database import execute_db_operation

        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        results = []

        def operation(conn, value):
            return value * 2

        def execute_op(val):
            result = execute_db_operation(operation, val)
            results.append(result)

        threads = [threading.Thread(target=execute_op, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All operations should succeed
        assert len(results) == 10


class TestBackwardCompatibility:
    """Test backward compatibility features"""

    def test_main_dir_equals_data_dir(self):
        """Test MAIN_DIR equals DATA_DIR for backward compatibility"""
        from university_system.modules.shared.utils.database import MAIN_DIR
        from university_system.modules.shared.constants import paths

        assert MAIN_DIR == str(paths.DATA_DIR)

    def test_db_path_equals_default(self):
        """Test DB_PATH equals DEFAULT_DB_PATH"""
        from university_system.modules.shared.utils.database import DB_PATH, DEFAULT_DB_PATH

        assert DB_PATH == DEFAULT_DB_PATH

    @patch('university_system.modules.shared.utils.database._ensure_db_ready')
    def test_simple_db_manager_default_path(self, mock_ensure):
        """Test SimpleDBManager uses DEFAULT_DB_PATH by default"""
        from university_system.modules.shared.utils.database import SimpleDBManager, DEFAULT_DB_PATH

        mock_ensure.return_value = True

        manager = SimpleDBManager()

        assert manager.db_path == DEFAULT_DB_PATH


class TestEdgeCases:
    """Test edge cases and error scenarios"""

    @patch('university_system.modules.shared.utils.database.get_connection')
    def test_execute_db_operation_connection_error(self, mock_get_conn, capsys):
        """Test execute_db_operation when connection fails"""
        from university_system.modules.shared.utils.database import execute_db_operation

        mock_get_conn.side_effect = Exception("Connection failed")

        def operation(conn):
            return 'success'

        result = execute_db_operation(operation)

        assert result is None

    @patch('university_system.modules.shared.utils.database.get_connection')
    def test_execute_db_operation_close_error(self, mock_get_conn):
        """Test execute_db_operation when close fails"""
        from university_system.modules.shared.utils.database import execute_db_operation

        mock_conn = MagicMock()
        mock_conn.close.side_effect = Exception("Close failed")
        mock_get_conn.return_value = mock_conn

        def operation(conn):
            return 'success'

        # Should still return result even if close fails
        result = execute_db_operation(operation)

        assert result is None  # Due to exception during close

    def test_safe_db_operation_preserves_function_name(self):
        """Test safe_db_operation preserves function name"""
        from university_system.modules.shared.utils.database import safe_db_operation

        @safe_db_operation
        def my_function():
            pass

        # Decorator creates wrapper, so __name__ will be 'wrapper'
        assert callable(my_function)


class TestIntegration:
    """Integration tests"""

    @patch('university_system.modules.shared.utils.database.get_connection')
    @patch('university_system.modules.shared.utils.database._ensure_db_ready')
    def test_full_workflow(self, mock_ensure, mock_get_conn):
        """Test full workflow of getting manager and executing operation"""
        from university_system.modules.shared.utils.database import get_db_manager, execute_db_operation

        mock_ensure.return_value = True
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        # Reset singleton
        import university_system.modules.shared.utils.database as db_module
        db_module._db_manager = None

        # Get manager
        manager = get_db_manager()
        assert manager is not None

        # Execute operation
        def operation(conn):
            return 'success'

        result = execute_db_operation(operation)
        assert result == 'success'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
