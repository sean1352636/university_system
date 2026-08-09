"""
Comprehensive test suite for classroom_manager.py

Tests all classes, functions, and functionality including:
- VirtualClassroomManager class
- Classroom creation and management
- Platform validation
- Feature management
- Classroom statistics
- Update and delete operations
"""

import pytest
import os
import json
import tempfile
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime

from education_system.systems.university.domain.academics.services.virtual_classroom.classroom_manager import (
    VirtualClassroomManager
)

@pytest.fixture
def temp_db():
    """Create a temporary test database with required tables."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create required tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS courses (
            course_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS instructors (
            instructor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS virtual_classrooms (
            classroom_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            course_id INTEGER,
            instructor_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            meeting_link TEXT,
            meeting_id TEXT,
            passcode TEXT,
            max_participants INTEGER DEFAULT 100,
            features TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (course_id) REFERENCES courses(course_id),
            FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id)
        );

        CREATE TABLE IF NOT EXISTS virtual_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom_id INTEGER NOT NULL,
            session_type TEXT DEFAULT 'lecture',
            start_time TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'scheduled',
            FOREIGN KEY (classroom_id) REFERENCES virtual_classrooms(classroom_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS session_participants (
            participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            duration INTEGER,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS virtual_recordings (
            recording_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            file_size INTEGER,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
        );
    """)

    # Insert test data
    cursor.execute("INSERT INTO instructors (name) VALUES ('Dr. Smith')")
    cursor.execute("INSERT INTO courses (course_name) VALUES ('CS 101')")

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)

@pytest.fixture
def manager(temp_db):
    """Create a VirtualClassroomManager instance with temp database."""
    return VirtualClassroomManager(db_path=temp_db)

class TestVirtualClassroomManagerInit:
    """Test VirtualClassroomManager initialization."""

    def test_init_default_db_path(self):
        """Test initialization with default database path."""
        manager = VirtualClassroomManager()
        assert manager.db_path is not None

    def test_init_custom_db_path(self, temp_db):
        """Test initialization with custom database path."""
        manager = VirtualClassroomManager(db_path=temp_db)
        assert manager.db_path == temp_db

class TestCreateClassroom:
    """Test virtual classroom creation."""

    def test_create_basic_classroom(self, manager):
        """Test creating a basic virtual classroom."""
        classroom_id = manager.create_classroom(
            session_name="Introduction to Python",
            instructor_id=1,
            platform="zoom"
        )
        assert classroom_id is not None
        assert isinstance(classroom_id, int)

    def test_create_classroom_with_course(self, manager):
        """Test creating classroom linked to a course."""
        classroom_id = manager.create_classroom(
            session_name="CS 101 Lecture",
            instructor_id=1,
            platform="teams",
            course_id=1
        )
        assert classroom_id is not None

        classroom = manager.get_classroom(classroom_id)
        assert classroom['course_id'] == 1

    def test_create_classroom_with_meeting_details(self, manager):
        """Test creating classroom with meeting link and credentials."""
        classroom_id = manager.create_classroom(
            session_name="Database Systems",
            instructor_id=1,
            platform="zoom",
            meeting_link="https://zoom.us/j/123456789",
            meeting_id="123456789",
            passcode="abc123"
        )
        assert classroom_id is not None

        classroom = manager.get_classroom(classroom_id)
        assert classroom['meeting_link'] == "https://zoom.us/j/123456789"
        assert classroom['meeting_id'] == "123456789"
        assert classroom['passcode'] == "abc123"

    def test_create_classroom_with_custom_capacity(self, manager):
        """Test creating classroom with custom max participants."""
        classroom_id = manager.create_classroom(
            session_name="Small Seminar",
            instructor_id=1,
            platform="meet",
            max_participants=25
        )
        assert classroom_id is not None

        classroom = manager.get_classroom(classroom_id)
        assert classroom['max_participants'] == 25

    def test_create_classroom_with_custom_features(self, manager):
        """Test creating classroom with custom features."""
        features = {
            'whiteboard': True,
            'breakout_rooms': False,
            'recording': True,
            'polling': False,
            'chat': True,
            'screen_sharing': True
        }

        classroom_id = manager.create_classroom(
            session_name="Webinar",
            instructor_id=1,
            platform="webrtc",
            features=features
        )
        assert classroom_id is not None

        classroom = manager.get_classroom(classroom_id)
        assert classroom['features'] == features

    def test_create_classroom_default_features(self, manager):
        """Test that default features are set when not provided."""
        classroom_id = manager.create_classroom(
            session_name="Test Classroom",
            instructor_id=1,
            platform="zoom"
        )

        classroom = manager.get_classroom(classroom_id)
        assert classroom['features']['whiteboard'] is True
        assert classroom['features']['breakout_rooms'] is True
        assert classroom['features']['recording'] is True

    def test_create_classroom_invalid_platform(self, manager):
        """Test creating classroom with invalid platform."""
        classroom_id = manager.create_classroom(
            session_name="Test",
            instructor_id=1,
            platform="invalid_platform"
        )
        assert classroom_id is None

    def test_create_classroom_platform_case_insensitive(self, manager):
        """Test that platform validation is case-insensitive."""
        classroom_id = manager.create_classroom(
            session_name="Test",
            instructor_id=1,
            platform="ZOOM"
        )
        assert classroom_id is not None

        classroom = manager.get_classroom(classroom_id)
        assert classroom['platform'] == "zoom"  # Should be lowercased

class TestGetClassroom:
    """Test retrieving classroom details."""

    def test_get_existing_classroom(self, manager):
        """Test getting an existing classroom."""
        classroom_id = manager.create_classroom(
            session_name="Test Classroom",
            instructor_id=1,
            platform="zoom",
            meeting_link="https://zoom.us/j/123"
        )

        classroom = manager.get_classroom(classroom_id)
        assert classroom is not None
        assert classroom['classroom_id'] == classroom_id
        assert classroom['session_name'] == "Test Classroom"
        assert classroom['platform'] == "zoom"
        assert isinstance(classroom['features'], dict)

    def test_get_nonexistent_classroom(self, manager):
        """Test getting a non-existent classroom."""
        classroom = manager.get_classroom(99999)
        assert classroom is None

class TestGetClassroomsByInstructor:
    """Test retrieving classrooms by instructor."""

    def test_get_all_instructor_classrooms(self, manager):
        """Test getting all classrooms for an instructor."""
        manager.create_classroom("Class 1", 1, "zoom")
        manager.create_classroom("Class 2", 1, "teams")
        manager.create_classroom("Class 3", 1, "meet")

        classrooms = manager.get_classrooms_by_instructor(1)
        assert len(classrooms) == 3
        assert all(c['instructor_id'] == 1 for c in classrooms)

    def test_get_active_classrooms_only(self, manager):
        """Test getting only active classrooms."""
        c1 = manager.create_classroom("Class 1", 1, "zoom")
        c2 = manager.create_classroom("Class 2", 1, "teams")
        c3 = manager.create_classroom("Class 3", 1, "meet")

        # Deactivate one classroom
        manager.deactivate_classroom(c2)

        classrooms = manager.get_classrooms_by_instructor(1, active_only=True)
        assert len(classrooms) == 2
        assert all(c['is_active'] == 1 for c in classrooms)

    def test_get_classrooms_ordered_by_date(self, manager):
        """Test that classrooms are ordered by creation date descending."""
        c1 = manager.create_classroom("Class 1", 1, "zoom")
        c2 = manager.create_classroom("Class 2", 1, "teams")
        c3 = manager.create_classroom("Class 3", 1, "meet")

        classrooms = manager.get_classrooms_by_instructor(1)
        # Most recent first
        assert classrooms[0]['classroom_id'] == c3
        assert classrooms[1]['classroom_id'] == c2
        assert classrooms[2]['classroom_id'] == c1

    def test_get_classrooms_for_instructor_with_none(self, manager):
        """Test getting classrooms for instructor with no classrooms."""
        classrooms = manager.get_classrooms_by_instructor(999)
        assert classrooms == []

class TestGetClassroomsByCourse:
    """Test retrieving classrooms by course."""

    def test_get_course_classrooms(self, manager):
        """Test getting all classrooms for a course."""
        manager.create_classroom("Lecture 1", 1, "zoom", course_id=1)
        manager.create_classroom("Lecture 2", 1, "teams", course_id=1)
        manager.create_classroom("Lab Session", 1, "meet", course_id=1)

        classrooms = manager.get_classrooms_by_course(1)
        assert len(classrooms) == 3
        assert all(c['course_id'] == 1 for c in classrooms)

    def test_get_course_classrooms_active_only(self, manager):
        """Test getting only active classrooms for a course."""
        c1 = manager.create_classroom("Class 1", 1, "zoom", course_id=1)
        c2 = manager.create_classroom("Class 2", 1, "teams", course_id=1)

        manager.deactivate_classroom(c1)

        classrooms = manager.get_classrooms_by_course(1)
        assert len(classrooms) == 1
        assert classrooms[0]['is_active'] == 1

    def test_get_classrooms_for_course_with_none(self, manager):
        """Test getting classrooms for course with no classrooms."""
        classrooms = manager.get_classrooms_by_course(999)
        assert classrooms == []

class TestUpdateClassroom:
    """Test updating classroom details."""

    def test_update_session_name(self, manager):
        """Test updating classroom session name."""
        classroom_id = manager.create_classroom("Old Name", 1, "zoom")

        result = manager.update_classroom(classroom_id, session_name="New Name")
        assert result is True

        classroom = manager.get_classroom(classroom_id)
        assert classroom['session_name'] == "New Name"

    def test_update_meeting_details(self, manager):
        """Test updating meeting link and credentials."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")

        result = manager.update_classroom(
            classroom_id,
            meeting_link="https://new-link.com",
            meeting_id="new123",
            passcode="newpass"
        )
        assert result is True

        classroom = manager.get_classroom(classroom_id)
        assert classroom['meeting_link'] == "https://new-link.com"
        assert classroom['meeting_id'] == "new123"
        assert classroom['passcode'] == "newpass"

    def test_update_max_participants(self, manager):
        """Test updating max participants."""
        classroom_id = manager.create_classroom("Test", 1, "zoom", max_participants=100)

        result = manager.update_classroom(classroom_id, max_participants=50)
        assert result is True

        classroom = manager.get_classroom(classroom_id)
        assert classroom['max_participants'] == 50

    def test_update_features(self, manager):
        """Test updating classroom features."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")

        new_features = {
            'whiteboard': False,
            'recording': True,
            'chat': True
        }

        result = manager.update_classroom(classroom_id, features=new_features)
        assert result is True

        classroom = manager.get_classroom(classroom_id)
        assert classroom['features'] == new_features

    def test_update_is_active(self, manager):
        """Test updating is_active status."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")

        result = manager.update_classroom(classroom_id, is_active=0)
        assert result is True

        classroom = manager.get_classroom(classroom_id)
        assert classroom['is_active'] == 0

    def test_update_multiple_fields(self, manager):
        """Test updating multiple fields at once."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")

        result = manager.update_classroom(
            classroom_id,
            session_name="Updated",
            max_participants=75,
            passcode="newpass123"
        )
        assert result is True

        classroom = manager.get_classroom(classroom_id)
        assert classroom['session_name'] == "Updated"
        assert classroom['max_participants'] == 75
        assert classroom['passcode'] == "newpass123"

    def test_update_with_invalid_fields(self, manager):
        """Test updating with non-allowed fields."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")

        # Try to update with a non-allowed field
        result = manager.update_classroom(classroom_id, instructor_id=999)
        assert result is False

    def test_update_nonexistent_classroom(self, manager):
        """Test updating a non-existent classroom."""
        result = manager.update_classroom(99999, session_name="Test")
        assert result is False

class TestDeactivateClassroom:
    """Test deactivating classrooms."""

    def test_deactivate_classroom(self, manager):
        """Test deactivating a classroom."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")

        result = manager.deactivate_classroom(classroom_id)
        assert result is True

        classroom = manager.get_classroom(classroom_id)
        assert classroom['is_active'] == 0

    def test_deactivate_nonexistent_classroom(self, manager):
        """Test deactivating a non-existent classroom."""
        result = manager.deactivate_classroom(99999)
        assert result is False

class TestDeleteClassroom:
    """Test deleting classrooms."""

    def test_delete_classroom(self, manager):
        """Test deleting a classroom."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")

        result = manager.delete_classroom(classroom_id)
        assert result is True

        classroom = manager.get_classroom(classroom_id)
        assert classroom is None

    def test_delete_nonexistent_classroom(self, manager):
        """Test deleting a non-existent classroom."""
        result = manager.delete_classroom(99999)
        assert result is False

    def test_delete_cascades_to_sessions(self, manager, temp_db):
        """Test that deleting classroom deletes associated sessions."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")

        # Create a session
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_sessions (classroom_id, start_time)
            VALUES (?, CURRENT_TIMESTAMP)
        """, (classroom_id,))
        conn.commit()
        conn.close()

        # Delete classroom
        manager.delete_classroom(classroom_id)

        # Check sessions are deleted (cascade)
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM virtual_sessions WHERE classroom_id = ?", (classroom_id,))
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0

class TestListClassrooms:
    """Test listing all classrooms."""

    def test_list_all_classrooms(self, manager):
        """Test listing all classrooms."""
        manager.create_classroom("Class 1", 1, "zoom")
        manager.create_classroom("Class 2", 1, "teams")
        manager.create_classroom("Class 3", 1, "meet")

        classrooms = manager.list_classrooms()
        assert len(classrooms) == 3

    def test_list_active_classrooms_only(self, manager):
        """Test listing only active classrooms."""
        c1 = manager.create_classroom("Class 1", 1, "zoom")
        c2 = manager.create_classroom("Class 2", 1, "teams")
        manager.deactivate_classroom(c1)

        classrooms = manager.list_classrooms(active_only=True)
        assert len(classrooms) == 1
        assert classrooms[0]['is_active'] == 1

    def test_list_classrooms_ordered_by_date(self, manager):
        """Test that classrooms are ordered by creation date descending."""
        c1 = manager.create_classroom("Class 1", 1, "zoom")
        c2 = manager.create_classroom("Class 2", 1, "teams")

        classrooms = manager.list_classrooms()
        assert classrooms[0]['classroom_id'] == c2
        assert classrooms[1]['classroom_id'] == c1

    def test_list_classrooms_empty(self, manager):
        """Test listing when no classrooms exist."""
        classrooms = manager.list_classrooms()
        assert classrooms == []

class TestGetClassroomStats:
    """Test retrieving classroom statistics."""

    def test_get_basic_stats(self, manager, temp_db):
        """Test getting basic classroom statistics."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")

        # Create some sessions
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_sessions (classroom_id, start_time, status)
            VALUES (?, CURRENT_TIMESTAMP, 'scheduled')
        """, (classroom_id,))
        cursor.execute("""
            INSERT INTO virtual_sessions (classroom_id, start_time, status)
            VALUES (?, CURRENT_TIMESTAMP, 'completed')
        """, (classroom_id,))
        conn.commit()
        conn.close()

        stats = manager.get_classroom_stats(classroom_id)
        assert stats is not None
        assert stats['total_sessions'] == 2
        assert stats['completed_sessions'] == 1
        assert stats['scheduled_sessions'] == 1

    def test_get_stats_with_participants(self, manager, temp_db):
        """Test getting stats including participant information."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")

        # Create sessions and participants
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_sessions (classroom_id, start_time)
            VALUES (?, CURRENT_TIMESTAMP)
        """, (classroom_id,))
        session_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO session_participants (session_id, user_id, duration)
            VALUES (?, 101, 3600), (?, 102, 3500)
        """, (session_id, session_id))
        conn.commit()
        conn.close()

        stats = manager.get_classroom_stats(classroom_id)
        assert stats['unique_participants'] == 2
        assert stats['avg_duration'] > 0

    def test_get_stats_with_recordings(self, manager, temp_db):
        """Test getting stats including recording information."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")

        # Create sessions and recordings
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_sessions (classroom_id, start_time)
            VALUES (?, CURRENT_TIMESTAMP)
        """, (classroom_id,))
        session_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO virtual_recordings (session_id, file_size)
            VALUES (?, 1000000)
        """, (session_id,))
        conn.commit()
        conn.close()

        stats = manager.get_classroom_stats(classroom_id)
        assert stats['total_recordings'] == 1
        assert stats['total_storage'] == 1000000

    def test_get_stats_for_nonexistent_classroom(self, manager):
        """Test getting stats for non-existent classroom."""
        stats = manager.get_classroom_stats(99999)
        assert stats is not None
        assert stats['total_sessions'] == 0

class TestRowToDict:
    """Test row to dictionary conversion."""

    def test_row_to_dict_with_features(self, manager):
        """Test converting row with JSON features to dict."""
        classroom_id = manager.create_classroom("Test", 1, "zoom")
        classroom = manager.get_classroom(classroom_id)

        assert isinstance(classroom['features'], dict)
        assert 'whiteboard' in classroom['features']

    def test_row_to_dict_handles_invalid_json(self, manager, temp_db):
        """Test handling invalid JSON in features field."""
        # Manually insert classroom with invalid JSON
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_classrooms (session_name, instructor_id, platform, features)
            VALUES ('Test', 1, 'zoom', 'invalid json')
        """)
        classroom_id = cursor.lastrowid
        conn.commit()
        conn.close()

        classroom = manager.get_classroom(classroom_id)
        # Should default to empty dict on JSON parse error
        assert classroom['features'] == {}

class TestDatabaseConnection:
    """Test database connection handling."""

    def test_get_connection(self, manager):
        """Test getting a database connection."""
        conn = manager._get_connection()
        assert conn is not None

        # Test connection works
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1

        conn.close()

class TestErrorHandling:
    """Test error handling in various scenarios."""

    def test_operations_with_invalid_db_path(self):
        """Test operations with invalid database path."""
        manager = VirtualClassroomManager(db_path="/invalid/path/to/db.db")

        classroom_id = manager.create_classroom("Test", 1, "zoom")
        assert classroom_id is None

        classroom = manager.get_classroom(1)
        assert classroom is None

        classrooms = manager.list_classrooms()
        assert classrooms == []

        stats = manager.get_classroom_stats(1)
        assert stats is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
