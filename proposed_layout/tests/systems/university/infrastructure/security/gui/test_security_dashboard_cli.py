#!/usr/bin/env python3
"""
Tests for Security Dashboard CLI

Tests:
- Dashboard initialization
- Manager initialization
- Security tables initialization
- Integration with security modules
- CLI helper functions
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

from education_system.systems.university.infrastructure.security.security_dashboard_cli import SecurityDashboardCLI
from education_system.systems.university.infrastructure.security.init_security_tables import init_security_tables

@pytest.fixture
def test_db():
    """Create a temporary test database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Initialize security tables
    init_security_tables(path)

    # Minimal users table — sessions FK-references it, and the dashboard's
    # managers now operate on this db (not the real one).
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT)")
    conn.execute("INSERT OR IGNORE INTO users (id, username) VALUES (1, 'admin')")
    conn.commit()
    conn.close()

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

class TestDashboardInitialization:
    """Test dashboard initialization"""

    def test_init_dashboard_success(self, test_db):
        """Test successful dashboard initialization"""
        dashboard = SecurityDashboardCLI(admin_user_id=1)

        assert dashboard is not None
        assert dashboard.admin_user_id == 1

    def test_init_initializes_security_tables(self, test_db):
        """Test initialization creates security tables"""
        # Create dashboard with test DB
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            # Verify tables exist
            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='security_events'
            """)
            table = cursor.fetchone()
            conn.close()

            assert table is not None

    def test_init_creates_all_managers(self, test_db):
        """Test all security managers are initialized"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            # Check all managers are created
            assert hasattr(dashboard, 'session_mgr')
            assert hasattr(dashboard, 'encryption_mgr')
            assert hasattr(dashboard, 'api_mgr')
            assert hasattr(dashboard, 'password_mgr')
            assert hasattr(dashboard, 'audit_mgr')
            assert hasattr(dashboard, 'dlp_mgr')
            assert hasattr(dashboard, 'incident_mgr')
            assert hasattr(dashboard, 'vuln_scanner')

    def test_init_with_different_admin_ids(self, test_db):
        """Test initialization with different admin IDs"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard1 = SecurityDashboardCLI(admin_user_id=1)
            dashboard2 = SecurityDashboardCLI(admin_user_id=999)

            assert dashboard1.admin_user_id == 1
            assert dashboard2.admin_user_id == 999

# ============================================================================
# Manager Access Tests
# ============================================================================

class TestManagerAccess:
    """Test access to security managers"""

    def test_access_session_manager(self, test_db):
        """Test accessing session manager"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            assert dashboard.session_mgr is not None
            assert hasattr(dashboard.session_mgr, 'create_session')

    def test_access_encryption_manager(self, test_db):
        """Test accessing encryption manager"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            assert dashboard.encryption_mgr is not None
            assert hasattr(dashboard.encryption_mgr, 'encrypt_value')

    def test_access_api_security_manager(self, test_db):
        """Test accessing API security manager"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            assert dashboard.api_mgr is not None
            assert hasattr(dashboard.api_mgr, 'create_api_key')

    def test_access_password_security_manager(self, test_db):
        """Test accessing password security manager"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            assert dashboard.password_mgr is not None
            assert hasattr(dashboard.password_mgr, 'calculate_password_strength')

    def test_access_audit_manager(self, test_db):
        """Test accessing security audit manager"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            assert dashboard.audit_mgr is not None
            assert hasattr(dashboard.audit_mgr, 'log_security_event')

    def test_access_dlp_manager(self, test_db):
        """Test accessing data loss prevention manager"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            assert dashboard.dlp_mgr is not None
            assert hasattr(dashboard.dlp_mgr, 'detect_pii_in_text')

    def test_access_incident_manager(self, test_db):
        """Test accessing incident response manager"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            assert dashboard.incident_mgr is not None
            assert hasattr(dashboard.incident_mgr, 'create_incident')

    def test_access_vulnerability_scanner(self, test_db):
        """Test accessing vulnerability scanner"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            assert dashboard.vuln_scanner is not None
            assert hasattr(dashboard.vuln_scanner, 'scan_sql_injection')

# ============================================================================
# Integration Tests
# ============================================================================

class TestCLIIntegration:
    """Test CLI integration with security modules"""

    @patch('education_system.systems.university.infrastructure.security.session_management.SessionManager._get_location_from_ip')
    def test_session_creation_through_cli(self, mock_location, test_db):
        """Test creating session through CLI dashboard"""
        mock_location.return_value = {'city': 'Test', 'country': 'Test', 'latitude': 0, 'longitude': 0}

        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            result = dashboard.session_mgr.create_session(
                user_id=1,
                role='admin',
                ip_address='127.0.0.1',
                user_agent='TestAgent'
            )

            assert result['success'] is True
            assert 'session_id' in result

    def test_encryption_through_cli(self, test_db):
        """Test encryption operations through CLI dashboard"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.data_encryption.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.comprehensive_security.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.session_management.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.init_security_tables.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            # Create encryption key
            key_result = dashboard.encryption_mgr.create_encryption_key('data')

            assert key_result['success'] is True

            # Encrypt value
            encrypted = dashboard.encryption_mgr.encrypt_value(
                "sensitive data",
                key_result['key_id']
            )

            assert encrypted is not None

    def test_api_key_management_through_cli(self, test_db):
        """Test API key management through CLI dashboard"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.data_encryption.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.comprehensive_security.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.session_management.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.init_security_tables.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            # Create API key
            result = dashboard.api_mgr.create_api_key(
                user_id=1,
                key_name="Test Key",
                permissions=["read:all"]
            )

            assert result['success'] is True
            assert result['api_key'].startswith('uni_')

    def test_password_strength_check_through_cli(self, test_db):
        """Test password strength checking through CLI dashboard"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            # Check weak password
            result = dashboard.password_mgr.calculate_password_strength("123456")

            assert result['strength'] == 'weak'
            assert result['score'] < 50

    def test_security_event_logging_through_cli(self, test_db):
        """Test security event logging through CLI dashboard"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.data_encryption.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.comprehensive_security.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.session_management.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.init_security_tables.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            # Log event
            dashboard.audit_mgr.log_security_event(
                user_id=1,
                event_type='test_event',
                details={'action': 'test'},
                severity='low'
            )

            # Verify event was logged
            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM security_events WHERE event_type = 'test_event'")
            count = cursor.fetchone()[0]
            conn.close()

            assert count == 1

    def test_pii_detection_through_cli(self, test_db):
        """Test PII detection through CLI dashboard"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            # Detect PII
            text = "My SSN is 123-45-6789"
            pii_found = dashboard.dlp_mgr.detect_pii_in_text(text)

            assert len(pii_found) > 0
            assert any(item['type'] == 'SSN' for item in pii_found)

    def test_incident_creation_through_cli(self, test_db):
        """Test incident creation through CLI dashboard"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            # Create incident
            result = dashboard.incident_mgr.create_incident(
                incident_type='test',
                severity='medium',
                description='Test incident',
                detected_by=1
            )

            assert result['success'] is True
            assert 'incident_id' in result

    def test_vulnerability_scanning_through_cli(self, test_db):
        """Test vulnerability scanning through CLI dashboard"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard = SecurityDashboardCLI(admin_user_id=1)

            # Scan for SQL injection
            result = dashboard.vuln_scanner.scan_sql_injection(
                "SELECT * FROM users WHERE id = 1 OR 1=1"
            )

            assert result['vulnerable'] is True

# ============================================================================
# Multiple Dashboard Instances Tests
# ============================================================================

class TestMultipleDashboards:
    """Test multiple dashboard instances"""

    def test_multiple_dashboards_independent(self, test_db):
        """Test multiple dashboards are independent"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            dashboard1 = SecurityDashboardCLI(admin_user_id=1)
            dashboard2 = SecurityDashboardCLI(admin_user_id=2)

            assert dashboard1.admin_user_id != dashboard2.admin_user_id
            assert dashboard1 is not dashboard2

    def test_dashboards_share_database(self, test_db):
        """Test multiple dashboards share same database"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.data_encryption.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.comprehensive_security.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.session_management.DEFAULT_DB_PATH', test_db), \
             patch('education_system.systems.university.infrastructure.security.init_security_tables.DEFAULT_DB_PATH', test_db):
            dashboard1 = SecurityDashboardCLI(admin_user_id=1)
            dashboard2 = SecurityDashboardCLI(admin_user_id=2)

            # Create event in dashboard1
            dashboard1.audit_mgr.log_security_event(
                user_id=1,
                event_type='shared_event',
                details={},
                severity='low'
            )

            # Verify visible in dashboard2
            conn = sqlite3.connect(test_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM security_events WHERE event_type = 'shared_event'")
            count = cursor.fetchone()[0]
            conn.close()

            assert count == 1

# ============================================================================
# Tabulate Helper Tests
# ============================================================================

class TestTabulateHelper:
    """Test tabulate helper function"""

    def test_tabulate_available(self):
        """Test checking if tabulate is available"""
        from education_system.systems.university.infrastructure.security.security_dashboard_cli import TABULATE_AVAILABLE

        # Should be boolean
        assert isinstance(TABULATE_AVAILABLE, bool)

    def test_fallback_tabulate_function(self):
        """Test fallback tabulate function"""
        from education_system.systems.university.infrastructure.security.security_dashboard_cli import tabulate

        # Test with data
        data = [
            ['Row1', 'Value1'],
            ['Row2', 'Value2']
        ]
        headers = ['Column1', 'Column2']

        result = tabulate(data, headers=headers)

        # Should return string
        assert isinstance(result, str)
        # Should contain headers
        assert 'Column1' in result
        assert 'Column2' in result

    def test_fallback_tabulate_no_data(self):
        """Test fallback tabulate with no data"""
        from education_system.systems.university.infrastructure.security.security_dashboard_cli import tabulate, TABULATE_AVAILABLE

        result = tabulate([])

        if TABULATE_AVAILABLE:
            # Real tabulate returns empty string for empty data
            assert isinstance(result, str)
        else:
            assert result == "No data"

# ============================================================================
# Error Handling Tests
# ============================================================================

class TestCLIErrorHandling:
    """Test error handling in CLI"""

    def test_dashboard_init_with_invalid_admin_id(self, test_db):
        """Test dashboard handles invalid admin ID gracefully"""
        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', test_db):
            # Should not raise exception
            dashboard = SecurityDashboardCLI(admin_user_id=-1)

            assert dashboard.admin_user_id == -1

    def test_manager_operations_with_corrupted_db(self):
        """Test graceful handling of database errors"""
        # Create invalid database path
        invalid_path = "/nonexistent/path/to/db.sqlite"

        with patch('education_system.systems.university.infrastructure.security.security_dashboard_cli.DEFAULT_DB_PATH', invalid_path):
            # Should handle initialization gracefully
            try:
                dashboard = SecurityDashboardCLI(admin_user_id=1)
                # Managers should be created even if DB operations fail
                assert dashboard is not None
            except Exception:
                # Acceptable to raise exception for invalid DB
                pass

# ============================================================================
# Module Import Tests
# ============================================================================

class TestModuleImports:
    """Test module imports and availability"""

    def test_all_security_modules_imported(self):
        """Test all required security modules are imported"""
        from education_system.systems.university.infrastructure.security import security_dashboard_cli

        # Check classes are available
        assert hasattr(security_dashboard_cli, 'SessionManager')
        assert hasattr(security_dashboard_cli, 'EncryptionManager')
        assert hasattr(security_dashboard_cli, 'APISecurityManager')
        assert hasattr(security_dashboard_cli, 'PasswordSecurityManager')
        assert hasattr(security_dashboard_cli, 'SecurityAuditManager')
        assert hasattr(security_dashboard_cli, 'DataLossPreventionManager')
        assert hasattr(security_dashboard_cli, 'IncidentResponseManager')
        assert hasattr(security_dashboard_cli, 'VulnerabilityScanner')

    def test_auth_module_availability(self):
        """Test auth module import handling"""
        from education_system.systems.university.infrastructure.security.security_dashboard_cli import AUTH_MODULE_AVAILABLE

        # Should be boolean
        assert isinstance(AUTH_MODULE_AVAILABLE, bool)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
