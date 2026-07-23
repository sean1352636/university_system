"""
Comprehensive test suite for recording_manager.py

Tests all classes, functions, and functionality including:
- RecordingManager class
- Recording metadata storage
- Transcript and caption management
- View and download tracking
- Storage usage statistics
- Recording expiration
"""

import pytest
import os
import tempfile
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

from education_system.post_18.university_system.modules.domain.academics.services.virtual_classroom.recording_manager import (
    RecordingManager
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
            instructor_id INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS virtual_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom_id INTEGER NOT NULL,
            session_type TEXT DEFAULT 'lecture',
            start_time TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'completed',
            FOREIGN KEY (classroom_id) REFERENCES virtual_classrooms(classroom_id)
        );

        CREATE TABLE IF NOT EXISTS virtual_recordings (
            recording_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            file_url TEXT NOT NULL,
            file_name TEXT,
            file_size INTEGER,
            duration INTEGER,
            format TEXT DEFAULT 'mp4',
            has_transcript BOOLEAN DEFAULT 0,
            transcript_url TEXT,
            has_captions BOOLEAN DEFAULT 0,
            captions_url TEXT,
            view_count INTEGER DEFAULT 0,
            download_count INTEGER DEFAULT 0,
            is_public BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
        );
    """)

    cursor.execute("INSERT INTO virtual_classrooms (session_name, instructor_id) VALUES ('Test Classroom', 999)")
    cursor.execute("INSERT INTO virtual_sessions (classroom_id, start_time) VALUES (1, CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

    yield db_path
    os.unlink(db_path)

@pytest.fixture
def manager(temp_db):
    """Create a RecordingManager instance with temp database."""
    return RecordingManager(db_path=temp_db)

class TestRecordingManagerInit:
    """Test RecordingManager initialization."""

    def test_init_default_db_path(self):
        manager = RecordingManager()
        assert manager.db_path is not None

    def test_init_custom_db_path(self, temp_db):
        manager = RecordingManager(db_path=temp_db)
        assert manager.db_path == temp_db

class TestSaveRecording:
    """Test saving recording metadata."""

    def test_save_basic_recording(self, manager):
        recording_id = manager.save_recording(
            session_id=1,
            file_url="https://example.com/recording.mp4"
        )
        assert recording_id is not None

    def test_save_recording_with_details(self, manager):
        recording_id = manager.save_recording(
            session_id=1,
            file_url="https://example.com/recording.mp4",
            file_name="lecture_01.mp4",
            file_size=1024000,
            duration=3600,
            file_format='mp4'
        )
        assert recording_id is not None

        recording = manager.get_recording(recording_id)
        assert recording['file_size'] == 1024000
        assert recording['duration'] == 3600

    def test_save_public_recording(self, manager):
        recording_id = manager.save_recording(
            session_id=1,
            file_url="https://example.com/public.mp4",
            is_public=True
        )

        recording = manager.get_recording(recording_id)
        assert recording['is_public'] == 1

    def test_save_recording_with_expiry(self, manager, temp_db):
        recording_id = manager.save_recording(
            session_id=1,
            file_url="https://example.com/temp.mp4",
            expiry_days=30
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT expires_at FROM virtual_recordings WHERE recording_id = ?", (recording_id,))
        expires_at = cursor.fetchone()[0]
        conn.close()

        assert expires_at is not None

class TestAddTranscript:
    """Test adding transcripts to recordings."""

    def test_add_transcript(self, manager):
        recording_id = manager.save_recording(1, "https://example.com/video.mp4")

        result = manager.add_transcript(recording_id, "https://example.com/transcript.vtt")
        assert result is True

        recording = manager.get_recording(recording_id)
        assert recording['has_transcript'] == 1
        assert recording['transcript_url'] == "https://example.com/transcript.vtt"

    def test_add_transcript_to_nonexistent_recording(self, manager):
        result = manager.add_transcript(99999, "https://example.com/transcript.vtt")
        assert result is False

class TestAddCaptions:
    """Test adding captions to recordings."""

    def test_add_captions(self, manager):
        recording_id = manager.save_recording(1, "https://example.com/video.mp4")

        result = manager.add_captions(recording_id, "https://example.com/captions.srt")
        assert result is True

        recording = manager.get_recording(recording_id)
        assert recording['has_captions'] == 1
        assert recording['captions_url'] == "https://example.com/captions.srt"

    def test_add_captions_to_nonexistent_recording(self, manager):
        result = manager.add_captions(99999, "https://example.com/captions.srt")
        assert result is False

class TestIncrementViewCount:
    """Test incrementing view count."""

    def test_increment_view_count(self, manager):
        recording_id = manager.save_recording(1, "https://example.com/video.mp4")

        result = manager.increment_view_count(recording_id)
        assert result is True

    def test_increment_view_count_multiple_times(self, manager, temp_db):
        recording_id = manager.save_recording(1, "https://example.com/video.mp4")

        manager.increment_view_count(recording_id)
        manager.increment_view_count(recording_id)
        manager.increment_view_count(recording_id)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT view_count FROM virtual_recordings WHERE recording_id = ?", (recording_id,))
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 3

    def test_increment_view_count_nonexistent_recording(self, manager):
        result = manager.increment_view_count(99999)
        assert result is False

class TestIncrementDownloadCount:
    """Test incrementing download count."""

    def test_increment_download_count(self, manager):
        recording_id = manager.save_recording(1, "https://example.com/video.mp4")

        result = manager.increment_download_count(recording_id)
        assert result is True

    def test_increment_download_count_multiple_times(self, manager, temp_db):
        recording_id = manager.save_recording(1, "https://example.com/video.mp4")

        manager.increment_download_count(recording_id)
        manager.increment_download_count(recording_id)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT download_count FROM virtual_recordings WHERE recording_id = ?", (recording_id,))
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 2

class TestGetRecording:
    """Test retrieving recording details."""

    def test_get_existing_recording(self, manager):
        recording_id = manager.save_recording(1, "https://example.com/video.mp4", file_name="test.mp4")

        recording = manager.get_recording(recording_id)
        assert recording is not None
        assert recording['file_url'] == "https://example.com/video.mp4"
        assert 'session_type' in recording  # Joined data

    def test_get_nonexistent_recording(self, manager):
        recording = manager.get_recording(99999)
        assert recording is None

class TestGetRecordingsBySession:
    """Test retrieving recordings for a session."""

    def test_get_session_recordings(self, manager):
        manager.save_recording(1, "https://example.com/video1.mp4")
        manager.save_recording(1, "https://example.com/video2.mp4")
        manager.save_recording(1, "https://example.com/video3.mp4")

        recordings = manager.get_recordings_by_session(1)
        assert len(recordings) == 3

    def test_get_recordings_ordered_by_date(self, manager):
        r1 = manager.save_recording(1, "https://example.com/video1.mp4")
        r2 = manager.save_recording(1, "https://example.com/video2.mp4")

        recordings = manager.get_recordings_by_session(1)
        assert recordings[0]['recording_id'] == r2  # Most recent first

class TestGetRecordingsByClassroom:
    """Test retrieving recordings for a classroom."""

    def test_get_classroom_recordings(self, manager, temp_db):
        # Create another session
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO virtual_sessions (classroom_id, start_time) VALUES (1, CURRENT_TIMESTAMP)")
        session2_id = cursor.lastrowid
        conn.commit()
        conn.close()

        manager.save_recording(1, "https://example.com/v1.mp4")
        manager.save_recording(session2_id, "https://example.com/v2.mp4")

        recordings = manager.get_recordings_by_classroom(1)
        assert len(recordings) == 2

    def test_get_classroom_recordings_exclude_expired(self, manager, temp_db):
        # Create expired recording
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_recordings (session_id, file_url, expires_at)
            VALUES (1, 'https://example.com/expired.mp4', datetime('now', '-1 day'))
        """)
        conn.commit()
        conn.close()

        manager.save_recording(1, "https://example.com/active.mp4", expiry_days=30)

        recordings = manager.get_recordings_by_classroom(1, include_expired=False)
        assert len(recordings) == 1

class TestListRecordings:
    """Test listing recordings with filters."""

    def test_list_all_recordings(self, manager):
        manager.save_recording(1, "https://example.com/v1.mp4")
        manager.save_recording(1, "https://example.com/v2.mp4")

        recordings = manager.list_recordings()
        assert len(recordings) == 2

    def test_list_recordings_by_session(self, manager):
        manager.save_recording(1, "https://example.com/v1.mp4")

        recordings = manager.list_recordings(session_id=1)
        assert len(recordings) == 1

    def test_list_public_recordings_only(self, manager):
        manager.save_recording(1, "https://example.com/private.mp4", is_public=False)
        manager.save_recording(1, "https://example.com/public.mp4", is_public=True)

        recordings = manager.list_recordings(is_public=True)
        assert len(recordings) == 1
        assert recordings[0]['is_public'] == 1

class TestDeleteRecording:
    """Test deleting recordings."""

    def test_delete_recording(self, manager):
        recording_id = manager.save_recording(1, "https://example.com/video.mp4")

        result = manager.delete_recording(recording_id)
        assert result is True

        recording = manager.get_recording(recording_id)
        assert recording is None

    def test_delete_nonexistent_recording(self, manager):
        result = manager.delete_recording(99999)
        assert result is False

class TestGetExpiredRecordings:
    """Test retrieving expired recordings."""

    def test_get_expired_recordings(self, manager, temp_db):
        # Create expired recording
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO virtual_recordings (session_id, file_url, expires_at)
            VALUES (1, 'https://example.com/expired.mp4', datetime('now', '-1 day'))
        """)
        conn.commit()
        conn.close()

        expired = manager.get_expired_recordings()
        assert len(expired) == 1

class TestGetStorageUsage:
    """Test getting storage usage statistics."""

    def test_get_total_storage_usage(self, manager):
        manager.save_recording(1, "https://example.com/v1.mp4", file_size=1000000, duration=3600)
        manager.save_recording(1, "https://example.com/v2.mp4", file_size=2000000, duration=1800)

        usage = manager.get_storage_usage()
        assert usage['total_recordings'] == 2
        assert usage['total_size'] == 3000000
        assert usage['total_duration'] == 5400

    def test_get_classroom_storage_usage(self, manager):
        manager.save_recording(1, "https://example.com/v1.mp4", file_size=1000000)

        usage = manager.get_storage_usage(classroom_id=1)
        assert usage['total_recordings'] == 1
        assert usage['total_size'] == 1000000

class TestErrorHandling:
    """Test error handling."""

    def test_operations_with_invalid_db_path(self):
        manager = RecordingManager(db_path="/invalid/path.db")

        recording_id = manager.save_recording(1, "https://example.com/video.mp4")
        assert recording_id is None

        recordings = manager.list_recordings()
        assert recordings == []

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
