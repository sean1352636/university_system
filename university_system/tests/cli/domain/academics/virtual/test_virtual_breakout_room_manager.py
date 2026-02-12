"""
Comprehensive test suite for breakout_room_manager.py

Tests all classes, functions, and functionality including:
- BreakoutRoomManager class
- Room creation and management
- Participant management
- Auto-assignment logic
- Room lifecycle (start, end)
"""

import pytest
import os
import json
import tempfile
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

from university_system.modules.domain.academics.services.virtual_classroom.breakout_room_manager import (
    BreakoutRoomManager
)

@pytest.fixture
def temp_db():
    """Create a temporary test database with required tables."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create virtual_sessions table (parent table)
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS virtual_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom_id INTEGER NOT NULL,
            session_type TEXT DEFAULT 'lecture',
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            status TEXT DEFAULT 'scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS breakout_rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            room_name TEXT NOT NULL,
            room_number INTEGER,
            participants TEXT,
            facilitator_id INTEGER,
            max_capacity INTEGER DEFAULT 10,
            topic TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration INTEGER,
            is_active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
        );
    """)

    # Insert test session
    cursor.execute("""
        INSERT INTO virtual_sessions (classroom_id, session_type, start_time, status)
        VALUES (1, 'lecture', CURRENT_TIMESTAMP, 'in_progress')
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)

@pytest.fixture
def manager(temp_db):
    """Create a BreakoutRoomManager instance with temp database."""
    return BreakoutRoomManager(db_path=temp_db)

class TestBreakoutRoomManagerInit:
    """Test BreakoutRoomManager initialization."""

    def test_init_default_db_path(self):
        """Test initialization with default database path."""
        manager = BreakoutRoomManager()
        assert manager.db_path is not None

    def test_init_custom_db_path(self, temp_db):
        """Test initialization with custom database path."""
        manager = BreakoutRoomManager(db_path=temp_db)
        assert manager.db_path == temp_db

class TestCreateBreakoutRoom:
    """Test breakout room creation."""

    def test_create_basic_room(self, manager):
        """Test creating a basic breakout room."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Team A",
            room_number=1,
            participants=[101, 102, 103]
        )
        assert room_id is not None
        assert isinstance(room_id, int)

    def test_create_room_with_facilitator(self, manager):
        """Test creating a room with a facilitator."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Team B",
            room_number=2,
            participants=[201, 202],
            facilitator_id=999
        )
        assert room_id is not None

        room = manager.get_breakout_room(room_id)
        assert room['facilitator_id'] == 999

    def test_create_room_with_topic(self, manager):
        """Test creating a room with a topic."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Discussion Room",
            room_number=3,
            participants=[301, 302],
            topic="Database Design",
            duration_minutes=20
        )
        assert room_id is not None

        room = manager.get_breakout_room(room_id)
        assert room['topic'] == "Database Design"
        assert room['duration'] == 20

    def test_create_room_custom_capacity(self, manager):
        """Test creating a room with custom max capacity."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Large Room",
            room_number=4,
            participants=[401],
            max_capacity=15
        )
        assert room_id is not None

        room = manager.get_breakout_room(room_id)
        assert room['max_capacity'] == 15

    def test_create_room_empty_participants(self, manager):
        """Test creating a room with no participants initially."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Empty Room",
            room_number=5,
            participants=[]
        )
        assert room_id is not None

        room = manager.get_breakout_room(room_id)
        assert room['participants'] == []

class TestStartBreakoutRoom:
    """Test starting breakout rooms."""

    def test_start_room_success(self, manager):
        """Test successfully starting a breakout room."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Test Room",
            room_number=1,
            participants=[101, 102]
        )

        result = manager.start_breakout_room(room_id)
        assert result is True

        room = manager.get_breakout_room(room_id)
        assert room['is_active'] == 1
        assert room['start_time'] is not None

    def test_start_nonexistent_room(self, manager):
        """Test starting a non-existent room."""
        result = manager.start_breakout_room(99999)
        assert result is False

class TestEndBreakoutRoom:
    """Test ending breakout rooms."""

    def test_end_room_success(self, manager):
        """Test successfully ending a breakout room."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Test Room",
            room_number=1,
            participants=[101, 102]
        )
        manager.start_breakout_room(room_id)

        result = manager.end_breakout_room(room_id)
        assert result is True

        room = manager.get_breakout_room(room_id)
        assert room['is_active'] == 0
        assert room['end_time'] is not None

    def test_end_nonexistent_room(self, manager):
        """Test ending a non-existent room."""
        result = manager.end_breakout_room(99999)
        assert result is False

class TestAddParticipantToRoom:
    """Test adding participants to rooms."""

    def test_add_participant_success(self, manager):
        """Test successfully adding a participant."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Test Room",
            room_number=1,
            participants=[101, 102]
        )

        result = manager.add_participant_to_room(room_id, 103)
        assert result is True

        room = manager.get_breakout_room(room_id)
        assert 103 in room['participants']
        assert len(room['participants']) == 3

    def test_add_duplicate_participant(self, manager):
        """Test adding a participant that's already in the room."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Test Room",
            room_number=1,
            participants=[101, 102]
        )

        result = manager.add_participant_to_room(room_id, 101)
        assert result is False

        room = manager.get_breakout_room(room_id)
        assert len(room['participants']) == 2  # Should not add duplicate

    def test_add_participant_at_max_capacity(self, manager):
        """Test adding a participant when room is at max capacity."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Small Room",
            room_number=1,
            participants=[101, 102],
            max_capacity=2
        )

        result = manager.add_participant_to_room(room_id, 103)
        assert result is False

        room = manager.get_breakout_room(room_id)
        assert len(room['participants']) == 2

    def test_add_participant_to_nonexistent_room(self, manager):
        """Test adding participant to non-existent room."""
        result = manager.add_participant_to_room(99999, 101)
        assert result is False

class TestRemoveParticipantFromRoom:
    """Test removing participants from rooms."""

    def test_remove_participant_success(self, manager):
        """Test successfully removing a participant."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Test Room",
            room_number=1,
            participants=[101, 102, 103]
        )

        result = manager.remove_participant_from_room(room_id, 102)
        assert result is True

        room = manager.get_breakout_room(room_id)
        assert 102 not in room['participants']
        assert len(room['participants']) == 2

    def test_remove_nonexistent_participant(self, manager):
        """Test removing a participant not in the room."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Test Room",
            room_number=1,
            participants=[101, 102]
        )

        result = manager.remove_participant_from_room(room_id, 999)
        assert result is False

    def test_remove_participant_from_nonexistent_room(self, manager):
        """Test removing participant from non-existent room."""
        result = manager.remove_participant_from_room(99999, 101)
        assert result is False

class TestGetBreakoutRoom:
    """Test retrieving breakout room details."""

    def test_get_existing_room(self, manager):
        """Test getting an existing breakout room."""
        room_id = manager.create_breakout_room(
            session_id=1,
            room_name="Test Room",
            room_number=1,
            participants=[101, 102],
            facilitator_id=999,
            topic="Test Topic"
        )

        room = manager.get_breakout_room(room_id)
        assert room is not None
        assert room['room_name'] == "Test Room"
        assert room['room_number'] == 1
        assert room['facilitator_id'] == 999
        assert room['topic'] == "Test Topic"
        assert isinstance(room['participants'], list)
        assert 101 in room['participants']

    def test_get_nonexistent_room(self, manager):
        """Test getting a non-existent room."""
        room = manager.get_breakout_room(99999)
        assert room is None

class TestGetSessionBreakoutRooms:
    """Test retrieving all rooms for a session."""

    def test_get_all_session_rooms(self, manager):
        """Test getting all breakout rooms for a session."""
        # Create multiple rooms
        manager.create_breakout_room(1, "Room 1", 1, [101, 102])
        manager.create_breakout_room(1, "Room 2", 2, [201, 202])
        manager.create_breakout_room(1, "Room 3", 3, [301, 302])

        rooms = manager.get_session_breakout_rooms(1)
        assert len(rooms) == 3
        assert all(room['session_id'] == 1 for room in rooms)

    def test_get_active_rooms_only(self, manager):
        """Test getting only active rooms for a session."""
        room1 = manager.create_breakout_room(1, "Room 1", 1, [101])
        room2 = manager.create_breakout_room(1, "Room 2", 2, [201])
        room3 = manager.create_breakout_room(1, "Room 3", 3, [301])

        # Start only room1 and room2
        manager.start_breakout_room(room1)
        manager.start_breakout_room(room2)

        active_rooms = manager.get_session_breakout_rooms(1, active_only=True)
        assert len(active_rooms) == 2

    def test_get_rooms_ordered_by_number(self, manager):
        """Test that rooms are ordered by room_number."""
        manager.create_breakout_room(1, "Room 3", 3, [301])
        manager.create_breakout_room(1, "Room 1", 1, [101])
        manager.create_breakout_room(1, "Room 2", 2, [201])

        rooms = manager.get_session_breakout_rooms(1)
        assert rooms[0]['room_number'] == 1
        assert rooms[1]['room_number'] == 2
        assert rooms[2]['room_number'] == 3

    def test_get_rooms_for_nonexistent_session(self, manager):
        """Test getting rooms for a non-existent session."""
        rooms = manager.get_session_breakout_rooms(99999)
        assert rooms == []

class TestGetUserBreakoutRoom:
    """Test finding which room a user is in."""

    def test_find_user_in_room(self, manager):
        """Test finding a user's breakout room."""
        room1 = manager.create_breakout_room(1, "Room 1", 1, [101, 102])
        room2 = manager.create_breakout_room(1, "Room 2", 2, [201, 202])

        manager.start_breakout_room(room1)
        manager.start_breakout_room(room2)

        user_room = manager.get_user_breakout_room(1, 201)
        assert user_room is not None
        assert user_room['room_id'] == room2
        assert 201 in user_room['participants']

    def test_user_not_in_any_room(self, manager):
        """Test when user is not in any active room."""
        room1 = manager.create_breakout_room(1, "Room 1", 1, [101, 102])
        manager.start_breakout_room(room1)

        user_room = manager.get_user_breakout_room(1, 999)
        assert user_room is None

    def test_user_only_found_in_active_rooms(self, manager):
        """Test that only active rooms are searched."""
        room1 = manager.create_breakout_room(1, "Room 1", 1, [101, 102])
        # Don't start the room (not active)

        user_room = manager.get_user_breakout_room(1, 101)
        assert user_room is None

class TestAutoAssignBreakoutRooms:
    """Test automatic room assignment."""

    def test_auto_assign_even_distribution(self, manager):
        """Test auto-assigning users evenly across rooms."""
        user_ids = [101, 102, 103, 104, 105, 106]

        room_ids = manager.auto_assign_breakout_rooms(
            session_id=1,
            user_ids=user_ids,
            num_rooms=3
        )

        assert len(room_ids) == 3

        # Check distribution
        all_participants = []
        for room_id in room_ids:
            room = manager.get_breakout_room(room_id)
            all_participants.extend(room['participants'])
            # Each room should have 2 users
            assert len(room['participants']) == 2

        # All users should be assigned
        assert sorted(all_participants) == sorted(user_ids)

    def test_auto_assign_uneven_distribution(self, manager):
        """Test auto-assigning when users don't divide evenly."""
        user_ids = [101, 102, 103, 104, 105]

        room_ids = manager.auto_assign_breakout_rooms(
            session_id=1,
            user_ids=user_ids,
            num_rooms=2
        )

        assert len(room_ids) == 2

        # Check all users are assigned
        all_participants = []
        for room_id in room_ids:
            room = manager.get_breakout_room(room_id)
            all_participants.extend(room['participants'])

        assert sorted(all_participants) == sorted(user_ids)

        # Last room should have the extra user
        last_room = manager.get_breakout_room(room_ids[-1])
        assert len(last_room['participants']) == 3

    def test_auto_assign_custom_prefix(self, manager):
        """Test auto-assigning with custom room name prefix."""
        user_ids = [101, 102, 103, 104]

        room_ids = manager.auto_assign_breakout_rooms(
            session_id=1,
            user_ids=user_ids,
            num_rooms=2,
            room_name_prefix="Group"
        )

        room1 = manager.get_breakout_room(room_ids[0])
        room2 = manager.get_breakout_room(room_ids[1])

        assert room1['room_name'] == "Group 1"
        assert room2['room_name'] == "Group 2"

    def test_auto_assign_single_room(self, manager):
        """Test auto-assigning all users to a single room."""
        user_ids = [101, 102, 103]

        room_ids = manager.auto_assign_breakout_rooms(
            session_id=1,
            user_ids=user_ids,
            num_rooms=1
        )

        assert len(room_ids) == 1

        room = manager.get_breakout_room(room_ids[0])
        assert sorted(room['participants']) == sorted(user_ids)

    def test_auto_assign_empty_user_list(self, manager):
        """Test auto-assigning with empty user list."""
        room_ids = manager.auto_assign_breakout_rooms(
            session_id=1,
            user_ids=[],
            num_rooms=2
        )

        assert len(room_ids) == 2

        # All rooms should be empty
        for room_id in room_ids:
            room = manager.get_breakout_room(room_id)
            assert room['participants'] == []

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

    def test_create_room_invalid_session(self, manager):
        """Test creating room with invalid session ID."""
        room_id = manager.create_breakout_room(
            session_id=99999,
            room_name="Test Room",
            room_number=1,
            participants=[101]
        )
        # Should return None on error (foreign key constraint)
        assert room_id is None

    def test_operations_with_invalid_db_path(self):
        """Test operations with invalid database path."""
        manager = BreakoutRoomManager(db_path="/invalid/path/to/db.db")

        room_id = manager.create_breakout_room(1, "Room", 1, [])
        assert room_id is None

        result = manager.start_breakout_room(1)
        assert result is False

        rooms = manager.get_session_breakout_rooms(1)
        assert rooms == []

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
