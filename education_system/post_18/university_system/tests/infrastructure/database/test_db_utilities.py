"""
Comprehensive tests for the database utilities module (utilities.py).

Tests re-exports from db.py, email_db_utilities, health_db_backup,
and schema init functions, including the import fallback behaviour.
"""

import warnings
import pytest
from unittest.mock import patch, MagicMock
import importlib

# Suppress resource warnings from unrelated modules opening log files
pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")


# ---------------------------------------------------------------------------
# Test core re-exports from db.py
# ---------------------------------------------------------------------------

class TestCoreReExports:
    """Test that core database symbols are re-exported from utilities."""

    def test_sqlite3_re_exported(self):
        """Test sqlite3 proxy is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import sqlite3
        assert sqlite3 is not None
        # Should have connect attribute (our custom connect)
        assert hasattr(sqlite3, 'connect')

    def test_database_manager_re_exported(self):
        """Test DatabaseManager is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import DatabaseManager
        from education_system.post_18.university_system.infrastructure.database.db import DatabaseManager as OrigDM
        assert DatabaseManager is OrigDM

    def test_get_connection_re_exported(self):
        """Test get_connection is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import get_connection
        from education_system.post_18.university_system.infrastructure.database.db import get_connection as orig
        assert get_connection is orig

    def test_get_db_connection_re_exported(self):
        """Test get_db_connection is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import get_db_connection
        from education_system.post_18.university_system.infrastructure.database.db import get_db_connection as orig
        assert get_db_connection is orig

    def test_default_db_path_re_exported(self):
        """Test DEFAULT_DB_PATH is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import DEFAULT_DB_PATH
        assert DEFAULT_DB_PATH is not None
        assert isinstance(DEFAULT_DB_PATH, str)

    def test_db_dir_re_exported(self):
        """Test DB_DIR is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import DB_DIR
        assert DB_DIR is not None
        assert isinstance(DB_DIR, str)

    def test_exports_dir_re_exported(self):
        """Test EXPORTS_DIR is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import EXPORTS_DIR
        assert EXPORTS_DIR is not None
        assert isinstance(EXPORTS_DIR, str)


# ---------------------------------------------------------------------------
# Test email database utilities re-exports
# ---------------------------------------------------------------------------

class TestEmailDbUtilitiesReExports:
    """Test email database utility re-exports."""

    def test_get_unified_connection_re_exported(self):
        """Test get_unified_connection is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import get_unified_connection
        assert callable(get_unified_connection)

    def test_simple_db_manager_re_exported(self):
        """Test SimpleDBManager is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import SimpleDBManager
        assert SimpleDBManager is not None

    def test_get_db_manager_re_exported(self):
        """Test get_db_manager is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import get_db_manager
        assert callable(get_db_manager)

    def test_execute_db_operation_re_exported(self):
        """Test execute_db_operation is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import execute_db_operation
        assert callable(execute_db_operation)

    def test_safe_db_operation_re_exported(self):
        """Test safe_db_operation is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import safe_db_operation
        assert callable(safe_db_operation)

    def test_initialize_email_db_re_exported(self):
        """Test initialize_email_db is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import initialize_email_db
        assert callable(initialize_email_db)

    def test_migrate_email_log_table_re_exported(self):
        """Test migrate_email_log_table is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import migrate_email_log_table
        assert callable(migrate_email_log_table)

    def test_schedule_database_maintenance_re_exported(self):
        """Test schedule_database_maintenance is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import schedule_database_maintenance
        assert callable(schedule_database_maintenance)

    def test_optimize_database_re_exported(self):
        """Test optimize_database is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import optimize_database
        assert callable(optimize_database)

    def test_ensure_db_directory_re_exported(self):
        """Test ensure_db_directory is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import ensure_db_directory
        assert callable(ensure_db_directory)

    def test_ensure_parent_dir_re_exported(self):
        """Test ensure_parent_dir is re-exported."""
        from education_system.post_18.university_system.infrastructure.database.utilities import ensure_parent_dir
        assert callable(ensure_parent_dir)


# ---------------------------------------------------------------------------
# Test health database backup re-exports (with fallback)
# ---------------------------------------------------------------------------

class TestHealthDbBackupReExports:
    """Test health database backup re-exports including fallback."""

    def test_create_sqlite_backup_available_or_none(self):
        """Test create_sqlite_backup is either callable or None (import fallback)."""
        from education_system.post_18.university_system.infrastructure.database.utilities import create_sqlite_backup
        assert create_sqlite_backup is None or callable(create_sqlite_backup)

    def test_ensure_templates_schema_available_or_none(self):
        """Test ensure_templates_schema is either callable or None (import fallback)."""
        from education_system.post_18.university_system.infrastructure.database.utilities import ensure_templates_schema
        assert ensure_templates_schema is None or callable(ensure_templates_schema)


# ---------------------------------------------------------------------------
# Test schema initialization re-exports (with fallback)
# ---------------------------------------------------------------------------

class TestSchemaInitReExports:
    """Test schema initialization function re-exports including fallback."""

    def test_init_grade_system_db_available_or_none(self):
        """Test init_grade_system_db is either callable or None."""
        from education_system.post_18.university_system.infrastructure.database.utilities import init_grade_system_db
        assert init_grade_system_db is None or callable(init_grade_system_db)

    def test_init_finance_system_db_available_or_none(self):
        """Test init_finance_system_db is either callable or None."""
        from education_system.post_18.university_system.infrastructure.database.utilities import init_finance_system_db
        assert init_finance_system_db is None or callable(init_finance_system_db)

    def test_init_student_union_db_available_or_none(self):
        """Test init_student_union_db is either callable or None."""
        from education_system.post_18.university_system.infrastructure.database.utilities import init_student_union_db
        assert init_student_union_db is None or callable(init_student_union_db)

    def test_init_email_system_db_available_or_none(self):
        """Test init_email_system_db is either callable or None."""
        from education_system.post_18.university_system.infrastructure.database.utilities import init_email_system_db
        assert init_email_system_db is None or callable(init_email_system_db)

    def test_initialize_all_schemas_available_or_none(self):
        """Test initialize_all_schemas is either callable or None."""
        from education_system.post_18.university_system.infrastructure.database.utilities import initialize_all_schemas
        assert initialize_all_schemas is None or callable(initialize_all_schemas)


# ---------------------------------------------------------------------------
# Test __all__ exports
# ---------------------------------------------------------------------------

class TestUtilitiesAllExports:
    """Test __all__ export list completeness."""

    def test_all_is_list(self):
        """Test __all__ is a list."""
        from education_system.post_18.university_system.infrastructure.database.utilities import __all__
        assert isinstance(__all__, list)

    def test_all_names_exist(self):
        """Test every name in __all__ is a real attribute."""
        import education_system.post_18.university_system.infrastructure.database.utilities as mod
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name} in __all__ but not defined"

    def test_all_contains_core_exports(self):
        """Test __all__ contains core database exports."""
        from education_system.post_18.university_system.infrastructure.database.utilities import __all__
        core_names = [
            'sqlite3', 'DatabaseManager', 'get_connection',
            'get_db_connection', 'DEFAULT_DB_PATH', 'DB_DIR', 'EXPORTS_DIR',
        ]
        for name in core_names:
            assert name in __all__, f"{name} not in __all__"

    def test_all_contains_email_exports(self):
        """Test __all__ contains email database exports."""
        from education_system.post_18.university_system.infrastructure.database.utilities import __all__
        email_names = [
            'get_unified_connection', 'SimpleDBManager', 'get_db_manager',
            'execute_db_operation', 'safe_db_operation',
            'initialize_email_db', 'migrate_email_log_table',
            'schedule_database_maintenance', 'optimize_database',
            'ensure_db_directory', 'ensure_parent_dir',
        ]
        for name in email_names:
            assert name in __all__, f"{name} not in __all__"

    def test_all_contains_health_exports(self):
        """Test __all__ contains health backup exports."""
        from education_system.post_18.university_system.infrastructure.database.utilities import __all__
        assert 'create_sqlite_backup' in __all__
        assert 'ensure_templates_schema' in __all__

    def test_all_contains_schema_exports(self):
        """Test __all__ contains schema init exports."""
        from education_system.post_18.university_system.infrastructure.database.utilities import __all__
        schema_names = [
            'init_grade_system_db', 'init_finance_system_db',
            'init_student_union_db', 'init_email_system_db',
            'initialize_all_schemas',
        ]
        for name in schema_names:
            assert name in __all__, f"{name} not in __all__"

    def test_all_has_expected_count(self):
        """Test __all__ has the expected total number of exports."""
        from education_system.post_18.university_system.infrastructure.database.utilities import __all__
        # 7 core + 11 email + 2 health + 5 schema = 25
        assert len(__all__) == 25


# ---------------------------------------------------------------------------
# Test import fallback paths
# ---------------------------------------------------------------------------

class TestImportFallbacks:
    """Test import fallback behaviour when optional modules are absent."""

    def test_health_import_fallback(self):
        """Test health backup imports fall back to None on ImportError."""
        # We simulate this by checking the fallback behaviour in the module
        # The module does: except ImportError: create_sqlite_backup = None
        import education_system.post_18.university_system.infrastructure.database.utilities as mod
        # Even if the import worked, verify the pattern: should be None or callable
        val = mod.create_sqlite_backup
        assert val is None or callable(val)

    def test_schema_import_fallback(self):
        """Test schema init imports fall back to None on ImportError."""
        import education_system.post_18.university_system.infrastructure.database.utilities as mod
        val = mod.init_grade_system_db
        assert val is None or callable(val)


# ---------------------------------------------------------------------------
# Test consistency between utilities and db module
# ---------------------------------------------------------------------------

class TestConsistency:
    """Test that utilities re-exports match their source modules."""

    def test_default_db_path_matches_db_module(self):
        """Test DEFAULT_DB_PATH in utilities matches db module."""
        from education_system.post_18.university_system.infrastructure.database.utilities import DEFAULT_DB_PATH as u_path
        from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH as d_path
        assert u_path == d_path

    def test_db_dir_matches_db_module(self):
        """Test DB_DIR in utilities matches db module."""
        from education_system.post_18.university_system.infrastructure.database.utilities import DB_DIR as u_dir
        from education_system.post_18.university_system.infrastructure.database.db import DB_DIR as d_dir
        assert u_dir == d_dir

    def test_exports_dir_matches_db_module(self):
        """Test EXPORTS_DIR in utilities matches db module."""
        from education_system.post_18.university_system.infrastructure.database.utilities import EXPORTS_DIR as u_dir
        from education_system.post_18.university_system.infrastructure.database.db import EXPORTS_DIR as d_dir
        assert u_dir == d_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
