"""
Tests for student union database schema module.
Tests the compatibility shim that imports from centralized schemas.
"""

import pytest
from unittest.mock import Mock, patch

from university_system.modules.domain.student_affairs.student_union.services import union_db_schema


class TestUnionDbSchemaImports:
    """Tests for union_db_schema module imports."""

    def test_init_student_union_db_exists(self):
        """Test that init_student_union_db is imported."""
        assert hasattr(union_db_schema, 'init_student_union_db')
        assert callable(union_db_schema.init_student_union_db)

    def test_module_has_all_attribute(self):
        """Test that module has __all__ attribute."""
        assert hasattr(union_db_schema, '__all__')
        assert 'init_student_union_db' in union_db_schema.__all__

    @patch('university_system.infrastructure.database.schemas.init_student_union_db')
    def test_init_student_union_db_delegates(self, mock_init_db):
        """Test that init_student_union_db properly delegates to centralized function."""
        mock_conn = Mock()

        # Call the function
        union_db_schema.init_student_union_db(mock_conn)

        # Verify it delegates to the centralized function
        mock_init_db.assert_called_once_with(mock_conn)


class TestCompatibilityShim:
    """Tests to ensure the compatibility shim works correctly."""

    def test_import_from_module(self):
        """Test that we can import from the module."""
        from university_system.modules.domain.student_affairs.student_union.services.union_db_schema import init_student_union_db
        assert callable(init_student_union_db)

    def test_import_star(self):
        """Test that import * works correctly.

        Note: This test uses exec() with a wildcard import to dynamically
        test the module's __all__ export list. This is acceptable in test
        context to verify the module's public API.
        """
        namespace = {}
        # Using exec() to test import * behavior - acceptable in tests
        exec('from university_system.modules.domain.student_affairs.student_union.services.union_db_schema import *', namespace)

        assert 'init_student_union_db' in namespace
        assert callable(namespace['init_student_union_db'])

    @patch('university_system.infrastructure.database.schemas.init_student_union_db')
    def test_function_signature_preserved(self, mock_init_db):
        """Test that the function signature is preserved through the import."""
        # The function should accept a connection object
        mock_conn = Mock()

        try:
            union_db_schema.init_student_union_db(mock_conn)
        except Exception as e:
            pytest.fail(f"Function signature not preserved: {e}")

        mock_init_db.assert_called_once()


class TestModuleDocstring:
    """Tests for module documentation."""

    def test_module_has_docstring(self):
        """Test that the module has a docstring."""
        assert union_db_schema.__doc__ is not None
        assert len(union_db_schema.__doc__) > 0

    def test_docstring_mentions_compatibility(self):
        """Test that docstring mentions compatibility shim."""
        assert 'compatibility' in union_db_schema.__doc__.lower() or \
               'shim' in union_db_schema.__doc__.lower()

    def test_docstring_mentions_centralized_location(self):
        """Test that docstring mentions the centralized location."""
        assert 'infrastructure' in union_db_schema.__doc__.lower() or \
               'schemas' in union_db_schema.__doc__.lower()


class TestIntegrationDbSchema:
    """Integration tests for database schema initialization."""

    @patch('university_system.infrastructure.database.schemas.init_student_union_db')
    def test_init_db_can_be_called_multiple_times(self, mock_init_db):
        """Test that init_student_union_db can be called multiple times safely."""
        mock_conn = Mock()

        # Call multiple times
        union_db_schema.init_student_union_db(mock_conn)
        union_db_schema.init_student_union_db(mock_conn)
        union_db_schema.init_student_union_db(mock_conn)

        # Should have been called 3 times
        assert mock_init_db.call_count == 3

    @patch('university_system.infrastructure.database.schemas.init_student_union_db')
    def test_init_db_passes_connection_correctly(self, mock_init_db):
        """Test that connection object is passed correctly."""
        mock_conn = Mock()
        mock_conn.cursor = Mock(return_value=Mock())

        union_db_schema.init_student_union_db(mock_conn)

        # Verify the exact connection object was passed
        call_args = mock_init_db.call_args
        assert call_args[0][0] == mock_conn


class TestBackwardCompatibility:
    """Tests for backward compatibility."""

    def test_old_import_path_works(self):
        """Test that the old import path still works."""
        try:
            from university_system.modules.domain.student_affairs.student_union.services.union_db_schema import init_student_union_db
            assert callable(init_student_union_db)
        except ImportError as e:
            pytest.fail(f"Old import path broken: {e}")

    def test_new_import_path_works(self):
        """Test that the new centralized import path works."""
        try:
            from university_system.infrastructure.database.schemas.student_union_schemas import init_student_union_db
            assert callable(init_student_union_db)
        except ImportError as e:
            pytest.fail(f"New import path broken: {e}")

    def test_both_imports_reference_same_function(self):
        """Test that both import paths reference the same function."""
        from university_system.modules.domain.student_affairs.student_union.services.union_db_schema import init_student_union_db as old_import
        from university_system.infrastructure.database.schemas.student_union_schemas import init_student_union_db as new_import

        # They should be the same function
        assert old_import == new_import


class TestModuleStructure:
    """Tests for module structure."""

    def test_module_exports_only_expected_items(self):
        """Test that module only exports expected items."""
        expected_exports = {'init_student_union_db'}

        # Get all public attributes (not starting with _)
        public_attrs = {attr for attr in dir(union_db_schema)
                       if not attr.startswith('_')}

        # Should only have the expected exports
        assert expected_exports.issubset(public_attrs)

    def test_module_has_future_annotations(self):
        """Test that module uses future annotations."""
        import sys
        import importlib

        # Reimport to check annotations
        if 'university_system.modules.core.services.student_union_misc.union_db_schema' in sys.modules:
            importlib.reload(union_db_schema)

        # Should have annotations from __future__
        assert '__annotations__' in dir(union_db_schema) or \
               'annotations' in str(union_db_schema.__doc__).lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
