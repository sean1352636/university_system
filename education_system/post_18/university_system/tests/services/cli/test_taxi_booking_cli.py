"""Behavioral tests for the Taxi Booking CLI (``modules.services.cli.taxi_booking_cli``).

CLI modules are interactive: they resolve the current user via ``get_user`` and drive
menus with ``input()`` / ``print()``. The testable surface is:

* pure helpers (ticket-number generator),
* auth resolution (``get_current_user`` — falls back to a guest identity),
* DB-backed reads/writes, driven directly or with a scripted ``input()`` sequence.

Isolation mirrors the gym-CLI tests: repoint the shared ``DEFAULT_DB_PATH`` at a temp
file (``get_connection`` reads it at call time), build the schema via the module's own
``init_taxi_database()`` (which seeds eight default services), and stub the ``get_user``
seam so nothing escapes the test.
"""

from unittest.mock import patch

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services.cli import taxi_booking_cli as taxi


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def taxi_db(tmp_path, monkeypatch):
    """Temp DB + taxi schema (with the eight seeded default services).

    Returns the db path so tests can inspect rows directly. ``get_user`` is
    neutralised to ``None`` so ``get_current_user`` returns the guest identity
    unless a test overrides it.
    """
    db_path = str(tmp_path / "taxi.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert taxi.init_taxi_database() is True
    monkeypatch.setattr(taxi, "get_user", None)
    return db_path


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_ticket_number_shape(self):
        tn = taxi.generate_ticket_number()
        assert tn.startswith("TXI-")
        assert len(tn) == 12  # "TXI-" + 8 chars

    def test_ticket_numbers_unique(self):
        assert taxi.generate_ticket_number() != taxi.generate_ticket_number()


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_authenticated_user(self, monkeypatch):
        monkeypatch.setattr(
            taxi, "get_user", lambda: {"username": "bob", "name": "Bob Jones", "role": "student"}
        )
        user = taxi.get_current_user()
        assert user["username"] == "bob"
        assert user["name"] == "Bob Jones"

    def test_guest_when_get_user_unavailable(self, monkeypatch):
        monkeypatch.setattr(taxi, "get_user", None)
        user = taxi.get_current_user()
        assert user["username"] == "guest"
        assert user["role"] == "guest"

    def test_guest_when_no_user_logged_in(self, monkeypatch):
        monkeypatch.setattr(taxi, "get_user", lambda: None)
        user = taxi.get_current_user()
        assert user["username"] == "guest"


# ---------------------------------------------------------------------------
# Service reads
# ---------------------------------------------------------------------------

class TestServices:
    def test_get_all_services_returns_seeded(self, taxi_db):
        services = taxi.get_all_services()
        assert len(services) == 8
        names = {s["service_name"] for s in services}
        assert "City Express" in names

    def test_get_service_by_id_found(self, taxi_db):
        service = taxi.get_service_by_id(1)
        assert service is not None
        assert service["id"] == 1
        assert service["price_per_km"] > 0

    def test_get_service_by_id_missing(self, taxi_db):
        assert taxi.get_service_by_id(9999) is None


# ---------------------------------------------------------------------------
# Ticket writes / reads
# ---------------------------------------------------------------------------

class TestTickets:
    def test_get_all_tickets_empty(self, taxi_db):
        assert taxi.get_all_tickets() == []

    def test_create_ticket_persists(self, taxi_db):
        ticket_id, ticket_number = taxi.create_ticket(
            service_id=1, customer_name="Alice", pickup="Campus",
            dropoff="Station", distance=10.0, total_fare=30.0, payment_method="Cash",
        )
        assert ticket_id is not None
        assert ticket_number.startswith("TXI-")

        rows = _rows(taxi_db, "SELECT * FROM taxi_booking_tickets WHERE id = ?", (ticket_id,))
        assert len(rows) == 1
        assert rows[0]["customer_name"] == "Alice"
        assert rows[0]["total_fare"] == 30.0

    def test_get_all_tickets_seeded(self, taxi_db):
        taxi.create_ticket(1, "Alice", "A", "B", 5.0, 17.5, "Card")
        tickets = taxi.get_all_tickets()
        assert len(tickets) == 1
        # JOIN pulls the service name through.
        assert tickets[0]["service_name"] == "City Express"


# ---------------------------------------------------------------------------
# book_taxi_menu (scripted input)
# ---------------------------------------------------------------------------

class TestBookTaxiMenu:
    @patch("builtins.print")
    def test_happy_path_persists(self, _p, taxi_db):
        # service id, customer name, pickup, dropoff, distance, payment choice, confirm.
        script = ["1", "John", "Campus", "Station", "10", "1", "yes"]
        with patch("builtins.input", side_effect=script):
            taxi.book_taxi_menu()

        rows = _rows(taxi_db, "SELECT * FROM taxi_booking_tickets")
        assert len(rows) == 1
        assert rows[0]["customer_name"] == "John"
        assert rows[0]["payment_method"] == "Cash"
        # base_fare 5.00 + 10 * 2.50 = 30.00
        assert rows[0]["total_fare"] == pytest.approx(30.0)

    @patch("builtins.print")
    def test_invalid_service_writes_nothing(self, _p, taxi_db):
        with patch("builtins.input", side_effect=["9999"]):
            taxi.book_taxi_menu()
        assert _rows(taxi_db, "SELECT * FROM taxi_booking_tickets") == []

    @patch("builtins.print")
    def test_declined_confirmation_writes_nothing(self, _p, taxi_db):
        script = ["1", "John", "Campus", "Station", "10", "1", "no"]
        with patch("builtins.input", side_effect=script):
            taxi.book_taxi_menu()
        assert _rows(taxi_db, "SELECT * FROM taxi_booking_tickets") == []
