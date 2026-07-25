"""Behavioral tests for the Academic Misconduct CLI
(``modules.services.cli.academic_misconduct_cli``).

This module connects directly with ``sqlite3.connect(str(DEFAULT_DB_PATH))`` where
``DEFAULT_DB_PATH`` is imported into the module namespace from ``core.paths``. We
therefore repoint ``academic_misconduct_cli.DEFAULT_DB_PATH`` at a temp file and
create the schema via the module's own ``init_misconduct_tables()``. It has no
``get_current_user`` helper; auth is only consulted (via ``get_auth``) when
attributing uploaded evidence, so that seam is exercised there instead.
"""

from unittest.mock import patch

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.interfaces.cli.shell.services import (
    academic_misconduct_cli as amc,
)


class _FakeAuth:
    def __init__(self, current_user):
        self.current_user = current_user


@pytest.fixture()
def amc_db(tmp_path, monkeypatch):
    """Temp DB pointed at by the module's DEFAULT_DB_PATH, schema created."""
    db_path = str(tmp_path / "misconduct.db")
    monkeypatch.setattr(amc, "DEFAULT_DB_PATH", db_path)
    amc.init_misconduct_tables()
    return db_path


def _seed_case(case_id="AM-2000-0001", **over):
    data = {
        "id": case_id,
        "student": "John Doe",
        "student_id": "S123",
        "student_email": "john@uni.ac.uk",
        "course": "CS101",
        "type": "Plagiarism",
        "status": "Under Review",
        "date_filed": "2024-01-01",
        "severity": "Medium",
        "notes": "copied essay",
    }
    data.update(over)
    return data


# ---------------------------------------------------------------------------
# get_next_case_id (pure-ish helper backed by DB)
# ---------------------------------------------------------------------------

class TestNextCaseId:
    def test_first_id_for_year(self, amc_db):
        cid = amc.get_next_case_id()
        assert cid.startswith("AM-")
        assert cid.endswith("-0001")

    def test_increments_within_year(self, amc_db):
        from datetime import datetime
        year = datetime.now().year
        assert amc.save_case(_seed_case(f"AM-{year}-0007")) is True
        assert amc.get_next_case_id() == f"AM-{year}-0008"


# ---------------------------------------------------------------------------
# save / read round-trip
# ---------------------------------------------------------------------------

class TestSaveAndRead:
    def test_save_case_persists_and_reads_back(self, amc_db):
        assert amc.save_case(_seed_case()) is True
        case = amc.get_case_by_id("AM-2000-0001")
        assert case is not None
        assert case["student"] == "John Doe"
        assert case["status"] == "Under Review"
        # save_case also writes an initial history entry.
        history = amc.get_case_history("AM-2000-0001")
        assert any("filed" in desc.lower() for _d, desc, _t in history)

    def test_get_missing_case_returns_none(self, amc_db):
        assert amc.get_case_by_id("AM-9999-9999") is None

    def test_load_all_cases(self, amc_db):
        amc.save_case(_seed_case("AM-2000-0001"))
        amc.save_case(_seed_case("AM-2000-0002", student="Jane"))
        cases = amc.load_all_cases()
        assert {c["id"] for c in cases} == {"AM-2000-0001", "AM-2000-0002"}


# ---------------------------------------------------------------------------
# create_case_menu (scripted write action + guard)
# ---------------------------------------------------------------------------

class TestCreateCaseMenu:
    @patch("builtins.print")
    def test_happy_path_creates_case(self, _p, amc_db):
        # name, id, email, course, violation(1=Plagiarism), severity(2=Medium), notes
        script = ["Alice Smith", "S777", "alice@uni.ac.uk", "MA200", "1", "2", "some notes"]
        with patch("builtins.input", side_effect=script):
            amc.create_case_menu()
        cases = amc.load_all_cases()
        assert len(cases) == 1
        c = cases[0]
        assert c["student"] == "Alice Smith"
        assert c["type"] == "Plagiarism"
        assert c["severity"] == "Medium"
        assert c["status"] == "Under Review"

    @patch("builtins.print")
    def test_blank_student_name_aborts(self, _p, amc_db):
        with patch("builtins.input", side_effect=[""]):
            amc.create_case_menu()
        assert amc.load_all_cases() == []


# ---------------------------------------------------------------------------
# update_case_menu (status change)
# ---------------------------------------------------------------------------

class TestUpdateCaseMenu:
    @patch("builtins.print")
    def test_status_update_persists(self, _p, amc_db):
        amc.save_case(_seed_case("AM-2000-0001"))
        # enter case id, choose "1" (status), then "4" (Resolved)
        with patch("builtins.input", side_effect=["AM-2000-0001", "1", "4"]):
            amc.update_case_menu()
        assert amc.get_case_by_id("AM-2000-0001")["status"] == "Resolved"

    @patch("builtins.print")
    def test_unknown_case_id_is_safe(self, _p, amc_db):
        with patch("builtins.input", side_effect=["AM-0000-0000"]):
            assert amc.update_case_menu() is None


# ---------------------------------------------------------------------------
# add_evidence_menu exercises the get_auth seam (3 cases)
# ---------------------------------------------------------------------------

class TestAddEvidenceAuthSeam:
    def _run(self, case_id="AM-2000-0001"):
        # case-id, file name, file path, file size
        with patch("builtins.input", side_effect=[case_id, "proof.pdf", "", "10kb"]):
            amc.add_evidence_menu()

    @patch("builtins.print")
    def test_uploaded_by_from_current_user(self, _p, amc_db, monkeypatch):
        amc.save_case(_seed_case("AM-2000-0001"))
        monkeypatch.setattr(amc, "AUTH_AVAILABLE", True)
        monkeypatch.setattr(amc, "get_auth", lambda: _FakeAuth({"username": "reviewer"}))
        self._run()
        ev = amc.get_case_evidence("AM-2000-0001")
        assert len(ev) == 1
        assert ev[0][0] == "proof.pdf"
        assert ev[0][4] == "reviewer"  # uploaded_by

    @patch("builtins.print")
    def test_auth_unavailable_still_records(self, _p, amc_db, monkeypatch):
        amc.save_case(_seed_case("AM-2000-0001"))
        monkeypatch.setattr(amc, "AUTH_AVAILABLE", False)
        self._run()
        ev = amc.get_case_evidence("AM-2000-0001")
        assert len(ev) == 1
        assert ev[0][4] == ""  # no attributed uploader

    @patch("builtins.print")
    def test_no_current_user_records_blank_uploader(self, _p, amc_db, monkeypatch):
        amc.save_case(_seed_case("AM-2000-0001"))
        monkeypatch.setattr(amc, "AUTH_AVAILABLE", True)
        monkeypatch.setattr(amc, "get_auth", lambda: _FakeAuth(None))
        self._run()
        ev = amc.get_case_evidence("AM-2000-0001")
        assert ev[0][4] == ""


# ---------------------------------------------------------------------------
# stats + read views run cleanly
# ---------------------------------------------------------------------------

class TestStatsAndViews:
    def test_dashboard_stats(self, amc_db):
        amc.save_case(_seed_case("AM-2000-0001", severity="High"))
        amc.save_case(_seed_case("AM-2000-0002", severity="Low"))
        stats = amc.get_dashboard_stats()
        assert stats["total_cases"] == 2
        assert stats["by_severity"] == {"High": 1, "Low": 1}

    @patch("builtins.print")
    def test_list_and_statistics_menus(self, _p, amc_db):
        amc.save_case(_seed_case("AM-2000-0001"))
        assert amc.list_cases_menu() is None
        assert amc.view_statistics_menu() is None
