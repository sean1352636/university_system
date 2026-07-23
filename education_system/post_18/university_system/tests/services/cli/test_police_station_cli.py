"""Behavioral tests for the Police Station CLI (``modules.services.cli.police_station_cli``).

This CLI resolves the current user via the ``get_user`` seam (from
``shared_context.get_current_user``) and falls back to a "guest" dict. Isolation:
repoint the shared ``DEFAULT_DB_PATH`` at a temp file (``get_connection`` reads
it at call time), build the schema via the module's own ``init_police_database()``,
and patch the ``get_user`` seam.
"""

from unittest.mock import patch

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services.cli import police_station_cli as police_cli


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def police_db(tmp_path, monkeypatch):
    """Temp DB + police schema and a logged-in user seam."""
    db_path = str(tmp_path / "police.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert police_cli.init_police_database() is True

    monkeypatch.setattr(
        police_cli, "get_user",
        lambda: {"name": "Officer Jane", "username": "jane", "role": "staff", "id": "OF1"},
    )
    return db_path


# ---------------------------------------------------------------------------
# Pure helpers & catalog
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_get_next_case_id_shape(self, police_db):
        assert police_cli.get_next_case_id().startswith("CASE-")

    def test_get_next_case_id_increments(self, police_db):
        first = police_cli.get_next_case_id()
        second = police_cli.get_next_case_id()
        assert first != second

    def test_catalogs_wellformed(self):
        assert "Theft" in police_cli.INCIDENT_TYPES
        assert "Main Library" in police_cli.CAMPUS_LOCATIONS
        assert "Active Threat" in police_cli.EMERGENCY_TYPES


# ---------------------------------------------------------------------------
# get_current_user (3 cases)
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_user_from_seam(self, police_db):
        assert police_cli.get_current_user()["name"] == "Officer Jane"

    def test_guest_when_seam_returns_none(self, monkeypatch):
        monkeypatch.setattr(police_cli, "get_user", lambda: None)
        assert police_cli.get_current_user()["username"] == "guest"

    def test_guest_when_seam_unavailable(self, monkeypatch):
        monkeypatch.setattr(police_cli, "get_user", None)
        assert police_cli.get_current_user()["role"] == "guest"


# ---------------------------------------------------------------------------
# create_case / create_case_menu (write action)
# ---------------------------------------------------------------------------

class TestCreateCase:
    @patch("builtins.print")
    def test_create_case_persists(self, _p, police_db):
        db_path = police_db
        case_data = {
            "id": police_cli.get_next_case_id(),
            "title": "Stolen bike",
            "type": "Bike Theft",
            "status": "Open",
            "priority": "High",
            "officer": "Officer Jane",
            "location": "Parking Lot A",
            "description": "Bike taken from rack",
            "date": "2026-01-01",
            "created_at": "2026-01-01 09:00:00",
            "updated_at": "2026-01-01 09:00:00",
        }
        assert police_cli.create_case(case_data) is True
        rows = _rows(db_path, "SELECT * FROM police_cases WHERE id = ?", (case_data["id"],))
        assert len(rows) == 1
        assert rows[0]["title"] == "Stolen bike"
        assert rows[0]["status"] == "Open"

    @patch("builtins.print")
    def test_create_case_menu_happy_path(self, _p, police_db):
        db_path = police_db
        # title, incident_type(1=Theft), location(1=Main Library), description,
        # priority(3=High), officer, student_involved(no)
        script = ["Laptop theft", "1", "1", "Taken from library", "3", "Officer Jane", "no"]
        with patch("builtins.input", side_effect=script):
            police_cli.create_case_menu()

        rows = _rows(db_path, "SELECT * FROM police_cases WHERE title = 'Laptop theft'")
        assert len(rows) == 1
        assert rows[0]["type"] == "Theft"
        assert rows[0]["location"] == "Main Library"
        assert rows[0]["priority"] == "High"
        assert rows[0]["status"] == "Open"

    @patch("builtins.print")
    def test_create_case_menu_requires_title(self, _p, police_db):
        db_path = police_db
        with patch("builtins.input", side_effect=[""]):
            police_cli.create_case_menu()
        assert _rows(db_path, "SELECT * FROM police_cases") == []

    def test_update_case_rejects_unknown_column(self, police_db):
        # The allowed-column guard must refuse an unexpected field.
        assert police_cli.update_case("CASE-99999", {"not_a_column": "x"}) is False


# ---------------------------------------------------------------------------
# read views run cleanly
# ---------------------------------------------------------------------------

class TestReadViews:
    @patch("builtins.print")
    def test_list_cases_menu_empty(self, _p, police_db):
        assert police_cli.list_cases_menu() is None

    @patch("builtins.print")
    def test_get_all_cases_reflects_writes(self, _p, police_db):
        assert police_cli.get_all_cases() == []
        police_cli.create_case({
            "id": police_cli.get_next_case_id(), "title": "T", "type": "Other",
            "status": "Open", "priority": "Low", "officer": "X", "location": "Quad",
            "description": "d", "date": "2026-01-01",
            "created_at": "2026-01-01 00:00:00", "updated_at": "2026-01-01 00:00:00",
        })
        assert len(police_cli.get_all_cases()) == 1
