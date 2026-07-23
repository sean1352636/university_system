"""Behavioral tests for the Car Rental CLI (``modules.services.cli.carrental_cli``).

The CLI is interactive: it resolves the current user via the ``get_user`` seam and
drives menus with ``input()`` / ``print()``. The testable surface is:

* module constants / pure helpers,
* auth resolution (``get_current_user``),
* DB-backed data helpers and write actions, driven with scripted ``input()`` against
  a temp DB.

Isolation mirrors the gym CLI tests: repoint the shared ``DEFAULT_DB_PATH`` at a temp
file (``get_connection`` reads it at call time), build the schema via the module's own
``init_carrental_database()``, and stub the seams (``get_user``, email fan-out) so
nothing escapes the test.
"""

from unittest.mock import patch

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services.cli import carrental_cli


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def carrental_db(tmp_path, monkeypatch):
    """Temp DB + seeded car-rental schema, with a fake user and no email fan-out.

    Returns the db path so tests can inspect rows directly.
    """
    db_path = str(tmp_path / "carrental.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    # Build (and seed) the car-rental tables via the module's own initialiser.
    assert carrental_cli.init_carrental_database() is True

    # A logged-in staff user by default; tests can override get_user.
    fake_user = {"username": "staff", "role": "staff", "email": "s@uni.ac.uk",
                 "id": 1, "name": "Staff Member"}
    monkeypatch.setattr(carrental_cli, "get_user", lambda: fake_user)
    monkeypatch.setattr(carrental_cli, "EMAIL_AVAILABLE", False)
    return db_path, fake_user


# ---------------------------------------------------------------------------
# Pure helpers & catalog constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_vehicle_categories(self):
        assert "Economy" in carrental_cli.VEHICLE_CATEGORIES
        assert "SUV" in carrental_cli.VEHICLE_CATEGORIES

    def test_rental_statuses(self):
        assert carrental_cli.RENTAL_STATUSES[0] == "Active"
        assert "Returned" in carrental_cli.RENTAL_STATUSES

    def test_vehicle_statuses(self):
        assert "Available" in carrental_cli.VEHICLE_STATUSES
        assert "Rented" in carrental_cli.VEHICLE_STATUSES


# ---------------------------------------------------------------------------
# get_current_user (3 cases)
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_user_from_seam(self, carrental_db):
        user = carrental_cli.get_current_user()
        assert user["username"] == "staff"

    def test_guest_when_seam_missing(self, monkeypatch):
        monkeypatch.setattr(carrental_cli, "get_user", None)
        user = carrental_cli.get_current_user()
        assert user["role"] == "guest"

    def test_guest_when_seam_returns_none(self, monkeypatch):
        monkeypatch.setattr(carrental_cli, "get_user", lambda: None)
        user = carrental_cli.get_current_user()
        assert user["username"] == "guest"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

class TestVehicleQueries:
    def test_get_all_vehicles_returns_seeded(self, carrental_db):
        vehicles = carrental_cli.get_all_vehicles()
        assert len(vehicles) == 11
        assert all("registration" in v for v in vehicles)

    def test_get_all_vehicles_filtered_by_category(self, carrental_db):
        suvs = carrental_cli.get_all_vehicles("SUV")
        assert len(suvs) == 2
        assert all(v["category"] == "SUV" for v in suvs)

    def test_get_vehicle_by_id(self, carrental_db):
        v = carrental_cli.get_vehicle_by_id(1)
        assert v is not None
        assert v["status"] == "Available"

    def test_get_vehicle_by_id_missing(self, carrental_db):
        assert carrental_cli.get_vehicle_by_id(9999) is None


# ---------------------------------------------------------------------------
# create_rental / return_vehicle (direct write helpers)
# ---------------------------------------------------------------------------

def _rental_payload(vehicle_id=1):
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return {
        'vehicle_id': vehicle_id, 'customer_name': 'Jane Roe',
        'customer_email': '', 'customer_phone': '', 'student_id': '',
        'rental_date': now, 'expected_return_date': '2099-01-01',
        'daily_rate': 35.0, 'total_cost': 105.0,
        'payment_status': 'Pending', 'rental_status': 'Active', 'created_date': now,
    }


class TestCreateAndReturn:
    def test_create_rental_persists_and_marks_rented(self, carrental_db):
        db_path, _ = carrental_db
        assert carrental_cli.create_rental(_rental_payload(1)) is True

        rentals = _rows(db_path, "SELECT * FROM carrental_rentals")
        assert len(rentals) == 1
        assert rentals[0]["customer_name"] == "Jane Roe"

        veh = _rows(db_path, "SELECT status FROM carrental_vehicles WHERE vehicle_id = 1")
        assert veh[0]["status"] == "Rented"

    def test_return_vehicle_updates_status(self, carrental_db):
        db_path, _ = carrental_db
        carrental_cli.create_rental(_rental_payload(1))
        rental_id = _rows(db_path, "SELECT rental_id FROM carrental_rentals")[0]["rental_id"]

        assert carrental_cli.return_vehicle(rental_id) is True

        rental = _rows(db_path, "SELECT rental_status, return_date FROM carrental_rentals WHERE rental_id = ?", (rental_id,))
        assert rental[0]["rental_status"] == "Returned"
        assert rental[0]["return_date"] is not None

        veh = _rows(db_path, "SELECT status FROM carrental_vehicles WHERE vehicle_id = 1")
        assert veh[0]["status"] == "Available"

    def test_return_unknown_rental(self, carrental_db):
        assert carrental_cli.return_vehicle(9999) is False


# ---------------------------------------------------------------------------
# book_rental_menu (scripted input)
# ---------------------------------------------------------------------------

class TestBookRentalMenu:
    @patch("builtins.print")
    def test_happy_path_books_and_marks_rented(self, _p, carrental_db):
        db_path, _ = carrental_db
        # vehicle id 1, name, email, phone, student id, days=3, confirm yes
        script = ["1", "John Doe", "", "", "", "3", "yes"]
        with patch("builtins.input", side_effect=script):
            carrental_cli.book_rental_menu()

        rentals = _rows(db_path, "SELECT * FROM carrental_rentals")
        assert len(rentals) == 1
        assert rentals[0]["customer_name"] == "John Doe"
        assert rentals[0]["total_cost"] == 35.0 * 3
        veh = _rows(db_path, "SELECT status FROM carrental_vehicles WHERE vehicle_id = 1")
        assert veh[0]["status"] == "Rented"

    @patch("builtins.print")
    def test_declined_confirmation_writes_nothing(self, _p, carrental_db):
        db_path, _ = carrental_db
        script = ["1", "John Doe", "", "", "", "3", "no"]
        with patch("builtins.input", side_effect=script):
            carrental_cli.book_rental_menu()
        assert _rows(db_path, "SELECT * FROM carrental_rentals") == []
        veh = _rows(db_path, "SELECT status FROM carrental_vehicles WHERE vehicle_id = 1")
        assert veh[0]["status"] == "Available"

    @patch("builtins.print")
    def test_invalid_vehicle_id_writes_nothing(self, _p, carrental_db):
        db_path, _ = carrental_db
        with patch("builtins.input", side_effect=["notanumber"]):
            carrental_cli.book_rental_menu()
        assert _rows(db_path, "SELECT * FROM carrental_rentals") == []


# ---------------------------------------------------------------------------
# Read views run cleanly
# ---------------------------------------------------------------------------

class TestReadViews:
    @patch("builtins.print")
    def test_list_vehicles_menu_all(self, _p, carrental_db):
        with patch("builtins.input", return_value="0"):
            assert carrental_cli.list_vehicles_menu() is None

    @patch("builtins.print")
    def test_view_rentals_menu_all(self, _p, carrental_db):
        with patch("builtins.input", return_value="0"):
            assert carrental_cli.view_rentals_menu() is None

    @patch("builtins.print")
    def test_statistics_menu(self, _p, carrental_db):
        assert carrental_cli.statistics_menu() is None
