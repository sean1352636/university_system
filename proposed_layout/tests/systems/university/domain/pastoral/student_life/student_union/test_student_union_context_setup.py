"""
Tests for student union context setup module.
Tests authentication instance setup functionality.
"""

import pytest
from unittest.mock import Mock, patch

from education_system.systems.university.domain.pastoral.student_life.student_union.services import context_setup
from education_system.systems.university.infrastructure.auth import UserAuth


class TestSetAuth:
    """Tests for set_auth function."""

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context')
    def test_set_auth_basic(self, mock_union_context):
        """Test setting auth instance."""
        # Create mock auth object
        mock_auth = Mock(spec=UserAuth)

        # Call function
        context_setup.set_auth(mock_auth)

        # Verify auth was set in union_context
        assert mock_union_context.auth == mock_auth

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.context_setup.HAS_AUTH', True)
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.context_setup.set_auth_instance')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context')
    def test_set_auth_with_global_instance(self, mock_union_context, mock_set_auth_instance):
        """Test setting auth when global auth instance is available."""
        # Create mock auth object
        mock_auth = Mock(spec=UserAuth)

        # Call function
        context_setup.set_auth(mock_auth)

        # Verify auth was set in both places
        assert mock_union_context.auth == mock_auth
        mock_set_auth_instance.assert_called_once_with(mock_auth)

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.context_setup.HAS_AUTH', False)
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context')
    def test_set_auth_without_global_instance(self, mock_union_context):
        """Test setting auth when global auth instance is not available."""
        # Create mock auth object
        mock_auth = Mock(spec=UserAuth)

        # Call function
        context_setup.set_auth(mock_auth)

        # Verify auth was set in union_context
        assert mock_union_context.auth == mock_auth

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context')
    def test_set_auth_with_none(self, mock_union_context):
        """Test setting auth to None."""
        # Call function with None
        context_setup.set_auth(None)

        # Verify auth was set to None
        assert mock_union_context.auth is None

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context')
    def test_set_auth_multiple_times(self, mock_union_context):
        """Test setting auth multiple times."""
        # Create multiple mock auth objects
        mock_auth1 = Mock(spec=UserAuth)
        mock_auth2 = Mock(spec=UserAuth)
        mock_auth3 = Mock(spec=UserAuth)

        # Call function multiple times
        context_setup.set_auth(mock_auth1)
        assert mock_union_context.auth == mock_auth1

        context_setup.set_auth(mock_auth2)
        assert mock_union_context.auth == mock_auth2

        context_setup.set_auth(mock_auth3)
        assert mock_union_context.auth == mock_auth3

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.context_setup.HAS_AUTH', True)
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.context_setup.set_auth_instance')
    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context')
    def test_set_auth_with_configured_user(self, mock_union_context, mock_set_auth_instance):
        """Test setting auth with a configured UserAuth object."""
        # Create mock auth with some attributes
        mock_auth = Mock(spec=UserAuth)
        mock_auth.current_user = {'id': 1, 'username': 'testuser'}
        mock_auth.check_permission = Mock(return_value=True)

        # Call function
        context_setup.set_auth(mock_auth)

        # Verify auth was set correctly
        assert mock_union_context.auth == mock_auth
        assert mock_union_context.auth.current_user == {'id': 1, 'username': 'testuser'}
        mock_set_auth_instance.assert_called_once_with(mock_auth)


class TestModuleConstants:
    """Tests for module constants and configuration."""

    def test_has_auth_constant_exists(self):
        """Test that HAS_AUTH constant exists."""
        assert hasattr(context_setup, 'HAS_AUTH')
        assert isinstance(context_setup.HAS_AUTH, bool)

    def test_fallback_functions_exist(self):
        """Test that fallback functions exist when imports fail."""
        # When HAS_AUTH is False, fallback functions should be defined
        assert hasattr(context_setup, 'get_current_user')
        assert hasattr(context_setup, 'set_auth_instance')
        assert callable(context_setup.get_current_user)
        assert callable(context_setup.set_auth_instance)

    def test_fallback_get_current_user(self):
        """Test fallback get_current_user returns None."""
        # When ImportError occurs, get_current_user should return None
        if not context_setup.HAS_AUTH:
            result = context_setup.get_current_user()
            assert result is None

    def test_fallback_set_auth_instance(self):
        """Test fallback set_auth_instance does nothing."""
        # When ImportError occurs, set_auth_instance should do nothing
        if not context_setup.HAS_AUTH:
            try:
                context_setup.set_auth_instance(Mock())
                # Should not raise any exception
            except Exception as e:
                pytest.fail(f"Fallback set_auth_instance raised exception: {e}")


class TestIntegrationContextSetup:
    """Integration tests for context setup."""

    @patch('education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context')
    def test_set_auth_integration_workflow(self, mock_union_context):
        """Test complete workflow of setting and using auth."""
        # Create realistic auth mock
        mock_auth = Mock(spec=UserAuth)
        mock_auth.current_user = {'id': 1, 'username': 'admin', 'role': 'admin'}
        mock_auth.is_logged_in = Mock(return_value=True)
        mock_auth.check_permission = Mock(return_value=True)

        # Set auth
        context_setup.set_auth(mock_auth)

        # Verify auth is accessible
        assert mock_union_context.auth.is_logged_in()
        assert mock_union_context.auth.check_permission('manage_all_clubs')
        assert mock_union_context.auth.current_user['username'] == 'admin'


class TestDocumentation:
    """Tests for module documentation."""

    def test_set_auth_has_docstring(self):
        """Test that set_auth function has documentation."""
        assert context_setup.set_auth.__doc__ is not None
        assert len(context_setup.set_auth.__doc__.strip()) > 0

    def test_set_auth_docstring_content(self):
        """Test that set_auth docstring describes the function."""
        docstring = context_setup.set_auth.__doc__.lower()
        assert 'auth' in docstring or 'authentication' in docstring

    def test_module_has_future_annotations(self):
        """Test that module uses future annotations."""
        # Check module annotations
        import sys
        import importlib

        if 'university_system.modules.domain.student_affairs.student_union.services.context_setup' in sys.modules:
            module = sys.modules['university_system.modules.domain.student_affairs.student_union.services.context_setup']
            # Should have __annotations__ or be using from __future__ import annotations
            assert hasattr(module, '__annotations__') or 'annotations' in str(module.__doc__ or '')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
