"""Behavioral tests for the Security Desk CLI (``modules.services.cli.security_desk_cli``).

This CLI is interactive: it resolves the current user via ``get_user`` (the shared
``get_current_user`` seam) and drives menus with ``input()`` / ``print()``. The testable
surface is:

* pure helpers (``get_next_ticket_id`` counter, ``get_current_user`` resolution),
* data-layer CRUD (``create_ticket`` / ``get_ticket_by_id`` / ``get_all_tickets`` /
  ``update_ticket`` / ``delete_ticket``),
* menu actions driven with a scripted ``input()`` sequence against a temp DB.

Isolation mirrors the gym CLI tests: repoint the shared ``DEFAULT_DB_PATH`` at a temp
file (``get_connection`` reads it at call time), build the schema via the module's own
``init_security_desk_database()``, and stub the ``get_user`` seam so nothing escapes.
"""

from unittest.mock import patch

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services.cli import security_desk_cli as sd


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def sd_db(tmp_path, monkeypatch):
    """Temp DB + security-desk schema, with a logged-in user and neutralised seams.

    Returns the db path so tests can inspect rows directly.
    """
    db_path = str(tmp_path / "security.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    # Build the tables + seed the counter via the module's own initialiser.
    assert sd.init_security_desk_database() is True

    # A logged-in user by default; tests can override get_user.
    user = {"id": "U001", "username": "bob", "name": "Bob Smith", "email": "bob@uni.ac.uk"}
    monkeypatch.setattr(sd, "get_user", lambda: user)
    return db_path, user


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestTicketIdCounter:
    def test_first_id_shape_and_value(self, sd_db):
        # Seeded counter starts at 1000; first id increments to 1001.
        assert sd.get_next_ticket_id() == "SD-01001"

    def test_counter_increments_and_persists(self, sd_db):
        db_path, _ = sd_db
        assert sd.get_next_ticket_id() == "SD-01001"
        assert sd.get_next_ticket_id() == "SD-01002"
        rows = _rows(db_path, "SELECT counter FROM security_desk_counter WHERE id = 1")
        assert rows[0]["counter"] == 1002


class TestGetCurrentUser:
    def test_returns_authenticated_user(self, sd_db):
        assert sd.get_current_user()["username"] == "bob"

    def test_guest_when_user_none(self, sd_db, monkeypatch):
        monkeypatch.setattr(sd, "get_user", lambda: None)
        user = sd.get_current_user()
        assert user["username"] == "guest"
        assert user["role"] == "guest"

    def test_guest_when_seam_unavailable(self, sd_db, monkeypatch):
        monkeypatch.setattr(sd, "get_user", None)
        assert sd.get_current_user()["username"] == "guest"


# ---------------------------------------------------------------------------
# Data-layer CRUD
# ---------------------------------------------------------------------------

def _sample_ticket(ticket_id="SD-09001"):
    return {
        "id": ticket_id,
        "type": "Help Request",
        "category": "Lockout",
        "priority": "High",
        "status": "Open",
        "subject": "Locked out",
        "description": "Cannot get into the lab",
        "location": "Building A",
        "user_id": "U001",
        "user_name": "Bob Smith",
        "user_email": "bob@uni.ac.uk",
        "created_at": "2026-07-22 10:00:00",
        "updated_at": "2026-07-22 10:00:00",
    }


class TestCrud:
    def test_create_and_fetch_roundtrip(self, sd_db):
        db_path, _ = sd_db
        assert sd.create_ticket(_sample_ticket()) is True

        fetched = sd.get_ticket_by_id("SD-09001")
        assert fetched is not None
        assert fetched["subject"] == "Locked out"
        assert fetched["priority"] == "High"

        assert _rows(db_path, "SELECT id FROM security_desk_tickets") == [{"id": "SD-09001"}]

    def test_get_all_tickets_returns_created(self, sd_db):
        sd.create_ticket(_sample_ticket("SD-09001"))
        sd.create_ticket(_sample_ticket("SD-09002"))
        ids = {t["id"] for t in sd.get_all_tickets()}
        assert ids == {"SD-09001", "SD-09002"}

    def test_get_ticket_by_id_missing_returns_none(self, sd_db):
        assert sd.get_ticket_by_id("SD-DOESNOTEXIST") is None

    def test_update_ticket_happy_path(self, sd_db):
        db_path, _ = sd_db
        sd.create_ticket(_sample_ticket())
        assert sd.update_ticket("SD-09001", {"status": "Resolved"}) is True
        rows = _rows(db_path, "SELECT status FROM security_desk_tickets WHERE id = 'SD-09001'")
        assert rows[0]["status"] == "Resolved"

    def test_update_ticket_rejects_unknown_column(self, sd_db):
        db_path, _ = sd_db
        sd.create_ticket(_sample_ticket())
        # Column not in the allow-list -> ValueError caught -> False, nothing written.
        assert sd.update_ticket("SD-09001", {"id = 'x'; DROP TABLE": "boom"}) is False
        rows = _rows(db_path, "SELECT status FROM security_desk_tickets WHERE id = 'SD-09001'")
        assert rows[0]["status"] == "Open"

    def test_delete_ticket(self, sd_db):
        db_path, _ = sd_db
        sd.create_ticket(_sample_ticket())
        assert sd.delete_ticket("SD-09001") is True
        assert _rows(db_path, "SELECT id FROM security_desk_tickets") == []


# ---------------------------------------------------------------------------
# create_ticket_menu (scripted input)
# ---------------------------------------------------------------------------

class TestCreateTicketMenu:
    @patch("builtins.print")
    def test_happy_path_persists_ticket(self, _p, sd_db):
        db_path, _ = sd_db
        # type=1 (Help Request), category, subject, description, location, priority=3 (High)
        script = ["1", "Lockout", "Locked out of room", "Door jammed", "Building A", "3"]
        with patch("builtins.input", side_effect=script):
            sd.create_ticket_menu()

        rows = _rows(db_path, "SELECT * FROM security_desk_tickets")
        assert len(rows) == 1
        row = rows[0]
        assert row["id"].startswith("SD-")
        assert row["type"] == "Help Request"
        assert row["priority"] == "High"
        assert row["status"] == "Open"
        assert row["subject"] == "Locked out of room"
        assert row["user_name"] == "Bob Smith"

    @patch("builtins.print")
    def test_blank_subject_writes_nothing(self, _p, sd_db):
        db_path, _ = sd_db
        # subject blank -> guard fires, returns without creating.
        script = ["1", "Lockout", "", "desc"]
        with patch("builtins.input", side_effect=script):
            sd.create_ticket_menu()
        assert _rows(db_path, "SELECT * FROM security_desk_tickets") == []


# ---------------------------------------------------------------------------
# read views run cleanly
# ---------------------------------------------------------------------------

class TestReadViews:
    @patch("builtins.print")
    def test_list_tickets_menu_empty(self, _p, sd_db):
        # No tickets: must not raise.
        assert sd.list_tickets_menu() is None

    @patch("builtins.print")
    def test_list_tickets_menu_with_data(self, _p, sd_db):
        sd.create_ticket(_sample_ticket())
        assert sd.list_tickets_menu() is None

    @patch("builtins.print")
    def test_statistics_menu_with_data(self, _p, sd_db):
        sd.create_ticket(_sample_ticket("SD-09001"))
        sd.create_ticket(_sample_ticket("SD-09002"))
        assert sd.statistics_menu() is None
