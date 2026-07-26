"""Behavioral tests for the Legal Services CLI (``modules.services.cli.legal_services_cli``).

This CLI resolves the current user via the ``get_user`` seam (from
``shared_context.get_current_user``) and falls back to a "guest" dict. Isolation:
repoint the shared ``DEFAULT_DB_PATH`` at a temp file (``get_connection`` reads
it at call time), build the schema via the module's own ``init_legal_database()``,
and patch the ``get_user`` seam.
"""

from unittest.mock import patch

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.cli.shell.services import legal_services_cli as legal_cli


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def legal_db(tmp_path, monkeypatch):
    """Temp DB + legal schema and a logged-in user seam."""
    db_path = str(tmp_path / "legal.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert legal_cli.init_legal_database() is True

    monkeypatch.setattr(
        legal_cli, "get_user",
        lambda: {"name": "Attorney Ada", "username": "ada", "role": "staff", "id": "AT1"},
    )
    return db_path


# ---------------------------------------------------------------------------
# Pure helpers & catalog
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_generate_case_number_shape(self):
        assert legal_cli.generate_case_number().startswith("LEGAL-")

    def test_catalogs_wellformed(self):
        assert "Contract Dispute" in legal_cli.CASE_TYPES
        assert "Pending" in legal_cli.CASE_STATUSES
        assert "Scheduled" in legal_cli.CONSULTATION_STATUSES


# ---------------------------------------------------------------------------
# get_current_user (3 cases)
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_user_from_seam(self, legal_db):
        assert legal_cli.get_current_user()["name"] == "Attorney Ada"

    def test_guest_when_seam_returns_none(self, monkeypatch):
        monkeypatch.setattr(legal_cli, "get_user", lambda: None)
        assert legal_cli.get_current_user()["username"] == "guest"

    def test_guest_when_seam_unavailable(self, monkeypatch):
        monkeypatch.setattr(legal_cli, "get_user", None)
        assert legal_cli.get_current_user()["role"] == "guest"


# ---------------------------------------------------------------------------
# create_case / create_case_menu (write action)
# ---------------------------------------------------------------------------

class TestCreateCase:
    @patch("builtins.print")
    def test_create_case_persists(self, _p, legal_db):
        db_path = legal_db
        case_data = {
            "case_number": legal_cli.generate_case_number(),
            "client_name": "Jane Doe",
            "client_email": "jane@x.com",
            "case_type": "Contract Dispute",
            "status": "Pending",
            "description": "Dispute over lease",
            "assigned_attorney": "Attorney Ada",
            "created_date": "2026-01-01 09:00:00",
            "updated_date": "2026-01-01 09:00:00",
        }
        assert legal_cli.create_case(case_data) is True
        rows = _rows(db_path, "SELECT * FROM legal_cases WHERE client_name = 'Jane Doe'")
        assert len(rows) == 1
        assert rows[0]["case_type"] == "Contract Dispute"
        assert rows[0]["status"] == "Pending"

    @patch("builtins.print")
    def test_create_case_menu_happy_path(self, _p, legal_db):
        db_path = legal_db
        # client_name, email, phone, student_id, type_choice(1=Contract Dispute),
        # description, attorney
        script = ["John Roe", "john@x.com", "555-0000", "S5", "1", "Contract issue", "Mr Smith"]
        with patch("builtins.input", side_effect=script):
            legal_cli.create_case_menu()

        rows = _rows(db_path, "SELECT * FROM legal_cases WHERE client_name = 'John Roe'")
        assert len(rows) == 1
        assert rows[0]["case_type"] == "Contract Dispute"
        assert rows[0]["assigned_attorney"] == "Mr Smith"
        assert rows[0]["status"] == "Pending"

    @patch("builtins.print")
    def test_create_case_menu_requires_client_name(self, _p, legal_db):
        db_path = legal_db
        with patch("builtins.input", side_effect=[""]):
            legal_cli.create_case_menu()
        assert _rows(db_path, "SELECT * FROM legal_cases") == []

    def test_update_case_rejects_unknown_column(self, legal_db):
        assert legal_cli.update_case(9999, {"not_a_column": "x"}) is False


# ---------------------------------------------------------------------------
# consultations + read views
# ---------------------------------------------------------------------------

class TestConsultationsAndViews:
    @patch("builtins.print")
    def test_schedule_consultation_persists(self, _p, legal_db):
        db_path = legal_db
        consult_data = {
            "case_id": None,
            "client_name": "Kelly",
            "client_email": "kelly@x.com",
            "consultation_date": "2026-02-01",
            "consultation_time": "10:00",
            "status": "Scheduled",
            "attorney": "Ada",
            "notes": "",
            "created_date": "2026-01-01 09:00:00",
        }
        assert legal_cli.schedule_consultation(consult_data) is True
        rows = _rows(db_path, "SELECT * FROM legal_consultations WHERE client_name = 'Kelly'")
        assert len(rows) == 1
        assert rows[0]["status"] == "Scheduled"

    @patch("builtins.print")
    def test_list_cases_menu_empty(self, _p, legal_db):
        assert legal_cli.list_cases_menu() is None

    @patch("builtins.print")
    def test_view_consultations_menu_empty(self, _p, legal_db):
        assert legal_cli.view_consultations_menu() is None
