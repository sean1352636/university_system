"""
Comprehensive test suite for integration_marketplace_core.py

Tests all classes, functions, and functionality including:
- IntegrationCatalogManager class
- InstallationManager class
- CredentialManager class
- SyncManager class
- DataMappingManager class
- WebhookManager class
- display_integration_marketplace_menu function
- launch_integration_marketplace_gui function
"""

import pytest
import os
import tempfile
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO

from education_system.post_18.university_system.modules.shared.services.integrations.integration_marketplace_core import (
    IntegrationCatalogManager,
    InstallationManager,
    CredentialManager,
    SyncManager,
    DataMappingManager,
    WebhookManager,
    display_integration_marketplace_menu,
    launch_integration_marketplace_gui
)

# Patch path prefix for submodules
_PATCH_BASE = 'education_system.post_18.university_system.modules.shared.services.integrations.integration_marketplace_core'

@pytest.fixture
def temp_db():
    """Create a temporary test database with required tables."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create all required tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS integration_catalog (
            integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_name TEXT NOT NULL,
            provider_name TEXT NOT NULL,
            integration_type TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            version TEXT DEFAULT '1.0',
            is_official INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            rating REAL DEFAULT 0.0,
            install_count INTEGER DEFAULT 0,
            pricing_model TEXT,
            documentation_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS installed_integrations (
            install_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_id INTEGER NOT NULL,
            installed_by TEXT NOT NULL,
            version_installed TEXT NOT NULL,
            installation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            last_sync_date TIMESTAMP,
            sync_frequency TEXT,
            is_enabled INTEGER DEFAULT 1,
            configuration TEXT,
            FOREIGN KEY (integration_id) REFERENCES integration_catalog(integration_id)
        );

        CREATE TABLE IF NOT EXISTS integration_credentials (
            credential_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            credential_type TEXT NOT NULL,
            api_key TEXT,
            api_secret TEXT,
            oauth_token TEXT,
            endpoint_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            token_expiry TIMESTAMP,
            FOREIGN KEY (install_id) REFERENCES installed_integrations(install_id)
        );

        CREATE TABLE IF NOT EXISTS integration_sync_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            sync_start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sync_end_time TIMESTAMP,
            sync_status TEXT DEFAULT 'running',
            records_synced INTEGER DEFAULT 0,
            errors_encountered INTEGER DEFAULT 0,
            error_details TEXT,
            FOREIGN KEY (install_id) REFERENCES installed_integrations(install_id)
        );

        CREATE TABLE IF NOT EXISTS integration_data_mappings (
            mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            source_field TEXT NOT NULL,
            target_field TEXT NOT NULL,
            transformation_rule TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (install_id) REFERENCES installed_integrations(install_id)
        );

        CREATE TABLE IF NOT EXISTS integration_webhooks (
            webhook_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            webhook_url TEXT NOT NULL,
            event_type TEXT NOT NULL,
            secret_key TEXT,
            is_active INTEGER DEFAULT 1,
            last_triggered_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (install_id) REFERENCES installed_integrations(install_id)
        );
    """)

    conn.commit()
    conn.close()

    yield db_path

    try:
        os.unlink(db_path)
    except (OSError, IOError):
        pass


def _make_conn(db_path):
    """Create a new SQLite connection to the temp DB with Row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


class TestIntegrationCatalogManager:
    """Test IntegrationCatalogManager class."""

    @patch(f'{_PATCH_BASE}.catalog.get_connection')
    def test_add_integration_basic(self, mock_get_connection, temp_db):
        """Test adding a basic integration."""
        mock_get_connection.return_value = _make_conn(temp_db)

        integration_id = IntegrationCatalogManager.add_integration(
            integration_name="Test Integration",
            provider_name="Test Provider",
            integration_type="API",
            category="LMS",
            description="Test description"
        )

        assert integration_id is not None
        assert isinstance(integration_id, int)

    @patch(f'{_PATCH_BASE}.catalog.get_connection')
    def test_add_integration_with_version(self, mock_get_connection, temp_db):
        """Test adding an integration with version."""
        mock_get_connection.return_value = _make_conn(temp_db)

        integration_id = IntegrationCatalogManager.add_integration(
            integration_name="Test Integration",
            provider_name="Test Provider",
            integration_type="API",
            category="LMS",
            version="2.0.1"
        )

        assert integration_id is not None

    @patch(f'{_PATCH_BASE}.catalog.get_connection')
    def test_add_integration_official(self, mock_get_connection, temp_db):
        """Test adding an official integration."""
        mock_get_connection.return_value = _make_conn(temp_db)

        integration_id = IntegrationCatalogManager.add_integration(
            integration_name="Official Integration",
            provider_name="Official Provider",
            integration_type="API",
            category="Finance",
            is_official=True
        )

        assert integration_id is not None

    @patch(f'{_PATCH_BASE}.catalog.get_connection')
    def test_add_integration_error_handling(self, mock_get_connection):
        """Test error handling when adding integration fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        with pytest.raises(Exception) as exc_info:
            IntegrationCatalogManager.add_integration(
                integration_name="Test",
                provider_name="Test",
                integration_type="API",
                category="Test"
            )

        assert "Error adding integration:" in str(exc_info.value)

    @patch(f'{_PATCH_BASE}.catalog.get_connection')
    def test_get_available_integrations_all(self, mock_get_connection, temp_db):
        """Test getting all available integrations."""
        # Seed data first
        seed_conn = _make_conn(temp_db)
        cursor = seed_conn.cursor()
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, rating, install_count)
            VALUES ('Integration 1', 'Provider 1', 'API', 'LMS', 4.5, 100)
        """)
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, rating, install_count)
            VALUES ('Integration 2', 'Provider 2', 'Webhook', 'Finance', 4.0, 50)
        """)
        seed_conn.commit()
        seed_conn.close()

        mock_get_connection.return_value = _make_conn(temp_db)

        integrations = IntegrationCatalogManager.get_available_integrations()

        assert isinstance(integrations, list)
        assert len(integrations) == 2

    @patch(f'{_PATCH_BASE}.catalog.get_connection')
    def test_get_available_integrations_by_category(self, mock_get_connection, temp_db):
        """Test getting integrations by category."""
        # Seed data first
        seed_conn = _make_conn(temp_db)
        cursor = seed_conn.cursor()
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, rating)
            VALUES ('LMS Integration', 'Provider', 'API', 'LMS', 4.5)
        """)
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, rating)
            VALUES ('Finance Integration', 'Provider', 'API', 'Finance', 4.0)
        """)
        seed_conn.commit()
        seed_conn.close()

        mock_get_connection.return_value = _make_conn(temp_db)

        integrations = IntegrationCatalogManager.get_available_integrations(category="LMS")

        assert isinstance(integrations, list)
        assert len(integrations) == 1
        assert integrations[0]['category'] == 'LMS'

class TestInstallationManager:
    """Test InstallationManager class."""

    @patch(f'{_PATCH_BASE}.installation.get_connection')
    def test_install_integration(self, mock_get_connection, temp_db):
        """Test installing an integration."""
        # Seed catalog entry
        seed_conn = _make_conn(temp_db)
        cursor = seed_conn.cursor()
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, version)
            VALUES ('Test Integration', 'Provider', 'API', 'LMS', '1.0.0')
        """)
        integration_id = cursor.lastrowid
        seed_conn.commit()
        seed_conn.close()

        mock_get_connection.return_value = _make_conn(temp_db)

        # Install integration
        install_id = InstallationManager.install_integration(
            integration_id=integration_id,
            installed_by="testuser",
            configuration='{"api_key": "test"}'
        )

        assert install_id is not None
        assert isinstance(install_id, int)

        # Verify install count was updated using a fresh connection
        verify_conn = _make_conn(temp_db)
        verify_cursor = verify_conn.cursor()
        verify_cursor.execute("SELECT install_count FROM integration_catalog WHERE integration_id = ?", (integration_id,))
        row = verify_cursor.fetchone()
        assert row['install_count'] == 1
        verify_conn.close()

    @patch(f'{_PATCH_BASE}.installation.get_connection')
    def test_install_integration_error_handling(self, mock_get_connection):
        """Test error handling when installation fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'version': '1.0.0'}
        mock_cursor.execute.side_effect = [None, Exception("Database error")]
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        with pytest.raises(Exception) as exc_info:
            InstallationManager.install_integration(
                integration_id=1,
                installed_by="testuser"
            )

        assert "Error installing integration:" in str(exc_info.value)

    @patch(f'{_PATCH_BASE}.installation.get_connection')
    def test_uninstall_integration(self, mock_get_connection, temp_db):
        """Test uninstalling an integration."""
        # Seed data
        seed_conn = _make_conn(temp_db)
        cursor = seed_conn.cursor()
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, version)
            VALUES ('Test Integration', 'Provider', 'API', 'LMS', '1.0.0')
        """)
        integration_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO installed_integrations (integration_id, installed_by, version_installed)
            VALUES (?, 'testuser', '1.0.0')
        """, (integration_id,))
        install_id = cursor.lastrowid
        seed_conn.commit()
        seed_conn.close()

        mock_get_connection.return_value = _make_conn(temp_db)

        # Uninstall
        result = InstallationManager.uninstall_integration(install_id)

        assert result is True

        # Verify status was updated using a fresh connection
        verify_conn = _make_conn(temp_db)
        verify_cursor = verify_conn.cursor()
        verify_cursor.execute("SELECT status, is_enabled FROM installed_integrations WHERE install_id = ?", (install_id,))
        row = verify_cursor.fetchone()
        assert row['status'] == 'uninstalled'
        assert row['is_enabled'] == 0
        verify_conn.close()

class TestCredentialManager:
    """Test CredentialManager class."""

    @patch(f'{_PATCH_BASE}.credentials.get_connection')
    def test_store_credentials_api_key(self, mock_get_connection, temp_db):
        """Test storing API key credentials."""
        # Seed data
        seed_conn = _make_conn(temp_db)
        cursor = seed_conn.cursor()
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, version)
            VALUES ('Test', 'Provider', 'API', 'LMS', '1.0.0')
        """)
        integration_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO installed_integrations (integration_id, installed_by, version_installed)
            VALUES (?, 'testuser', '1.0.0')
        """, (integration_id,))
        install_id = cursor.lastrowid
        seed_conn.commit()
        seed_conn.close()

        mock_get_connection.return_value = _make_conn(temp_db)

        # Store credentials
        credential_id = CredentialManager.store_credentials(
            install_id=install_id,
            credential_type="api_key",
            api_key="test_api_key_123",
            endpoint_url="https://api.example.com"
        )

        assert credential_id is not None
        assert isinstance(credential_id, int)

    @patch(f'{_PATCH_BASE}.credentials.get_connection')
    def test_store_credentials_oauth(self, mock_get_connection, temp_db):
        """Test storing OAuth credentials."""
        # Seed data
        seed_conn = _make_conn(temp_db)
        cursor = seed_conn.cursor()
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, version)
            VALUES ('Test', 'Provider', 'API', 'LMS', '1.0.0')
        """)
        integration_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO installed_integrations (integration_id, installed_by, version_installed)
            VALUES (?, 'testuser', '1.0.0')
        """, (integration_id,))
        install_id = cursor.lastrowid
        seed_conn.commit()
        seed_conn.close()

        mock_get_connection.return_value = _make_conn(temp_db)

        # Store OAuth credentials
        credential_id = CredentialManager.store_credentials(
            install_id=install_id,
            credential_type="oauth",
            oauth_token="oauth_token_xyz"
        )

        assert credential_id is not None

class TestSyncManager:
    """Test SyncManager class."""

    @patch(f'{_PATCH_BASE}.sync.get_connection')
    def test_start_sync(self, mock_get_connection, temp_db):
        """Test starting a sync operation."""
        # Seed data
        seed_conn = _make_conn(temp_db)
        cursor = seed_conn.cursor()
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, version)
            VALUES ('Test', 'Provider', 'API', 'LMS', '1.0.0')
        """)
        integration_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO installed_integrations (integration_id, installed_by, version_installed)
            VALUES (?, 'testuser', '1.0.0')
        """, (integration_id,))
        install_id = cursor.lastrowid
        seed_conn.commit()
        seed_conn.close()

        mock_get_connection.return_value = _make_conn(temp_db)

        # Start sync
        log_id = SyncManager.start_sync(install_id)

        assert log_id is not None
        assert isinstance(log_id, int)

        # Verify sync log was created using a fresh connection
        verify_conn = _make_conn(temp_db)
        verify_cursor = verify_conn.cursor()
        verify_cursor.execute("SELECT sync_status FROM integration_sync_logs WHERE log_id = ?", (log_id,))
        row = verify_cursor.fetchone()
        assert row['sync_status'] == 'running'
        verify_conn.close()

    @patch(f'{_PATCH_BASE}.sync.get_connection')
    def test_start_sync_error_handling(self, mock_get_connection):
        """Test error handling when starting sync fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        with pytest.raises(Exception) as exc_info:
            SyncManager.start_sync(1)

        assert "Error starting sync:" in str(exc_info.value)

    @patch(f'{_PATCH_BASE}.sync.get_connection')
    def test_complete_sync_success(self, mock_get_connection, temp_db):
        """Test completing a sync operation successfully."""
        # Seed data
        seed_conn = _make_conn(temp_db)
        cursor = seed_conn.cursor()
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, version)
            VALUES ('Test', 'Provider', 'API', 'LMS', '1.0.0')
        """)
        integration_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO installed_integrations (integration_id, installed_by, version_installed)
            VALUES (?, 'testuser', '1.0.0')
        """, (integration_id,))
        install_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO integration_sync_logs (install_id, sync_status)
            VALUES (?, 'running')
        """, (install_id,))
        log_id = cursor.lastrowid
        seed_conn.commit()
        seed_conn.close()

        mock_get_connection.return_value = _make_conn(temp_db)

        # Complete sync
        result = SyncManager.complete_sync(
            log_id=log_id,
            sync_status="completed",
            records_synced=100,
            errors_encountered=0
        )

        assert result is True

        # Verify sync log was updated using a fresh connection
        verify_conn = _make_conn(temp_db)
        verify_cursor = verify_conn.cursor()
        verify_cursor.execute("""
            SELECT sync_status, records_synced, errors_encountered
            FROM integration_sync_logs WHERE log_id = ?
        """, (log_id,))
        row = verify_cursor.fetchone()
        assert row['sync_status'] == 'completed'
        assert row['records_synced'] == 100
        assert row['errors_encountered'] == 0
        verify_conn.close()

    @patch(f'{_PATCH_BASE}.sync.get_connection')
    def test_complete_sync_with_errors(self, mock_get_connection, temp_db):
        """Test completing a sync operation with errors."""
        # Seed data
        seed_conn = _make_conn(temp_db)
        cursor = seed_conn.cursor()
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, version)
            VALUES ('Test', 'Provider', 'API', 'LMS', '1.0.0')
        """)
        integration_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO installed_integrations (integration_id, installed_by, version_installed)
            VALUES (?, 'testuser', '1.0.0')
        """, (integration_id,))
        install_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO integration_sync_logs (install_id, sync_status)
            VALUES (?, 'running')
        """, (install_id,))
        log_id = cursor.lastrowid
        seed_conn.commit()
        seed_conn.close()

        mock_get_connection.return_value = _make_conn(temp_db)

        # Complete sync with errors
        result = SyncManager.complete_sync(
            log_id=log_id,
            sync_status="failed",
            records_synced=50,
            errors_encountered=10,
            error_details="Connection timeout"
        )

        assert result is True

    @patch(f'{_PATCH_BASE}.sync.get_connection')
    def test_complete_sync_error_handling(self, mock_get_connection):
        """Test error handling when completing sync fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value = mock_conn

        with pytest.raises(Exception) as exc_info:
            SyncManager.complete_sync(log_id=1, sync_status="completed")

        assert "Error completing sync:" in str(exc_info.value)

class TestDataMappingManager:
    """Test DataMappingManager class."""

    @patch(f'{_PATCH_BASE}.data_mapping.get_connection')
    def test_create_mapping(self, mock_get_connection, temp_db):
        """Test creating a data mapping."""
        # Seed data
        seed_conn = _make_conn(temp_db)
        cursor = seed_conn.cursor()
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, version)
            VALUES ('Test', 'Provider', 'API', 'LMS', '1.0.0')
        """)
        integration_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO installed_integrations (integration_id, installed_by, version_installed)
            VALUES (?, 'testuser', '1.0.0')
        """, (integration_id,))
        install_id = cursor.lastrowid
        seed_conn.commit()
        seed_conn.close()

        mock_get_connection.return_value = _make_conn(temp_db)

        # Create mapping
        mapping_id = DataMappingManager.create_mapping(
            install_id=install_id,
            source_field="external_student_id",
            target_field="student_id"
        )

        assert mapping_id is not None
        assert isinstance(mapping_id, int)

class TestWebhookManager:
    """Test WebhookManager class."""

    @patch(f'{_PATCH_BASE}.webhooks.get_connection')
    def test_register_webhook(self, mock_get_connection, temp_db):
        """Test registering a webhook."""
        # Seed data
        seed_conn = _make_conn(temp_db)
        cursor = seed_conn.cursor()
        cursor.execute("""
            INSERT INTO integration_catalog (integration_name, provider_name, integration_type, category, version)
            VALUES ('Test', 'Provider', 'Webhook', 'LMS', '1.0.0')
        """)
        integration_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO installed_integrations (integration_id, installed_by, version_installed)
            VALUES (?, 'testuser', '1.0.0')
        """, (integration_id,))
        install_id = cursor.lastrowid
        seed_conn.commit()
        seed_conn.close()

        mock_get_connection.return_value = _make_conn(temp_db)

        # Register webhook
        webhook_id = WebhookManager.register_webhook(
            install_id=install_id,
            webhook_url="https://example.com/webhook",
            event_type="student.created"
        )

        assert webhook_id is not None
        assert isinstance(webhook_id, int)

class TestDisplayIntegrationMarketplaceMenu:
    """Test display_integration_marketplace_menu function."""

    @patch('builtins.input', side_effect=['0'])
    @patch('builtins.print')
    def test_menu_display_and_exit(self, mock_print, mock_input):
        """Test menu displays and exits on choice 0."""
        mock_auth = Mock()
        display_integration_marketplace_menu(mock_auth)

        # Verify menu was displayed
        assert any("INTEGRATION MARKETPLACE" in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['1', '0'])
    @patch('builtins.print')
    def test_menu_choice_1(self, mock_print, mock_input):
        """Test menu choice 1 (Browse Integration Catalog)."""
        mock_auth = Mock()
        display_integration_marketplace_menu(mock_auth)

        # Verify message was printed
        assert any("Feature available via Integration managers" in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=['invalid', '0'])
    @patch('builtins.print')
    def test_menu_invalid_choice(self, mock_print, mock_input):
        """Test menu handles invalid choice."""
        mock_auth = Mock()
        display_integration_marketplace_menu(mock_auth)

        # Verify error message was printed
        assert any("Invalid choice" in str(call) for call in mock_print.call_args_list)

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    @patch('builtins.print')
    def test_menu_keyboard_interrupt(self, mock_print, mock_input):
        """Test menu handles keyboard interrupt."""
        mock_auth = Mock()
        display_integration_marketplace_menu(mock_auth)
        # Should exit gracefully

class TestLaunchIntegrationMarketplaceGui:
    """Test launch_integration_marketplace_gui function."""

    def test_launch_gui_function_exists(self):
        """Test that launch_integration_marketplace_gui function exists."""
        assert callable(launch_integration_marketplace_gui)

    @patch('builtins.print')
    def test_launch_gui_execution(self, mock_print):
        """Test launching GUI with no auth shows error via messagebox."""
        mock_root = Mock()
        mock_auth = Mock()
        mock_auth.current_user = None

        with patch('tkinter.messagebox.showerror') as mock_showerror:
            launch_integration_marketplace_gui(mock_root, mock_auth)
            # When current_user is None, messagebox.showerror is called
            mock_showerror.assert_called_once()

class TestIntegration:
    """Integration tests for complex workflows."""

    def test_full_integration_workflow(self, temp_db):
        """Test complete integration workflow."""
        with patch(f'{_PATCH_BASE}.catalog.get_connection', return_value=_make_conn(temp_db)):
            # 1. Add integration to catalog
            integration_id = IntegrationCatalogManager.add_integration(
                integration_name="Complete Test Integration",
                provider_name="Test Provider",
                integration_type="API",
                category="LMS",
                version="1.0.0",
                is_official=True
            )

        with patch(f'{_PATCH_BASE}.installation.get_connection', return_value=_make_conn(temp_db)):
            # 2. Install integration
            install_id = InstallationManager.install_integration(
                integration_id=integration_id,
                installed_by="admin",
                configuration='{"sync_enabled": true}'
            )

        with patch(f'{_PATCH_BASE}.credentials.get_connection', return_value=_make_conn(temp_db)):
            # 3. Store credentials
            credential_id = CredentialManager.store_credentials(
                install_id=install_id,
                credential_type="api_key",
                api_key="test_api_key",
                endpoint_url="https://api.test.com"
            )

        with patch(f'{_PATCH_BASE}.data_mapping.get_connection', return_value=_make_conn(temp_db)):
            # 4. Create data mapping
            mapping_id = DataMappingManager.create_mapping(
                install_id=install_id,
                source_field="student_id",
                target_field="external_id"
            )

        with patch(f'{_PATCH_BASE}.webhooks.get_connection', return_value=_make_conn(temp_db)):
            # 5. Register webhook
            webhook_id = WebhookManager.register_webhook(
                install_id=install_id,
                webhook_url="https://test.com/webhook",
                event_type="sync.completed",
                secret_key="webhook_secret"
            )

        with patch(f'{_PATCH_BASE}.sync.get_connection', return_value=_make_conn(temp_db)):
            # 6. Start sync
            log_id = SyncManager.start_sync(install_id)

        with patch(f'{_PATCH_BASE}.sync.get_connection', return_value=_make_conn(temp_db)):
            # 7. Complete sync
            result = SyncManager.complete_sync(
                log_id=log_id,
                sync_status="completed",
                records_synced=100
            )

        # Verify all operations succeeded
        assert integration_id is not None
        assert install_id is not None
        assert credential_id is not None
        assert mapping_id is not None
        assert webhook_id is not None
        assert log_id is not None
        assert result is True


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
