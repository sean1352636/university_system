"""Behavioral tests for the Church Management CLI
(``modules.services.cli.church_cli``).

The module uses the shared ``get_connection`` (which reads the db module's
``DEFAULT_DB_PATH`` at call time), so we repoint that at a temp file and build the
schema via the module's own ``init_church_database()``. This CLI has no auth seam
of its own; coverage focuses on the data helpers, one scripted write action per
menu, a guard, and read views.
"""

from unittest.mock import patch

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.cli.shell.services import church_cli as church


def _rows(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@pytest.fixture()
def church_db(tmp_path, monkeypatch):
    """Temp DB + church schema."""
    db_path = str(tmp_path / "church.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    assert church.init_church_database() is True
    return db_path


# ---------------------------------------------------------------------------
# data helpers: members
# ---------------------------------------------------------------------------

class TestMembers:
    def test_add_and_list_member(self, church_db):
        assert church.add_member("Grace Lee", "grace@uni.ac.uk", "0123", "1 High St") is True
        members = church.list_members()
        assert len(members) == 1
        assert members[0][1] == "Grace Lee"

    def test_get_member_by_id(self, church_db):
        church.add_member("Sam Roe")
        mid = church.list_members()[0][0]
        member = church.get_member(mid)
        assert member is not None
        assert member[1] == "Sam Roe"
        assert member[5] == "Active"  # default status


# ---------------------------------------------------------------------------
# data helpers: donations
# ---------------------------------------------------------------------------

class TestDonations:
    def test_record_donation_returns_reference(self, church_db):
        ref = church.record_donation("Anon", 50.0, "Tithe", "Cash")
        assert ref is not None
        assert ref.startswith("DON-")
        rows = church.list_donations()
        assert len(rows) == 1
        assert rows[0][2] == 50.0

    def test_donation_stats_aggregate(self, church_db):
        church.record_donation("A", 100.0, "Tithe", "Cash")
        church.record_donation("B", 25.0, "Offering", "Card")
        stats = church.get_donation_stats()
        assert stats["total_amount"] == 125.0
        assert stats["total_count"] == 2

    def test_stats_empty_is_zeroed(self, church_db):
        stats = church.get_donation_stats()
        assert stats["total_amount"] == 0
        assert stats["total_count"] == 0


# ---------------------------------------------------------------------------
# data helpers: prayer requests
# ---------------------------------------------------------------------------

class TestPrayerRequests:
    def test_add_list_and_answer(self, church_db):
        assert church.add_prayer_request("Mary", "Please pray for healing", "Healing") is True
        active = church.list_prayer_requests("Active")
        assert len(active) == 1
        pid = active[0][0]
        assert church.mark_prayer_answered(pid) is True
        # No longer in the Active list once answered.
        assert church.list_prayer_requests("Active") == []


# ---------------------------------------------------------------------------
# menu-driven write action + guard (members_menu option 3)
# ---------------------------------------------------------------------------

class TestMembersMenu:
    @patch("builtins.print")
    def test_add_member_via_menu(self, _p, church_db):
        # choice 3 (add), name, email, phone, address, Press-Enter, choice 0 (back)
        script = ["3", "Peter Ng", "peter@uni.ac.uk", "555", "2 Elm Rd", "", "0"]
        with patch("builtins.input", side_effect=script):
            church.members_menu()
        rows = _rows(church_db, "SELECT * FROM church_members WHERE name = 'Peter Ng'")
        assert len(rows) == 1

    @patch("builtins.print")
    def test_blank_name_adds_nothing(self, _p, church_db):
        # choice 3, blank name -> 'continue', then choice 0 to exit
        script = ["3", "", "0"]
        with patch("builtins.input", side_effect=script):
            church.members_menu()
        assert _rows(church_db, "SELECT * FROM church_members") == []


# ---------------------------------------------------------------------------
# sermons
# ---------------------------------------------------------------------------

class TestSermons:
    def test_add_and_list_sermon(self, church_db):
        assert church.add_sermon("Faith", "Rev Adams", "2024-03-01", "John 3:16") is True
        sermons = church.list_sermons()
        assert len(sermons) == 1
        assert sermons[0][1] == "Faith"
