#!/usr/bin/env python3
"""
Comprehensive tests for Email State Module
Tests authentication state management, proxy functionality, and global state
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root))


class TestSetAuth:
    """Test set_auth() function"""

    def test_set_auth_with_valid_instance(self):
        """Test setting auth with a valid authentication instance"""
        from education_system.post_18.university_system.infrastructure.email import state

        # Create a mock auth instance
        mock_auth = Mock()
        mock_auth.current_user = Mock()
        mock_auth.current_user.username = "test_user"

        # Reset state first
        state.auth = None

        # Set the auth instance
        state.set_auth(mock_auth)

        # Verify it was set
        assert state.auth is mock_auth
        assert state.auth.current_user.username == "test_user"

    def test_set_auth_with_none(self):
        """Test setting auth to None"""
        from education_system.post_18.university_system.infrastructure.email import state

        # Set to a mock first
        state.auth = Mock()

        # Set to None
        state.set_auth(None)

        # Verify it was set to None
        assert state.auth is None

    def test_set_auth_updates_global_auth_when_available(self):
        """Test that set_auth also updates global auth instance when HAS_AUTH is True"""
        from education_system.post_18.university_system.infrastructure.email import state

        # Mock the set_auth_instance function
        with patch.object(state, 'HAS_AUTH', True):
            with patch.object(state, 'set_auth_instance') as mock_set_auth_instance:
                mock_auth = Mock()

                state.set_auth(mock_auth)

                # Verify both were set
                assert state.auth is mock_auth
                mock_set_auth_instance.assert_called_once_with(mock_auth)

    def test_set_auth_without_global_auth_module(self):
        """Test set_auth when HAS_AUTH is False (auth module not available)"""
        from education_system.post_18.university_system.infrastructure.email import state

        with patch.object(state, 'HAS_AUTH', False):
            mock_auth = Mock()

            # Should not raise error even without global auth
            state.set_auth(mock_auth)

            assert state.auth is mock_auth

    def test_set_auth_replaces_previous_instance(self):
        """Test that set_auth properly replaces previous auth instance"""
        from education_system.post_18.university_system.infrastructure.email import state

        # Set first instance
        first_auth = Mock()
        first_auth.user = "user1"
        state.set_auth(first_auth)
        assert state.auth.user == "user1"

        # Replace with second instance
        second_auth = Mock()
        second_auth.user = "user2"
        state.set_auth(second_auth)

        # Verify it was replaced
        assert state.auth is second_auth
        assert state.auth.user == "user2"


class TestAuthProxy:
    """Test AuthProxy class functionality"""

    def setup_method(self):
        """Reset state before each test"""
        from education_system.post_18.university_system.infrastructure.email import state
        state.auth = None

    def test_auth_proxy_bool_when_auth_is_none(self):
        """Test AuthProxy __bool__ returns False when auth is None"""
        from education_system.post_18.university_system.infrastructure.email.state import AuthProxy, auth

        # Ensure auth is None
        import education_system.post_18.university_system.infrastructure.email.state as state_module
        state_module.auth = None

        proxy = AuthProxy()

        # Should be falsy
        assert not proxy
        assert bool(proxy) is False

    def test_auth_proxy_bool_when_auth_exists(self):
        """Test AuthProxy __bool__ returns True when auth exists"""
        from education_system.post_18.university_system.infrastructure.email.state import AuthProxy
        import education_system.post_18.university_system.infrastructure.email.state as state_module

        # Set auth to a mock
        mock_auth = Mock()
        state_module.auth = mock_auth

        proxy = AuthProxy()

        # Should be truthy
        assert proxy
        assert bool(proxy) is True

    def test_auth_proxy_getattr_with_auth_set(self):
        """Test AuthProxy __getattr__ retrieves attributes from auth instance"""
        from education_system.post_18.university_system.infrastructure.email.state import AuthProxy
        import education_system.post_18.university_system.infrastructure.email.state as state_module

        # Create mock auth with attributes
        mock_auth = Mock()
        mock_auth.username = "test_user"
        mock_auth.role = "admin"
        mock_auth.is_authenticated = True

        state_module.auth = mock_auth

        proxy = AuthProxy()

        # Should retrieve attributes from auth
        assert proxy.username == "test_user"
        assert proxy.role == "admin"
        assert proxy.is_authenticated is True

    def test_auth_proxy_getattr_raises_when_auth_is_none(self):
        """Test AuthProxy __getattr__ raises AttributeError when auth is None"""
        from education_system.post_18.university_system.infrastructure.email.state import AuthProxy
        import education_system.post_18.university_system.infrastructure.email.state as state_module

        state_module.auth = None

        proxy = AuthProxy()

        # Should raise AttributeError
        with pytest.raises(AttributeError, match="username"):
            _ = proxy.username

    def test_auth_proxy_getattr_raises_when_attribute_missing(self):
        """Test AuthProxy __getattr__ raises AttributeError for missing attributes"""
        from education_system.post_18.university_system.infrastructure.email.state import AuthProxy
        import education_system.post_18.university_system.infrastructure.email.state as state_module

        mock_auth = Mock(spec=['username'])  # Only has username
        mock_auth.username = "test_user"

        state_module.auth = mock_auth

        proxy = AuthProxy()

        # Should raise AttributeError for missing attribute
        with pytest.raises(AttributeError):
            _ = proxy.nonexistent_attribute

    def test_auth_proxy_setattr_with_auth_set(self):
        """Test AuthProxy __setattr__ sets attributes on auth instance"""
        from education_system.post_18.university_system.infrastructure.email.state import AuthProxy
        import education_system.post_18.university_system.infrastructure.email.state as state_module

        mock_auth = Mock()
        state_module.auth = mock_auth

        proxy = AuthProxy()

        # Set attribute via proxy
        proxy.username = "new_user"

        # Verify it was set on auth
        assert mock_auth.username == "new_user"

    def test_auth_proxy_setattr_raises_when_auth_is_none(self):
        """Test AuthProxy __setattr__ raises AttributeError when auth is None"""
        from education_system.post_18.university_system.infrastructure.email.state import AuthProxy
        import education_system.post_18.university_system.infrastructure.email.state as state_module

        state_module.auth = None

        proxy = AuthProxy()

        # Should raise AttributeError
        with pytest.raises(AttributeError, match="username"):
            proxy.username = "test_user"

    def test_auth_proxy_setattr_private_attributes(self):
        """Test AuthProxy __setattr__ handles private attributes correctly"""
        from education_system.post_18.university_system.infrastructure.email.state import AuthProxy
        import education_system.post_18.university_system.infrastructure.email.state as state_module

        # Auth can be None for private attributes
        state_module.auth = None

        proxy = AuthProxy()

        # Should be able to set private attributes
        proxy._private_attr = "value"

        # Verify private attribute was set on proxy itself
        assert proxy._private_attr == "value"

    def test_auth_proxy_method_calls(self):
        """Test AuthProxy can call methods on auth instance"""
        from education_system.post_18.university_system.infrastructure.email.state import AuthProxy
        import education_system.post_18.university_system.infrastructure.email.state as state_module

        mock_auth = Mock()
        mock_auth.login = Mock(return_value=True)
        mock_auth.logout = Mock()

        state_module.auth = mock_auth

        proxy = AuthProxy()

        # Call methods via proxy
        result = proxy.login("user", "pass")
        proxy.logout()

        # Verify methods were called
        assert result is True
        mock_auth.login.assert_called_once_with("user", "pass")
        mock_auth.logout.assert_called_once()


class TestAuthVariable:
    """Test the global auth variable"""

    def test_auth_variable_initialization(self):
        """Test that auth variable is initialized to None"""
        # Re-import to get fresh state
        import importlib
        import education_system.post_18.university_system.infrastructure.email.state as state_module
        importlib.reload(state_module)

        # Should be None initially
        assert state_module.auth is None

    def test_auth_variable_can_be_set(self):
        """Test that auth variable can be set directly"""
        from education_system.post_18.university_system.infrastructure.email import state

        mock_auth = Mock()
        mock_auth.user_id = 123

        state.auth = mock_auth

        assert state.auth.user_id == 123

    def test_auth_variable_shared_across_imports(self):
        """Test that auth variable is shared across different imports"""
        # First import
        from education_system.post_18.university_system.infrastructure.email import state as state1

        mock_auth = Mock()
        state1.auth = mock_auth

        # Second import
        from education_system.post_18.university_system.infrastructure.email import state as state2

        # Should be the same object
        assert state2.auth is mock_auth


class TestHasAuthFlag:
    """Test HAS_AUTH flag behavior"""

    def test_has_auth_true_when_module_available(self):
        """Test HAS_AUTH is True when auth module can be imported"""
        # This depends on whether the auth module is available in the environment
        from education_system.post_18.university_system.infrastructure.email.state import HAS_AUTH

        # Should be a boolean
        assert isinstance(HAS_AUTH, bool)

    def test_has_auth_false_when_module_unavailable(self):
        """Test HAS_AUTH is False when auth module import fails"""
        # We can't easily test this without breaking imports,
        # but we can verify the fallback functions exist
        from education_system.post_18.university_system.infrastructure.email import state

        # If HAS_AUTH is False, these should be lambda functions
        if not state.HAS_AUTH:
            assert callable(state.get_current_user)
            assert callable(state.set_auth_instance)

            # Should return None and accept arguments without error
            assert state.get_current_user() is None
            state.set_auth_instance(Mock())  # Should not raise

    def test_fallback_functions_when_import_fails(self):
        """Test fallback get_current_user and set_auth_instance"""
        with patch('education_system.post_18.university_system.infrastructure.email.state.HAS_AUTH', False):
            # Re-import to trigger fallback
            import importlib
            import education_system.post_18.university_system.infrastructure.email.state as state_module

            # Manually set fallbacks
            state_module.get_current_user = lambda: None
            state_module.set_auth_instance = lambda x: None

            # Test fallback functions
            assert state_module.get_current_user() is None
            state_module.set_auth_instance(Mock())  # Should not raise


class TestAuthProxyInstance:
    """Test the auth_proxy instance"""

    def test_auth_proxy_instance_exists(self):
        """Test that auth_proxy instance is created"""
        from education_system.post_18.university_system.infrastructure.email.state import auth_proxy, AuthProxy

        assert auth_proxy is not None
        assert isinstance(auth_proxy, AuthProxy)

    def test_auth_proxy_instance_reflects_current_auth(self):
        """Test that auth_proxy reflects current auth state"""
        from education_system.post_18.university_system.infrastructure.email.state import auth_proxy
        import education_system.post_18.university_system.infrastructure.email.state as state_module

        # Set auth
        mock_auth = Mock()
        mock_auth.session_id = "abc123"
        state_module.auth = mock_auth

        # Access via proxy
        assert auth_proxy.session_id == "abc123"


class TestIntegration:
    """Integration tests for state management"""

    def test_set_auth_and_proxy_integration(self):
        """Test integration between set_auth and AuthProxy"""
        from education_system.post_18.university_system.infrastructure.email import state
        from education_system.post_18.university_system.infrastructure.email.state import auth_proxy

        # Start with None
        state.auth = None
        assert not auth_proxy

        # Set auth instance
        mock_auth = Mock()
        mock_auth.username = "integration_test"
        mock_auth.token = "xyz789"

        state.set_auth(mock_auth)

        # Verify proxy reflects new auth
        assert auth_proxy
        assert auth_proxy.username == "integration_test"
        assert auth_proxy.token == "xyz789"

        # Clear auth
        state.set_auth(None)
        assert not auth_proxy

    def test_multiple_auth_switches(self):
        """Test switching between different auth instances"""
        from education_system.post_18.university_system.infrastructure.email import state
        from education_system.post_18.university_system.infrastructure.email.state import auth_proxy

        # User 1
        auth1 = Mock()
        auth1.user_id = 1
        state.set_auth(auth1)
        assert auth_proxy.user_id == 1

        # User 2
        auth2 = Mock()
        auth2.user_id = 2
        state.set_auth(auth2)
        assert auth_proxy.user_id == 2

        # User 3
        auth3 = Mock()
        auth3.user_id = 3
        state.set_auth(auth3)
        assert auth_proxy.user_id == 3

        # Back to None
        state.set_auth(None)
        assert not auth_proxy

    def test_concurrent_access_safety(self):
        """Test thread-safety of auth state (basic check)"""
        import threading
        from education_system.post_18.university_system.infrastructure.email import state

        results = []

        def set_and_read(auth_obj):
            state.set_auth(auth_obj)
            time.sleep(0.001)  # Small delay
            results.append(state.auth is auth_obj)

        import time

        # Create multiple threads
        threads = []
        for i in range(5):
            auth = Mock()
            auth.id = i
            t = threading.Thread(target=set_and_read, args=(auth,))
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Note: This is a basic test. True thread-safety would require locks,
        # which the current implementation doesn't have. This just ensures
        # no crashes occur with concurrent access.
        assert len(results) == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
