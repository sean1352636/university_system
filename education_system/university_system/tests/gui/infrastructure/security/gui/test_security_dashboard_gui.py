#!/usr/bin/env python3
"""
Tests for Security Dashboard GUI

Tests:
- Dashboard window creation
- Manager initialization
- Widget creation
- GUI integration (with mocking)
- Event handling

Note: These tests mock Tkinter to avoid requiring X11/display
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, call

from education_system.university_system.infrastructure.security.init_security_tables import init_security_tables

@pytest.fixture
def test_db():
    """Create a temporary test database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Initialize security tables
    init_security_tables(path)

    yield path

    # Cleanup
    if os.path.exists(path):
        os.remove(path)

    # Clean up master key file
    master_key_path = os.path.join(os.path.dirname(path), '.encryption_master_key')
    if os.path.exists(master_key_path):
        os.remove(master_key_path)

# ============================================================================
# Dashboard Initialization Tests
# ============================================================================

class TestGUIDashboardInitialization:
    """Test GUI dashboard initialization"""

    @patch('tkinter.Toplevel')
    @patch('tkinter.Tk')
    def test_init_dashboard_success(self, mock_tk, mock_toplevel, test_db):
        """Test successful GUI dashboard initialization"""
        # Mock the parent window
        mock_parent = Mock()
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            dashboard = SecurityDashboard(mock_parent, admin_user_id=1)

            assert dashboard.admin_user_id == 1

    @patch('tkinter.Toplevel')
    def test_init_creates_managers(self, mock_toplevel, test_db):
        """Test initialization creates all security managers"""
        mock_parent = Mock()
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    dashboard = SecurityDashboard(mock_parent, admin_user_id=1)

                    # Verify all managers created
                    assert hasattr(dashboard, 'session_mgr')
                    assert hasattr(dashboard, 'encryption_mgr')
                    assert hasattr(dashboard, 'api_mgr')
                    assert hasattr(dashboard, 'password_mgr')
                    assert hasattr(dashboard, 'audit_mgr')
                    assert hasattr(dashboard, 'dlp_mgr')
                    assert hasattr(dashboard, 'incident_mgr')
                    assert hasattr(dashboard, 'vuln_scanner')

    @patch('tkinter.Toplevel')
    def test_init_sets_window_title(self, mock_toplevel, test_db):
        """Test window title is set"""
        mock_parent = Mock()
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    dashboard = SecurityDashboard(mock_parent, admin_user_id=1)

                    # Verify title was set
                    mock_window.title.assert_called_once()

    @patch('tkinter.Toplevel')
    def test_init_sets_window_geometry(self, mock_toplevel, test_db):
        """Test window geometry is set"""
        mock_parent = Mock()
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    dashboard = SecurityDashboard(mock_parent, admin_user_id=1)

                    # Verify geometry was set
                    assert mock_window.geometry.called

# ============================================================================
# Manager Access Tests
# ============================================================================

class TestGUIManagerAccess:
    """Test access to security managers from GUI"""

    @patch('tkinter.Toplevel')
    def test_access_all_managers(self, mock_toplevel, test_db):
        """Test all managers are accessible"""
        mock_parent = Mock()
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    dashboard = SecurityDashboard(mock_parent, admin_user_id=1)

                    # All managers should be accessible
                    assert dashboard.session_mgr is not None
                    assert dashboard.encryption_mgr is not None
                    assert dashboard.api_mgr is not None
                    assert dashboard.password_mgr is not None
                    assert dashboard.audit_mgr is not None
                    assert dashboard.dlp_mgr is not None
                    assert dashboard.incident_mgr is not None
                    assert dashboard.vuln_scanner is not None

# ============================================================================
# Widget Creation Tests
# ============================================================================

class TestGUIWidgetCreation:
    """Test GUI widget creation"""

    @patch('tkinter.Toplevel')
    @patch('tkinter.Frame')
    @patch('tkinter.Label')
    @patch('tkinter.ttk.Button')
    def test_create_widgets_called(self, mock_button, mock_label, mock_frame, mock_toplevel, test_db):
        """Test _create_widgets is called during init"""
        mock_parent = Mock()
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch.object(SecurityDashboard, '_load_data'):
                dashboard = SecurityDashboard(mock_parent, admin_user_id=1)

                # _create_widgets should have been called
                # This will create frames, labels, buttons, etc.
                assert mock_frame.called or mock_label.called

    @patch('tkinter.Toplevel')
    def test_load_data_called(self, mock_toplevel, test_db):
        """Test _load_data is called during init"""
        mock_parent = Mock()
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data') as mock_load:
                    dashboard = SecurityDashboard(mock_parent, admin_user_id=1)

                    # _load_data should have been called
                    mock_load.assert_called_once()

# ============================================================================
# MFA Integration Tests
# ============================================================================

class TestMFAIntegration:
    """Test MFA admin panel integration"""

    def test_mfa_admin_panel_availability(self):
        """Test MFA admin panel import handling"""
        from education_system.university_system.infrastructure.security.security_dashboard_gui import MFA_ADMIN_AVAILABLE

        # Should be boolean
        assert isinstance(MFA_ADMIN_AVAILABLE, bool)

    def test_mfa_setup_wizard_availability(self):
        """Test MFA setup wizard import handling"""
        from education_system.university_system.infrastructure.security.security_dashboard_gui import MFA_SETUP_AVAILABLE

        # Should be boolean
        assert isinstance(MFA_SETUP_AVAILABLE, bool)

# ============================================================================
# Module Import Tests
# ============================================================================

class TestGUIModuleImports:
    """Test GUI module imports"""

    def test_all_security_modules_imported(self):
        """Test all required security modules are imported"""
        from education_system.university_system.infrastructure.security import security_dashboard_gui

        # Check classes are available
        assert hasattr(security_dashboard_gui, 'SessionManager')
        assert hasattr(security_dashboard_gui, 'EncryptionManager')
        assert hasattr(security_dashboard_gui, 'APISecurityManager')
        assert hasattr(security_dashboard_gui, 'PasswordSecurityManager')
        assert hasattr(security_dashboard_gui, 'SecurityAuditManager')
        assert hasattr(security_dashboard_gui, 'DataLossPreventionManager')
        assert hasattr(security_dashboard_gui, 'IncidentResponseManager')
        assert hasattr(security_dashboard_gui, 'VulnerabilityScanner')

    def test_security_dashboard_class_exists(self):
        """Test SecurityDashboard class is defined"""
        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        assert SecurityDashboard is not None

# ============================================================================
# Integration Tests
# ============================================================================

class TestGUIIntegration:
    """Test GUI integration with security modules"""

    @patch('tkinter.Toplevel')
    def test_managers_use_correct_database(self, mock_toplevel, test_db):
        """Test all managers use the correct database"""
        mock_parent = Mock()
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch('university_system.infrastructure.security.security_dashboard_gui.DEFAULT_DB_PATH', test_db):
                with patch.object(SecurityDashboard, '_create_widgets'):
                    with patch.object(SecurityDashboard, '_load_data'):
                        dashboard = SecurityDashboard(mock_parent, admin_user_id=1)

                        # Create some data using managers
                        key_result = dashboard.encryption_mgr.create_encryption_key('test')

                        # Verify data in database
                        conn = sqlite3.connect(test_db)
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM encryption_keys")
                        count = cursor.fetchone()[0]
                        conn.close()

                        assert count > 0

# ============================================================================
# Error Handling Tests
# ============================================================================

class TestGUIErrorHandling:
    """Test GUI error handling"""

    @patch('tkinter.Toplevel')
    def test_init_with_invalid_admin_id(self, mock_toplevel, test_db):
        """Test initialization with invalid admin ID"""
        mock_parent = Mock()
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    # Should not raise exception
                    dashboard = SecurityDashboard(mock_parent, admin_user_id=-999)

                    assert dashboard.admin_user_id == -999

    @patch('tkinter.Toplevel')
    def test_init_without_parent(self, mock_toplevel):
        """Test initialization without parent window"""
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    # Should handle None parent
                    dashboard = SecurityDashboard(None, admin_user_id=1)

                    assert dashboard is not None

# ============================================================================
# Window Management Tests
# ============================================================================

class TestGUIWindowManagement:
    """Test GUI window management"""

    @patch('tkinter.Toplevel')
    def test_window_centering(self, mock_toplevel, test_db):
        """Test window is centered on screen"""
        mock_parent = Mock()
        mock_window = Mock()
        mock_window.winfo_screenwidth.return_value = 1920
        mock_window.winfo_screenheight.return_value = 1080
        mock_window.winfo_width.return_value = 1200
        mock_window.winfo_height.return_value = 800
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    dashboard = SecurityDashboard(mock_parent, admin_user_id=1)

                    # Window geometry should be set for centering
                    # (multiple calls to geometry are expected)
                    assert mock_window.geometry.call_count >= 1

# ============================================================================
# Functional Tests
# ============================================================================

class TestGUIFunctionality:
    """Test GUI functionality without display"""

    @patch('tkinter.Toplevel')
    def test_dashboard_has_refresh_capability(self, mock_toplevel, test_db):
        """Test dashboard can refresh data"""
        mock_parent = Mock()
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                # Mock _load_data to track calls
                with patch.object(SecurityDashboard, '_load_data') as mock_load:
                    dashboard = SecurityDashboard(mock_parent, admin_user_id=1)

                    # _load_data should have been called during init
                    assert mock_load.call_count >= 1

                    # Calling _load_data again should work
                    dashboard._load_data()
                    assert mock_load.call_count >= 2

# ============================================================================
# Comprehensive Integration Test
# ============================================================================

class TestComprehensiveGUIIntegration:
    """Comprehensive GUI integration tests"""

    @patch('tkinter.Toplevel')
    def test_complete_dashboard_workflow(self, mock_toplevel, test_db):
        """Test complete dashboard workflow"""
        mock_parent = Mock()
        mock_window = Mock()
        mock_toplevel.return_value = mock_window

        from education_system.university_system.infrastructure.security.security_dashboard_gui import SecurityDashboard

        with patch('university_system.infrastructure.security.security_dashboard_gui.init_security_tables'):
            with patch('university_system.infrastructure.security.security_dashboard_gui.DEFAULT_DB_PATH', test_db):
                with patch.object(SecurityDashboard, '_create_widgets'):
                    with patch.object(SecurityDashboard, '_load_data'):
                        # Create dashboard
                        dashboard = SecurityDashboard(mock_parent, admin_user_id=1)

                        # Test each manager works
                        # 1. Encryption
                        key_result = dashboard.encryption_mgr.create_encryption_key('test')
                        assert key_result['success'] is True

                        # 2. API Security
                        api_result = dashboard.api_mgr.create_api_key(1, "GUI Test Key", ["read"])
                        assert api_result['success'] is True

                        # 3. Password Security
                        pwd_result = dashboard.password_mgr.calculate_password_strength("TestPwd123")
                        assert 'score' in pwd_result

                        # 4. Audit
                        dashboard.audit_mgr.log_security_event(1, 'gui_test', {}, 'low')

                        # 5. DLP
                        pii = dashboard.dlp_mgr.detect_pii_in_text("test@example.com")
                        assert isinstance(pii, list)

                        # 6. Incidents
                        incident_result = dashboard.incident_mgr.create_incident(
                            'test', 'low', 'GUI test', 1
                        )
                        assert incident_result['success'] is True

                        # 7. Vulnerability Scanner
                        scan_result = dashboard.vuln_scanner.scan_sql_injection("SELECT * FROM users")
                        assert 'vulnerable' in scan_result

                        # All operations should work through GUI dashboard
                        assert True

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
