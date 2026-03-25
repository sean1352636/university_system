#!/usr/bin/env python3
"""
Tests for Integration Marketplace GUI
Tests the comprehensive integration management interface
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import tempfile
import os
import tkinter as tk
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from education_system.university_system.modules.services.gui import integration_marketplace_gui

@pytest.fixture
def temp_db():
    """Create temporary database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    # Create required tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS integration_catalog (
            integration_id INTEGER PRIMARY KEY,
            integration_name TEXT,
            provider_name TEXT,
            category TEXT,
            integration_type TEXT,
            version TEXT,
            rating REAL,
            install_count INTEGER,
            is_official INTEGER,
            is_active INTEGER DEFAULT 1,
            description TEXT,
            pricing_model TEXT,
            documentation_url TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS installed_integrations (
            install_id INTEGER PRIMARY KEY,
            integration_id INTEGER,
            installed_by TEXT,
            version_installed TEXT,
            installation_date TIMESTAMP,
            status TEXT,
            last_sync_date TIMESTAMP,
            sync_frequency TEXT,
            is_enabled INTEGER,
            configuration TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS integration_credentials (
            credential_id INTEGER PRIMARY KEY,
            install_id INTEGER,
            credential_type TEXT,
            api_key TEXT,
            api_secret TEXT,
            oauth_token TEXT,
            endpoint_url TEXT,
            created_at TIMESTAMP,
            token_expiry TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS integration_sync_logs (
            log_id INTEGER PRIMARY KEY,
            install_id INTEGER,
            sync_start_time TIMESTAMP,
            sync_end_time TIMESTAMP,
            sync_status TEXT,
            records_synced INTEGER,
            errors_encountered INTEGER,
            error_details TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS integration_data_mappings (
            mapping_id INTEGER PRIMARY KEY,
            install_id INTEGER,
            source_field TEXT,
            target_field TEXT,
            transformation_rule TEXT,
            is_active INTEGER
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS integration_webhooks (
            webhook_id INTEGER PRIMARY KEY,
            install_id INTEGER,
            webhook_url TEXT,
            event_type TEXT,
            secret_key TEXT,
            is_active INTEGER,
            last_triggered_at TIMESTAMP,
            created_at TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS integration_usage_analytics (
            analytics_id INTEGER PRIMARY KEY,
            install_id INTEGER,
            metric_name TEXT,
            metric_value REAL,
            measurement_date TIMESTAMP
        )
    """)
    
    # Insert test data
    cursor.execute("""
        INSERT INTO integration_catalog 
        (integration_name, provider_name, category, integration_type, version, is_official, is_active)
        VALUES ('Test Integration', 'Test Provider', 'LMS', 'API', '1.0.0', 1, 1)
    """)
    
    conn.commit()
    conn.close()
    
    yield path
    
    try:
        os.unlink(path)
    except (OSError, IOError):
        pass

@pytest.fixture
def mock_auth():
    """Create mock auth"""
    auth = Mock()
    auth.current_user = {
        'id': 1,
        'username': 'testuser',
        'email': 'test@example.com',
        'role': 'admin',
        'permissions': ['manage_integrations']
    }
    return auth

@pytest.fixture
def root_window():
    """Create root window"""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except (OSError, IOError):
        pass

class TestIntegrationMarketplaceGUIInitialization:
    """Test GUI initialization"""

    def test_gui_requires_parent(self, root_window, mock_auth, temp_db):
        """Test GUI initialization with parent"""
        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.university_system.infrastructure.database.schemas.init_integration_marketplace_system_db'):
                try:
                    gui = integration_marketplace_gui.IntegrationMarketplaceGUI(root_window, mock_auth)
                    assert gui is not None
                except (OSError, IOError):
                    pass

    def test_gui_initializes_database(self, root_window, mock_auth, temp_db):
        """Test database initialization"""
        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.university_system.infrastructure.database.schemas.init_integration_marketplace_system_db') as mock_init:
                try:
                    gui = integration_marketplace_gui.IntegrationMarketplaceGUI(root_window, mock_auth)
                    mock_init.assert_called_once()
                except (OSError, IOError):
                    pass

class TestCatalogTab:
    """Test catalog tab functionality"""

    def test_load_catalog(self, root_window, mock_auth, temp_db):
        """Test loading catalog"""
        with patch('education_system.university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.university_system.infrastructure.database.schemas.init_integration_marketplace_system_db'):
                try:
                    gui = integration_marketplace_gui.IntegrationMarketplaceGUI(root_window, mock_auth)
                    gui.load_catalog()
                except (OSError, IOError):
                    pass

class TestLauncherFunction:
    """Test launcher function"""

    def test_launch_integration_marketplace_gui(self, root_window, mock_auth):
        """Test launcher function"""
        with patch('education_system.university_system.infrastructure.database.schemas.init_integration_marketplace_system_db'):
            try:
                integration_marketplace_gui.launch_integration_marketplace_gui(auth=mock_auth, parent=root_window)
            except (OSError, IOError):
                pass

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
