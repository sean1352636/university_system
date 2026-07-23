"""Behavioral tests for the Train Station CLI (``modules.services.cli.train_station_cli``).

This CLI resolves the current user via the ``get_user`` seam (imported from
``shared_context.get_current_user``) and falls back to a "guest" dict when no
user is available. Isolation: repoint the shared ``DEFAULT_DB_PATH`` at a temp
file (``get_connection`` reads it at call time), build the schema via the
module's own ``init_train_database()`` (which also seeds sample services), and
patch the ``get_user`` seam.
"""

from unittest.mock import patch

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services.cli import train_station_cli as train_cli


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def train_db(tmp_path, monkeypatch):
    """Temp DB + train schema (with seeded services) and a logged-in user seam."""
    db_path = str(tmp_path / "train.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert train_cli.init_train_database() is True

    monkeypatch.setattr(
        train_cli, "get_user",
        lambda: {"name": "Tess", "username": "tess", "role": "student", "id": "S9"},
    )
    return db_path


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_generate_ticket_number_shape(self):
        assert train_cli.generate_ticket_number().startswith("TKT-")

    def test_generate_receipt_number_shape(self):
        assert train_cli.generate_receipt_number().startswith("RCP-")

    def test_ticket_numbers_unique(self):
        assert train_cli.generate_ticket_number() != train_cli.generate_ticket_number()


# ---------------------------------------------------------------------------
# get_current_user (3 cases)
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_user_from_seam(self, train_db):
        assert train_cli.get_current_user()["name"] == "Tess"

    def test_guest_when_seam_returns_none(self, monkeypatch):
        monkeypatch.setattr(train_cli, "get_user", lambda: None)
        assert train_cli.get_current_user()["username"] == "guest"

    def test_guest_when_seam_unavailable(self, monkeypatch):
        monkeypatch.setattr(train_cli, "get_user", None)
        assert train_cli.get_current_user()["role"] == "guest"


# ---------------------------------------------------------------------------
# purchase / book_ticket_menu (write action)
# ---------------------------------------------------------------------------

class TestBooking:
    @patch("builtins.print")
    def test_purchase_ticket_persists_and_decrements_seats(self, _p, train_db):
        db_path = train_db
        before = _rows(db_path, "SELECT available_seats FROM train_station_services WHERE id = 1")[0]
        ticket_id, ticket_number, receipt_number = train_cli.purchase_ticket(1, "Alice", "Card", 89.50)

        assert ticket_id is not None
        assert ticket_number.startswith("TKT-")
        assert receipt_number.startswith("RCP-")

        tickets = _rows(db_path, "SELECT * FROM train_station_tickets WHERE ticket_number = ?", (ticket_number,))
        assert len(tickets) == 1
        assert tickets[0]["passenger_name"] == "Alice"

        receipts = _rows(db_path, "SELECT * FROM train_station_receipts WHERE receipt_number = ?", (receipt_number,))
        assert len(receipts) == 1

        after = _rows(db_path, "SELECT available_seats FROM train_station_services WHERE id = 1")[0]
        assert after["available_seats"] == before["available_seats"] - 1

    @patch("builtins.print")
    def test_book_menu_happy_path(self, _p, train_db):
        db_path = train_db
        # service id, passenger name (blank -> default "Tess"), payment choice, confirm yes
        script = ["1", "", "2", "yes"]
        with patch("builtins.input", side_effect=script):
            train_cli.book_ticket_menu()

        tickets = _rows(db_path, "SELECT * FROM train_station_tickets")
        assert len(tickets) == 1
        assert tickets[0]["passenger_name"] == "Tess"
        assert tickets[0]["payment_method"] == "Card"

    @patch("builtins.print")
    def test_book_menu_invalid_service_writes_nothing(self, _p, train_db):
        db_path = train_db
        with patch("builtins.input", side_effect=["abc"]):
            train_cli.book_ticket_menu()
        assert _rows(db_path, "SELECT * FROM train_station_tickets") == []

    @patch("builtins.print")
    def test_book_menu_declined_writes_nothing(self, _p, train_db):
        db_path = train_db
        with patch("builtins.input", side_effect=["1", "", "2", "no"]):
            train_cli.book_ticket_menu()
        assert _rows(db_path, "SELECT * FROM train_station_tickets") == []


# ---------------------------------------------------------------------------
# read views run cleanly
# ---------------------------------------------------------------------------

class TestReadViews:
    @patch("builtins.print")
    def test_list_services_menu(self, _p, train_db):
        # init seeds 10 services; the view must render without error.
        assert train_cli.list_services_menu() is None

    @patch("builtins.print")
    def test_view_tickets_menu_none(self, _p, train_db):
        assert train_cli.view_tickets_menu() is None
