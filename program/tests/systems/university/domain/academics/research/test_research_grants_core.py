"""
Tests for Research & Grants Management Core Service.

Covers the static manager classes (ResearchProjectManager, GrantApplicationManager,
PublicationManager, MilestoneManager, EquipmentManager, EthicsReviewManager) and
the instance-based GrantTrackerService.
"""

import pytest
import sqlite3
import tempfile
import os
from contextlib import contextmanager
from unittest.mock import patch

MODULE = "education_system.systems.university.domain.academics.research.services.research_grants_core"


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.remove(path)


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _create_static_tables(path):
    """Create the tables used by the static manager classes."""
    conn = _connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS research_projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_title TEXT NOT NULL,
            principal_investigator_id TEXT,
            department TEXT,
            project_type TEXT,
            start_date TEXT,
            project_description TEXT,
            total_budget REAL DEFAULT 0,
            publications_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS research_team_members (
            member_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            staff_id TEXT,
            role TEXT,
            contribution_percentage REAL DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES research_projects(project_id)
        );
        CREATE TABLE IF NOT EXISTS grant_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            grant_name TEXT,
            funding_agency TEXT,
            principal_investigator_id TEXT,
            requested_amount REAL,
            application_deadline TEXT,
            project_id INTEGER,
            decision_status TEXT,
            decision_date TEXT,
            awarded_amount REAL DEFAULT 0,
            grant_period_start TEXT,
            grant_period_end TEXT,
            FOREIGN KEY (project_id) REFERENCES research_projects(project_id)
        );
        CREATE TABLE IF NOT EXISTS research_publications (
            publication_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            title TEXT NOT NULL,
            authors TEXT,
            publication_type TEXT,
            journal_name TEXT,
            publication_date TEXT,
            doi TEXT,
            FOREIGN KEY (project_id) REFERENCES research_projects(project_id)
        );
        CREATE TABLE IF NOT EXISTS research_milestones (
            milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            milestone_name TEXT NOT NULL,
            milestone_description TEXT,
            target_date TEXT,
            FOREIGN KEY (project_id) REFERENCES research_projects(project_id)
        );
        CREATE TABLE IF NOT EXISTS research_equipment (
            equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT NOT NULL,
            equipment_type TEXT,
            serial_number TEXT,
            purchase_cost REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ethics_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            review_type TEXT,
            submission_date TEXT,
            FOREIGN KEY (project_id) REFERENCES research_projects(project_id)
        );
    """)
    conn.close()


@contextmanager
def _fake_transaction(path):
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def _fake_get_connection(path):
    conn = _connect(path)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Static manager tests
# ---------------------------------------------------------------------------

class TestResearchProjectManager:

    def test_create_project_returns_id(self, temp_db):
        _create_static_tables(temp_db)
        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.systems.university.domain.academics.research.services.research_grants_core import ResearchProjectManager
            pid = ResearchProjectManager.create_project(
                "Quantum Computing", "INV001", "Physics", "fundamental",
                "2026-01-01", "A quantum project", 500000
            )
            assert isinstance(pid, int)
            assert pid >= 1

    def test_create_project_persists(self, temp_db):
        _create_static_tables(temp_db)
        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.systems.university.domain.academics.research.services.research_grants_core import ResearchProjectManager
            pid = ResearchProjectManager.create_project(
                "AI Ethics", "INV002", "CS", "applied", "2026-06-01"
            )
        conn = _connect(temp_db)
        row = conn.execute("SELECT * FROM research_projects WHERE project_id=?", (pid,)).fetchone()
        conn.close()
        assert row is not None
        assert row["project_title"] == "AI Ethics"
        assert row["total_budget"] == 0

    def test_add_team_member(self, temp_db):
        _create_static_tables(temp_db)
        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.systems.university.domain.academics.research.services.research_grants_core import ResearchProjectManager
            pid = ResearchProjectManager.create_project(
                "Proj", "INV001", "Dept", "fundamental", "2026-01-01"
            )
            mid = ResearchProjectManager.add_team_member(pid, "STF001", "researcher", 50.0)
            assert isinstance(mid, int)
        conn = _connect(temp_db)
        row = conn.execute("SELECT * FROM research_team_members WHERE member_id=?", (mid,)).fetchone()
        conn.close()
        assert row["staff_id"] == "STF001"
        assert row["contribution_percentage"] == 50.0


class TestGrantApplicationManager:

    def test_submit_application(self, temp_db):
        _create_static_tables(temp_db)
        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.systems.university.domain.academics.research.services.research_grants_core import GrantApplicationManager
            aid = GrantApplicationManager.submit_application(
                "UKRI Grant", "UKRI", "INV001", 100000, "2026-12-01"
            )
            assert isinstance(aid, int)
        conn = _connect(temp_db)
        row = conn.execute("SELECT * FROM grant_applications WHERE application_id=?", (aid,)).fetchone()
        conn.close()
        assert row["grant_name"] == "UKRI Grant"
        assert row["requested_amount"] == 100000

    def test_update_decision(self, temp_db):
        _create_static_tables(temp_db)
        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.systems.university.domain.academics.research.services.research_grants_core import GrantApplicationManager
            aid = GrantApplicationManager.submit_application(
                "Grant A", "Agency", "INV001", 50000, "2026-06-01"
            )
            result = GrantApplicationManager.update_decision(
                aid, "awarded", 45000, "2026-07-01", "2027-06-30"
            )
            assert result is True
        conn = _connect(temp_db)
        row = conn.execute("SELECT * FROM grant_applications WHERE application_id=?", (aid,)).fetchone()
        conn.close()
        assert row["decision_status"] == "awarded"
        assert row["awarded_amount"] == 45000


class TestPublicationManager:

    def test_record_publication_without_project(self, temp_db):
        _create_static_tables(temp_db)
        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.systems.university.domain.academics.research.services.research_grants_core import PublicationManager
            pub_id = PublicationManager.record_publication(
                "Paper Title", "Author A, Author B", "journal_article",
                journal_name="Nature", publication_date="2026-03-15", doi="10.1234/test"
            )
            assert isinstance(pub_id, int)

    def test_record_publication_with_project_updates_count(self, temp_db):
        _create_static_tables(temp_db)
        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.systems.university.domain.academics.research.services.research_grants_core import (
                ResearchProjectManager, PublicationManager
            )
            pid = ResearchProjectManager.create_project(
                "Proj", "INV001", "Dept", "applied", "2026-01-01"
            )
            PublicationManager.record_publication(
                "Paper", "Auth", "journal_article", project_id=pid
            )
        conn = _connect(temp_db)
        row = conn.execute("SELECT publications_count FROM research_projects WHERE project_id=?", (pid,)).fetchone()
        conn.close()
        assert row["publications_count"] == 1


class TestMilestoneManager:

    def test_create_milestone(self, temp_db):
        _create_static_tables(temp_db)
        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.systems.university.domain.academics.research.services.research_grants_core import (
                ResearchProjectManager, MilestoneManager
            )
            pid = ResearchProjectManager.create_project(
                "Proj", "INV001", "Dept", "fundamental", "2026-01-01"
            )
            mid = MilestoneManager.create_milestone(pid, "Phase 1", "2026-06-01", "First phase")
            assert isinstance(mid, int)
        conn = _connect(temp_db)
        row = conn.execute("SELECT * FROM research_milestones WHERE milestone_id=?", (mid,)).fetchone()
        conn.close()
        assert row["milestone_name"] == "Phase 1"


class TestEquipmentManager:

    def test_register_equipment(self, temp_db):
        _create_static_tables(temp_db)
        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.systems.university.domain.academics.research.services.research_grants_core import EquipmentManager
            eid = EquipmentManager.register_equipment(
                "Spectrometer", "lab_instrument", "SN-12345", 25000
            )
            assert isinstance(eid, int)
        conn = _connect(temp_db)
        row = conn.execute("SELECT * FROM research_equipment WHERE equipment_id=?", (eid,)).fetchone()
        conn.close()
        assert row["equipment_name"] == "Spectrometer"
        assert row["purchase_cost"] == 25000


class TestEthicsReviewManager:

    def test_submit_ethics_review(self, temp_db):
        _create_static_tables(temp_db)
        with patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)):
            from education_system.systems.university.domain.academics.research.services.research_grants_core import (
                ResearchProjectManager, EthicsReviewManager
            )
            pid = ResearchProjectManager.create_project(
                "Proj", "INV001", "Dept", "fundamental", "2026-01-01"
            )
            rid = EthicsReviewManager.submit_ethics_review(pid, "full_review", "2026-02-01")
            assert isinstance(rid, int)
        conn = _connect(temp_db)
        row = conn.execute("SELECT * FROM ethics_reviews WHERE review_id=?", (rid,)).fetchone()
        conn.close()
        assert row["review_type"] == "full_review"


# ---------------------------------------------------------------------------
# GrantTrackerService tests
# ---------------------------------------------------------------------------

class TestGrantTrackerService:

    @pytest.fixture(autouse=True)
    def setup_tracker(self, temp_db):
        self.db_path = temp_db
        self.patches = [
            patch(f"{MODULE}.transaction", lambda **kw: _fake_transaction(temp_db)),
            patch(f"{MODULE}.get_connection", lambda **kw: _fake_get_connection(temp_db)),
        ]
        for p in self.patches:
            p.start()
        from education_system.systems.university.domain.academics.research.services.research_grants_core import GrantTrackerService
        self.tracker = GrantTrackerService()
        yield
        for p in self.patches:
            p.stop()

    def test_create_application(self):
        gid = self.tracker.create_application("Test Grant", funding_body="EPSRC", department="Physics")
        assert isinstance(gid, int)
        assert gid >= 1

    def test_get_application(self):
        gid = self.tracker.create_application("Grant X", funding_body="AHRC")
        app = self.tracker.get_application(gid)
        assert app is not None
        assert app["title"] == "Grant X"
        assert app["funding_body"] == "AHRC"
        assert app["status"] == "draft"

    def test_get_application_not_found(self):
        result = self.tracker.get_application(99999)
        assert result is None

    def test_list_applications_all(self):
        self.tracker.create_application("Grant A")
        self.tracker.create_application("Grant B")
        apps = self.tracker.list_applications()
        assert len(apps) == 2

    def test_list_applications_filter_by_status(self):
        gid = self.tracker.create_application("Grant A")
        self.tracker.create_application("Grant B")
        self.tracker.update_application_status(gid, "submitted")
        submitted = self.tracker.list_applications(status="submitted")
        assert len(submitted) == 1
        assert submitted[0]["title"] == "Grant A"

    def test_update_application_status(self):
        gid = self.tracker.create_application("Grant X")
        self.tracker.update_application_status(gid, "awarded", amount_awarded=75000)
        app = self.tracker.get_application(gid)
        assert app["status"] == "awarded"
        assert app["amount_awarded"] == 75000

    def test_update_status_submitted_sets_timestamp(self):
        gid = self.tracker.create_application("Grant Y")
        self.tracker.update_application_status(gid, "submitted")
        app = self.tracker.get_application(gid)
        assert app["submitted_at"] is not None

    def test_add_and_get_milestones(self):
        gid = self.tracker.create_application("Grant M")
        mid = self.tracker.add_milestone(gid, "Kickoff", description="Project start", deadline="2026-06-01")
        assert isinstance(mid, int)
        milestones = self.tracker.get_milestones(gid)
        assert len(milestones) == 1
        assert milestones[0]["milestone_title"] == "Kickoff"
        assert milestones[0]["status"] == "pending"

    def test_update_milestone_completed(self):
        gid = self.tracker.create_application("Grant M")
        mid = self.tracker.add_milestone(gid, "Final Report")
        self.tracker.update_milestone(mid, "completed")
        milestones = self.tracker.get_milestones(gid)
        assert milestones[0]["status"] == "completed"
        assert milestones[0]["completed_at"] is not None

    def test_add_budget_item_and_summary(self):
        gid = self.tracker.create_application("Grant B")
        self.tracker.add_budget_item(gid, "personnel", "Research Assistant", 30000)
        self.tracker.add_budget_item(gid, "equipment", "Laptop", 2000)
        summary = self.tracker.get_budget_summary(gid)
        assert summary["total"] == 32000
        assert summary["by_category"]["personnel"] == 30000
        assert summary["by_category"]["equipment"] == 2000
        assert len(summary["items"]) == 2

    def test_get_pipeline_summary(self):
        self.tracker.create_application("A")
        self.tracker.create_application("B")
        gid = self.tracker.create_application("C")
        self.tracker.update_application_status(gid, "submitted")
        pipeline = self.tracker.get_pipeline_summary()
        assert pipeline.get("draft") == 2
        assert pipeline.get("submitted") == 1

    def test_get_success_rate_no_decisions(self):
        self.tracker.create_application("A")
        result = self.tracker.get_success_rate()
        assert result["total_decided"] == 0
        assert result["success_rate"] == 0

    def test_get_success_rate_with_decisions(self):
        g1 = self.tracker.create_application("A")
        g2 = self.tracker.create_application("B")
        g3 = self.tracker.create_application("C")
        self.tracker.update_application_status(g1, "awarded", 50000)
        self.tracker.update_application_status(g2, "rejected")
        self.tracker.update_application_status(g3, "awarded", 30000)
        result = self.tracker.get_success_rate()
        assert result["total_decided"] == 3
        assert result["awarded"] == 2
        assert abs(result["success_rate"] - 66.7) < 0.1

    def test_get_funding_by_department(self):
        g1 = self.tracker.create_application("A", department="Physics", amount_requested=100000)
        g2 = self.tracker.create_application("B", department="Physics", amount_requested=50000)
        g3 = self.tracker.create_application("C", department="Chemistry", amount_requested=80000)
        self.tracker.update_application_status(g1, "awarded", 90000)
        depts = self.tracker.get_funding_by_department()
        assert len(depts) == 2
        physics = next(d for d in depts if d["department"] == "Physics")
        assert physics["applications"] == 2
        assert physics["total_requested"] == 150000
        assert physics["total_awarded"] == 90000

    def test_get_upcoming_deadlines(self):
        self.tracker.create_application("Soon", deadline="2026-04-10")
        self.tracker.create_application("Later", deadline="2027-12-31")
        self.tracker.create_application("No deadline")
        # The date-based query depends on 'now'; just verify it returns a list
        deadlines = self.tracker.get_upcoming_deadlines(days=365 * 5)
        assert isinstance(deadlines, list)
