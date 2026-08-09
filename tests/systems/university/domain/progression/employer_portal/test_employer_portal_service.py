"""Tests for EmployerPortalService.

Service creates its own employer-portal tables in init_schema() against the
isolated DEFAULT_DB_PATH. Dashboard/progress helpers additionally read the
internships / internship_placements tables, which we create in-line.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.domain.progression.employer_portal.services.employer_portal_service import (
    EmployerPortalService,
    EmployerPortalError,
)


def _create_internship_tables(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS internships (
            internship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, company TEXT, start_date TEXT, end_date TEXT
        );
        CREATE TABLE IF NOT EXISTS internship_placements (
            placement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            internship_id INTEGER, student_id TEXT,
            start_date TEXT, end_date TEXT, status TEXT
        );
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def svc(temp_db):
    # placement_reviews carries an FK to internship_placements, so that table
    # must exist for inserts to succeed under foreign_keys=ON.
    _create_internship_tables(temp_db)
    return EmployerPortalService()


@pytest.fixture
def placement_id(svc, temp_db):
    """Seed one internship + placement and return the placement_id so review
    inserts satisfy the FK to internship_placements."""
    _, pid = _seed_internship_tables(temp_db)
    return pid


def _seed_internship_tables(db_path, company="Acme Corp"):
    _create_internship_tables(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO internships (title, company, start_date, end_date) VALUES (?, ?, ?, ?)",
        ("Software Intern", company, "2026-01-01", "2026-06-01"),
    )
    internship_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO internship_placements (internship_id, student_id, start_date, end_date, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (internship_id, "STU100", "2026-01-01", "2026-06-01", "active"),
    )
    placement_id = cur.lastrowid
    conn.commit()
    conn.close()
    return internship_id, placement_id


def test_register_and_list_employer(svc):
    eid = svc.register_employer("Acme Corp", contact_name="Jane", sector="Tech")
    assert isinstance(eid, int)

    employers = svc.list_employers()
    assert len(employers) == 1
    assert employers[0]["company_name"] == "Acme Corp"
    assert employers[0]["contact_name"] == "Jane"


def test_register_employer_blank_name_raises(svc):
    with pytest.raises(EmployerPortalError):
        svc.register_employer("   ")


def test_update_employer(svc):
    eid = svc.register_employer("Beta Ltd")
    svc.update_employer(eid, contact_name="Bob", sector="Finance", bogus_field="ignored")
    emp = svc.get_employer_by_company("Beta Ltd")
    assert emp["contact_name"] == "Bob"
    assert emp["sector"] == "Finance"


def test_get_employer_by_company_missing(svc):
    assert svc.get_employer_by_company("Nonexistent") is None


def test_schedule_review_bad_date_raises(svc):
    with pytest.raises(EmployerPortalError):
        svc.schedule_review(1, "01-01-2026")


def test_schedule_and_list_reviews(svc, placement_id):
    rid = svc.schedule_review(placement_id, "2026-03-01", review_type="monthly")
    assert isinstance(rid, int)
    reviews = svc.list_reviews(placement_id=placement_id)
    assert len(reviews) == 1
    assert reviews[0]["status"] == "scheduled"


def test_list_reviews_invalid_status_raises(svc):
    with pytest.raises(EmployerPortalError):
        svc.list_reviews(status="bogus")


def test_complete_review_updates_row(svc, placement_id):
    rid = svc.schedule_review(placement_id, "2026-03-01")
    svc.complete_review(rid, on_track=True, competency_progress="Good",
                        hours_logged=120.0, employer_feedback="On target")
    reviews = svc.list_reviews(placement_id=placement_id, status="completed")
    assert len(reviews) == 1
    assert reviews[0]["on_track"] == 1
    assert reviews[0]["hours_logged"] == 120.0


def test_complete_review_missing_raises(svc):
    with pytest.raises(EmployerPortalError):
        svc.complete_review(9999, on_track=False, competency_progress="",
                            hours_logged=0, employer_feedback="")


def test_sign_off_review(svc, placement_id):
    rid = svc.schedule_review(placement_id, "2026-03-01")
    svc.sign_off_review(rid, "employer", "Manager Mike", comments="Approved")
    reviews = svc.list_reviews(placement_id=placement_id)
    assert reviews[0]["employer_signed"] == 1


def test_sign_off_invalid_signer_raises(svc, placement_id):
    rid = svc.schedule_review(placement_id, "2026-03-01")
    with pytest.raises(EmployerPortalError):
        svc.sign_off_review(rid, "random", "Someone")


def test_employer_dashboard(svc, temp_db):
    _seed_internship_tables(temp_db, company="Acme Corp")
    eid = svc.register_employer("Acme Corp")
    dash = svc.get_employer_dashboard(eid)
    assert dash["employer"]["company_name"] == "Acme Corp"
    assert dash["total_placements"] == 1
    assert dash["active_placements"] == 1


def test_get_placement_progress(svc, temp_db):
    _, placement_id = _seed_internship_tables(temp_db)
    rid = svc.schedule_review(placement_id, "2026-02-01")
    svc.complete_review(rid, on_track=True, competency_progress="ok",
                        hours_logged=40.0, employer_feedback="good")
    prog = svc.get_placement_progress(placement_id)
    assert prog["review_count"] == 1
    assert prog["total_hours_logged"] == 40.0


def test_get_overdue_reviews(svc, temp_db):
    _, placement_id = _seed_internship_tables(temp_db)
    svc.schedule_review(placement_id, "2000-01-01")  # far in the past
    overdue = svc.get_overdue_reviews()
    assert len(overdue) == 1
    assert overdue[0]["placement_id"] == placement_id
