"""
Comprehensive test suite for chat_manager.py

Tests all classes, functions, and functionality including:
- ChatManager class
- Message sending (public, private, announcements)
- Message deletion and reactions
- Thread messages and replies
- Message search and statistics
- Chat clearing
"""

import pytest
import os
import json
import tempfile
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime

from education_system.university_system.modules.domain.academics.services.virtual_classroom.chat_manager import (
    ChatManager
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
        CREATE TABLE IF NOT EXISTS virtual_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom_id INTEGER NOT NULL,
            session_type TEXT DEFAULT 'lecture',
            start_time TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'scheduled'
        );

        CREATE TABLE IF NOT EXISTS session_participants (
            participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_type TEXT NOT NULL,
            join_time TIMESTAMP,
            chat_message_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS virtual_chat_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            message_text TEXT NOT NULL,
            message_type TEXT DEFAULT 'public',
            recipient_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT 0,
            replied_to INTEGER,
            reactions TEXT,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (replied_to) REFERENCES virtual_chat_messages(message_id)
        );
    """)

    # Insert test data
    cursor.execute("""
        INSERT INTO virtual_sessions (classroom_id, session_type, start_time, status)
        VALUES (1, 'lecture', CURRENT_TIMESTAMP, 'in_progress')
    """)

    cursor.execute("""
        INSERT INTO session_participants (session_id, user_id, user_type, join_time)
        VALUES (1, 101, 'student', CURRENT_TIMESTAMP)
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    os.unlink(db_path)

@pytest.fixture
def manager(temp_db):
    """Create a ChatManager instance with temp database."""
    return ChatManager(db_path=temp_db)

class TestChatManagerInit:
    """Test ChatManager initialization."""

    def test_init_default_db_path(self):
        """Test initialization with default database path."""
        manager = ChatManager()
        assert manager.db_path is not None

    def test_init_custom_db_path(self, temp_db):
        """Test initialization with custom database path."""
        manager = ChatManager(db_path=temp_db)
        assert manager.db_path == temp_db

class TestSendMessage:
    """Test sending chat messages."""

    def test_send_public_message(self, manager):
        """Test sending a public message."""
        message_id = manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John Doe",
            message_text="Hello everyone!",
            message_type='public'
        )
        assert message_id is not None
        assert isinstance(message_id, int)

        # Verify message was saved
        message = manager.get_message(message_id)
        assert message['message_text'] == "Hello everyone!"
        assert message['message_type'] == 'public'
        assert message['user_name'] == "John Doe"

    def test_send_private_message(self, manager):
        """Test sending a private message."""
        message_id = manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John Doe",
            message_text="Private message",
            message_type='private',
            recipient_id=102
        )
        assert message_id is not None

        message = manager.get_message(message_id)
        assert message['message_type'] == 'private'
        assert message['recipient_id'] == 102

    def test_send_announcement(self, manager):
        """Test sending an announcement."""
        message_id = manager.send_message(
            session_id=1,
            user_id=999,
            user_name="Instructor",
            message_text="Class will end in 10 minutes",
            message_type='announcement'
        )
        assert message_id is not None

        message = manager.get_message(message_id)
        assert message['message_type'] == 'announcement'

    def test_send_reply_message(self, manager):
        """Test sending a reply to another message."""
        # Send original message
        parent_id = manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John",
            message_text="What's the homework?",
            message_type='public'
        )

        # Send reply
        reply_id = manager.send_message(
            session_id=1,
            user_id=102,
            user_name="Jane",
            message_text="Chapter 5 exercises",
            message_type='public',
            replied_to=parent_id
        )
        assert reply_id is not None

        reply = manager.get_message(reply_id)
        assert reply['replied_to'] == parent_id

    def test_send_message_invalid_type(self, manager):
        """Test sending a message with invalid type."""
        message_id = manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John",
            message_text="Test",
            message_type='invalid_type'
        )
        assert message_id is None

    def test_send_private_message_without_recipient(self, manager):
        """Test sending private message without recipient_id."""
        message_id = manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John",
            message_text="Private message",
            message_type='private'
        )
        assert message_id is None

    def test_message_increments_participant_count(self, manager, temp_db):
        """Test that sending a message increments participant chat count."""
        manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John",
            message_text="Test message"
        )

        # Check participant count
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chat_message_count FROM session_participants
            WHERE session_id = 1 AND user_id = 101
        """)
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1

class TestDeleteMessage:
    """Test message deletion."""

    def test_delete_existing_message(self, manager):
        """Test soft deleting an existing message."""
        message_id = manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John",
            message_text="Delete me"
        )

        result = manager.delete_message(message_id)
        assert result is True

        message = manager.get_message(message_id)
        assert message['is_deleted'] == 1

    def test_delete_nonexistent_message(self, manager):
        """Test deleting a non-existent message."""
        result = manager.delete_message(99999)
        assert result is False

class TestAddReaction:
    """Test adding reactions to messages."""

    def test_add_reaction(self, manager):
        """Test adding a reaction to a message."""
        message_id = manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John",
            message_text="Great class!"
        )

        result = manager.add_reaction(message_id, "👍")
        assert result is True

        message = manager.get_message(message_id)
        assert message['reactions']['👍'] == 1

    def test_add_multiple_reactions(self, manager):
        """Test adding multiple reactions to a message."""
        message_id = manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John",
            message_text="Test message"
        )

        manager.add_reaction(message_id, "👍")
        manager.add_reaction(message_id, "👍")
        manager.add_reaction(message_id, "❤️")

        message = manager.get_message(message_id)
        assert message['reactions']['👍'] == 2
        assert message['reactions']['❤️'] == 1

    def test_remove_reaction(self, manager):
        """Test removing a reaction from a message."""
        message_id = manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John",
            message_text="Test message"
        )

        manager.add_reaction(message_id, "👍")
        manager.add_reaction(message_id, "👍")

        result = manager.add_reaction(message_id, "👍", increment=False)
        assert result is True

        message = manager.get_message(message_id)
        assert message['reactions']['👍'] == 1

    def test_remove_last_reaction(self, manager):
        """Test removing the last instance of a reaction."""
        message_id = manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John",
            message_text="Test message"
        )

        manager.add_reaction(message_id, "👍")
        manager.add_reaction(message_id, "👍", increment=False)

        message = manager.get_message(message_id)
        # Reaction should be removed from dict when count reaches 0
        assert '👍' not in message['reactions']

    def test_add_reaction_to_nonexistent_message(self, manager):
        """Test adding reaction to non-existent message."""
        result = manager.add_reaction(99999, "👍")
        assert result is False

class TestGetMessage:
    """Test retrieving messages."""

    def test_get_existing_message(self, manager):
        """Test getting an existing message."""
        message_id = manager.send_message(
            session_id=1,
            user_id=101,
            user_name="John Doe",
            message_text="Test message"
        )

        message = manager.get_message(message_id)
        assert message is not None
        assert message['message_id'] == message_id
        assert message['user_name'] == "John Doe"
        assert message['message_text'] == "Test message"

    def test_get_nonexistent_message(self, manager):
        """Test getting a non-existent message."""
        message = manager.get_message(99999)
        assert message is None

class TestGetSessionMessages:
    """Test retrieving messages for a session."""

    def test_get_all_messages(self, manager):
        """Test getting all messages for a session."""
        # Send multiple messages
        manager.send_message(1, 101, "John", "Message 1")
        manager.send_message(1, 102, "Jane", "Message 2")
        manager.send_message(1, 103, "Bob", "Message 3")

        messages = manager.get_session_messages(1)
        assert len(messages) == 3

    def test_get_messages_by_type(self, manager):
        """Test filtering messages by type."""
        manager.send_message(1, 101, "John", "Public", message_type='public')
        manager.send_message(1, 102, "Jane", "Private", message_type='private', recipient_id=103)
        manager.send_message(1, 999, "Admin", "Announcement", message_type='announcement')

        public_messages = manager.get_session_messages(1, message_type='public')
        assert len(public_messages) == 1
        assert public_messages[0]['message_type'] == 'public'

    def test_get_messages_by_user(self, manager):
        """Test filtering messages by user."""
        manager.send_message(1, 101, "John", "From John")
        manager.send_message(1, 101, "John", "Also from John")
        manager.send_message(1, 102, "Jane", "From Jane")
        manager.send_message(1, 103, "Bob", "Private to John", message_type='private', recipient_id=101)

        user_messages = manager.get_session_messages(1, user_id=101)
        # Should include messages sent by 101 and messages to 101
        assert len(user_messages) >= 2

    def test_exclude_deleted_messages(self, manager):
        """Test that deleted messages are excluded by default."""
        msg1 = manager.send_message(1, 101, "John", "Keep this")
        msg2 = manager.send_message(1, 102, "Jane", "Delete this")

        manager.delete_message(msg2)

        messages = manager.get_session_messages(1, include_deleted=False)
        assert len(messages) == 1
        assert messages[0]['message_id'] == msg1

    def test_include_deleted_messages(self, manager):
        """Test including deleted messages."""
        manager.send_message(1, 101, "John", "Message 1")
        msg2 = manager.send_message(1, 102, "Jane", "Message 2")
        manager.delete_message(msg2)

        messages = manager.get_session_messages(1, include_deleted=True)
        assert len(messages) == 2

    def test_message_limit(self, manager):
        """Test limiting the number of messages returned."""
        for i in range(10):
            manager.send_message(1, 101, "John", f"Message {i}")

        messages = manager.get_session_messages(1, limit=5)
        assert len(messages) == 5

    def test_messages_ordered_by_timestamp_desc(self, manager):
        """Test that messages are ordered by timestamp descending."""
        msg1 = manager.send_message(1, 101, "John", "First")
        msg2 = manager.send_message(1, 102, "Jane", "Second")
        msg3 = manager.send_message(1, 103, "Bob", "Third")

        messages = manager.get_session_messages(1)
        # Most recent first
        assert messages[0]['message_id'] == msg3
        assert messages[1]['message_id'] == msg2
        assert messages[2]['message_id'] == msg1

class TestGetThreadMessages:
    """Test retrieving thread/reply messages."""

    def test_get_thread_messages(self, manager):
        """Test getting all replies to a message."""
        parent_id = manager.send_message(1, 101, "John", "Original question")

        reply1 = manager.send_message(1, 102, "Jane", "Reply 1", replied_to=parent_id)
        reply2 = manager.send_message(1, 103, "Bob", "Reply 2", replied_to=parent_id)

        thread = manager.get_thread_messages(parent_id)
        assert len(thread) == 2
        assert all(msg['replied_to'] == parent_id for msg in thread)

    def test_get_thread_ordered_by_timestamp_asc(self, manager):
        """Test that thread messages are ordered by timestamp ascending."""
        parent_id = manager.send_message(1, 101, "John", "Original")

        reply1 = manager.send_message(1, 102, "Jane", "First reply", replied_to=parent_id)
        reply2 = manager.send_message(1, 103, "Bob", "Second reply", replied_to=parent_id)

        thread = manager.get_thread_messages(parent_id)
        # Oldest first in thread
        assert thread[0]['message_id'] == reply1
        assert thread[1]['message_id'] == reply2

    def test_get_thread_excludes_deleted(self, manager):
        """Test that deleted replies are excluded."""
        parent_id = manager.send_message(1, 101, "John", "Original")

        reply1 = manager.send_message(1, 102, "Jane", "Keep", replied_to=parent_id)
        reply2 = manager.send_message(1, 103, "Bob", "Delete", replied_to=parent_id)

        manager.delete_message(reply2)

        thread = manager.get_thread_messages(parent_id)
        assert len(thread) == 1
        assert thread[0]['message_id'] == reply1

    def test_get_thread_for_message_with_no_replies(self, manager):
        """Test getting thread for message with no replies."""
        message_id = manager.send_message(1, 101, "John", "No replies")

        thread = manager.get_thread_messages(message_id)
        assert thread == []

class TestSearchMessages:
    """Test message search functionality."""

    def test_search_messages(self, manager):
        """Test searching messages by text."""
        manager.send_message(1, 101, "John", "Python is great")
        manager.send_message(1, 102, "Jane", "I love Python programming")
        manager.send_message(1, 103, "Bob", "JavaScript is cool")

        results = manager.search_messages(1, "Python")
        assert len(results) == 2
        assert all("Python" in msg['message_text'] for msg in results)

    def test_search_case_insensitive(self, manager):
        """Test that search is case-insensitive."""
        manager.send_message(1, 101, "John", "PYTHON is great")
        manager.send_message(1, 102, "Jane", "python is awesome")

        results = manager.search_messages(1, "python")
        assert len(results) == 2

    def test_search_partial_match(self, manager):
        """Test searching with partial match."""
        manager.send_message(1, 101, "John", "Database design")
        manager.send_message(1, 102, "Jane", "Data structures")

        results = manager.search_messages(1, "Data")
        assert len(results) == 2

    def test_search_excludes_deleted(self, manager):
        """Test that search excludes deleted messages."""
        manager.send_message(1, 101, "John", "Python test")
        msg2 = manager.send_message(1, 102, "Jane", "Python example")

        manager.delete_message(msg2)

        results = manager.search_messages(1, "Python")
        assert len(results) == 1

    def test_search_with_limit(self, manager):
        """Test search result limit."""
        for i in range(10):
            manager.send_message(1, 101, "John", f"Python example {i}")

        results = manager.search_messages(1, "Python", limit=5)
        assert len(results) == 5

    def test_search_no_results(self, manager):
        """Test search with no matching results."""
        manager.send_message(1, 101, "John", "JavaScript is cool")

        results = manager.search_messages(1, "Python")
        assert results == []

class TestGetChatStatistics:
    """Test chat statistics retrieval."""

    def test_get_basic_statistics(self, manager):
        """Test getting basic chat statistics."""
        manager.send_message(1, 101, "John", "Message 1", message_type='public')
        manager.send_message(1, 102, "Jane", "Message 2", message_type='public')
        manager.send_message(1, 103, "Bob", "Message 3", message_type='private', recipient_id=101)

        stats = manager.get_chat_statistics(1)
        assert stats['total_messages'] == 3
        assert stats['active_users'] == 3
        assert stats['public_messages'] == 2
        assert stats['private_messages'] == 1

    def test_get_statistics_with_announcements(self, manager):
        """Test statistics include announcement count."""
        manager.send_message(1, 101, "John", "Public message", message_type='public')
        manager.send_message(1, 999, "Instructor", "Announcement", message_type='announcement')

        stats = manager.get_chat_statistics(1)
        assert stats['announcements'] == 1

    def test_get_top_contributors(self, manager):
        """Test getting top message contributors."""
        # User 101 sends 3 messages
        manager.send_message(1, 101, "John", "Message 1")
        manager.send_message(1, 101, "John", "Message 2")
        manager.send_message(1, 101, "John", "Message 3")

        # User 102 sends 2 messages
        manager.send_message(1, 102, "Jane", "Message 1")
        manager.send_message(1, 102, "Jane", "Message 2")

        # User 103 sends 1 message
        manager.send_message(1, 103, "Bob", "Message 1")

        stats = manager.get_chat_statistics(1)
        assert len(stats['top_contributors']) > 0
        # John should be #1
        assert stats['top_contributors'][0]['user_name'] == "John"
        assert stats['top_contributors'][0]['message_count'] == 3

    def test_statistics_exclude_deleted(self, manager):
        """Test that statistics exclude deleted messages."""
        manager.send_message(1, 101, "John", "Keep")
        msg2 = manager.send_message(1, 102, "Jane", "Delete")

        manager.delete_message(msg2)

        stats = manager.get_chat_statistics(1)
        assert stats['total_messages'] == 1

    def test_statistics_for_session_with_no_messages(self, manager):
        """Test statistics for session with no messages."""
        stats = manager.get_chat_statistics(1)
        assert stats['total_messages'] == 0
        assert stats['active_users'] == 0

class TestClearSessionChat:
    """Test clearing all messages for a session."""

    def test_clear_session_chat(self, manager):
        """Test clearing all chat messages for a session."""
        manager.send_message(1, 101, "John", "Message 1")
        manager.send_message(1, 102, "Jane", "Message 2")
        manager.send_message(1, 103, "Bob", "Message 3")

        result = manager.clear_session_chat(1)
        assert result is True

        # All messages should be marked as deleted
        messages = manager.get_session_messages(1, include_deleted=True)
        assert all(msg['is_deleted'] == 1 for msg in messages)

    def test_clear_empty_session(self, manager):
        """Test clearing chat for session with no messages."""
        result = manager.clear_session_chat(1)
        # Should return False if no rows affected
        assert result is False

    def test_clear_nonexistent_session(self, manager):
        """Test clearing chat for non-existent session."""
        result = manager.clear_session_chat(99999)
        assert result is False

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
        manager = ChatManager(db_path="/invalid/path/to/db.db")

        message_id = manager.send_message(1, 101, "John", "Test")
        assert message_id is None

        result = manager.delete_message(1)
        assert result is False

        messages = manager.get_session_messages(1)
        assert messages == []

        stats = manager.get_chat_statistics(1)
        assert stats == {}

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
