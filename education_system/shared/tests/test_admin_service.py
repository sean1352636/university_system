"""Tests for the shared AdminService."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from education_system.shared.admin_portal.admin_service import AdminService


@pytest.fixture()
def temp_dbs(tmp_path):
    """Create temporary DBs for all 4 systems + auth."""
    db_paths = {}
    for system, table, id_col in [
        ("primary", "pupils", "pupil_id"),
        ("secondary", "students", "student_id"),
        ("college", "students", "student_id"),
        ("university", "students", "student_id"),
    ]:
        db_file = tmp_path / f"{system}.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute(
            f"CREATE TABLE {table} ({id_col} INTEGER PRIMARY KEY, name TEXT, status TEXT)"
        )
        conn.execute(f"INSERT INTO {table} (name, status) VALUES ('Alice', 'active')")
        conn.execute(f"INSERT INTO {table} (name, status) VALUES ('Bob', 'graduated')")
        if system != "primary":
            conn.execute("CREATE TABLE staff (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO staff (name) VALUES ('Prof X')")
        conn.commit()
        conn.close()
        db_paths[system] = db_file

    # Auth DB
    auth_db = tmp_path / "auth.db"
    conn = sqlite3.connect(str(auth_db))
    conn.execute(
        """CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT,
            email TEXT,
            password_hash TEXT,
            is_active INTEGER DEFAULT 1,
            last_login TEXT
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
        """CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT,
            created_at TEXT,
            expires_at TEXT
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
            created_at TEXT
        )"""
    )
    # Seed a test user
    conn.execute(
        "INSERT INTO users (username, display_name, email, password_hash, is_active) "
        "VALUES ('testadmin', 'Test Admin', 'admin@test.com', '$2b$12$fake', 1)"
    )
    conn.execute(
        "INSERT INTO user_systems (user_id, system_key, role) VALUES (1, 'university', 'admin')"
    )
    conn.execute(
        "INSERT INTO sessions (user_id, token, created_at, expires_at) "
        "VALUES (1, 'tok_abc123', '2026-01-01 00:00:00', '2099-12-31 23:59:59')"
    )
    conn.commit()
    conn.close()

    return db_paths, auth_db


@pytest.fixture()
def svc(temp_dbs):
    db_paths, auth_db = temp_dbs
    return AdminService(db_paths=db_paths, auth_db=str(auth_db))


class TestSystemHealth:
    def test_returns_all_systems(self, svc):
        health = svc.get_system_health()
        assert len(health) == 4
        systems = {h["system"] for h in health}
        assert systems == {"primary", "secondary", "college", "university"}

    def test_counts_students(self, svc):
        health = svc.get_system_health()
        for h in health:
            assert h["student_count"] == 2
            assert h["db_exists"] is True
            assert h["status"] == "online"

    def test_counts_staff(self, svc):
        health = svc.get_system_health()
        primary = next(h for h in health if h["system"] == "primary")
        uni = next(h for h in health if h["system"] == "university")
        assert primary["staff_count"] == 0  # no staff table in primary test DB
        assert uni["staff_count"] == 1


class TestUserManagement:
    def test_get_user_summary(self, svc):
        summary = svc.get_user_summary()
        assert summary["total_users"] == 1
        assert "university" in summary["by_system"]

    def test_get_all_users(self, svc):
        users = svc.get_all_users()
        assert len(users) == 1
        assert users[0]["username"] == "testadmin"
        assert len(users[0]["systems"]) == 1

    def test_get_all_users_filter_by_system(self, svc):
        assert len(svc.get_all_users(system="university")) == 1
        assert len(svc.get_all_users(system="primary")) == 0

    def test_get_all_users_filter_by_role(self, svc):
        assert len(svc.get_all_users(role="admin")) == 1
        assert len(svc.get_all_users(role="student")) == 0

    def test_create_user(self, svc):
        uid = svc.create_user(
            "newuser", "New User", "new@test.com", "Pass123!",
            [{"system_key": "college", "role": "staff"}],
        )
        assert uid is not None
        users = svc.get_all_users()
        assert len(users) == 2
        new = next(u for u in users if u["username"] == "newuser")
        assert new["display_name"] == "New User"
        assert new["systems"][0]["system_key"] == "college"

    def test_create_duplicate_user_raises(self, svc):
        with pytest.raises(ValueError, match="already exists"):
            svc.create_user("testadmin", "Dup", "dup@test.com", "pw", [])

    def test_update_user(self, svc):
        svc.update_user(1, display_name="Updated Admin", email="updated@test.com")
        users = svc.get_all_users()
        assert users[0]["display_name"] == "Updated Admin"
        assert users[0]["email"] == "updated@test.com"

    def test_deactivate_user(self, svc):
        svc.deactivate_user(1)
        users = svc.get_all_users()
        assert users[0]["is_active"] is False

    def test_reset_password(self, svc):
        # Should not raise
        svc.reset_password(1, "NewPassword123!")

    def test_update_user_systems(self, svc):
        svc.update_user_systems(1, [
            {"system_key": "primary", "role": "admin"},
            {"system_key": "secondary", "role": "staff"},
        ])
        users = svc.get_all_users()
        assert len(users[0]["systems"]) == 2
        sys_keys = {s["system_key"] for s in users[0]["systems"]}
        assert sys_keys == {"primary", "secondary"}


class TestBackup:
    def test_backup_creates_file(self, svc, temp_dbs):
        db_paths, _ = temp_dbs
        backup_path = svc.backup_database("university")
        assert Path(backup_path).exists()
        assert "backup_" in backup_path

    def test_backup_missing_system_raises(self, svc):
        with pytest.raises(ValueError):
            svc.backup_database("nonexistent")


class TestAuditLog:
    def test_empty_audit(self, svc):
        entries = svc.get_audit_summary()
        assert isinstance(entries, list)

    def test_audit_filters(self, svc):
        # Should not raise with any filter combo
        entries = svc.get_audit_summary(
            type_filter="notification",
            search_text="test",
            date_from="2020-01-01",
            date_to="2030-12-31",
        )
        assert isinstance(entries, list)


class TestSessions:
    def test_get_active_sessions(self, svc):
        sessions = svc.get_active_sessions()
        assert len(sessions) >= 1
        assert sessions[0]["username"] == "testadmin"

    def test_force_logout(self, svc):
        svc.force_logout_user(1)
        sessions = svc.get_active_sessions()
        assert len(sessions) == 0


class TestSystemConfig:
    def test_get_system_config(self, svc):
        cfg = svc.get_system_config("university")
        assert cfg["system"] == "university"
        assert cfg["db_exists"] is True
        assert cfg["db_size_mb"] >= 0
