#!/usr/bin/env python3
"""
Tests for security database table initialization

Tests:
- Table creation
- Index creation
- Schema correctness
- Idempotency (running multiple times)
- Error handling
"""

import pytest
import sqlite3
import tempfile
import os

from university_system.infrastructure.security.init_security_tables import init_security_tables


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    yield path

    # Cleanup
    if os.path.exists(path):
        os.remove(path)


# ============================================================================
# Table Creation Tests
# ============================================================================

class TestTableCreation:
    """Test creation of all security tables"""

    def test_init_security_tables_success(self, test_db):
        """Test successful table initialization"""
        result = init_security_tables(test_db)

        assert result is True

    def test_sessions_table_created(self, test_db):
        """Test sessions table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='sessions'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_security_events_table_created(self, test_db):
        """Test security_events table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='security_events'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_encrypted_fields_metadata_table_created(self, test_db):
        """Test encrypted_fields_metadata table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='encrypted_fields_metadata'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_api_keys_table_created(self, test_db):
        """Test api_keys table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='api_keys'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_api_rate_limits_table_created(self, test_db):
        """Test api_rate_limits table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='api_rate_limits'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_security_incidents_table_created(self, test_db):
        """Test security_incidents table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='security_incidents'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_incident_response_actions_table_created(self, test_db):
        """Test incident_response_actions table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='incident_response_actions'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_bulk_export_log_table_created(self, test_db):
        """Test bulk_export_log table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='bulk_export_log'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_vulnerability_scan_results_table_created(self, test_db):
        """Test vulnerability_scan_results table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='vulnerability_scan_results'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_encryption_keys_table_created(self, test_db):
        """Test encryption_keys table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='encryption_keys'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_password_history_table_created(self, test_db):
        """Test password_history table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='password_history'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_password_policy_compliance_table_created(self, test_db):
        """Test password_policy_compliance table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='password_policy_compliance'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_data_access_log_table_created(self, test_db):
        """Test data_access_log table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='data_access_log'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_permission_changes_log_table_created(self, test_db):
        """Test permission_changes_log table is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='permission_changes_log'
        """)
        table = cursor.fetchone()
        conn.close()

        assert table is not None

    def test_all_14_tables_created(self, test_db):
        """Test all 14 security tables are created"""
        init_security_tables(test_db)

        expected_tables = {
            'sessions',
            'security_events',
            'encrypted_fields_metadata',
            'api_keys',
            'api_rate_limits',
            'security_incidents',
            'incident_response_actions',
            'bulk_export_log',
            'vulnerability_scan_results',
            'encryption_keys',
            'password_history',
            'password_policy_compliance',
            'data_access_log',
            'permission_changes_log'
        }

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
        """)
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert expected_tables.issubset(tables)


# ============================================================================
# Schema Tests
# ============================================================================

class TestTableSchemas:
    """Test table schemas are correct"""

    def test_sessions_table_schema(self, test_db):
        """Test sessions table has correct columns"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(sessions)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        required_columns = {
            'id', 'user_id', 'session_token', 'ip_address',
            'created_at', 'last_activity', 'expires_at', 'is_active'
        }

        assert required_columns.issubset(columns)

    def test_api_keys_table_schema(self, test_db):
        """Test api_keys table has correct columns"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(api_keys)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        required_columns = {
            'id', 'user_id', 'key_hash', 'key_name',
            'permissions', 'created_at', 'expires_at', 'rate_limit'
        }

        assert required_columns.issubset(columns)

    def test_encryption_keys_table_schema(self, test_db):
        """Test encryption_keys table has correct columns"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(encryption_keys)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        required_columns = {
            'id', 'key_id', 'key_type', 'encrypted_key',
            'created_at', 'is_active', 'version'
        }

        assert required_columns.issubset(columns)


# ============================================================================
# Index Tests
# ============================================================================

class TestIndexCreation:
    """Test indexes are created"""

    def test_sessions_user_id_index_created(self, test_db):
        """Test index on sessions(user_id) is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_sessions_user_id'
        """)
        index = cursor.fetchone()
        conn.close()

        assert index is not None

    def test_sessions_active_index_created(self, test_db):
        """Test index on sessions(is_active, last_activity) is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_sessions_active'
        """)
        index = cursor.fetchone()
        conn.close()

        assert index is not None

    def test_security_events_time_index_created(self, test_db):
        """Test index on security_events(event_time) is created"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name='idx_security_events_time'
        """)
        index = cursor.fetchone()
        conn.close()

        assert index is not None


# ============================================================================
# Idempotency Tests
# ============================================================================

class TestIdempotency:
    """Test running init multiple times is safe"""

    def test_running_init_twice(self, test_db):
        """Test running init_security_tables twice doesn't fail"""
        result1 = init_security_tables(test_db)
        result2 = init_security_tables(test_db)

        assert result1 is True
        assert result2 is True

    def test_data_preserved_after_reinit(self, test_db):
        """Test existing data is preserved when re-initializing"""
        init_security_tables(test_db)

        # Insert test data
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO security_events (user_id, event_type, severity, details)
            VALUES (1, 'test_event', 'low', '{}')
        """)
        conn.commit()
        conn.close()

        # Re-initialize
        init_security_tables(test_db)

        # Verify data still exists
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM security_events WHERE event_type = 'test_event'")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1


# ============================================================================
# Constraint Tests
# ============================================================================

class TestConstraints:
    """Test table constraints"""

    def test_api_keys_unique_key_hash(self, test_db):
        """Test api_keys has UNIQUE constraint on key_hash"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Insert first key
        cursor.execute("""
            INSERT INTO api_keys (user_id, key_hash, key_name, permissions)
            VALUES (1, 'hash123', 'Key 1', '[]')
        """)
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO api_keys (user_id, key_hash, key_name, permissions)
                VALUES (2, 'hash123', 'Key 2', '[]')
            """)
            conn.commit()

        conn.close()

    def test_encryption_keys_unique_key_id(self, test_db):
        """Test encryption_keys has UNIQUE constraint on key_id"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Insert first key
        cursor.execute("""
            INSERT INTO encryption_keys (key_id, key_type, encrypted_key)
            VALUES ('key_123', 'data', 'encrypted')
        """)
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO encryption_keys (key_id, key_type, encrypted_key)
                VALUES ('key_123', 'file', 'encrypted2')
            """)
            conn.commit()

        conn.close()

    def test_encrypted_fields_unique_table_column(self, test_db):
        """Test encrypted_fields_metadata has UNIQUE on (table_name, column_name)"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Insert first entry
        cursor.execute("""
            INSERT INTO encrypted_fields_metadata (table_name, column_name, key_id)
            VALUES ('users', 'ssn', 'key_1')
        """)
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO encrypted_fields_metadata (table_name, column_name, key_id)
                VALUES ('users', 'ssn', 'key_2')
            """)
            conn.commit()

        conn.close()


# ============================================================================
# Default Values Tests
# ============================================================================

class TestDefaultValues:
    """Test default values are set correctly"""

    def test_sessions_default_timestamps(self, test_db):
        """Test sessions table sets default timestamps"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sessions (user_id, session_token, ip_address)
            VALUES (1, 'token123', '127.0.0.1')
        """)
        conn.commit()

        cursor.execute("SELECT created_at, last_activity FROM sessions WHERE user_id = 1")
        created_at, last_activity = cursor.fetchone()
        conn.close()

        assert created_at is not None
        assert last_activity is not None

    def test_security_events_default_timestamp(self, test_db):
        """Test security_events sets default event_time"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO security_events (user_id, event_type, severity, details)
            VALUES (1, 'test', 'low', '{}')
        """)
        conn.commit()

        cursor.execute("SELECT event_time FROM security_events WHERE user_id = 1")
        event_time = cursor.fetchone()[0]
        conn.close()

        assert event_time is not None

    def test_api_keys_default_is_active(self, test_db):
        """Test api_keys defaults is_active to 1"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO api_keys (user_id, key_hash, key_name, permissions)
            VALUES (1, 'hash', 'Key', '[]')
        """)
        conn.commit()

        cursor.execute("SELECT is_active FROM api_keys WHERE user_id = 1")
        is_active = cursor.fetchone()[0]
        conn.close()

        assert is_active == 1


# ============================================================================
# Integration Tests
# ============================================================================

class TestTableIntegration:
    """Test tables work together"""

    def test_insert_complete_security_workflow(self, test_db):
        """Test inserting data across multiple security tables"""
        init_security_tables(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Create session
        cursor.execute("""
            INSERT INTO sessions (user_id, session_token, ip_address)
            VALUES (1, 'token123', '192.168.1.1')
        """)
        session_id = cursor.lastrowid

        # Log security event
        cursor.execute("""
            INSERT INTO security_events (user_id, event_type, severity, details)
            VALUES (1, 'login', 'low', '{}')
        """)

        # Create API key
        cursor.execute("""
            INSERT INTO api_keys (user_id, key_hash, key_name, permissions)
            VALUES (1, 'hash123', 'API Key', '["read"]')
        """)

        # Log data access
        cursor.execute("""
            INSERT INTO data_access_log (user_id, resource_type, resource_id, action, session_id)
            VALUES (1, 'student', 100, 'view', ?)
        """, (session_id,))

        conn.commit()

        # Verify all inserts worked
        cursor.execute("SELECT COUNT(*) FROM sessions")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM security_events")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM api_keys")
        assert cursor.fetchone()[0] == 1

        cursor.execute("SELECT COUNT(*) FROM data_access_log")
        assert cursor.fetchone()[0] == 1

        conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
