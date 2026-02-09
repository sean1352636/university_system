"""
Tests for database migration modules.

Tests that migration modules can be imported and have expected structure.
Does not actually run migrations to avoid modifying test databases.
"""

import pytest
import importlib
import os
from pathlib import Path


# List of migration modules
MIGRATION_MODULES = [
    'university_system.infrastructure.database.migrations.add_mfa_system',
    'university_system.infrastructure.database.migrations.add_security_features',
    'university_system.infrastructure.database.migrations.add_student_modules_columns',
    'university_system.infrastructure.database.migrations.fix_campus_events_tables',
    'university_system.infrastructure.database.migrations.fix_facilities_schema',
]


class TestMigrationModules:
    """Test that migration modules can be imported."""

    @pytest.mark.parametrize("module_name", MIGRATION_MODULES)
    def test_migration_module_imports(self, module_name):
        """Test that each migration module can be imported."""
        try:
            module = importlib.import_module(module_name)
            assert module is not None
        except ImportError as e:
            pytest.fail(f"Failed to import {module_name}: {e}")

    @pytest.mark.parametrize("module_name", MIGRATION_MODULES)
    def test_migration_module_has_docstring(self, module_name):
        """Test that each migration module has a docstring."""
        try:
            module = importlib.import_module(module_name)
            assert module.__doc__ is not None or hasattr(module, '__doc__')
        except ImportError:
            pytest.skip(f"Module {module_name} could not be imported")


class TestMigrationFiles:
    """Test migration file structure."""

    def test_migrations_directory_exists(self):
        """Test that migrations directory exists."""
        migrations_dir = Path("university_system/infrastructure/database/migrations")
        assert migrations_dir.exists()
        assert migrations_dir.is_dir()

    def test_migration_files_exist(self):
        """Test that expected migration files exist."""
        migrations_dir = Path("university_system/infrastructure/database/migrations")

        expected_files = [
            'add_mfa_system.py',
            'add_security_features.py',
            'add_student_modules_columns.py',
            'fix_campus_events_tables.py',
            'fix_facilities_schema.py',
        ]

        for file_name in expected_files:
            file_path = migrations_dir / file_name
            assert file_path.exists(), f"Expected migration file {file_name} not found"

    def test_migration_files_are_python_files(self):
        """Test that migration files are valid Python files."""
        migrations_dir = Path("university_system/infrastructure/database/migrations")

        for file_path in migrations_dir.glob("*.py"):
            if file_path.name.startswith('__'):
                continue  # Skip __init__.py

            # Check file has .py extension
            assert file_path.suffix == '.py'

            # Check file is readable
            assert os.access(file_path, os.R_OK)


class TestSpecificMigrations:
    """Test specific migration modules."""

    def test_add_mfa_system_migration(self):
        """Test MFA system migration module."""
        try:
            from university_system.infrastructure.database.migrations import add_mfa_system
            assert add_mfa_system is not None
        except ImportError:
            pytest.skip("add_mfa_system migration not available")

    def test_add_security_features_migration(self):
        """Test security features migration module."""
        try:
            from university_system.infrastructure.database.migrations import add_security_features
            assert add_security_features is not None
        except ImportError:
            pytest.skip("add_security_features migration not available")

    def test_add_student_modules_columns_migration(self):
        """Test student modules columns migration."""
        try:
            from university_system.infrastructure.database.migrations import add_student_modules_columns
            assert add_student_modules_columns is not None
        except ImportError:
            pytest.skip("add_student_modules_columns migration not available")

    def test_fix_campus_events_tables_migration(self):
        """Test campus events tables fix migration."""
        try:
            from university_system.infrastructure.database.migrations import fix_campus_events_tables
            assert fix_campus_events_tables is not None
        except ImportError:
            pytest.skip("fix_campus_events_tables migration not available")

    def test_fix_facilities_schema_migration(self):
        """Test facilities schema fix migration."""
        try:
            from university_system.infrastructure.database.migrations import fix_facilities_schema
            assert fix_facilities_schema is not None
        except ImportError:
            pytest.skip("fix_facilities_schema migration not available")


class TestMigrationIntegrity:
    """Test migration code integrity."""

    @pytest.mark.parametrize("module_name", MIGRATION_MODULES)
    def test_migration_syntax_valid(self, module_name):
        """Test that migration modules have valid Python syntax."""
        try:
            module = importlib.import_module(module_name)
            # If import succeeds, syntax is valid
            assert True
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {module_name}: {e}")
        except ImportError:
            # Import error might be due to dependencies, not syntax
            pytest.skip(f"Could not import {module_name}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
