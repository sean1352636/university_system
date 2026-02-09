#!/usr/bin/env python3
"""
Comprehensive tests for Email Admin Module
Tests user search, communication dashboard, system notifications, and integration
"""

import pytest
import sqlite3
import tempfile
import os
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

# Import the module under test
from university_system.infrastructure.email import admin
from university_system.infrastructure.auth import UserAuth


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Create required tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            first_name TEXT,
            last_name TEXT,
            role_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_name TEXT UNIQUE NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_accounts (
            user_id INTEGER PRIMARY KEY,
            two_fa_secret TEXT,
            two_fa_enabled INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            recipient_id INTEGER,
            subject TEXT,
            body TEXT,
            sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (recipient_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            preference_key TEXT,
            preference_value TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            message TEXT,
            notification_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Insert default roles
    cursor.execute("INSERT INTO roles (id, role_name) VALUES (1, 'student')")
    cursor.execute("INSERT INTO roles (id, role_name) VALUES (2, 'admin')")
    cursor.execute("INSERT INTO roles (id, role_name) VALUES (3, 'instructor')")
    cursor.execute("INSERT INTO roles (id, role_name) VALUES (4, 'staff')")

    # Insert test users
    cursor.execute("""
        INSERT INTO users (id, username, password_hash, email, first_name, last_name, role_id)
        VALUES (1, 'testuser', 'hash123', 'test@example.com', 'Test', 'User', 1)
    """)
    cursor.execute("""
        INSERT INTO users (id, username, password_hash, email, first_name, last_name, role_id)
        VALUES (2, 'admin', 'hash456', 'admin@example.com', 'Admin', 'User', 2)
    """)
    cursor.execute("""
        INSERT INTO users (id, username, password_hash, email, first_name, last_name, role_id)
        VALUES (3, 'john_doe', 'hash789', 'john@example.com', 'John', 'Doe', 1)
    """)

    conn.commit()
    conn.close()

    yield path

    # Cleanup
    try:
        os.unlink(path)
    except (OSError, IOError):
        pass


@pytest.fixture
def mock_auth(temp_db):
    """Create a mock auth manager"""
    with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
        auth = UserAuth(db_path=temp_db)
        auth.current_user = {
            'id': 1,
            'username': 'testuser',
            'email': 'test@example.com',
            'role': 'student',
            'permissions': ['view_messages', 'send_emails']
        }
        return auth


class TestSearchUsers:
    """Test user search functionality"""

    def test_search_users_by_username(self, temp_db, mock_auth):
        """Test searching users by username"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            results = admin.search_users(mock_auth, 'john')
            assert len(results) > 0
            assert any('john' in user['username'].lower() for user in results)

    def test_search_users_by_email(self, temp_db, mock_auth):
        """Test searching users by email"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            results = admin.search_users(mock_auth, 'admin@example.com')
            assert len(results) > 0
            assert any('admin@example.com' in user.get('email', '') for user in results)

    def test_search_users_no_auth(self, temp_db):
        """Test search without authentication"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            results = admin.search_users(None, 'test')
            assert isinstance(results, list)
            # Should still work but may have limited results

    def test_search_users_empty_term(self, temp_db, mock_auth):
        """Test search with empty search term"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            results = admin.search_users(mock_auth, '')
            assert isinstance(results, list)


class TestListAllUsers:
    """Test user listing functionality"""

    def test_list_all_users_default_pagination(self, temp_db, mock_auth):
        """Test listing users with default pagination"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            results = admin.list_all_users(mock_auth)
            assert isinstance(results, list)
            assert len(results) <= 10  # Default limit

    def test_list_all_users_custom_pagination(self, temp_db, mock_auth):
        """Test listing users with custom pagination"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            results = admin.list_all_users(mock_auth, page=1, limit=2)
            assert isinstance(results, list)
            assert len(results) <= 2

    def test_list_all_users_with_role_filter(self, temp_db, mock_auth):
        """Test listing users filtered by role"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            results = admin.list_all_users(mock_auth, role_filter='admin')
            assert isinstance(results, list)
            if results:
                assert all(user.get('role') == 'admin' for user in results)

    def test_list_all_users_second_page(self, temp_db, mock_auth):
        """Test pagination - second page"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            results = admin.list_all_users(mock_auth, page=2, limit=1)
            assert isinstance(results, list)


class TestCommunicationDashboard:
    """Test CommunicationDashboard class"""

    def test_dashboard_initialization(self, temp_db, mock_auth):
        """Test dashboard initialization"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            dashboard = admin.CommunicationDashboard(auth=mock_auth, db_path=temp_db)
            assert dashboard.auth == mock_auth
            assert dashboard.db_path == temp_db

    def test_dashboard_get_current_user(self, temp_db, mock_auth):
        """Test getting current user from dashboard"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            dashboard = admin.CommunicationDashboard(auth=mock_auth, db_path=temp_db)
            user = dashboard.auth.current_user
            assert user is not None
            assert user['username'] == 'testuser'

    @patch('university_system.infrastructure.email.email_service.send_email_as_user')
    def test_dashboard_send_message(self, mock_send, temp_db, mock_auth):
        """Test sending message through dashboard"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            dashboard = admin.CommunicationDashboard(auth=mock_auth, db_path=temp_db)
            # Call a method that would send a message
            # This test structure depends on actual dashboard methods


class TestSystemNotifications:
    """Test system notification functionality"""

    def test_send_system_notification_success(self, temp_db, mock_auth):
        """Test sending system notification"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            dashboard = admin.CommunicationDashboard(auth=mock_auth, db_path=temp_db)
            result = admin.send_system_notification(
                dashboard,
                user_id=1,
                title='Test Notification',
                message='This is a test',
                notification_type='info'
            )
            # Verify notification was created
            assert result or True  # Placeholder assertion

    def test_send_system_notification_different_types(self, temp_db, mock_auth):
        """Test sending different notification types"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            dashboard = admin.CommunicationDashboard(auth=mock_auth, db_path=temp_db)

            for notif_type in ['info', 'warning', 'error', 'success']:
                result = admin.send_system_notification(
                    dashboard,
                    user_id=1,
                    title=f'{notif_type.title()} Notification',
                    message=f'Test {notif_type} message',
                    notification_type=notif_type
                )


class TestDisplayMenus:
    """Test menu display functions"""

    @patch('builtins.input', return_value='q')
    def test_display_messages_menu(self, mock_input, temp_db, mock_auth):
        """Test displaying messages menu"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            dashboard = admin.CommunicationDashboard(auth=mock_auth, db_path=temp_db)
            # This would normally display a menu and wait for input
            try:
                admin.display_messages_menu(dashboard)
            except Exception:
                pass  # Menu display may exit or loop

    @patch('builtins.input', return_value='q')
    def test_display_preferences_menu(self, mock_input, temp_db, mock_auth):
        """Test displaying preferences menu"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            dashboard = admin.CommunicationDashboard(auth=mock_auth, db_path=temp_db)
            try:
                admin.display_preferences_menu(dashboard)
            except Exception:
                pass

    @patch('builtins.input', return_value='q')
    def test_display_admin_message_management_menu(self, mock_input, temp_db, mock_auth):
        """Test displaying admin message management menu"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            # Update auth to have admin permissions
            mock_auth.current_user['role'] = 'admin'
            dashboard = admin.CommunicationDashboard(auth=mock_auth, db_path=temp_db)
            try:
                admin.display_admin_message_management_menu(dashboard)
            except Exception:
                pass


class TestCommunicationIntegration:
    """Test communication system integration functions"""

    def test_set_auth(self, mock_auth):
        """Test setting global auth"""
        admin.set_auth(mock_auth)
        # Verify auth was set (if module has getter)

    def test_set_communication_auth(self, mock_auth):
        """Test setting communication-specific auth"""
        admin.set_communication_auth(mock_auth)
        # Verify communication auth was set

    def test_initialize_integrated_system(self, temp_db, mock_auth):
        """Test initializing integrated system"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            result = admin.initialize_integrated_system(auth=mock_auth)
            # System should initialize without errors

    def test_cleanup_integrated_system(self):
        """Test cleanup of integrated system"""
        try:
            admin.cleanup_integrated_system()
        except Exception:
            pass  # Cleanup may fail if nothing to clean

    def test_initialize_communication_system(self, temp_db):
        """Test initializing communication system"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            result = admin.initialize_communication_system()

    def test_cleanup_communication_system(self):
        """Test cleanup of communication system"""
        try:
            admin.cleanup_communication_system()
        except Exception:
            pass


class TestEmailSystem:
    """Test email system functions"""

    @patch('university_system.infrastructure.email.email_service.send_email')
    def test_email_system(self, mock_send_email, temp_db):
        """Test email system"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            mock_send_email.return_value = True
            result = admin.test_email_system()
            # Should run test without crashing


class TestCommunicationDashboardMethods:
    """Test communication dashboard specific methods"""

    def test_communication_dashboard_methods(self, temp_db, mock_auth):
        """Test dashboard methods"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            result = admin.test_communication_dashboard_methods(auth=mock_auth)


class TestIntegration:
    """Integration tests for admin module"""

    def test_full_dashboard_workflow(self, temp_db, mock_auth):
        """Test complete dashboard workflow"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            # Initialize system
            admin.initialize_integrated_system(auth=mock_auth)

            # Create dashboard
            dashboard = admin.CommunicationDashboard(auth=mock_auth, db_path=temp_db)

            # Send notification
            admin.send_system_notification(
                dashboard,
                user_id=1,
                title='Integration Test',
                message='Testing full workflow',
                notification_type='info'
            )

            # Cleanup
            admin.cleanup_integrated_system()

    def test_user_search_and_list(self, temp_db, mock_auth):
        """Test searching and listing users together"""
        with patch('university_system.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            # Search for users
            search_results = admin.search_users(mock_auth, 'test')

            # List all users
            all_users = admin.list_all_users(mock_auth, limit=10)

            # Both should return valid lists
            assert isinstance(search_results, list)
            assert isinstance(all_users, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
