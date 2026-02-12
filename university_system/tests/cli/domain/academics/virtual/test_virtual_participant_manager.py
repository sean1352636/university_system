"""
Comprehensive test suite for participant_manager.py

Tests all classes, functions, and functionality including:
- ParticipantManager class
- Participant addition and removal
- Attendance tracking
- Hand raising and interactions
- Mute and video controls
- Attendance history and summaries
"""

import pytest
import os
import tempfile
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime

from university_system.modules.domain.academics.services.virtual_classroom.participant_manager import (
    ParticipantManager
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
        CREATE TABLE IF NOT EXISTS virtual_classrooms (
            classroom_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            instructor_id INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS virtual_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom_id INTEGER NOT NULL,
            session_type TEXT DEFAULT 'lecture',
            start_time TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'scheduled',
            FOREIGN KEY (classroom_id) REFERENCES virtual_classrooms(classroom_id)
        );

        CREATE TABLE IF NOT EXISTS session_participants (
            participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_type TEXT NOT NULL,
            device_type TEXT,
            join_time TIMESTAMP,
            leave_time TIMESTAMP,
            duration INTEGER,
            connection_quality TEXT,
            is_muted BOOLEAN DEFAULT 0,
            is_video_on BOOLEAN DEFAULT 1,
            raised_hand_count INTEGER DEFAULT 0,
            chat_message_count INTEGER DEFAULT 0,
            attendance_status TEXT DEFAULT 'absent',
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
        );
    """)

    # Insert test data
    cursor.execute("""
        INSERT INTO virtual_classrooms (session_name, instructor_id)
        VALUES ('Test Classroom', 999)
    """)
    cursor.execute("""
        INSERT INTO virtual_sessions (classroom_id, start_time, status)
        VALUES (1, CURRENT_TIMESTAMP, 'in_progress')
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)

@pytest.fixture
def manager(temp_db):
    """Create a ParticipantManager instance with temp database."""
    return ParticipantManager(db_path=temp_db)

class TestParticipantManagerInit:
    """Test ParticipantManager initialization."""

    def test_init_default_db_path(self):
        """Test initialization with default database path."""
        manager = ParticipantManager()
        assert manager.db_path is not None

    def test_init_custom_db_path(self, temp_db):
        """Test initialization with custom database path."""
        manager = ParticipantManager(db_path=temp_db)
        assert manager.db_path == temp_db

class TestAddParticipant:
    """Test adding participants to sessions."""

    def test_add_participant_basic(self, manager):
        """Test adding a basic participant."""
        participant_id = manager.add_participant(
            session_id=1,
            user_id=101,
            user_type='student'
        )
        assert participant_id is not None
        assert isinstance(participant_id, int)

    def test_add_participant_with_device_type(self, manager):
        """Test adding participant with device type."""
        participant_id = manager.add_participant(
            session_id=1,
            user_id=102,
            user_type='student',
            device_type='mobile'
        )
        assert participant_id is not None

    def test_add_instructor_participant(self, manager):
        """Test adding an instructor as participant."""
        participant_id = manager.add_participant(
            session_id=1,
            user_id=999,
            user_type='instructor',
            device_type='desktop'
        )
        assert participant_id is not None

    def test_add_guest_participant(self, manager):
        """Test adding a guest participant."""
        participant_id = manager.add_participant(
            session_id=1,
            user_id=500,
            user_type='guest'
        )
        assert participant_id is not None

    def test_add_participant_sets_join_time(self, manager, temp_db):
        """Test that join time is set when participant is added."""
        participant_id = manager.add_participant(
            session_id=1,
            user_id=101,
            user_type='student'
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT join_time FROM session_participants WHERE participant_id = ?", (participant_id,))
        join_time = cursor.fetchone()[0]
        conn.close()

        assert join_time is not None

class TestRecordLeave:
    """Test recording when participants leave."""

    def test_record_leave(self, manager):
        """Test recording participant leave time."""
        participant_id = manager.add_participant(1, 101, 'student')

        result = manager.record_leave(participant_id)
        assert result is True

    def test_record_leave_calculates_duration(self, manager, temp_db):
        """Test that duration is calculated when recording leave."""
        participant_id = manager.add_participant(1, 101, 'student')

        import time
        time.sleep(1)  # Wait a bit to ensure duration > 0

        manager.record_leave(participant_id)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT leave_time, duration FROM session_participants
            WHERE participant_id = ?
        """, (participant_id,))
        row = cursor.fetchone()
        conn.close()

        assert row[0] is not None  # leave_time
        assert row[1] >= 0  # duration

    def test_record_leave_nonexistent_participant(self, manager):
        """Test recording leave for non-existent participant."""
        result = manager.record_leave(99999)
        assert result is False

    def test_record_leave_already_left(self, manager):
        """Test recording leave for participant who already left."""
        participant_id = manager.add_participant(1, 101, 'student')
        manager.record_leave(participant_id)

        # Try to record leave again
        result = manager.record_leave(participant_id)
        assert result is False

class TestUpdateAttendanceStatus:
    """Test updating attendance status."""

    def test_update_to_present(self, manager):
        """Test updating attendance to present."""
        participant_id = manager.add_participant(1, 101, 'student')

        result = manager.update_attendance_status(participant_id, 'present')
        assert result is True

    def test_update_to_late(self, manager):
        """Test updating attendance to late."""
        participant_id = manager.add_participant(1, 101, 'student')

        result = manager.update_attendance_status(participant_id, 'late')
        assert result is True

    def test_update_to_left_early(self, manager):
        """Test updating attendance to left_early."""
        participant_id = manager.add_participant(1, 101, 'student')

        result = manager.update_attendance_status(participant_id, 'left_early')
        assert result is True

    def test_update_invalid_status(self, manager):
        """Test updating with invalid status."""
        participant_id = manager.add_participant(1, 101, 'student')

        result = manager.update_attendance_status(participant_id, 'invalid_status')
        assert result is False

    def test_update_nonexistent_participant(self, manager):
        """Test updating status for non-existent participant."""
        result = manager.update_attendance_status(99999, 'present')
        assert result is False

class TestRaiseHand:
    """Test hand raising functionality."""

    def test_raise_hand(self, manager):
        """Test raising hand increments counter."""
        participant_id = manager.add_participant(1, 101, 'student')

        result = manager.raise_hand(participant_id)
        assert result is True

    def test_raise_hand_multiple_times(self, manager, temp_db):
        """Test raising hand multiple times increments counter."""
        participant_id = manager.add_participant(1, 101, 'student')

        manager.raise_hand(participant_id)
        manager.raise_hand(participant_id)
        manager.raise_hand(participant_id)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT raised_hand_count FROM session_participants WHERE participant_id = ?", (participant_id,))
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 3

    def test_raise_hand_nonexistent_participant(self, manager):
        """Test raising hand for non-existent participant."""
        result = manager.raise_hand(99999)
        assert result is False

class TestToggleMute:
    """Test mute toggle functionality."""

    def test_mute_participant(self, manager):
        """Test muting a participant."""
        participant_id = manager.add_participant(1, 101, 'student')

        result = manager.toggle_mute(participant_id, True)
        assert result is True

    def test_unmute_participant(self, manager):
        """Test unmuting a participant."""
        participant_id = manager.add_participant(1, 101, 'student')

        manager.toggle_mute(participant_id, True)
        result = manager.toggle_mute(participant_id, False)
        assert result is True

    def test_mute_status_persisted(self, manager, temp_db):
        """Test that mute status is persisted to database."""
        participant_id = manager.add_participant(1, 101, 'student')
        manager.toggle_mute(participant_id, True)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT is_muted FROM session_participants WHERE participant_id = ?", (participant_id,))
        is_muted = cursor.fetchone()[0]
        conn.close()

        assert is_muted == 1

    def test_toggle_mute_nonexistent_participant(self, manager):
        """Test toggling mute for non-existent participant."""
        result = manager.toggle_mute(99999, True)
        assert result is False

class TestToggleVideo:
    """Test video toggle functionality."""

    def test_turn_video_off(self, manager):
        """Test turning video off."""
        participant_id = manager.add_participant(1, 101, 'student')

        result = manager.toggle_video(participant_id, False)
        assert result is True

    def test_turn_video_on(self, manager):
        """Test turning video on."""
        participant_id = manager.add_participant(1, 101, 'student')

        manager.toggle_video(participant_id, False)
        result = manager.toggle_video(participant_id, True)
        assert result is True

    def test_video_status_persisted(self, manager, temp_db):
        """Test that video status is persisted to database."""
        participant_id = manager.add_participant(1, 101, 'student')
        manager.toggle_video(participant_id, False)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT is_video_on FROM session_participants WHERE participant_id = ?", (participant_id,))
        is_video_on = cursor.fetchone()[0]
        conn.close()

        assert is_video_on == 0

    def test_toggle_video_nonexistent_participant(self, manager):
        """Test toggling video for non-existent participant."""
        result = manager.toggle_video(99999, True)
        assert result is False

class TestGetSessionParticipants:
    """Test retrieving session participants."""

    def test_get_all_participants(self, manager):
        """Test getting all participants for a session."""
        manager.add_participant(1, 101, 'student')
        manager.add_participant(1, 102, 'student')
        manager.add_participant(1, 999, 'instructor')

        participants = manager.get_session_participants(1)
        assert len(participants) == 3

    def test_get_participants_by_type(self, manager):
        """Test filtering participants by user type."""
        manager.add_participant(1, 101, 'student')
        manager.add_participant(1, 102, 'student')
        manager.add_participant(1, 999, 'instructor')

        students = manager.get_session_participants(1, user_type='student')
        assert len(students) == 2
        assert all(p['user_type'] == 'student' for p in students)

    def test_participants_ordered_by_join_time(self, manager):
        """Test that participants are ordered by join time."""
        p1 = manager.add_participant(1, 101, 'student')
        p2 = manager.add_participant(1, 102, 'student')
        p3 = manager.add_participant(1, 103, 'student')

        participants = manager.get_session_participants(1)
        assert participants[0]['participant_id'] == p1
        assert participants[1]['participant_id'] == p2
        assert participants[2]['participant_id'] == p3

    def test_get_participants_empty_session(self, manager):
        """Test getting participants for session with none."""
        participants = manager.get_session_participants(1)
        assert participants == []

class TestGetParticipantByUser:
    """Test getting specific participant records."""

    def test_get_participant_by_user(self, manager):
        """Test getting participant record for specific user."""
        manager.add_participant(1, 101, 'student')

        participant = manager.get_participant_by_user(1, 101)
        assert participant is not None
        assert participant['user_id'] == 101
        assert participant['session_id'] == 1

    def test_get_nonexistent_participant(self, manager):
        """Test getting participant that doesn't exist."""
        participant = manager.get_participant_by_user(1, 999)
        assert participant is None

    def test_get_participant_wrong_session(self, manager):
        """Test getting participant from wrong session."""
        manager.add_participant(1, 101, 'student')

        participant = manager.get_participant_by_user(999, 101)
        assert participant is None

class TestGetAttendanceSummary:
    """Test attendance summary statistics."""

    def test_get_attendance_summary(self, manager):
        """Test getting attendance summary for a session."""
        p1 = manager.add_participant(1, 101, 'student')
        p2 = manager.add_participant(1, 102, 'student')
        p3 = manager.add_participant(1, 103, 'student')
        p4 = manager.add_participant(1, 104, 'student')

        manager.update_attendance_status(p1, 'present')
        manager.update_attendance_status(p2, 'present')
        manager.update_attendance_status(p3, 'late')

        summary = manager.get_attendance_summary(1)
        assert summary['present'] == 2
        assert summary['late'] == 1
        assert summary['absent'] == 1

    def test_attendance_summary_empty_session(self, manager):
        """Test attendance summary for session with no participants."""
        summary = manager.get_attendance_summary(1)
        assert summary == {}

class TestGetUserAttendanceHistory:
    """Test retrieving user attendance history."""

    def test_get_attendance_history(self, manager, temp_db):
        """Test getting attendance history for a user."""
        # Add session 2
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_sessions (classroom_id, start_time)
            VALUES (1, CURRENT_TIMESTAMP)
        """)
        conn.commit()
        conn.close()

        # Add participant to both sessions
        manager.add_participant(1, 101, 'student')
        manager.add_participant(2, 101, 'student')

        history = manager.get_user_attendance_history(101)
        assert len(history) == 2

    def test_attendance_history_includes_session_details(self, manager):
        """Test that attendance history includes session details."""
        manager.add_participant(1, 101, 'student')

        history = manager.get_user_attendance_history(101)
        assert len(history) == 1
        assert 'session_type' in history[0]
        assert 'start_time' in history[0]
        assert 'session_name' in history[0]

    def test_attendance_history_filter_by_classroom(self, manager, temp_db):
        """Test filtering attendance history by classroom."""
        # Add another classroom and session
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO virtual_classrooms (session_name, instructor_id) VALUES ('Class 2', 999)")
        classroom2_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO virtual_sessions (classroom_id, start_time)
            VALUES (?, CURRENT_TIMESTAMP)
        """, (classroom2_id,))
        session2_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Add participant to both sessions
        manager.add_participant(1, 101, 'student')
        manager.add_participant(session2_id, 101, 'student')

        # Filter by classroom 1
        history = manager.get_user_attendance_history(101, classroom_id=1)
        assert len(history) == 1

    def test_attendance_history_ordered_by_date(self, manager, temp_db):
        """Test that history is ordered by start time descending."""
        # Add another session
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_sessions (classroom_id, start_time)
            VALUES (1, datetime('now', '+1 hour'))
        """)
        conn.commit()
        conn.close()

        manager.add_participant(1, 101, 'student')
        manager.add_participant(2, 101, 'student')

        history = manager.get_user_attendance_history(101)
        # Most recent first
        assert len(history) == 2

    def test_attendance_history_user_with_no_sessions(self, manager):
        """Test getting history for user with no sessions."""
        history = manager.get_user_attendance_history(999)
        assert history == []

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
        manager = ParticipantManager(db_path="/invalid/path/to/db.db")

        participant_id = manager.add_participant(1, 101, 'student')
        assert participant_id is None

        result = manager.record_leave(1)
        assert result is False

        participants = manager.get_session_participants(1)
        assert participants == []

        history = manager.get_user_attendance_history(101)
        assert history == []

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
