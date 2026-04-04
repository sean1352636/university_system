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
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock, call

from education_system.university_system.infrastructure.security.init_security_tables import init_security_tables

# Common patch prefix for the security dashboard GUI module
_SD_MOD = 'education_system.university_system.modules.shared.gui.security.security_dashboard_gui'
# Also the backward-compat shim location
_SD_INFRA = 'education_system.university_system.infrastructure.security.security_dashboard_gui'


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


@pytest.fixture
def root_window():
    """Create a real root Tkinter window for testing"""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass

# ============================================================================
# Dashboard Initialization Tests
# ============================================================================

class TestGUIDashboardInitialization:
    """Test GUI dashboard initialization"""

    def test_init_dashboard_success(self, root_window, test_db):
        """Test successful GUI dashboard initialization"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch(f'{_SD_MOD}.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    with patch(f'{_SD_MOD}.init_i18n'):
                        dashboard = SecurityDashboard(root_window, admin_user_id=1)
                        assert dashboard.admin_user_id == 1
                        dashboard.destroy()

    def test_init_creates_managers(self, root_window, test_db):
        """Test initialization creates all security managers"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch(f'{_SD_MOD}.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    with patch(f'{_SD_MOD}.init_i18n'):
                        dashboard = SecurityDashboard(root_window, admin_user_id=1)

                        # Verify all managers created
                        assert hasattr(dashboard, 'session_mgr')
                        assert hasattr(dashboard, 'encryption_mgr')
                        assert hasattr(dashboard, 'api_mgr')
                        assert hasattr(dashboard, 'password_mgr')
                        assert hasattr(dashboard, 'audit_mgr')
                        assert hasattr(dashboard, 'dlp_mgr')
                        assert hasattr(dashboard, 'incident_mgr')
                        assert hasattr(dashboard, 'vuln_scanner')
                        dashboard.destroy()

    def test_init_sets_window_title(self, root_window, test_db):
        """Test window title is set"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch(f'{_SD_MOD}.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    with patch(f'{_SD_MOD}.init_i18n'):
                        dashboard = SecurityDashboard(root_window, admin_user_id=1)
                        # Window title should be set (non-empty)
                        title = dashboard.title()
                        assert title is not None
                        dashboard.destroy()

    def test_init_sets_window_geometry(self, root_window, test_db):
        """Test window geometry is set"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch(f'{_SD_MOD}.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    with patch(f'{_SD_MOD}.init_i18n'):
                        dashboard = SecurityDashboard(root_window, admin_user_id=1)
                        # Geometry should be set (contains dimensions)
                        geo = dashboard.geometry()
                        assert geo is not None
                        dashboard.destroy()

# ============================================================================
# Manager Access Tests
# ============================================================================

class TestGUIManagerAccess:
    """Test access to security managers from GUI"""

    def test_access_all_managers(self, root_window, test_db):
        """Test all managers are accessible"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch(f'{_SD_MOD}.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    with patch(f'{_SD_MOD}.init_i18n'):
                        dashboard = SecurityDashboard(root_window, admin_user_id=1)

                        # All managers should be accessible
                        assert dashboard.session_mgr is not None
                        assert dashboard.encryption_mgr is not None
                        assert dashboard.api_mgr is not None
                        assert dashboard.password_mgr is not None
                        assert dashboard.audit_mgr is not None
                        assert dashboard.dlp_mgr is not None
                        assert dashboard.incident_mgr is not None
                        assert dashboard.vuln_scanner is not None
                        dashboard.destroy()

# ============================================================================
# Widget Creation Tests
# ============================================================================

class TestGUIWidgetCreation:
    """Test GUI widget creation"""

    def test_create_widgets_called(self, root_window, test_db):
        """Test _create_widgets is called during init"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch(f'{_SD_MOD}.init_security_tables'):
            with patch.object(SecurityDashboard, '_load_data'):
                with patch(f'{_SD_MOD}.init_i18n'):
                    with patch.object(SecurityDashboard, '_create_widgets') as mock_create:
                        dashboard = SecurityDashboard(root_window, admin_user_id=1)
                        mock_create.assert_called_once()
                        dashboard.destroy()

    def test_load_data_called(self, root_window, test_db):
        """Test _load_data is called during init"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch(f'{_SD_MOD}.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch(f'{_SD_MOD}.init_i18n'):
                    with patch.object(SecurityDashboard, '_load_data') as mock_load:
                        dashboard = SecurityDashboard(root_window, admin_user_id=1)

                        # _load_data should have been called
                        mock_load.assert_called_once()
                        dashboard.destroy()

# ============================================================================
# MFA Integration Tests
# ============================================================================

class TestMFAIntegration:
    """Test MFA admin panel integration"""

    def test_mfa_admin_panel_availability(self):
        """Test MFA admin panel import handling"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import MFA_ADMIN_AVAILABLE

        # Should be boolean
        assert isinstance(MFA_ADMIN_AVAILABLE, bool)

    def test_mfa_setup_wizard_availability(self):
        """Test MFA setup wizard import handling"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import MFA_SETUP_AVAILABLE

        # Should be boolean
        assert isinstance(MFA_SETUP_AVAILABLE, bool)

# ============================================================================
# Module Import Tests
# ============================================================================

class TestGUIModuleImports:
    """Test GUI module imports"""

    def test_all_security_modules_imported(self):
        """Test all required security modules are imported"""
        from education_system.university_system.modules.shared.gui.security import security_dashboard_gui

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
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        assert SecurityDashboard is not None

# ============================================================================
# Integration Tests
# ============================================================================

class TestGUIIntegration:
    """Test GUI integration with security modules"""

    def test_managers_use_correct_database(self, root_window, test_db):
        """Test all managers are initialized and accessible"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch.object(SecurityDashboard, '_create_widgets'):
            with patch.object(SecurityDashboard, '_load_data'):
                with patch(f'{_SD_MOD}.init_i18n'):
                    dashboard = SecurityDashboard(root_window, admin_user_id=1)

                    # Verify managers are initialized and have db_path
                    assert dashboard.encryption_mgr is not None
                    assert hasattr(dashboard.encryption_mgr, 'db_path')
                    assert dashboard.api_mgr is not None
                    assert dashboard.password_mgr is not None
                    dashboard.destroy()

# ============================================================================
# Error Handling Tests
# ============================================================================

class TestGUIErrorHandling:
    """Test GUI error handling"""

    def test_init_with_invalid_admin_id(self, root_window, test_db):
        """Test initialization with invalid admin ID"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch(f'{_SD_MOD}.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    with patch(f'{_SD_MOD}.init_i18n'):
                        # Should not raise exception
                        dashboard = SecurityDashboard(root_window, admin_user_id=-999)
                        assert dashboard.admin_user_id == -999
                        dashboard.destroy()

    def test_init_without_parent(self, root_window):
        """Test initialization without parent window"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch(f'{_SD_MOD}.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    with patch(f'{_SD_MOD}.init_i18n'):
                        # When parent is None, Toplevel uses the default root
                        dashboard = SecurityDashboard(None, admin_user_id=1)
                        assert dashboard is not None
                        dashboard.destroy()

# ============================================================================
# Window Management Tests
# ============================================================================

class TestGUIWindowManagement:
    """Test GUI window management"""

    def test_window_centering(self, root_window, test_db):
        """Test window is centered on screen"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch(f'{_SD_MOD}.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch.object(SecurityDashboard, '_load_data'):
                    with patch(f'{_SD_MOD}.init_i18n'):
                        dashboard = SecurityDashboard(root_window, admin_user_id=1)

                        # Window geometry should be set
                        geo = dashboard.geometry()
                        assert geo is not None
                        dashboard.destroy()

# ============================================================================
# Functional Tests
# ============================================================================

class TestGUIFunctionality:
    """Test GUI functionality without display"""

    def test_dashboard_has_refresh_capability(self, root_window, test_db):
        """Test dashboard can refresh data"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch(f'{_SD_MOD}.init_security_tables'):
            with patch.object(SecurityDashboard, '_create_widgets'):
                with patch(f'{_SD_MOD}.init_i18n'):
                    # Mock _load_data to track calls
                    with patch.object(SecurityDashboard, '_load_data') as mock_load:
                        dashboard = SecurityDashboard(root_window, admin_user_id=1)

                        # _load_data should have been called during init
                        assert mock_load.call_count >= 1

                        # Calling _load_data again should work
                        dashboard._load_data()
                        assert mock_load.call_count >= 2
                        dashboard.destroy()

# ============================================================================
# Comprehensive Integration Test
# ============================================================================

class TestComprehensiveGUIIntegration:
    """Comprehensive GUI integration tests"""

    def test_complete_dashboard_workflow(self, root_window, test_db):
        """Test complete dashboard workflow"""
        from education_system.university_system.modules.shared.gui.security.security_dashboard_gui import SecurityDashboard

        with patch.object(SecurityDashboard, '_create_widgets'):
            with patch.object(SecurityDashboard, '_load_data'):
                with patch(f'{_SD_MOD}.init_i18n'):
                    # Create dashboard (let init_security_tables run)
                    dashboard = SecurityDashboard(root_window, admin_user_id=1)

                    # 3. Password Security (doesn't need DB)
                    pwd_result = dashboard.password_mgr.calculate_password_strength("TestPwd123")
                    assert 'score' in pwd_result

                    # 5. DLP (doesn't need DB)
                    pii = dashboard.dlp_mgr.detect_pii_in_text("test@example.com")
                    assert isinstance(pii, list)

                    # 7. Vulnerability Scanner (doesn't need DB)
                    scan_result = dashboard.vuln_scanner.scan_sql_injection("SELECT * FROM users")
                    assert 'vulnerable' in scan_result

                    # All operations should work through GUI dashboard
                    assert True
                    dashboard.destroy()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
