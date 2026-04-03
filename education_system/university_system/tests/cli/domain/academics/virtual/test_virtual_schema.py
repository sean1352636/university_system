"""
Comprehensive test suite for schema.py

Tests all classes, functions, and functionality including:
- Virtual classroom schema definition
- Table creation
- Foreign key relationships
- Index creation
- Schema integrity
"""

import pytest
import os
import tempfile
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.academics.services.virtual_classroom.schema import (
    VIRTUAL_CLASSROOM_SCHEMA,
    create_virtual_classroom_tables
)

@pytest.fixture
def temp_db():
    """Create a temporary test database with prerequisite tables."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    # Create stub tables referenced by virtual_classroom FK constraints
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS instructors (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS courses (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO instructors (id) VALUES (1)")
    conn.execute("INSERT INTO courses (id) VALUES (1)")
    conn.commit()
    conn.close()
    yield db_path
    os.unlink(db_path)

class TestSchemaDefinition:
    """Test schema SQL definition."""

    def test_schema_is_string(self):
        """Test that schema is a string."""
        assert isinstance(VIRTUAL_CLASSROOM_SCHEMA, str)

    def test_schema_contains_all_tables(self):
        """Test that schema includes all required tables."""
        required_tables = [
            'virtual_classrooms',
            'virtual_sessions',
            'session_participants',
            'virtual_recordings',
            'breakout_rooms',
            'virtual_polls',
            'poll_responses',
            'virtual_chat_messages'
        ]

        for table in required_tables:
            assert table in VIRTUAL_CLASSROOM_SCHEMA

    def test_schema_contains_indexes(self):
        """Test that schema includes performance indexes."""
        assert 'CREATE INDEX' in VIRTUAL_CLASSROOM_SCHEMA

class TestCreateVirtualClassroomTables:
    """Test table creation function."""

    def test_create_tables_success(self, temp_db):
        """Test successful table creation."""
        conn = sqlite3.connect(temp_db)

        # Should not raise an exception
        create_virtual_classroom_tables(conn)

        # Verify tables exist
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert 'virtual_classrooms' in tables
        assert 'virtual_sessions' in tables
        assert 'session_participants' in tables

    def test_all_tables_created(self, temp_db):
        """Test that all tables are created."""
        conn = sqlite3.connect(temp_db)
        create_virtual_classroom_tables(conn)

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_tables = [
            'virtual_classrooms',
            'virtual_sessions',
            'session_participants',
            'virtual_recordings',
            'breakout_rooms',
            'virtual_polls',
            'poll_responses',
            'virtual_chat_messages'
        ]

        for table in expected_tables:
            assert table in tables

    def test_indexes_created(self, temp_db):
        """Test that indexes are created."""
        conn = sqlite3.connect(temp_db)
        create_virtual_classroom_tables(conn)

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert 'idx_virtual_sessions_classroom' in indexes
        assert 'idx_session_participants_session' in indexes

    def test_idempotent_creation(self, temp_db):
        """Test that creating tables twice doesn't error (IF NOT EXISTS)."""
        conn = sqlite3.connect(temp_db)

        # Create once
        create_virtual_classroom_tables(conn)

        # Create again - should not raise error
        create_virtual_classroom_tables(conn)

        conn.close()

class TestTableStructure:
    """Test individual table structures."""

    def test_virtual_classrooms_structure(self, temp_db):
        """Test virtual_classrooms table structure."""
        conn = sqlite3.connect(temp_db)
        create_virtual_classroom_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(virtual_classrooms)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert 'classroom_id' in columns
        assert 'session_name' in columns
        assert 'instructor_id' in columns
        assert 'platform' in columns
        assert 'max_participants' in columns

    def test_virtual_sessions_structure(self, temp_db):
        """Test virtual_sessions table structure."""
        conn = sqlite3.connect(temp_db)
        create_virtual_classroom_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(virtual_sessions)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert 'session_id' in columns
        assert 'classroom_id' in columns
        assert 'start_time' in columns
        assert 'status' in columns

    def test_session_participants_structure(self, temp_db):
        """Test session_participants table structure."""
        conn = sqlite3.connect(temp_db)
        create_virtual_classroom_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(session_participants)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert 'participant_id' in columns
        assert 'session_id' in columns
        assert 'user_id' in columns
        assert 'attendance_status' in columns

    def test_virtual_polls_structure(self, temp_db):
        """Test virtual_polls table structure."""
        conn = sqlite3.connect(temp_db)
        create_virtual_classroom_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(virtual_polls)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert 'poll_id' in columns
        assert 'session_id' in columns
        assert 'question' in columns
        assert 'poll_type' in columns

class TestForeignKeys:
    """Test foreign key relationships."""

    def test_foreign_key_enforcement(self, temp_db):
        """Test that foreign key constraints are enforced."""
        conn = sqlite3.connect(temp_db)
        conn.execute("PRAGMA foreign_keys = ON")
        create_virtual_classroom_tables(conn)

        cursor = conn.cursor()

        # This should fail due to foreign key constraint
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO virtual_sessions (classroom_id, start_time)
                VALUES (99999, CURRENT_TIMESTAMP)
            """)

        conn.close()

class TestDefaultValues:
    """Test default column values."""

    def test_virtual_classroom_defaults(self, temp_db):
        """Test default values for virtual_classrooms."""
        conn = sqlite3.connect(temp_db)
        create_virtual_classroom_tables(conn)

        cursor = conn.cursor()
        # Insert minimal record
        cursor.execute("""
            INSERT INTO virtual_classrooms (session_name, instructor_id, platform)
            VALUES ('Test', 1, 'zoom')
        """)

        cursor.execute("SELECT is_active, max_participants FROM virtual_classrooms")
        row = cursor.fetchone()
        conn.close()

        assert row[0] == 1  # is_active defaults to 1
        assert row[1] == 100  # max_participants defaults to 100

    def test_session_defaults(self, temp_db):
        """Test default values for virtual_sessions."""
        conn = sqlite3.connect(temp_db)
        create_virtual_classroom_tables(conn)

        cursor = conn.cursor()
        # Create classroom first
        cursor.execute("""
            INSERT INTO virtual_classrooms (session_name, instructor_id, platform)
            VALUES ('Test', 1, 'zoom')
        """)

        cursor.execute("""
            INSERT INTO virtual_sessions (classroom_id, start_time)
            VALUES (1, CURRENT_TIMESTAMP)
        """)

        cursor.execute("SELECT status, session_type FROM virtual_sessions")
        row = cursor.fetchone()
        conn.close()

        assert row[0] == 'scheduled'
        assert row[1] == 'lecture'

class TestCascadeDeletes:
    """Test cascade delete behavior."""

    def test_session_cascade_delete(self, temp_db):
        """Test that deleting classroom deletes sessions."""
        conn = sqlite3.connect(temp_db)
        conn.execute("PRAGMA foreign_keys = ON")
        create_virtual_classroom_tables(conn)

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_classrooms (session_name, instructor_id, platform)
            VALUES ('Test', 1, 'zoom')
        """)
        classroom_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO virtual_sessions (classroom_id, start_time)
            VALUES (?, CURRENT_TIMESTAMP)
        """, (classroom_id,))

        # Delete classroom
        cursor.execute("DELETE FROM virtual_classrooms WHERE classroom_id = ?", (classroom_id,))

        # Check sessions are deleted
        cursor.execute("SELECT COUNT(*) FROM virtual_sessions WHERE classroom_id = ?", (classroom_id,))
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
