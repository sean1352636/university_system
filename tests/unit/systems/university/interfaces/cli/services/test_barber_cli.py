"""Behavioral tests for the Barber Shop CLI (``modules.services.cli.barber_cli``).

This CLI is interactive: it resolves the current user via ``get_auth()`` and drives
menus with ``input()`` / ``print()``. The testable surface is:

* pure helpers / role gate (``get_current_user``, ``is_staff_or_admin``, catalog consts),
* staff-only write actions (``add_service``) with their access guard,
* the customer booking flow (``book_appointment``) happy path + login guard,
* read views (``view_services`` / ``view_staff`` / ``view_my_appointments``).

Isolation mirrors the gym CLI tests: repoint the shared ``DEFAULT_DB_PATH`` at a temp
file (``get_connection`` / ``transaction`` read it at call time) and stub the seams
(``get_auth``, ``log_activity``, finance/email fan-out).

Note: with the real ``barber_core`` present, ``init_barber_db`` builds a schema whose
columns (``name`` / ``is_available``) don't match the SQL this CLI actually issues
(``service_name`` / ``status``). So we seed the touched tables with the schema the CLI's
own statements expect, per the "else seed touched tables" guidance.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.cli.shell.services import barber_cli


class _FakeAuth:
    def __init__(self, current_user):
        self.current_user = current_user


# Schema matching the SQL the CLI itself issues (service_name/status, staff_name, etc.).
_SCHEMA = """
CREATE TABLE barber_services (
    service_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_name TEXT NOT NULL,
    price REAL NOT NULL,
    duration_minutes INTEGER NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE barber_staff (
    staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_name TEXT NOT NULL,
    specialization TEXT,
    availability TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE barber_appointments (
    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_ref TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT,
    user_email TEXT,
    service_id INTEGER,
    service_name TEXT,
    staff_id INTEGER,
    staff_name TEXT,
    appointment_date DATE NOT NULL,
    appointment_time TEXT NOT NULL,
    duration_minutes INTEGER,
    price REAL NOT NULL,
    status TEXT DEFAULT 'scheduled',
    payment_status TEXT DEFAULT 'pending',
    payment_method TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def barber_db(tmp_path, monkeypatch):
    """Temp DB + barber schema (one seeded service + staff) with neutralised seams.

    Logged in as a student by default; returns (db_path, fake_auth) so tests can
    override ``current_user`` (e.g. to a staff role).
    """
    db_path = str(tmp_path / "barber.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT INTO barber_services (service_name, price, duration_minutes, description, status) "
            "VALUES ('Standard Haircut', 15.00, 30, 'Classic cut', 'active')"
        )
        conn.execute(
            "INSERT INTO barber_staff (staff_name, specialization, availability, status) "
            "VALUES ('Mike Davis', 'Fades', 'Mon-Sat', 'active')"
        )
        conn.commit()
    finally:
        conn.close()

    fake = _FakeAuth({"username": "alice", "full_name": "Alice A", "email": "alice@uni.ac.uk",
                      "role": "student"})
    monkeypatch.setattr(barber_cli, "get_auth", lambda: fake)
    # Disable side-effect fan-out.
    monkeypatch.setattr(barber_cli, "FINANCE_AVAILABLE", False)
    monkeypatch.setattr(barber_cli, "EMAIL_AVAILABLE", False)
    monkeypatch.setattr(barber_cli, "ACTIVITY_LOG_AVAILABLE", False)
    return db_path, fake


# ---------------------------------------------------------------------------
# Pure helpers / catalog / role gate
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_time_slots_wellformed(self):
        assert "09:00" in barber_cli.TIME_SLOTS
        assert all(":" in s for s in barber_cli.TIME_SLOTS)

    def test_appointment_statuses_include_scheduled(self):
        assert "scheduled" in barber_cli.APPOINTMENT_STATUSES
        assert "cancelled" in barber_cli.APPOINTMENT_STATUSES

    def test_is_staff_or_admin_true_for_staff(self, barber_db):
        _, fake = barber_db
        fake.current_user["role"] = "staff"
        assert barber_cli.is_staff_or_admin() is True

    def test_is_staff_or_admin_false_for_student(self, barber_db):
        assert barber_cli.is_staff_or_admin() is False

    def test_is_staff_or_admin_false_when_no_user(self, monkeypatch):
        monkeypatch.setattr(barber_cli, "get_auth", lambda: None)
        assert barber_cli.is_staff_or_admin() is False


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_current_user_dict(self, barber_db):
        assert barber_cli.get_current_user()["username"] == "alice"

    def test_none_when_no_auth(self, monkeypatch):
        monkeypatch.setattr(barber_cli, "get_auth", lambda: None)
        assert barber_cli.get_current_user() is None

    def test_none_when_not_logged_in(self, monkeypatch):
        monkeypatch.setattr(barber_cli, "get_auth", lambda: _FakeAuth(None))
        assert barber_cli.get_current_user() is None


# ---------------------------------------------------------------------------
# add_service (staff-only write) — happy path + guard
# ---------------------------------------------------------------------------

class TestAddService:
    @patch("builtins.print")
    def test_non_staff_blocked(self, _p, barber_db):
        db_path, _ = barber_db  # default user is a student
        with patch("builtins.input", return_value=""):
            barber_cli.add_service()
        # Guard fires before any insert; still just the seeded service.
        rows = _rows(db_path, "SELECT * FROM barber_services")
        assert len(rows) == 1

    @patch("builtins.print")
    def test_happy_path_persists_service(self, _p, barber_db):
        db_path, fake = barber_db
        fake.current_user["role"] = "staff"
        # name, price, duration, description, confirm=yes, final Enter
        script = ["Beard Trim", "10.50", "20", "Tidy beard", "yes", ""]
        with patch("builtins.input", side_effect=script):
            barber_cli.add_service()

        rows = _rows(db_path, "SELECT * FROM barber_services WHERE service_name = 'Beard Trim'")
        assert len(rows) == 1
        assert rows[0]["price"] == 10.50
        assert rows[0]["duration_minutes"] == 20
        assert rows[0]["status"] == "active"

    @patch("builtins.print")
    def test_declined_confirmation_writes_nothing(self, _p, barber_db):
        db_path, fake = barber_db
        fake.current_user["role"] = "staff"
        script = ["Beard Trim", "10.50", "20", "Tidy beard", "no", ""]
        with patch("builtins.input", side_effect=script):
            barber_cli.add_service()
        assert _rows(db_path, "SELECT * FROM barber_services WHERE service_name = 'Beard Trim'") == []

    @patch("builtins.print")
    def test_invalid_price_writes_nothing(self, _p, barber_db):
        db_path, fake = barber_db
        fake.current_user["role"] = "staff"
        script = ["Beard Trim", "notanumber", ""]
        with patch("builtins.input", side_effect=script):
            barber_cli.add_service()
        assert _rows(db_path, "SELECT * FROM barber_services WHERE service_name = 'Beard Trim'") == []


# ---------------------------------------------------------------------------
# book_appointment (customer write) — happy path + login guard
# ---------------------------------------------------------------------------

class TestBookAppointment:
    @patch("builtins.print")
    def test_requires_login(self, _p, monkeypatch):
        monkeypatch.setattr(barber_cli, "get_auth", lambda: None)
        with patch("builtins.input", return_value=""):
            assert barber_cli.book_appointment() is None

    @patch("builtins.print")
    def test_happy_path_persists_appointment(self, _p, barber_db):
        db_path, _ = barber_db
        future = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        # service_id=1, staff_id=0 (any), date, time, no special request, confirm=yes, final Enter
        script = ["1", "0", future, "09:00", "", "yes", ""]
        with patch("builtins.input", side_effect=script):
            barber_cli.book_appointment()

        rows = _rows(db_path, "SELECT * FROM barber_appointments WHERE user_id = 'alice'")
        assert len(rows) == 1
        assert rows[0]["service_name"] == "Standard Haircut"
        assert rows[0]["appointment_time"] == "09:00"
        assert rows[0]["appointment_date"] == future
        assert rows[0]["status"] == "scheduled"
        assert rows[0]["staff_name"] == "Any Available"

    @patch("builtins.print")
    def test_past_date_writes_nothing(self, _p, barber_db):
        db_path, _ = barber_db
        past = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        script = ["1", "0", past, ""]
        with patch("builtins.input", side_effect=script):
            barber_cli.book_appointment()
        assert _rows(db_path, "SELECT * FROM barber_appointments") == []


# ---------------------------------------------------------------------------
# read views run cleanly
# ---------------------------------------------------------------------------

class TestReadViews:
    @patch("builtins.print")
    def test_view_services_lists_seeded(self, _p, barber_db):
        with patch("builtins.input", return_value=""):
            assert barber_cli.view_services() is None

    @patch("builtins.print")
    def test_view_staff_lists_seeded(self, _p, barber_db):
        with patch("builtins.input", return_value=""):
            assert barber_cli.view_staff() is None

    @patch("builtins.print")
    def test_view_my_appointments_empty(self, _p, barber_db):
        with patch("builtins.input", return_value=""):
            assert barber_cli.view_my_appointments() is None

    @patch("builtins.print")
    def test_view_my_appointments_after_booking(self, _p, barber_db):
        future = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        with patch("builtins.input", side_effect=["1", "0", future, "09:00", "", "yes", ""]):
            barber_cli.book_appointment()
        with patch("builtins.input", return_value=""):
            assert barber_cli.view_my_appointments() is None
