"""Tests for the advanced housing CLI helpers.

The module is largely an interactive menu system; here we cover the pure/thin
helpers: prompt helpers (with patched ``input``), permission gating, the
error-tolerant DB lookups (which return safe defaults when tables are absent),
and ``_find_first_room`` against a self-contained in-memory cursor.
"""

from unittest.mock import MagicMock

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.domain.campus.housing.services.housing_accommodation import (
    extended_cli as ec,
    common as _common,
)


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

class TestPromptHelpers:
    def test_prompt_returns_input(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *a: "  hello  ")
        assert ec._prompt("Name") == "hello"

    def test_prompt_uses_default_when_blank(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *a: "")
        assert ec._prompt("Name", default="fallback") == "fallback"

    def test_yes_no_true(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *a: "y")
        assert ec._yes_no("Proceed?") is True

    def test_yes_no_default_on_blank(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda *a: "")
        assert ec._yes_no("Proceed?", default=True) is True
        assert ec._yes_no("Proceed?", default=False) is False

    def test_print_table_empty(self, capsys):
        ec._print_table([], [("k", "Header", 10)])
        assert "(no rows)" in capsys.readouterr().out

    def test_print_table_rows(self, capsys):
        ec._print_table([{"k": "value"}], [("k", "Header", 10)])
        out = capsys.readouterr().out
        assert "Header" in out
        assert "value" in out


# ---------------------------------------------------------------------------
# Permission / user helpers
# ---------------------------------------------------------------------------

class TestAuthHelpers:
    def test_require_permission_no_auth(self, monkeypatch, capsys):
        monkeypatch.setattr(_common, "auth", None)
        assert ec._require_permission("manage_accommodations") is False
        assert "logged in" in capsys.readouterr().out

    def test_require_permission_denied(self, monkeypatch):
        auth = MagicMock()
        auth.current_user = {"username": "bob"}
        auth.check_permission.return_value = False
        monkeypatch.setattr(_common, "auth", auth)
        assert ec._require_permission("manage_accommodations") is False

    def test_require_permission_granted(self, monkeypatch):
        auth = MagicMock()
        auth.current_user = {"username": "bob"}
        auth.check_permission.return_value = True
        monkeypatch.setattr(_common, "auth", auth)
        assert ec._require_permission("manage_accommodations") is True

    def test_current_user_from_auth(self, monkeypatch):
        auth = MagicMock()
        auth.current_user = {"username": "alice"}
        monkeypatch.setattr(_common, "auth", auth)
        assert ec._current_user() == "alice"

    def test_current_user_fallback(self, monkeypatch):
        monkeypatch.setattr(_common, "auth", None)
        assert ec._current_user() == "housing"


# ---------------------------------------------------------------------------
# Error-tolerant DB lookups (isolated DB lacks the housing tables)
# ---------------------------------------------------------------------------

class TestErrorTolerantLookups:
    def test_held_deposit_defaults_to_zero(self, temp_db):
        assert ec._moveout_held_deposit("A1") == 0.0

    def test_list_deductions_defaults_to_empty(self, temp_db):
        assert ec._moveout_list_deductions("A1") == []

    def test_latest_inspection_defaults_to_none(self, temp_db):
        assert ec._latest_moveout_inspection("R1") is None


# ---------------------------------------------------------------------------
# _find_first_room
# ---------------------------------------------------------------------------

class TestFindFirstRoom:
    def _conn(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE housing_rooms (
                room_id TEXT, building_id TEXT, room_number TEXT,
                floor_number INTEGER, room_type TEXT, monthly_rent REAL, status TEXT
            )
        """)
        return conn

    def test_prefers_matching_building(self):
        conn = self._conn()
        conn.execute("INSERT INTO housing_rooms VALUES ('R1', 'B1', '101', 1, 'Single', 500, 'Available')")
        conn.execute("INSERT INTO housing_rooms VALUES ('R2', 'B2', '201', 2, 'Single', 450, 'Available')")
        conn.commit()
        room = ec._find_first_room(conn.cursor(), "B2", "Single")
        assert room[0] == "R2"
        conn.close()

    def test_falls_back_to_any_building(self):
        conn = self._conn()
        conn.execute("INSERT INTO housing_rooms VALUES ('R3', 'B9', '301', 3, 'Double', 600, 'Available')")
        conn.commit()
        # No room in preferred building B1, but a Double exists elsewhere
        room = ec._find_first_room(conn.cursor(), "B1", "Double")
        assert room[0] == "R3"
        conn.close()

    def test_none_when_no_available_room(self):
        conn = self._conn()
        conn.execute("INSERT INTO housing_rooms VALUES ('R4', 'B1', '401', 4, 'Single', 500, 'Occupied')")
        conn.commit()
        assert ec._find_first_room(conn.cursor(), "B1", "Single") is None
        conn.close()
