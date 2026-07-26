"""
Tests for centralized database utilities module (utilities.py).

Tests the module that aggregates functionality from various database modules.
"""

import pytest
from unittest.mock import patch, MagicMock

from education_system.systems.university.infrastructure.database import utilities


class TestCoreDatabase:
    """Test core database exports."""

    def test_sqlite3_exported(self):
        """Test that sqlite3 is exported."""
        assert hasattr(utilities, 'sqlite3')

    def test_database_manager_exported(self):
        """Test that DatabaseManager is exported."""
        assert hasattr(utilities, 'DatabaseManager')

    def test_get_connection_exported(self):
        """Test that get_connection is exported."""
        assert hasattr(utilities, 'get_connection')

    def test_get_db_connection_exported(self):
        """Test that get_db_connection is exported."""
        assert hasattr(utilities, 'get_db_connection')

    def test_default_db_path_exported(self):
        """Test that DEFAULT_DB_PATH is exported."""
        assert hasattr(utilities, 'DEFAULT_DB_PATH')

    def test_db_dir_exported(self):
        """Test that DB_DIR is exported."""
        assert hasattr(utilities, 'DB_DIR')

    def test_exports_dir_exported(self):
        """Test that EXPORTS_DIR is exported."""
        assert hasattr(utilities, 'EXPORTS_DIR')


class TestEmailDatabaseUtilities:
    """Test email database utilities exports."""

    def test_get_unified_connection_exported(self):
        """Test get_unified_connection is exported."""
        assert hasattr(utilities, 'get_unified_connection')

    def test_simple_db_manager_exported(self):
        """Test SimpleDBManager is exported."""
        assert hasattr(utilities, 'SimpleDBManager')

    def test_execute_db_operation_exported(self):
        """Test execute_db_operation is exported."""
        assert hasattr(utilities, 'execute_db_operation')

    def test_initialize_email_db_exported(self):
        """Test initialize_email_db is exported."""
        assert hasattr(utilities, 'initialize_email_db')


class TestHealthDatabaseUtilities:
    """Test health database utilities exports."""

    def test_create_sqlite_backup_exported(self):
        """Test create_sqlite_backup is exported."""
        assert hasattr(utilities, 'create_sqlite_backup')

    def test_ensure_templates_schema_exported(self):
        """Test ensure_templates_schema is exported."""
        assert hasattr(utilities, 'ensure_templates_schema')


class TestSchemaInitialization:
    """Test schema initialization exports."""

    def test_schema_functions_availability(self):
        """Test that schema initialization functions are available (or None)."""
        # These may be None if schemas module doesn't exist
        init_funcs = [
            'init_grade_system_db',
            'init_finance_system_db',
            'init_student_union_db',
            'init_email_system_db',
            'initialize_all_schemas',
        ]

        for func_name in init_funcs:
            assert hasattr(utilities, func_name)
            func = getattr(utilities, func_name)
            assert func is None or callable(func)


class TestModuleExports:
    """Test module __all__ exports."""

    def test_all_exports_defined(self):
        """Test that all items in __all__ are defined."""
        for name in utilities.__all__:
            assert hasattr(utilities, name), f"{name} in __all__ but not defined"

    def test_essential_exports_in_all(self):
        """Test that essential exports are in __all__."""
        essential = [
            'sqlite3',
            'DatabaseManager',
            'get_connection',
            'DEFAULT_DB_PATH',
        ]

        for name in essential:
            assert name in utilities.__all__, f"Essential export {name} not in __all__"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
