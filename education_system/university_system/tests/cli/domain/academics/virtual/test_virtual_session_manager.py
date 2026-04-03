"""
Comprehensive test suite for session_manager.py

Tests all classes, functions, and functionality including:
- SessionManager class
- Session creation and scheduling
- Session lifecycle (start, end, cancel)
- Session queries and filtering
- Session statistics
- Session updates
"""

import pytest
import os
import tempfile
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

from education_system.university_system.modules.domain.academics.services.virtual_classroom.session_manager import (
    SessionManager
)

@pytest.fixture
def temp_db():
    """Create a temporary test database with required tables."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS virtual_classrooms (
            classroom_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            platform TEXT NOT NULL,
            meeting_link TEXT,
            instructor_id INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS virtual_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom_id INTEGER NOT NULL,
            session_type TEXT DEFAULT 'lecture',
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            actual_start_time TIMESTAMP,
            actual_end_time TIMESTAMP,
            recording_url TEXT,
            recording_size INTEGER,
            recording_duration INTEGER,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (classroom_id) REFERENCES virtual_classrooms(classroom_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS session_participants (
            participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            duration INTEGER,
            chat_message_count INTEGER DEFAULT 0,
            raised_hand_count INTEGER DEFAULT 0,
            attendance_status TEXT DEFAULT 'absent',
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS virtual_polls (
            poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            created_by INTEGER,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS breakout_rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            room_name TEXT NOT NULL,
            room_number INTEGER,
            participants TEXT,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        INSERT INTO virtual_classrooms (session_name, platform, meeting_link, instructor_id)
        VALUES ('Test Classroom', 'zoom', 'https://zoom.us/j/123', 999)
    """)
    conn.commit()
    conn.close()

    yield db_path
    os.unlink(db_path)

@pytest.fixture
def manager(temp_db):
    """Create a SessionManager instance with temp database."""
    return SessionManager(db_path=temp_db)

class TestSessionManagerInit:
    """Test SessionManager initialization."""

    def test_init_default_db_path(self):
        manager = SessionManager()
        assert manager.db_path is not None

    def test_init_custom_db_path(self, temp_db):
        manager = SessionManager(db_path=temp_db)
        assert manager.db_path == temp_db

class TestCreateSession:
    """Test session creation."""

    def test_create_basic_session(self, manager):
        start_time = datetime.now() + timedelta(hours=1)
        session_id = manager.create_session(
            classroom_id=1,
            start_time=start_time
        )
        assert session_id is not None

    def test_create_session_with_type(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(
            classroom_id=1,
            start_time=start_time,
            session_type='lab'
        )
        assert session_id is not None

        session = manager.get_session(session_id)
        assert session['session_type'] == 'lab'

    def test_create_session_with_duration(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(
            classroom_id=1,
            start_time=start_time,
            duration_minutes=90
        )

        session = manager.get_session(session_id)
        # Verify end_time is calculated
        assert session['end_time'] is not None

    def test_create_session_with_notes(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(
            classroom_id=1,
            start_time=start_time,
            notes="This is a review session"
        )

        session = manager.get_session(session_id)
        assert session['notes'] == "This is a review session"

    def test_create_session_invalid_type(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(
            classroom_id=1,
            start_time=start_time,
            session_type='invalid_type'
        )
        assert session_id is None

    def test_create_session_default_status(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(
            classroom_id=1,
            start_time=start_time
        )

        session = manager.get_session(session_id)
        assert session['status'] == 'scheduled'

class TestStartSession:
    """Test starting sessions."""

    def test_start_session(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time)

        result = manager.start_session(session_id)
        assert result is True

        session = manager.get_session(session_id)
        assert session['status'] == 'in_progress'
        assert session['actual_start_time'] is not None

    def test_start_nonexistent_session(self, manager):
        result = manager.start_session(99999)
        assert result is False

    def test_start_already_started_session(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time)

        manager.start_session(session_id)
        result = manager.start_session(session_id)
        assert result is False  # Already started

class TestEndSession:
    """Test ending sessions."""

    def test_end_session(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time)
        manager.start_session(session_id)

        result = manager.end_session(session_id)
        assert result is True

        session = manager.get_session(session_id)
        assert session['status'] == 'completed'
        assert session['actual_end_time'] is not None

    def test_end_session_with_recording(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time)
        manager.start_session(session_id)

        result = manager.end_session(
            session_id,
            recording_url="https://example.com/recording.mp4",
            recording_size=1024000,
            recording_duration=3600
        )
        assert result is True

        session = manager.get_session(session_id)
        assert session['recording_url'] == "https://example.com/recording.mp4"
        assert session['recording_size'] == 1024000

    def test_end_nonexistent_session(self, manager):
        result = manager.end_session(99999)
        assert result is False

    def test_end_non_started_session(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time)

        result = manager.end_session(session_id)
        assert result is False  # Not started

class TestCancelSession:
    """Test cancelling sessions."""

    def test_cancel_session(self, manager):
        start_time = datetime.now() + timedelta(hours=1)
        session_id = manager.create_session(1, start_time)

        result = manager.cancel_session(session_id)
        assert result is True

        session = manager.get_session(session_id)
        assert session['status'] == 'cancelled'

    def test_cancel_nonexistent_session(self, manager):
        result = manager.cancel_session(99999)
        assert result is False

    def test_cancel_already_started_session(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time)
        manager.start_session(session_id)

        result = manager.cancel_session(session_id)
        assert result is False  # Can't cancel in-progress session

class TestGetSession:
    """Test retrieving session details."""

    def test_get_existing_session(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time, session_type='office_hours')

        session = manager.get_session(session_id)
        assert session is not None
        assert session['session_id'] == session_id
        assert session['session_type'] == 'office_hours'
        assert 'session_name' in session  # Joined from classroom
        assert 'platform' in session

    def test_get_nonexistent_session(self, manager):
        session = manager.get_session(99999)
        assert session is None

class TestGetSessionsByClassroom:
    """Test retrieving sessions for a classroom."""

    def test_get_all_classroom_sessions(self, manager):
        start_time = datetime.now()
        manager.create_session(1, start_time)
        manager.create_session(1, start_time + timedelta(days=1))
        manager.create_session(1, start_time + timedelta(days=2))

        sessions = manager.get_sessions_by_classroom(1)
        assert len(sessions) == 3

    def test_get_sessions_by_status(self, manager):
        start_time = datetime.now()
        s1 = manager.create_session(1, start_time)
        s2 = manager.create_session(1, start_time + timedelta(days=1))

        manager.start_session(s1)

        in_progress = manager.get_sessions_by_classroom(1, status='in_progress')
        assert len(in_progress) == 1

        scheduled = manager.get_sessions_by_classroom(1, status='scheduled')
        assert len(scheduled) == 1

    def test_get_sessions_with_limit(self, manager):
        start_time = datetime.now()
        for i in range(10):
            manager.create_session(1, start_time + timedelta(hours=i))

        sessions = manager.get_sessions_by_classroom(1, limit=5)
        assert len(sessions) == 5

    def test_sessions_ordered_by_date_desc(self, manager):
        start_time = datetime.now()
        s1 = manager.create_session(1, start_time)
        s2 = manager.create_session(1, start_time + timedelta(days=1))
        s3 = manager.create_session(1, start_time + timedelta(days=2))

        sessions = manager.get_sessions_by_classroom(1)
        assert sessions[0]['session_id'] == s3  # Most recent first

class TestGetUpcomingSessions:
    """Test retrieving upcoming sessions."""

    def test_get_upcoming_sessions(self, manager):
        now = datetime.now()
        # Create past, present, and future sessions
        manager.create_session(1, now - timedelta(days=1))  # Past
        manager.create_session(1, now + timedelta(hours=1))  # Future
        manager.create_session(1, now + timedelta(days=2))  # Future

        upcoming = manager.get_upcoming_sessions(days_ahead=7)
        assert len(upcoming) == 2  # Only future scheduled sessions

    def test_get_upcoming_sessions_for_classroom(self, manager, temp_db):
        now = datetime.now()

        # Create another classroom
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_classrooms (session_name, platform, instructor_id)
            VALUES ('Class 2', 'teams', 999)
        """)
        classroom2_id = cursor.lastrowid
        conn.commit()
        conn.close()

        manager.create_session(1, now + timedelta(hours=1))
        manager.create_session(classroom2_id, now + timedelta(hours=2))

        upcoming = manager.get_upcoming_sessions(classroom_id=1)
        assert len(upcoming) == 1

    def test_upcoming_sessions_ordered_by_time(self, manager):
        now = datetime.now()
        s1 = manager.create_session(1, now + timedelta(days=3))
        s2 = manager.create_session(1, now + timedelta(hours=1))
        s3 = manager.create_session(1, now + timedelta(days=1))

        upcoming = manager.get_upcoming_sessions()
        # Should be ordered ascending (nearest first)
        assert upcoming[0]['session_id'] == s2
        assert upcoming[1]['session_id'] == s3
        assert upcoming[2]['session_id'] == s1

class TestGetActiveSessions:
    """Test retrieving active sessions."""

    def test_get_active_sessions(self, manager):
        now = datetime.now()
        s1 = manager.create_session(1, now)
        s2 = manager.create_session(1, now + timedelta(hours=1))

        manager.start_session(s1)

        active = manager.get_active_sessions()
        assert len(active) == 1
        assert active[0]['session_id'] == s1

    def test_get_active_sessions_multiple(self, manager):
        now = datetime.now()
        s1 = manager.create_session(1, now)
        s2 = manager.create_session(1, now)

        manager.start_session(s1)
        manager.start_session(s2)

        active = manager.get_active_sessions()
        assert len(active) == 2

class TestUpdateSession:
    """Test updating session details."""

    def test_update_session_type(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time, session_type='lecture')

        result = manager.update_session(session_id, session_type='lab')
        assert result is True

        session = manager.get_session(session_id)
        assert session['session_type'] == 'lab'

    def test_update_session_notes(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time)

        result = manager.update_session(session_id, notes="Updated notes")
        assert result is True

        session = manager.get_session(session_id)
        assert session['notes'] == "Updated notes"

    def test_update_multiple_fields(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time)

        result = manager.update_session(
            session_id,
            session_type='review',
            notes="Review session for midterm",
            status='scheduled'
        )
        assert result is True

    def test_update_nonexistent_session(self, manager):
        result = manager.update_session(99999, notes="Test")
        assert result is False

    def test_update_with_invalid_fields(self, manager):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time)

        result = manager.update_session(session_id, invalid_field="value")
        assert result is False

class TestListSessions:
    """Test listing sessions with filters."""

    def test_list_all_sessions(self, manager):
        start_time = datetime.now()
        manager.create_session(1, start_time)
        manager.create_session(1, start_time + timedelta(days=1))

        sessions = manager.list_sessions()
        assert len(sessions) == 2

    def test_list_sessions_by_classroom(self, manager, temp_db):
        start_time = datetime.now()

        # Create another classroom
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_classrooms (session_name, platform, instructor_id)
            VALUES ('Class 2', 'teams', 999)
        """)
        classroom2_id = cursor.lastrowid
        conn.commit()
        conn.close()

        manager.create_session(1, start_time)
        manager.create_session(classroom2_id, start_time)

        sessions = manager.list_sessions(classroom_id=1)
        assert len(sessions) == 1

    def test_list_sessions_by_status(self, manager):
        start_time = datetime.now()
        s1 = manager.create_session(1, start_time)
        s2 = manager.create_session(1, start_time + timedelta(hours=1))

        manager.start_session(s1)

        scheduled = manager.list_sessions(status='scheduled')
        assert len(scheduled) == 1

class TestGetSessionStatistics:
    """Test retrieving session statistics."""

    def test_get_basic_statistics(self, manager, temp_db):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time)

        # Add participants
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO session_participants (session_id, user_id, duration, attendance_status, chat_message_count, raised_hand_count)
            VALUES (?, 101, 3600, 'present', 5, 2), (?, 102, 3500, 'present', 3, 1)
        """, (session_id, session_id))
        conn.commit()
        conn.close()

        stats = manager.get_session_statistics(session_id)
        assert stats['total_participants'] == 2
        assert stats['attended'] == 2
        assert stats['avg_duration'] > 0

    def test_statistics_include_polls_and_breakouts(self, manager, temp_db):
        start_time = datetime.now()
        session_id = manager.create_session(1, start_time)

        # Add polls and breakout rooms
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO virtual_polls (session_id, question, created_by) VALUES (?, 'Q1?', 999)", (session_id,))
        cursor.execute("INSERT INTO breakout_rooms (session_id, room_name, room_number, participants) VALUES (?, 'Room1', 1, '[]')", (session_id,))
        conn.commit()
        conn.close()

        stats = manager.get_session_statistics(session_id)
        assert stats['total_polls'] == 1
        assert stats['total_breakout_rooms'] == 1

    def test_statistics_for_nonexistent_session(self, manager):
        stats = manager.get_session_statistics(99999)
        assert stats is not None  # Should return empty stats

class TestDatabaseConnection:
    """Test database connection handling."""

    def test_get_connection(self, manager):
        conn = manager._get_connection()
        assert conn is not None

        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1

        conn.close()

class TestErrorHandling:
    """Test error handling."""

    def test_operations_with_invalid_db_path(self):
        manager = SessionManager(db_path="/invalid/path.db")

        session_id = manager.create_session(1, datetime.now())
        assert session_id is None

        sessions = manager.list_sessions()
        assert sessions == []

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
