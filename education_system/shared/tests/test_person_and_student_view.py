"""Tests for the shared Person model and the single student view."""

import sqlite3

import pytest

from education_system.shared.auth.schema import initialise_auth_db
from education_system.shared.cross_system import (
    identity_service,
    person,
    progression,
    student_view,
)


@pytest.fixture()
def auth_db(tmp_path):
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)
    identity_service._initialised.discard(path)
    return path


# ── Person model ─────────────────────────────────────────────────────────

def test_person_get_and_demographics(auth_db):
    jid = identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace",
        date_of_birth="2019-12-10", system="nursery",
        student_id="N1", nhs_number="943", upn="UPN1", db_path=auth_db)
    identity_service.link_system(jid, "primary", student_id="P1",
                                 db_path=auth_db)

    p = person.get(jid, db_path=auth_db)
    assert p.full_name == "Ada Lovelace"
    assert p.local_id("nursery") == "N1"
    assert p.local_id("primary") == "P1"
    assert p.systems == ["nursery", "primary"]
    assert p.demographics() == {
        "legal_first_name": "Ada", "legal_last_name": "Lovelace",
        "date_of_birth": "2019-12-10", "nhs_number": "943", "upn": "UPN1"}


def test_person_get_by_student(auth_db):
    jid = identity_service.get_or_create_journey(
        first_name="Grace", last_name="Hopper",
        date_of_birth="2018-12-09", system="secondary",
        student_id="Y7", db_path=auth_db)
    p = person.get_by_student("secondary", "Y7", db_path=auth_db)
    assert p is not None and p.journey_id == jid


def test_update_demographics_single_source_of_truth(auth_db):
    jid = identity_service.get_or_create_journey(
        first_name="Mary", last_name="Smith",
        date_of_birth="2017-01-01", system="primary",
        student_id="P9", db_path=auth_db)
    updated = person.update_demographics(
        jid, legal_last_name="Somerville", upn="UPN9", db_path=auth_db)
    assert updated.legal_last_name == "Somerville"
    assert updated.legal_first_name == "Mary"  # untouched
    assert updated.upn == "UPN9"


def test_update_demographics_unknown_journey(auth_db):
    with pytest.raises(ValueError):
        person.update_demographics("nope", legal_first_name="X",
                                   db_path=auth_db)


def test_link_local_record_stamps_journey_id(tmp_path, auth_db):
    # A tiny stand-in for a system's pupils table.
    sys_db = tmp_path / "primary.db"
    conn = sqlite3.connect(str(sys_db))
    conn.execute("CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY, "
                 "first_name TEXT)")
    conn.execute("INSERT INTO pupils VALUES ('P1', 'Ada')")
    conn.commit()
    conn.close()

    ok = person.link_local_record("primary", "P1", "JID-123",
                                  db_path=str(sys_db))
    assert ok is True
    conn = sqlite3.connect(str(sys_db))
    row = conn.execute(
        "SELECT journey_id FROM pupils WHERE pupil_id='P1'").fetchone()
    conn.close()
    assert row[0] == "JID-123"  # column added + stamped


# ── Single student view ──────────────────────────────────────────────────

@pytest.fixture()
def two_system_dbs(tmp_path):
    """A nursery.db (record only) and a university.db (record + attendance)."""
    nursery = tmp_path / "nursery.db"
    conn = sqlite3.connect(str(nursery))
    conn.execute(
        "CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY, first_name TEXT, "
        "last_name TEXT, date_of_birth TEXT, room TEXT, status TEXT)")
    conn.execute("INSERT INTO pupils VALUES "
                 "('N1','Ada','Lovelace','2005-01-01','Toddler','left')")
    conn.commit()
    conn.close()

    uni = tmp_path / "uni.db"
    conn = sqlite3.connect(str(uni))
    conn.execute(
        "CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, "
        "last_name TEXT, date_of_birth TEXT, course TEXT, status TEXT)")
    conn.execute("INSERT INTO students VALUES "
                 "('U1','Ada','Lovelace','2005-01-01','CS','Active')")
    conn.execute(
        "CREATE TABLE attendance (student_id TEXT, module_id TEXT, "
        "class_date TEXT, status TEXT)")
    conn.executemany(
        "INSERT INTO attendance VALUES (?,?,?,?)",
        [("U1", "M1", "2024-01-01", "present"),
         ("U1", "M1", "2024-01-02", "present"),
         ("U1", "M1", "2024-01-03", "absent")])
    conn.commit()
    conn.close()
    return {"nursery": nursery, "university": uni}


def test_build_overview_aggregates_phases(auth_db, two_system_dbs):
    jid = identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace",
        date_of_birth="2005-01-01", system="nursery",
        student_id="N1", db_path=auth_db)
    identity_service.link_system(jid, "university", student_id="U1",
                                 set_current=True, db_path=auth_db)
    identity_service.record_transition(
        jid, from_system="nursery", to_system="university",
        reason="test", db_path=auth_db)

    ov = student_view.build_overview(
        jid, db_paths=two_system_dbs, auth_db=auth_db)

    assert ov["found"] is True
    assert ov["person"]["full_name"] == "Ada Lovelace"
    systems = [p["system"] for p in ov["phases"]]
    assert systems == ["nursery", "university"]  # phase order preserved

    uni = next(p for p in ov["phases"] if p["system"] == "university")
    assert uni["record"]["course"] == "CS"
    assert uni["attendance"]["total"] == 3
    assert uni["attendance"]["by_mark"]["present"] == 2
    assert uni["attendance"]["by_mark"]["absent"] == 1

    assert len(ov["transitions"]) == 1
    assert ov["transitions"][0]["to_system"] == "university"


def test_build_overview_for_student(auth_db, two_system_dbs):
    jid = identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace",
        date_of_birth="2005-01-01", system="university",
        student_id="U1", db_path=auth_db)
    ov = student_view.build_overview_for_student(
        "university", "U1", db_paths=two_system_dbs, auth_db=auth_db)
    assert ov["found"] is True
    assert ov["journey_id"] == jid


def test_build_overview_missing_journey(auth_db):
    ov = student_view.build_overview("ghost", auth_db=auth_db)
    assert ov["found"] is False


def test_format_overview_text(auth_db, two_system_dbs):
    jid = identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace",
        date_of_birth="2005-01-01", system="nursery",
        student_id="N1", db_path=auth_db)
    identity_service.link_system(jid, "university", student_id="U1",
                                 db_path=auth_db)
    ov = student_view.build_overview(
        jid, db_paths=two_system_dbs, auth_db=auth_db)
    text = student_view.format_overview_text(ov)
    assert "Ada Lovelace" in text
    assert "University" in text
    assert "Nursery" in text
