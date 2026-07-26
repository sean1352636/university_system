"""
Comprehensive test suite for communication schema.py

Tests all functionality including:
- COMMUNICATION_SCHEMA constant
- create_communication_tables function
- All table definitions
- All indexes
"""

import pytest
import os
import tempfile
from education_system.systems.university.infrastructure.database.db import sqlite3
from unittest.mock import patch, MagicMock

from education_system.systems.university.services.communication.schema import (
    COMMUNICATION_SCHEMA,
    create_communication_tables
)

@pytest.fixture
def temp_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    yield db_path

    try:
        os.unlink(db_path)
    except (OSError, IOError):
        pass

class TestCommunicationSchema:
    """Test the COMMUNICATION_SCHEMA constant."""

    def test_schema_is_string(self):
        """Test that COMMUNICATION_SCHEMA is a string."""
        assert isinstance(COMMUNICATION_SCHEMA, str)
        assert len(COMMUNICATION_SCHEMA) > 0

    def test_schema_contains_table_definitions(self):
        """Test that schema contains all expected table definitions."""
        tables = [
            'messages',
            'message_recipients',
            'email_queue',
            'sms_queue',
            'push_notifications',
            'announcements',
            'message_templates',
            'communication_preferences',
            'delivery_logs',
            'emergency_alerts',
            'notification_subscriptions'
        ]

        for table in tables:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in COMMUNICATION_SCHEMA

    def test_schema_contains_indexes(self):
        """Test that schema contains index definitions."""
        indexes = [
            'idx_messages_sender',
            'idx_messages_status',
            'idx_message_recipients_user',
            'idx_email_queue_status',
            'idx_sms_queue_status',
            'idx_push_notifications_user',
            'idx_announcements_active',
            'idx_delivery_logs_message',
            'idx_emergency_alerts_active',
            'idx_subscriptions_user'
        ]

        for index in indexes:
            assert f"CREATE INDEX IF NOT EXISTS {index}" in COMMUNICATION_SCHEMA

class TestCreateCommunicationTables:
    """Test the create_communication_tables function."""

    def test_create_tables_basic(self, temp_db, capsys):
        """Test creating tables in a new database."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)
        conn.close()

        # Verify tables were created
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_tables = [
            'announcements',
            'communication_preferences',
            'delivery_logs',
            'email_queue',
            'emergency_alerts',
            'message_recipients',
            'message_templates',
            'messages',
            'notification_subscriptions',
            'push_notifications',
            'sms_queue'
        ]

        for table in expected_tables:
            assert table in tables

        # Check output message
        captured = capsys.readouterr()
        assert "Unified Communication Hub tables created successfully" in captured.out

    def test_create_tables_idempotent(self, temp_db):
        """Test that creating tables is idempotent (can be run multiple times)."""
        conn = sqlite3.connect(temp_db)

        # Create tables twice
        create_communication_tables(conn)
        create_communication_tables(conn)

        conn.close()

        # Should not raise any errors

    def test_messages_table_structure(self, temp_db):
        """Test messages table has correct structure."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(messages)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            'message_id': 'INTEGER',
            'sender_id': 'INTEGER',
            'subject': 'TEXT',
            'body': 'TEXT',
            'message_type': 'TEXT',
            'priority': 'TEXT',
            'created_at': 'TIMESTAMP',
            'scheduled_time': 'TIMESTAMP',
            'status': 'TEXT'
        }

        for col_name in expected_columns:
            assert col_name in columns

    def test_email_queue_table_structure(self, temp_db):
        """Test email_queue table has correct structure."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(email_queue)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'queue_id',
            'to_address',
            'cc_addresses',
            'bcc_addresses',
            'subject',
            'body',
            'html_body',
            'attachments',
            'scheduled_time',
            'priority',
            'status',
            'attempts',
            'max_attempts',
            'sent_at',
            'error_message',
            'created_at'
        ]

        for col_name in expected_columns:
            assert col_name in columns

    def test_sms_queue_table_structure(self, temp_db):
        """Test sms_queue table has correct structure."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(sms_queue)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'sms_id',
            'phone_number',
            'message_text',
            'scheduled_time',
            'status',
            'attempts',
            'max_attempts',
            'sent_at',
            'message_id',
            'error_message',
            'cost',
            'created_at'
        ]

        for col_name in expected_columns:
            assert col_name in columns

    def test_push_notifications_table_structure(self, temp_db):
        """Test push_notifications table has correct structure."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(push_notifications)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'notification_id',
            'user_id',
            'title',
            'body',
            'data',
            'icon',
            'click_action',
            'status',
            'sent_at',
            'created_at'
        ]

        for col_name in expected_columns:
            assert col_name in columns

    def test_announcements_table_structure(self, temp_db):
        """Test announcements table has correct structure."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(announcements)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'announcement_id',
            'title',
            'content',
            'target_audience',
            'priority',
            'start_date',
            'end_date',
            'is_active',
            'created_by',
            'created_at'
        ]

        for col_name in expected_columns:
            assert col_name in columns

    def test_message_templates_table_structure(self, temp_db):
        """Test message_templates table has correct structure."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(message_templates)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'template_id',
            'name',
            'subject',
            'body',
            'variables',
            'template_type',
            'category',
            'is_active',
            'created_by',
            'created_at'
        ]

        for col_name in expected_columns:
            assert col_name in columns

    def test_communication_preferences_table_structure(self, temp_db):
        """Test communication_preferences table has correct structure."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(communication_preferences)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'pref_id',
            'user_id',
            'email_enabled',
            'sms_enabled',
            'push_enabled',
            'announcement_enabled',
            'marketing_enabled',
            'emergency_only',
            'preferred_method',
            'quiet_hours_start',
            'quiet_hours_end',
            'updated_at'
        ]

        for col_name in expected_columns:
            assert col_name in columns

    def test_delivery_logs_table_structure(self, temp_db):
        """Test delivery_logs table has correct structure."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(delivery_logs)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'log_id',
            'message_id',
            'recipient_id',
            'delivery_method',
            'delivery_time',
            'status',
            'error_message',
            'response_code',
            'provider_message_id'
        ]

        for col_name in expected_columns:
            assert col_name in columns

    def test_emergency_alerts_table_structure(self, temp_db):
        """Test emergency_alerts table has correct structure."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(emergency_alerts)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'alert_id',
            'alert_type',
            'message',
            'severity',
            'affected_locations',
            'sent_at',
            'resolved_at',
            'is_active',
            'sent_by',
            'total_recipients'
        ]

        for col_name in expected_columns:
            assert col_name in columns

    def test_notification_subscriptions_table_structure(self, temp_db):
        """Test notification_subscriptions table has correct structure."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(notification_subscriptions)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'subscription_id',
            'user_id',
            'topic',
            'channel',
            'is_active',
            'created_at'
        ]

        for col_name in expected_columns:
            assert col_name in columns

    def test_message_recipients_table_structure(self, temp_db):
        """Test message_recipients table has correct structure."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(message_recipients)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = [
            'recipient_id',
            'message_id',
            'user_id',
            'delivery_status',
            'delivered_at',
            'read_at',
            'error_message'
        ]

        for col_name in expected_columns:
            assert col_name in columns

class TestIndexes:
    """Test that indexes are created correctly."""

    def test_indexes_created(self, temp_db):
        """Test that all expected indexes are created."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_indexes = [
            'idx_messages_sender',
            'idx_messages_status',
            'idx_message_recipients_user',
            'idx_email_queue_status',
            'idx_sms_queue_status',
            'idx_push_notifications_user',
            'idx_announcements_active',
            'idx_delivery_logs_message',
            'idx_emergency_alerts_active',
            'idx_subscriptions_user'
        ]

        for index in expected_indexes:
            assert index in indexes

class TestDefaultValues:
    """Test that default values are set correctly."""

    def test_email_queue_defaults(self, temp_db):
        """Test email_queue default values."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO email_queue (to_address, subject, body)
            VALUES ('test@example.com', 'Test', 'Test body')
        """)

        cursor.execute("SELECT priority, status, attempts, max_attempts FROM email_queue WHERE queue_id = 1")
        row = cursor.fetchone()
        conn.close()

        priority, status, attempts, max_attempts = row
        assert priority == 5
        assert status == 'queued'
        assert attempts == 0
        assert max_attempts == 3

    def test_push_notifications_defaults(self, temp_db):
        """Test push_notifications default values."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO push_notifications (user_id, title, body)
            VALUES (1, 'Test', 'Test body')
        """)

        cursor.execute("SELECT status FROM push_notifications WHERE notification_id = 1")
        row = cursor.fetchone()
        conn.close()

        status = row[0]
        assert status == 'pending'

    def test_announcements_defaults(self, temp_db):
        """Test announcements default values."""
        conn = sqlite3.connect(temp_db)
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO announcements (title, content, created_by)
            VALUES ('Test', 'Test content', 1)
        """)

        cursor.execute("SELECT priority, is_active FROM announcements WHERE announcement_id = 1")
        row = cursor.fetchone()
        conn.close()

        priority, is_active = row
        assert priority == 'normal'
        assert is_active == 1

    def test_communication_preferences_defaults(self, temp_db):
        """Test communication_preferences default values."""
        conn = sqlite3.connect(temp_db)
        conn.execute("PRAGMA foreign_keys = OFF")
        create_communication_tables(conn)

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO communication_preferences (user_id)
            VALUES (1)
        """)

        cursor.execute("""
            SELECT email_enabled, sms_enabled, push_enabled,
                   announcement_enabled, marketing_enabled, emergency_only, preferred_method
            FROM communication_preferences WHERE user_id = 1
        """)
        row = cursor.fetchone()
        conn.close()

        (email_enabled, sms_enabled, push_enabled,
         announcement_enabled, marketing_enabled, emergency_only, preferred_method) = row

        assert email_enabled == 1
        assert sms_enabled == 0
        assert push_enabled == 1
        assert announcement_enabled == 1
        assert marketing_enabled == 0
        assert emergency_only == 0
        assert preferred_method == 'email'

class TestIntegration:
    """Integration tests for schema functionality."""

    def test_full_schema_creation_and_usage(self, temp_db):
        """Test creating schema and using tables."""
        conn = sqlite3.connect(temp_db)
        conn.execute("PRAGMA foreign_keys = OFF")
        create_communication_tables(conn)

        cursor = conn.cursor()

        # Insert test data into various tables
        cursor.execute("""
            INSERT INTO email_queue (to_address, subject, body)
            VALUES ('test@example.com', 'Test', 'Test body')
        """)

        cursor.execute("""
            INSERT INTO announcements (title, content, created_by)
            VALUES ('Test Announcement', 'Test content', 1)
        """)

        cursor.execute("""
            INSERT INTO communication_preferences (user_id, email_enabled)
            VALUES (1, 1)
        """)

        conn.commit()

        # Verify data was inserted
        cursor.execute("SELECT COUNT(*) FROM email_queue")
        email_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM announcements")
        announcement_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM communication_preferences")
        prefs_count = cursor.fetchone()[0]

        conn.close()

        assert email_count == 1
        assert announcement_count == 1
        assert prefs_count == 1

class TestMainExecution:
    """Test the __main__ execution block."""

    def test_main_execution(self):
        """Test that schema module can be imported without errors."""
        # Simply verify that importing required modules works

        from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
        from education_system.systems.university.services.communication.schema import create_communication_tables

        # Verify functions exist
        assert DEFAULT_DB_PATH is not None
        assert callable(create_communication_tables)

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
