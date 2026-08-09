"""Behavioral tests for the Mail/Post CLI (``modules.services.cli.mail_post_cli``).

Isolation mirrors the gym CLI tests: repoint the shared ``DEFAULT_DB_PATH`` at a
temp file (``get_connection``/``transaction`` read it at call time), create the
schema via the module's own ``init_mail_db()``, and stub the seams (``get_auth``,
``log_activity``, finance/email fan-out) so nothing escapes the test.
"""

from unittest.mock import patch

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.cli.shell.services import mail_post_cli as mail_cli


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
def mail_db(tmp_path, monkeypatch):
    """Temp DB + mail schema, with a logged-in staff user and neutralised side effects."""
    db_path = str(tmp_path / "mail.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert mail_cli.init_mail_db() is True

    fake = _FakeAuth({"id": "ST01", "username": "stan", "email": "stan@uni.ac.uk", "role": "staff"})
    monkeypatch.setattr(mail_cli, "get_auth", lambda: fake)
    monkeypatch.setattr(mail_cli, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(mail_cli, "FINANCE_AVAILABLE", False)
    monkeypatch.setattr(mail_cli, "EMAIL_AVAILABLE", False)
    return db_path, fake


# ---------------------------------------------------------------------------
# Pure helpers & catalog
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_generate_tracking_number_shape(self):
        assert mail_cli.generate_tracking_number().startswith("UNI-")

    def test_generate_reference_shape(self):
        assert mail_cli.generate_reference().startswith("REF-")

    def test_tracking_numbers_unique(self):
        assert mail_cli.generate_tracking_number() != mail_cli.generate_tracking_number()

    def test_package_catalog_wellformed(self):
        assert "letter" in mail_cli.PACKAGE_TYPES
        for pkg_type in mail_cli.PACKAGE_TYPES:
            assert pkg_type in mail_cli.STORAGE_FEES
            assert isinstance(mail_cli.STORAGE_FEES[pkg_type], (int, float))


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_current_user_dict(self, mail_db):
        assert mail_cli.get_current_user()["username"] == "stan"

    def test_none_when_no_auth(self, monkeypatch):
        monkeypatch.setattr(mail_cli, "get_auth", lambda: None)
        assert mail_cli.get_current_user() is None

    def test_none_when_not_logged_in(self, monkeypatch):
        monkeypatch.setattr(mail_cli, "get_auth", lambda: _FakeAuth(None))
        assert mail_cli.get_current_user() is None


# ---------------------------------------------------------------------------
# receive_package (write action, staff-gated)
# ---------------------------------------------------------------------------

class TestReceivePackage:
    @patch("builtins.print")
    def test_requires_staff(self, _p, mail_db, monkeypatch):
        db_path, _ = mail_db
        monkeypatch.setattr(
            mail_cli, "get_auth",
            lambda: _FakeAuth({"id": "S9", "username": "sam", "role": "student"}),
        )
        with patch("builtins.input", return_value=""):
            assert mail_cli.receive_package() is None
        assert _rows(db_path, "SELECT * FROM mail_packages") == []

    @patch("builtins.print")
    def test_happy_path_persists_package(self, _p, mail_db):
        db_path, _ = mail_db
        # recipient_id, name, email, phone, sender, sender_addr, pkg_choice(3=large_parcel),
        # description, storage_location, final Enter
        script = ["R100", "Bob Smith", "", "", "ACME Ltd", "", "3", "", "", ""]
        with patch("builtins.input", side_effect=script):
            mail_cli.receive_package()

        rows = _rows(db_path, "SELECT * FROM mail_packages WHERE recipient_id = 'R100'")
        assert len(rows) == 1
        assert rows[0]["recipient_name"] == "Bob Smith"
        assert rows[0]["package_type"] == "large_parcel"
        assert rows[0]["status"] == "received"
        assert rows[0]["storage_fee"] == 2.50

    @patch("builtins.print")
    def test_invalid_package_type_writes_nothing(self, _p, mail_db):
        db_path, _ = mail_db
        script = ["R1", "Name", "", "", "Sender", "", "999"]  # out-of-range -> early return
        with patch("builtins.input", side_effect=script):
            mail_cli.receive_package()
        assert _rows(db_path, "SELECT * FROM mail_packages") == []


# ---------------------------------------------------------------------------
# rent_po_box (user write action)
# ---------------------------------------------------------------------------

class TestRentPoBox:
    @patch("builtins.print")
    def test_requires_login(self, _p, monkeypatch):
        monkeypatch.setattr(mail_cli, "get_auth", lambda: None)
        with patch("builtins.input", return_value=""):
            assert mail_cli.rent_po_box() is None

    @patch("builtins.print")
    def test_happy_path_marks_box_rented(self, _p, mail_db):
        db_path, _ = mail_db
        # box_number, duration, confirm yes, final Enter
        script = ["PO-001", "6", "yes", ""]
        with patch("builtins.input", side_effect=script):
            mail_cli.rent_po_box()

        rows = _rows(db_path, "SELECT * FROM mail_po_boxes WHERE box_number = 'PO-001'")
        assert len(rows) == 1
        assert rows[0]["status"] == "rented"
        assert rows[0]["holder_id"] == "ST01"


# ---------------------------------------------------------------------------
# read views run cleanly
# ---------------------------------------------------------------------------

class TestReadViews:
    @patch("builtins.print")
    def test_view_available_po_boxes(self, _p, mail_db):
        # init_mail_db seeds 50 boxes; the view must render without error.
        with patch("builtins.input", return_value=""):
            assert mail_cli.view_available_po_boxes() is None

    @patch("builtins.print")
    def test_view_my_packages_none(self, _p, mail_db):
        with patch("builtins.input", return_value=""):
            assert mail_cli.view_my_packages() is None
