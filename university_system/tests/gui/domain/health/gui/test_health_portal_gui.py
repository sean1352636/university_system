"""
Comprehensive test suite for health portal GUI.
Tests all functionality in university_system/modules/domain/health/gui/health_portal_gui.py
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import os
import tempfile

from university_system.modules.domain.health.gui.health_portal_gui import (
    HealthPortalGUI,
    launch_health_portal_gui
)
from university_system.infrastructure.auth import UserAuth

@pytest.fixture
def temp_db_path():
    """Create a temporary database file"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock(spec=UserAuth)
    auth.current_user = {
        'id': 'test_user',
        'username': 'testuser',
        'role': 'admin',
        'email': 'test@example.com'
    }
    auth.check_permission = Mock(return_value=True)
    auth.has_permission = Mock(return_value=True)
    return auth

@pytest.fixture
def root_window():
    """Create a Tk root window for testing"""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except (OSError, IOError):
        pass

class TestHealthPortalGUIInit:
    """Test HealthPortalGUI initialization"""

    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_gui_init_with_auth(self, mock_messagebox, root_window, mock_auth):
        """Test GUI initialization with authenticated user"""
        with patch('university_system.infrastructure.shared_context.get_auth', return_value=mock_auth):
            gui = HealthPortalGUI(root_window, auth_system=mock_auth)

            assert gui.auth == mock_auth
            assert gui.root == root_window
            assert gui.cipher_suite is not None
            assert gui.audit_logger is not None

    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_gui_init_without_auth_shows_error(self, mock_messagebox, root_window):
        """Test GUI shows error when no authentication is present"""
        unauth_mock = Mock(spec=UserAuth)
        unauth_mock.current_user = None

        with patch('university_system.infrastructure.shared_context.get_auth', return_value=unauth_mock):
            gui = HealthPortalGUI(root_window, auth_system=unauth_mock)

            mock_messagebox.showerror.assert_called_once()
            assert 'Authentication Required' in str(mock_messagebox.showerror.call_args)

    def test_encryption_key_generation(self, root_window, mock_auth):
        """Test encryption key is generated properly"""
        with patch('university_system.infrastructure.shared_context.get_auth', return_value=mock_auth):
            with patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox'):
                gui = HealthPortalGUI(root_window, auth_system=mock_auth)

                # Verify encryption key is valid
                assert gui.encryption_key is not None
                assert len(gui.encryption_key) > 0

                # Test that it's a valid Fernet key
                try:
                    test_cipher = Fernet(gui.encryption_key)
                    assert test_cipher is not None
                except Exception:
                    pytest.fail("Generated encryption key is not a valid Fernet key")

class TestEncryptionMethods:
    """Test encryption and decryption methods"""

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_encrypt_decrypt_sensitive_data(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test encryption and decryption of sensitive data"""
        mock_get_auth.return_value = mock_auth
        gui = HealthPortalGUI(root_window, auth_system=mock_auth)

        test_data = "sensitive patient information"

        # Encrypt
        encrypted = gui.encrypt_sensitive_data(test_data)
        assert encrypted is not None
        assert encrypted != test_data

        # Decrypt
        decrypted = gui.decrypt_sensitive_data(encrypted)
        assert decrypted == test_data

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_encrypt_none_data(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test encrypting None returns None"""
        mock_get_auth.return_value = mock_auth
        gui = HealthPortalGUI(root_window, auth_system=mock_auth)

        result = gui.encrypt_sensitive_data(None)
        assert result is None

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_decrypt_invalid_data(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test decrypting invalid data returns original"""
        mock_get_auth.return_value = mock_auth
        gui = HealthPortalGUI(root_window, auth_system=mock_auth)

        invalid_data = "not encrypted data"
        result = gui.decrypt_sensitive_data(invalid_data)

        # Should return original data on decrypt failure
        assert result == invalid_data

class TestRoleChecking:
    """Test role checking methods"""

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_is_admin(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test admin role detection"""
        mock_get_auth.return_value = mock_auth
        mock_auth.current_user['role'] = 'admin'

        gui = HealthPortalGUI(root_window, auth_system=mock_auth)

        assert gui.is_admin() is True
        assert gui.is_staff() is False
        assert gui.is_student() is False

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_is_staff(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test staff role detection"""
        mock_get_auth.return_value = mock_auth
        mock_auth.current_user['role'] = 'staff'

        gui = HealthPortalGUI(root_window, auth_system=mock_auth)

        assert gui.is_admin() is False
        assert gui.is_staff() is True
        assert gui.is_student() is False

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_is_student(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test student role detection"""
        mock_get_auth.return_value = mock_auth
        mock_auth.current_user['role'] = 'student'

        gui = HealthPortalGUI(root_window, auth_system=mock_auth)

        assert gui.is_admin() is False
        assert gui.is_staff() is False
        assert gui.is_student() is True

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_get_user_role(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test getting user role"""
        mock_get_auth.return_value = mock_auth
        mock_auth.current_user['role'] = 'health_provider'

        gui = HealthPortalGUI(root_window, auth_system=mock_auth)

        assert gui.get_user_role() == 'health_provider'

class TestDatabaseOperations:
    """Test database initialization and operations"""

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_database_initialization(self, mock_messagebox, mock_get_auth, root_window, mock_auth, temp_db_path):
        """Test database tables are created properly"""
        mock_get_auth.return_value = mock_auth

        with patch('university_system.modules.domain.health.gui.health_portal_gui.paths.DEFAULT_DB_PATH', temp_db_path):
            gui = HealthPortalGUI(root_window, auth_system=mock_auth)

            # Verify tables exist
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()

            # Check for key tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            assert 'students' in tables
            assert 'health_records' in tables or len(tables) > 0

            conn.close()

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_get_connection(self, mock_messagebox, mock_get_auth, root_window, mock_auth, temp_db_path):
        """Test get_connection method"""
        mock_get_auth.return_value = mock_auth

        with patch('university_system.modules.domain.health.gui.health_portal_gui.paths.DEFAULT_DB_PATH', temp_db_path):
            gui = HealthPortalGUI(root_window, auth_system=mock_auth)

            conn = gui.get_connection()
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)
            conn.close()

class TestAuditLogging:
    """Test audit logging functionality"""

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_log_audit_event(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test audit event logging"""
        mock_get_auth.return_value = mock_auth
        gui = HealthPortalGUI(root_window, auth_system=mock_auth)

        # Mock the audit logger
        gui.audit_logger = Mock()

        # Log an event
        gui.log_audit_event('view', 'health_record', '12345', 'Viewed patient record')

        # Verify logger was called
        gui.audit_logger.info.assert_called_once()
        call_args = str(gui.audit_logger.info.call_args)

        assert 'view' in call_args
        assert 'health_record' in call_args
        assert '12345' in call_args

class TestLaunchFunction:
    """Test launch_health_portal_gui function"""

    @patch('university_system.modules.domain.health.gui.health_portal_gui.tk.Tk')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.HealthPortalGUI')
    def test_launch_health_portal_gui_with_auth(self, mock_gui_class, mock_tk, mock_auth):
        """Test launching GUI with authentication"""
        mock_root = Mock()
        mock_tk.return_value = mock_root

        launch_health_portal_gui(auth=mock_auth)

        # Verify Tk was created
        mock_tk.assert_called_once()

        # Verify HealthPortalGUI was instantiated
        mock_gui_class.assert_called_once()

    @patch('university_system.modules.domain.health.gui.health_portal_gui.tk.Tk')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.HealthPortalGUI')
    @patch('university_system.infrastructure.shared_context.get_auth')
    def test_launch_health_portal_gui_without_auth(self, mock_get_auth, mock_gui_class, mock_tk):
        """Test launching GUI without explicit auth uses global auth"""
        mock_root = Mock()
        mock_tk.return_value = mock_root
        mock_auth = Mock(spec=UserAuth)
        mock_auth.current_user = {'id': 'user1', 'username': 'test', 'role': 'admin'}
        mock_get_auth.return_value = mock_auth

        launch_health_portal_gui()

        # Verify it used the global auth
        mock_get_auth.assert_called()

class TestErrorHandling:
    """Test error handling scenarios"""

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_get_user_role_with_no_auth(self, mock_messagebox, mock_get_auth, root_window):
        """Test get_user_role handles missing auth gracefully"""
        no_auth = Mock(spec=UserAuth)
        no_auth.current_user = None
        mock_get_auth.return_value = no_auth

        gui = HealthPortalGUI(root_window, auth_system=no_auth)

        # Should handle None gracefully
        role = gui.get_user_role()
        assert role is None

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_decrypt_with_wrong_key(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test decryption with wrong key returns original data"""
        mock_get_auth.return_value = mock_auth
        gui = HealthPortalGUI(root_window, auth_system=mock_auth)

        # Encrypt with one key
        encrypted = gui.encrypt_sensitive_data("test data")

        # Create new GUI instance with different key
        gui2 = HealthPortalGUI(root_window, auth_system=mock_auth)

        # Try to decrypt - should return original encrypted string
        result = gui2.decrypt_sensitive_data(encrypted)
        assert result is not None  # Should not crash

class TestSecurityFeatures:
    """Test security-related features"""

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_encryption_key_persistence(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test encryption key is persisted and reused"""
        mock_get_auth.return_value = mock_auth

        with tempfile.TemporaryDirectory() as temp_dir:
            key_file = os.path.join(temp_dir, 'health_encryption.key')

            with patch('university_system.modules.domain.health.gui.health_portal_gui.paths.DATA_DIR', temp_dir):
                # First instance creates key
                gui1 = HealthPortalGUI(root_window, auth_system=mock_auth)
                key1 = gui1.encryption_key

                # Verify key file exists
                assert os.path.exists(key_file)

                # Second instance should reuse same key
                gui2 = HealthPortalGUI(root_window, auth_system=mock_auth)
                key2 = gui2.encryption_key

                assert key1 == key2

class TestDataEncryptionIntegration:
    """Integration tests for data encryption workflows"""

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_encrypt_decrypt_workflow(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test complete encrypt/decrypt workflow"""
        mock_get_auth.return_value = mock_auth
        gui = HealthPortalGUI(root_window, auth_system=mock_auth)

        # Test with various data types
        test_cases = [
            "Patient SSN: 123-45-6789",
            "Medical diagnosis: diabetes",
            "Prescription: 500mg daily",
            "Notes: Confidential medical information"
        ]

        for test_data in test_cases:
            encrypted = gui.encrypt_sensitive_data(test_data)
            decrypted = gui.decrypt_sensitive_data(encrypted)

            assert encrypted != test_data
            assert decrypted == test_data

    @patch('university_system.infrastructure.shared_context.get_auth')
    @patch('university_system.modules.domain.health.gui.health_portal_gui.messagebox')
    def test_audit_logging_integration(self, mock_messagebox, mock_get_auth, root_window, mock_auth):
        """Test audit logging captures all required information"""
        mock_get_auth.return_value = mock_auth
        gui = HealthPortalGUI(root_window, auth_system=mock_auth)

        gui.audit_logger = Mock()

        # Log various events
        events = [
            ('create', 'health_record', '1', 'Created new health record'),
            ('view', 'prescription', '42', 'Viewed prescription'),
            ('update', 'appointment', '100', 'Updated appointment status'),
            ('delete', 'allergy', '5', 'Removed allergy record')
        ]

        for action, resource_type, resource_id, details in events:
            gui.log_audit_event(action, resource_type, resource_id, details)

        # Verify all events were logged
        assert gui.audit_logger.info.call_count == len(events)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
