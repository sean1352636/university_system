"""
Comprehensive test suite for poll_manager.py

Tests all classes, functions, and functionality including:
- PollManager class
- Poll creation (multiple choice, true/false, rating, open-ended)
- Response submission and validation
- Poll results and analytics
- Quiz functionality with correct answers
"""

import pytest
import os
import json
import tempfile
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.domain.academics.services.virtual_classroom.poll_manager import (
    PollManager
)

@pytest.fixture
def temp_db():
    """Create a temporary test database with required tables."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS virtual_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom_id INTEGER NOT NULL,
            start_time TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'in_progress'
        );

        CREATE TABLE IF NOT EXISTS virtual_polls (
            poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            poll_type TEXT DEFAULT 'multiple_choice',
            options TEXT,
            correct_answer TEXT,
            is_anonymous BOOLEAN DEFAULT 1,
            is_active BOOLEAN DEFAULT 1,
            time_limit INTEGER,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS poll_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            answer TEXT NOT NULL,
            is_correct BOOLEAN,
            response_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            time_taken INTEGER,
            FOREIGN KEY (poll_id) REFERENCES virtual_polls(poll_id) ON DELETE CASCADE,
            UNIQUE(poll_id, user_id)
        );
    """)

    cursor.execute("INSERT INTO virtual_sessions (classroom_id, start_time) VALUES (1, CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

    yield db_path
    os.unlink(db_path)

@pytest.fixture
def manager(temp_db):
    """Create a PollManager instance with temp database."""
    return PollManager(db_path=temp_db)

class TestPollManagerInit:
    """Test PollManager initialization."""

    def test_init_default_db_path(self):
        manager = PollManager()
        assert manager.db_path is not None

    def test_init_custom_db_path(self, temp_db):
        manager = PollManager(db_path=temp_db)
        assert manager.db_path == temp_db

class TestCreatePoll:
    """Test poll creation."""

    def test_create_multiple_choice_poll(self, manager):
        poll_id = manager.create_poll(
            session_id=1,
            question="What is Python?",
            created_by=999,
            poll_type='multiple_choice',
            options=['A programming language', 'A snake', 'A movie', 'A book']
        )
        assert poll_id is not None

    def test_create_true_false_poll(self, manager):
        poll_id = manager.create_poll(
            session_id=1,
            question="Python is object-oriented?",
            created_by=999,
            poll_type='true_false',
            options=['True', 'False']
        )
        assert poll_id is not None

    def test_create_quiz_with_correct_answer(self, manager):
        poll_id = manager.create_poll(
            session_id=1,
            question="What is 2+2?",
            created_by=999,
            poll_type='multiple_choice',
            options=['3', '4', '5'],
            correct_answer='4'
        )
        assert poll_id is not None

        poll = manager.get_poll(poll_id)
        assert poll['correct_answer'] == '4'

    def test_create_anonymous_poll(self, manager):
        poll_id = manager.create_poll(
            session_id=1,
            question="Rate this class",
            created_by=999,
            poll_type='rating',
            is_anonymous=True
        )
        assert poll_id is not None

    def test_create_poll_with_time_limit(self, manager):
        poll_id = manager.create_poll(
            session_id=1,
            question="Quick question",
            created_by=999,
            time_limit=60
        )
        assert poll_id is not None

    def test_create_poll_invalid_type(self, manager):
        poll_id = manager.create_poll(
            session_id=1,
            question="Test",
            created_by=999,
            poll_type='invalid_type'
        )
        assert poll_id is None

class TestSubmitResponse:
    """Test submitting poll responses."""

    def test_submit_response(self, manager):
        poll_id = manager.create_poll(1, "Test?", 999, options=['A', 'B'])
        result = manager.submit_response(poll_id, 101, 'A')
        assert result is True

    def test_submit_response_to_quiz(self, manager):
        poll_id = manager.create_poll(
            1, "What is 5+5?", 999,
            options=['10', '15', '20'],
            correct_answer='10'
        )

        result = manager.submit_response(poll_id, 101, '10')
        assert result is True

        response = manager.get_user_response(poll_id, 101)
        assert response['is_correct'] == 1

    def test_submit_incorrect_answer(self, manager):
        poll_id = manager.create_poll(
            1, "What is 5+5?", 999,
            correct_answer='10'
        )

        manager.submit_response(poll_id, 101, '15')
        response = manager.get_user_response(poll_id, 101)
        assert response['is_correct'] == 0

    def test_update_existing_response(self, manager):
        poll_id = manager.create_poll(1, "Test?", 999)
        manager.submit_response(poll_id, 101, 'First answer')
        manager.submit_response(poll_id, 101, 'Updated answer')

        response = manager.get_user_response(poll_id, 101)
        assert response['answer'] == 'Updated answer'

    def test_submit_to_closed_poll(self, manager):
        poll_id = manager.create_poll(1, "Test?", 999)
        manager.close_poll(poll_id)

        result = manager.submit_response(poll_id, 101, 'Late answer')
        assert result is False

    def test_submit_to_nonexistent_poll(self, manager):
        result = manager.submit_response(99999, 101, 'Answer')
        assert result is False

class TestClosePoll:
    """Test closing polls."""

    def test_close_poll(self, manager):
        poll_id = manager.create_poll(1, "Test?", 999)
        result = manager.close_poll(poll_id)
        assert result is True

        poll = manager.get_poll(poll_id)
        assert poll['is_active'] == 0

    def test_close_nonexistent_poll(self, manager):
        result = manager.close_poll(99999)
        assert result is False

class TestGetPoll:
    """Test retrieving poll details."""

    def test_get_existing_poll(self, manager):
        poll_id = manager.create_poll(
            1, "Test question?", 999,
            poll_type='multiple_choice',
            options=['A', 'B', 'C']
        )

        poll = manager.get_poll(poll_id)
        assert poll is not None
        assert poll['question'] == "Test question?"
        assert poll['options'] == ['A', 'B', 'C']

    def test_get_nonexistent_poll(self, manager):
        poll = manager.get_poll(99999)
        assert poll is None

class TestGetSessionPolls:
    """Test retrieving polls for a session."""

    def test_get_all_session_polls(self, manager):
        manager.create_poll(1, "Q1", 999)
        manager.create_poll(1, "Q2", 999)
        manager.create_poll(1, "Q3", 999)

        polls = manager.get_session_polls(1)
        assert len(polls) == 3

    def test_get_active_polls_only(self, manager):
        p1 = manager.create_poll(1, "Q1", 999)
        p2 = manager.create_poll(1, "Q2", 999)
        manager.close_poll(p1)

        active_polls = manager.get_session_polls(1, active_only=True)
        assert len(active_polls) == 1

    def test_get_polls_for_empty_session(self, manager):
        polls = manager.get_session_polls(1)
        assert polls == []

class TestGetPollResults:
    """Test retrieving poll results."""

    def test_get_poll_results(self, manager):
        poll_id = manager.create_poll(1, "Favorite color?", 999, options=['Red', 'Blue', 'Green'])

        manager.submit_response(poll_id, 101, 'Red')
        manager.submit_response(poll_id, 102, 'Blue')
        manager.submit_response(poll_id, 103, 'Red')

        results = manager.get_poll_results(poll_id)
        assert results['total_responses'] == 3
        assert len(results['response_distribution']) > 0

    def test_get_quiz_results_with_accuracy(self, manager):
        poll_id = manager.create_poll(
            1, "What is 2+2?", 999,
            correct_answer='4'
        )

        manager.submit_response(poll_id, 101, '4')  # Correct
        manager.submit_response(poll_id, 102, '5')  # Incorrect
        manager.submit_response(poll_id, 103, '4')  # Correct

        results = manager.get_poll_results(poll_id)
        assert results['accuracy'] is not None
        assert results['accuracy'] > 0

    def test_get_results_for_nonexistent_poll(self, manager):
        results = manager.get_poll_results(99999)
        assert results == {}

class TestGetUserResponse:
    """Test retrieving user responses."""

    def test_get_existing_response(self, manager):
        poll_id = manager.create_poll(1, "Test?", 999)
        manager.submit_response(poll_id, 101, 'My answer')

        response = manager.get_user_response(poll_id, 101)
        assert response is not None
        assert response['answer'] == 'My answer'

    def test_get_nonexistent_response(self, manager):
        poll_id = manager.create_poll(1, "Test?", 999)
        response = manager.get_user_response(poll_id, 999)
        assert response is None

class TestDeletePoll:
    """Test deleting polls."""

    def test_delete_poll(self, manager):
        poll_id = manager.create_poll(1, "Test?", 999)
        result = manager.delete_poll(poll_id)
        assert result is True

        poll = manager.get_poll(poll_id)
        assert poll is None

    def test_delete_nonexistent_poll(self, manager):
        result = manager.delete_poll(99999)
        assert result is False

class TestErrorHandling:
    """Test error handling."""

    def test_operations_with_invalid_db_path(self):
        manager = PollManager(db_path="/invalid/path.db")

        poll_id = manager.create_poll(1, "Test?", 999)
        assert poll_id is None

        result = manager.submit_response(1, 101, 'Answer')
        assert result is False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
