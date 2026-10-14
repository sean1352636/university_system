"""Mobile App (PWA) against a real database, not mocks.

The sibling suite mocks every connection, so a mismatch between the code's
SQL and the actual table shape is invisible to it — which is how the module
shipped queries for ``is_active``, ``theme``, ``ip_address`` and
``mobile_analytics.device_id`` against live tables that had none of them,
plus an insert that failed with ``FOREIGN KEY constraint failed`` whenever an
unknown user id was typed.

These tests run the real statements against a temporary SQLite database
created from the *drifted* schema, so any future divergence fails here
instead of in the CLI.
"""

from __future__ import annotations

import builtins
import sqlite3
from contextlib import contextmanager

import pytest

from education_system.systems.university.domains.operations.domain.campus.mobility.services import (  # noqa: E501
    mobile_app_pwa_core as core,
)

# The shape these tables actually had in the running database: no is_active,
# no ip_address/location, no theme block, no analytics device_id.
DRIFTED_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    role TEXT
);
CREATE TABLE mobile_devices (
    device_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    device_name TEXT,
    device_type TEXT,
    os_version TEXT,
    app_version TEXT,
    push_token TEXT,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE mobile_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    device_id INTEGER,
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    logout_time TIMESTAMP,
    session_token TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id) ON DELETE CASCADE
);
CREATE TABLE mobile_preferences (
    pref_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    notifications_enabled BOOLEAN DEFAULT 1,
    dark_mode BOOLEAN DEFAULT 0,
    language TEXT DEFAULT 'en',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE mobile_analytics (
    analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    event_type TEXT NOT NULL,
    event_data TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE offline_sync_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    data TEXT NOT NULL,
    sync_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP
);
INSERT INTO users (id, username, role) VALUES (1, 'admin', 'admin'), (2, 'S12345', 'student');
"""


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """A drifted database wired into the module under test."""
    path = tmp_path / "mobile.db"
    seed = sqlite3.connect(path)
    seed.executescript(DRIFTED_SCHEMA)
    seed.commit()
    seed.close()

    def _connect():
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _transaction():
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    monkeypatch.setattr(core, "get_connection", _connect)
    monkeypatch.setattr(core, "transaction", _transaction)
    monkeypatch.setattr(core, "log_activity", lambda *a, **k: None)
    return _connect


def _answer(monkeypatch, *responses):
    it = iter(responses)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": str(next(it)))


# ---------------------------------------------------------------------------
# Schema healing
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_drifted_tables_are_missing_the_columns_the_code_queries(db):
    """Guards the premise: without the repair these queries cannot work."""
    with db() as conn:
        assert "is_active" not in _columns(conn, "mobile_devices")
        assert "ip_address" not in _columns(conn, "mobile_sessions")
        assert "theme" not in _columns(conn, "mobile_preferences")
        assert "device_id" not in _columns(conn, "mobile_analytics")


@pytest.mark.unit
def test_ensure_columns_adds_every_missing_column(db):
    conn = db()
    try:
        added = core._ensure_mobile_columns(conn)
        conn.commit()

        assert "is_active" in _columns(conn, "mobile_devices")
        assert {"ip_address", "location"} <= _columns(conn, "mobile_sessions")
        assert {"theme", "offline_mode_enabled", "data_saver_mode",
                "auto_sync"} <= _columns(conn, "mobile_preferences")
        assert "device_id" in _columns(conn, "mobile_analytics")
        assert len(added) == 8
    finally:
        conn.close()


@pytest.mark.unit
def test_ensure_columns_is_idempotent(db):
    conn = db()
    try:
        core._ensure_mobile_columns(conn)
        conn.commit()
        assert core._ensure_mobile_columns(conn) == []
    finally:
        conn.close()


@pytest.mark.unit
def test_ensure_columns_skips_a_missing_table(tmp_path):
    """A table that does not exist is left for CREATE TABLE, not ALTERed."""
    conn = sqlite3.connect(tmp_path / "empty.db")
    try:
        assert core._ensure_mobile_columns(conn) == []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The operations that were failing
# ---------------------------------------------------------------------------

@pytest.fixture()
def healed(db):
    conn = db()
    core._ensure_mobile_columns(conn)
    conn.commit()
    conn.close()
    return db


@pytest.mark.unit
def test_register_then_view_then_deactivate(healed, monkeypatch, capsys):
    monkeypatch.setattr(core, "_prompt_known_id", lambda *a, **k: 2)
    _answer(monkeypatch, "2", "iPhone 13", "17.1", "")
    core.register_mobile_device()
    assert "registered successfully" in capsys.readouterr().out

    # Previously "no such column: is_active", then a NULL last_active blew up
    # the column formatting.
    core.view_mobile_devices()
    out = capsys.readouterr().out
    assert "iPhone 13" in out and "Active" in out

    monkeypatch.setattr(core, "_prompt_known_id", lambda *a, **k: 1)
    _answer(monkeypatch, "yes")
    core.deactivate_mobile_device()
    assert "deactivated successfully" in capsys.readouterr().out

    with healed() as conn:
        assert conn.execute(
            "SELECT is_active FROM mobile_devices WHERE device_id = 1"
        ).fetchone()[0] == 0


@pytest.mark.unit
def test_registering_against_an_unknown_user_is_impossible(healed, monkeypatch, capsys):
    """The FK error came from accepting any id; the picker only offers real ones."""
    _answer(monkeypatch, "9999", "")   # rejected, then blank to cancel
    core.register_mobile_device()

    out = capsys.readouterr().out
    assert "not a valid" in out
    assert "cancelled" in out.lower()
    with healed() as conn:
        assert conn.execute("SELECT COUNT(*) FROM mobile_devices").fetchone()[0] == 0


@pytest.mark.unit
def test_session_create_and_view_use_ip_address(healed, monkeypatch, capsys):
    monkeypatch.setattr(core, "_prompt_known_id", lambda *a, **k: 2)
    _answer(monkeypatch, "2", "iPhone 13", "17.1", "")
    core.register_mobile_device()
    capsys.readouterr()

    ids = iter([1, 2])   # device 1, then user 2

    def _next_id(*a, **k):
        return next(ids)

    monkeypatch.setattr(core, "_prompt_known_id", _next_id)
    _answer(monkeypatch, "10.0.0.5", "Campus")
    core.create_mobile_session()          # was: no column named ip_address
    assert "created successfully" in capsys.readouterr().out

    core.view_active_mobile_sessions()    # was: no such column: ms.ip_address
    assert "10.0.0.5" in capsys.readouterr().out


@pytest.mark.unit
def test_preferences_round_trip_uses_theme(healed, monkeypatch, capsys):
    monkeypatch.setattr(core, "_prompt_known_id", lambda *a, **k: 2)
    _answer(monkeypatch, "2", "y", "y", "n", "y")
    core.update_mobile_preferences()
    assert "updated successfully" in capsys.readouterr().out

    core.view_mobile_preferences()        # was: no such column: theme
    out = capsys.readouterr().out
    assert "Theme: dark" in out


@pytest.mark.unit
def test_analytics_event_records_the_device(healed, monkeypatch, capsys):
    monkeypatch.setattr(core, "_prompt_known_id", lambda *a, **k: 2)
    _answer(monkeypatch, "2", "iPhone 13", "17.1", "")
    core.register_mobile_device()
    capsys.readouterr()

    monkeypatch.setattr(core, "_prompt_known_id", lambda *a, **k: 1)
    _answer(monkeypatch, "1", '{"page":"home"}')
    core.log_mobile_event()               # was: no column named device_id
    assert "logged successfully" in capsys.readouterr().out

    core.view_mobile_analytics()          # was: no such column: is_active
    out = capsys.readouterr().out
    assert "page_view: 1" in out

    with healed() as conn:
        assert conn.execute(
            "SELECT device_id FROM mobile_analytics"
        ).fetchone()[0] == 1


# ---------------------------------------------------------------------------
# Id validation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_picker_accepts_only_ids_that_exist(db, monkeypatch, capsys):
    _answer(monkeypatch, "77", "2")
    chosen = core._prompt_known_id("User ID", "SELECT id, username FROM users")

    assert chosen == 2
    assert "not a valid User ID" in capsys.readouterr().out


@pytest.mark.unit
def test_picker_blank_backs_out(db, monkeypatch):
    _answer(monkeypatch, "")
    assert core._prompt_known_id("User ID", "SELECT id, username FROM users") is None


@pytest.mark.unit
def test_picker_reports_when_there_is_nothing_to_choose(db, monkeypatch, capsys):
    assert core._prompt_known_id(
        "Device ID",
        "SELECT device_id, device_name FROM mobile_devices",
        empty_message="No active devices to deactivate",
    ) is None
    assert "No active devices to deactivate" in capsys.readouterr().out


@pytest.mark.unit
def test_picker_optional_allows_blank_without_listing_error(db, monkeypatch):
    _answer(monkeypatch, "")
    assert core._prompt_known_id(
        "Device ID",
        "SELECT device_id, device_name FROM mobile_devices",
        optional=True,
    ) is None
