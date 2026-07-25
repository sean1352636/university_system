"""Behavioural tests for the Nail Bar CLI (``modules.services.cli.nailbar_cli``).

Mirrors the gym-CLI test harness: repoint the shared ``DEFAULT_DB_PATH`` at a
temp file (``get_connection`` / ``transaction`` read it at call time), build the
schema via the module's own ``init_nailbar_db()`` (its fallback schema, which is
what the CLI queries are written against), and stub the seams (``get_auth``,
``log_activity``, email / finance fan-out) so nothing escapes the test.

Testable surface exercised here:

* pure helpers (``format_currency`` / ``format_date`` / ``generate_*``),
* auth resolution (``get_current_user``) and the ``is_staff`` gate,
* write actions (``add_treatment`` staff-gated, ``book_appointment``) driven by a
  scripted ``input()`` sequence, asserted against temp-DB rows,
* read views (``view_treatments`` / ``view_technicians``) run cleanly.
"""

import sqlite3
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from education_system.systems.university.interfaces.cli.shell.services import nailbar_cli


class _FakeAuth:
    def __init__(self, current_user):
        self.current_user = current_user


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def nailbar_db(tmp_path, monkeypatch):
    """Temp DB + nailbar schema, logged-in student, neutralised side effects."""
    db_path = str(tmp_path / "nailbar.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert nailbar_cli.init_nailbar_db() is True

    fake = _FakeAuth(
        {"id": "S001", "username": "alice", "email": "", "role": "student"}
    )
    monkeypatch.setattr(nailbar_cli, "get_auth", lambda: fake)
    monkeypatch.setattr(nailbar_cli, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(nailbar_cli, "EMAIL_AVAILABLE", False)
    monkeypatch.setattr(nailbar_cli, "FINANCE_AVAILABLE", False)
    return db_path, fake


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_format_currency_basic(self):
        assert nailbar_cli.format_currency(20) == "£20.00"
        assert nailbar_cli.format_currency(12.5) == "£12.50"
        assert nailbar_cli.format_currency(0) == "£0.00"

    def test_format_currency_bad_input(self):
        assert nailbar_cli.format_currency("not-a-number") == "£0.00"
        assert nailbar_cli.format_currency(None) == "£0.00"

    def test_format_date_valid(self):
        assert nailbar_cli.format_date("2024-01-05") == "05 January 2024"

    def test_format_date_invalid_passthrough(self):
        assert nailbar_cli.format_date("nonsense") == "nonsense"

    def test_generate_booking_ref_shape(self):
        ref = nailbar_cli.generate_booking_ref()
        assert ref.startswith("NAIL-")
        assert len(ref) > len("NAIL-")

    def test_generate_receipt_number_shape_and_unique(self):
        r1 = nailbar_cli.generate_receipt_number()
        r2 = nailbar_cli.generate_receipt_number()
        assert r1.startswith("REC-")
        assert r1 != r2


# ---------------------------------------------------------------------------
# get_current_user / is_staff
# ---------------------------------------------------------------------------

class TestAuthResolution:
    def test_get_current_user_returns_dict(self, nailbar_db):
        assert nailbar_cli.get_current_user()["username"] == "alice"

    def test_get_current_user_none_when_no_auth(self, monkeypatch):
        monkeypatch.setattr(nailbar_cli, "get_auth", lambda: None)
        assert nailbar_cli.get_current_user() is None

    def test_get_current_user_none_when_not_logged_in(self, monkeypatch):
        monkeypatch.setattr(nailbar_cli, "get_auth", lambda: _FakeAuth(None))
        assert nailbar_cli.get_current_user() is None

    def test_is_staff_true_for_staff_role(self, monkeypatch):
        monkeypatch.setattr(
            nailbar_cli, "get_auth", lambda: _FakeAuth({"role": "staff"})
        )
        assert nailbar_cli.is_staff() is True

    def test_is_staff_false_for_student(self, monkeypatch):
        monkeypatch.setattr(
            nailbar_cli, "get_auth", lambda: _FakeAuth({"role": "student"})
        )
        assert nailbar_cli.is_staff() is False


# ---------------------------------------------------------------------------
# add_treatment (staff-gated write)
# ---------------------------------------------------------------------------

class TestAddTreatment:
    @patch("builtins.print")
    def test_rejected_when_not_staff(self, _p, nailbar_db, monkeypatch):
        db_path, _ = nailbar_db
        monkeypatch.setattr(nailbar_cli, "is_staff", lambda: False)
        with patch("builtins.input", side_effect=[""]):
            assert nailbar_cli.add_treatment() is None
        assert _rows(
            db_path,
            "SELECT * FROM nailbar_treatments WHERE treatment_name = 'Gel Deluxe'",
        ) == []

    @patch("builtins.print")
    def test_happy_path_persists_treatment(self, _p, nailbar_db, monkeypatch):
        db_path, _ = nailbar_db
        monkeypatch.setattr(nailbar_cli, "is_staff", lambda: True)
        # name, category (1 -> manicure), price, duration, description, confirm, enter
        script = ["Gel Deluxe", "1", "30", "45", "", "yes", ""]
        with patch("builtins.input", side_effect=script):
            nailbar_cli.add_treatment()

        rows = _rows(
            db_path,
            "SELECT * FROM nailbar_treatments WHERE treatment_name = 'Gel Deluxe'",
        )
        assert len(rows) == 1
        assert rows[0]["category"] == "manicure"
        assert rows[0]["price"] == 30.0
        assert rows[0]["duration_minutes"] == 45
        assert rows[0]["status"] == "active"

    @patch("builtins.print")
    def test_declined_confirmation_writes_nothing(self, _p, nailbar_db, monkeypatch):
        db_path, _ = nailbar_db
        monkeypatch.setattr(nailbar_cli, "is_staff", lambda: True)
        script = ["Gel Deluxe", "1", "30", "45", "", "no", ""]
        with patch("builtins.input", side_effect=script):
            nailbar_cli.add_treatment()
        assert _rows(
            db_path,
            "SELECT * FROM nailbar_treatments WHERE treatment_name = 'Gel Deluxe'",
        ) == []


# ---------------------------------------------------------------------------
# book_appointment (user write)
# ---------------------------------------------------------------------------

class TestBookAppointment:
    @patch("builtins.print")
    def test_requires_login(self, _p, monkeypatch):
        monkeypatch.setattr(nailbar_cli, "get_auth", lambda: None)
        with patch("builtins.input", side_effect=[""]):
            assert nailbar_cli.book_appointment() is None

    @patch("builtins.print")
    def test_happy_path_persists_appointment(self, _p, nailbar_db):
        db_path, _ = nailbar_db
        # price of the treatment we will select (id 1)
        treat_price = _rows(
            db_path,
            "SELECT price FROM nailbar_treatments WHERE treatment_id = 1",
        )[0]["price"]

        future = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")
        # treatment id 1, finish (0), technician "Any" (0), date, time, confirm, enter
        script = ["1", "0", "0", future, "10:00", "yes", ""]
        with patch("builtins.input", side_effect=script):
            nailbar_cli.book_appointment()

        rows = _rows(
            db_path,
            "SELECT * FROM nailbar_appointments WHERE user_id = 'alice'",
        )
        assert len(rows) == 1
        assert rows[0]["status"] == "scheduled"
        assert rows[0]["total_price"] == treat_price
        assert rows[0]["appointment_date"] == future

    @patch("builtins.print")
    def test_cancelled_confirmation_writes_nothing(self, _p, nailbar_db):
        db_path, _ = nailbar_db
        future = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")
        script = ["1", "0", "0", future, "10:00", "no", ""]
        with patch("builtins.input", side_effect=script):
            nailbar_cli.book_appointment()
        assert _rows(db_path, "SELECT * FROM nailbar_appointments") == []


# ---------------------------------------------------------------------------
# read views
# ---------------------------------------------------------------------------

class TestReadViews:
    @patch("builtins.print")
    def test_view_treatments_runs(self, _p, nailbar_db):
        with patch("builtins.input", return_value=""):
            assert nailbar_cli.view_treatments() is None

    @patch("builtins.print")
    def test_view_technicians_runs(self, _p, nailbar_db):
        with patch("builtins.input", return_value=""):
            assert nailbar_cli.view_technicians() is None
