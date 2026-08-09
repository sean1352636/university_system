"""Tests for the shared CrossSystemNotificationService."""

import sqlite3

import pytest

from education_system.platform.features.notifications.service import CrossSystemNotificationService


@pytest.fixture()
def auth_db(tmp_path):
    """Create a temporary auth DB with required tables."""
    db_file = tmp_path / "auth.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        """CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            display_name TEXT,
            email TEXT,
            password_hash TEXT,
            is_active INTEGER DEFAULT 1
        )"""
    )
    conn.execute(
        """CREATE TABLE user_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            system_key TEXT,
            role TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cross_system_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_user_id INTEGER,
            sender_system TEXT,
            recipient_user_id INTEGER,
            recipient_system TEXT,
            title TEXT,
            message TEXT,
            priority TEXT DEFAULT 'normal',
            is_read INTEGER DEFAULT 0,
            read_at TEXT,
            created_at TEXT
        )"""
    )
    # Seed users
    conn.execute(
        "INSERT INTO users (username, display_name, password_hash, is_active) "
        "VALUES ('admin1', 'Admin One', 'hash', 1)"
    )
    conn.execute(
        "INSERT INTO users (username, display_name, password_hash, is_active) "
        "VALUES ('student1', 'Student One', 'hash', 1)"
    )
    conn.execute(
        "INSERT INTO users (username, display_name, password_hash, is_active) "
        "VALUES ('student2', 'Student Two', 'hash', 1)"
    )
    conn.execute("INSERT INTO user_systems (user_id, system_key, role) VALUES (1, 'university', 'admin')")
    conn.execute("INSERT INTO user_systems (user_id, system_key, role) VALUES (2, 'university', 'student')")
    conn.execute("INSERT INTO user_systems (user_id, system_key, role) VALUES (3, 'university', 'student')")
    conn.commit()
    conn.close()
    return str(db_file)


@pytest.fixture()
def svc(auth_db):
    return CrossSystemNotificationService(db_path=auth_db)


class TestSendNotification:
    def test_send_returns_dict(self, svc):
        result = svc.send(
            sender_user_id=1,
            sender_system="superadmin",
            recipient_user_id=2,
            recipient_system="university",
            title="Test Notification",
            message="Hello!",
        )
        assert isinstance(result, dict)
        assert result["title"] == "Test Notification"

    def test_send_with_priority(self, svc):
        result = svc.send(
            sender_user_id=1,
            sender_system="superadmin",
            recipient_user_id=2,
            recipient_system="university",
            title="Urgent",
            priority="high",
        )
        assert result["priority"] == "high"


class TestSendToRole:
    def test_broadcasts_to_role(self, svc):
        count = svc.send_to_role(
            sender_user_id=1,
            sender_system="superadmin",
            target_system="university",
            target_role="student",
            title="Broadcast Test",
        )
        assert count == 2  # student1 + student2


class TestRetrieve:
    def test_get_unread_empty(self, svc):
        unread = svc.get_unread(user_id=2)
        assert unread == []

    def test_get_unread_after_send(self, svc):
        svc.send(1, "superadmin", 2, "university", "Msg")
        unread = svc.get_unread(2)
        assert len(unread) == 1
        assert unread[0]["title"] == "Msg"

    def test_get_unread_count(self, svc):
        svc.send(1, "superadmin", 2, "university", "A")
        svc.send(1, "superadmin", 2, "university", "B")
        assert svc.get_unread_count(2) == 2

    def test_get_all_with_limit(self, svc):
        for i in range(5):
            svc.send(1, "superadmin", 2, "university", f"Msg {i}")
        all_notifs = svc.get_all(2, limit=3)
        assert len(all_notifs) == 3


class TestMarkRead:
    def test_mark_read(self, svc):
        result = svc.send(1, "superadmin", 2, "university", "ToRead")
        nid = result["id"]
        svc.mark_read(nid)
        unread = svc.get_unread(2)
        assert len(unread) == 0

    def test_mark_all_read(self, svc):
        svc.send(1, "superadmin", 2, "university", "A")
        svc.send(1, "superadmin", 2, "university", "B")
        assert svc.get_unread_count(2) == 2
        svc.mark_all_read(2)
        assert svc.get_unread_count(2) == 0
