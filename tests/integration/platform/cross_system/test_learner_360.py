"""Learner 360: sections, second spells, attendance, sensitivity gating,
backward compatibility of student_view, and journey_service by journey_id.

Temp auth and system databases only.
"""

from __future__ import annotations

import sqlite3

import pytest

from education_system.platform.cross_system import (
    enrolment_schema,
    enrolments,
    identity_service,
    learner_360,
    qualifications,
    student_view,
    transitions,
)
from education_system.platform.cross_system.journey_service import JourneyService
from education_system.platform.identity.auth.db import connect

DOB = "2012-05-01"


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "auth.db")
    enrolment_schema.reset_schema_cache_for_test()
    qualifications.reset_schema_cache_for_test()
    identity_service._initialised.clear()
    enrolment_schema.ensure_enrolment_schema(path)
    yield path
    enrolment_schema.reset_schema_cache_for_test()
    qualifications.reset_schema_cache_for_test()
    identity_service._initialised.clear()


def _sqlite(path, *statements, rows=()):
    conn = sqlite3.connect(str(path))
    for stmt in statements:
        conn.execute(stmt)
    for sql, args in rows:
        conn.execute(sql, args)
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def systems(tmp_path):
    nursery = _sqlite(
        tmp_path / "nursery.db",
        "CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY, first_name TEXT, "
        "last_name TEXT, date_of_birth TEXT, room TEXT, status TEXT)",
        "CREATE TABLE attendance_records (record_id TEXT, pupil_id TEXT, "
        "attend_date TEXT, status TEXT)",
        rows=[("INSERT INTO pupils VALUES ('N1','Ada','Lovelace',?,'Robins','left')",
               (DOB,)),
              ("INSERT INTO attendance_records VALUES ('1','N1','2015-01-01','present')", ()),
              ("INSERT INTO attendance_records VALUES ('2','N1','2015-01-02','absent')", ())])
    primary = _sqlite(
        tmp_path / "primary.db",
        "CREATE TABLE pupils (pupil_id TEXT PRIMARY KEY, first_name TEXT, "
        "last_name TEXT, date_of_birth TEXT, year_group TEXT, "
        "send_status TEXT, journey_id TEXT)",
        "CREATE TABLE attendance_records (record_id INTEGER PRIMARY KEY, "
        "pupil_id TEXT, date TEXT, session TEXT, mark TEXT)",
        "CREATE TABLE house_point_awards (award_id INTEGER PRIMARY KEY, "
        "house_id INTEGER, pupil_id TEXT, points INTEGER, reason TEXT, "
        "awarded_on TEXT)",
        rows=[("INSERT INTO pupils VALUES ('P1','Ada','Lovelace',?,'3','K',NULL)", (DOB,)),
              ("INSERT INTO pupils VALUES ('P2','Ada','Lovelace',?,'4','K',NULL)", (DOB,)),
              # A different Ada Lovelace, never registered: must not appear.
              ("INSERT INTO pupils VALUES ('P9','Ada','Lovelace','2011-01-01','5','',NULL)", ()),
              ("INSERT INTO attendance_records (pupil_id, date, session, mark) "
               "VALUES ('P2','2020-01-01','AM','/')", ()),
              ("INSERT INTO attendance_records (pupil_id, date, session, mark) "
               "VALUES ('P2','2020-01-01','PM','N')", ()),
              ("INSERT INTO house_point_awards (house_id, pupil_id, points, reason, "
               "awarded_on) VALUES (1,'P2',5,'kindness','2020-02-02')", ())])
    sixth = _sqlite(
        tmp_path / "sixth.db",
        "CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, "
        "last_name TEXT, date_of_birth TEXT, status TEXT)",
        "CREATE TABLE attendance_records (record_id INTEGER PRIMARY KEY, "
        "slot_id INTEGER, student_id TEXT, date TEXT, status TEXT)",
        rows=[("INSERT INTO students VALUES ('SF1','Ada','Lovelace',?,'Active')", (DOB,)),
              ("INSERT INTO attendance_records (slot_id, student_id, date, status) "
               "VALUES (1,'SF1','2029-09-01','present')", ()),
              ("INSERT INTO attendance_records (slot_id, student_id, date, status) "
               "VALUES (1,'SF1','2029-09-02','late')", ())])
    appr = _sqlite(
        tmp_path / "appr.db",
        "CREATE TABLE apprentices (apprentice_id INTEGER PRIMARY KEY, "
        "given_name TEXT, family_name TEXT, date_of_birth TEXT, status TEXT, "
        "support_needs TEXT, programme_id INTEGER)",
        "CREATE TABLE session_attendance (apprentice_id INTEGER, mark TEXT)",
        "CREATE TABLE portfolio_evidence (apprentice_id INTEGER, notes TEXT)",
        "CREATE TABLE documents (document_id INTEGER PRIMARY KEY, "
        "apprentice_id INTEGER, category TEXT, title TEXT, stored_name TEXT, "
        "created_at TEXT)",
        rows=[("INSERT INTO apprentices VALUES (7,'Ada','Lovelace',?,"
               "'On Programme','dyslexia — extra time',NULL)", (DOB,)),
              ("INSERT INTO session_attendance VALUES (7,'present')", ()),
              ("INSERT INTO portfolio_evidence VALUES (7,'FORMATIVE NOTE')", ()),
              ("INSERT INTO documents (apprentice_id, category, title, "
               "stored_name, created_at) VALUES (7,'Agreement',"
               "'Apprenticeship agreement','f00.pdf','2030-01-01')", ()),
              ("INSERT INTO documents (apprentice_id, category, title, "
               "stored_name, created_at) VALUES (7,'Safeguarding',"
               "'Disclosure record','secret.pdf','2030-01-02')", ())])
    return {"nursery": nursery, "primary": primary, "sixth_form": sixth,
            "apprenticeships": appr}


@pytest.fixture
def ada(db):
    """Nursery -> two primary schools -> sixth form, plus an apprenticeship."""
    jid = identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace", date_of_birth=DOB,
        system="nursery", student_id="N1", nhs_number="9434765919",
        db_path=db)
    enrolments.end_local_enrolment("nursery", "N1", reason="progressed",
                                   status="completed", db_path=db)
    p1 = enrolments.create_enrolment(
        journey_id=jid, system="primary", local_student_id="P1",
        institution_id="school-a", status="active", year_group="3",
        db_path=db)
    enrolments.close_enrolment(p1["enrolment_id"], reason="moved house",
                               status="transferred", db_path=db)
    identity_service.link_system(jid, "primary", student_id="P2", db_path=db)
    identity_service.link_system(jid, "sixth_form", student_id="SF1",
                                 set_current=True, db_path=db)
    identity_service.link_system(jid, "apprenticeships", student_id="7",
                                 db_path=db)
    conn = connect(db)
    try:
        conn.execute(
            "INSERT INTO safeguarding_alerts (alert_id, journey_id, "
            "source_system, category, summary) VALUES "
            "('SG1', ?, 'primary', 'neglect', 'SECRET DETAIL')", (jid,))
        conn.commit()
    finally:
        conn.close()
    return jid


def _view(jid, db, systems, **kw):
    return learner_360.build_learner_360(jid, db_paths=systems, auth_db=db, **kw)


# ── Sections ────────────────────────────────────────────────────────

def test_every_section_is_present_for_a_trusted_caller(db, systems, ada):
    view = _view(ada, db, systems)
    assert view["found"] is True
    for key, _title in learner_360.SECTION_TITLES:
        assert view[key] is not None, key
    assert view["restricted_sections"] == []


def test_second_spell_in_the_same_phase_is_visible(db, systems, ada):
    view = _view(ada, db, systems)
    primary = [r["student_id"] for r in view["records"] if r["system"] == "primary"]
    assert primary == ["P1", "P2"]
    starts = [e for e in view["timeline"]
              if e["kind"] == "enrolment_started" and e["system"] == "primary"]
    assert len(starts) == 2
    moved = [t for t in view["transfers"] if t["kind"] == "left institution"]
    assert moved and moved[0]["institution_id"] == "school-a"


def test_attendance_for_nursery_primary_and_sixth_form(db, systems, ada):
    by = {(a["system"], a["student_id"]): a
          for a in _view(ada, db, systems)["attendance"]}
    assert by[("nursery", "N1")]["total"] == 2
    assert by[("nursery", "N1")]["present_pct"] == 50.0
    assert by[("primary", "P2")]["by_mark"] == {"/": 1, "N": 1}
    assert by[("sixth_form", "SF1")]["present_pct"] == 100.0


def test_current_education_and_lineage(db, systems, ada):
    view = _view(ada, db, systems)
    active = {a["system"] for a in view["current_education"]["active"]}
    assert {"primary", "sixth_form", "apprenticeships"} <= active
    assert "nursery" not in active
    assert all(a["source_system"] for a in view["current_education"]["active"])
    sections = {li["section"] for li in view["lineage"]}
    assert {"enrolments", "records", "attendance"} <= sections


def test_achievements_and_progression(db, systems, ada):
    view = _view(ada, db, systems)
    [points] = view["achievements"]
    assert points["kind"] == "house_points" and points["total_points"] == 5
    transitions.start_transition(journey_id=ada, destination_system="university",
                                 db_path=db)
    progression = _view(ada, db, systems)["progression"]
    assert progression["recommended_next"] == "university"
    assert len(progression["open_transitions"]) == 1


def test_timeline_records_a_repeated_year(db, systems, ada):
    p2 = enrolments.current_enrolment(ada, "primary", db_path=db)
    enrolments.set_year_group(p2["enrolment_id"], "4", db_path=db)
    enrolments.set_year_group(p2["enrolment_id"], "4", academic_year="2021/22",
                              db_path=db)
    years = [e for e in _view(ada, db, systems)["timeline"]
             if e["kind"] == "year_group"]
    assert [e["detail"].split(":")[0] for e in years][-2:] == ["started", "repeated"]


def test_system_access_through_the_login_link(db, systems, ada):
    conn = connect(db)
    try:
        uid = conn.execute("INSERT INTO users (username, password_hash) "
                           "VALUES ('ada', 'x')").lastrowid
        conn.commit()
    finally:
        conn.close()
    identity_service.link_user_account(uid, ada, actor="admin", db_path=db)
    [account] = _view(ada, db, systems)["system_access"]
    assert account["username"] == "ada"


# ── Sensitivity ─────────────────────────────────────────────────────

def test_safeguarding_is_a_count_for_safeguarding_roles_and_never_detail(
        db, systems, ada):
    teacher = _view(ada, db, systems, viewer_role="teacher")
    assert teacher["support"]["safeguarding"]["visible"] is False
    dsl = _view(ada, db, systems, viewer_role="dsl")
    assert dsl["support"]["safeguarding"]["open_alerts"] == 1
    for view in (teacher, dsl, _view(ada, db, systems)):
        text = repr(view)
        assert "SECRET DETAIL" not in text
        assert "neglect" not in text


def test_support_is_flags_not_detail(db, systems, ada):
    support = _view(ada, db, systems, viewer_role="staff")["support"]
    flags = {f["flag"] for f in support["flags"]}
    assert "SEND support recorded" in flags
    assert "Support needs recorded" in flags
    assert "dyslexia" not in repr(support)


def test_formative_apprenticeship_data_is_never_read(db, systems, ada):
    assert "FORMATIVE NOTE" not in repr(_view(ada, db, systems))


def test_documents_are_links_and_sensitive_ones_are_withheld(db, systems, ada):
    view = _view(ada, db, systems, viewer_role="admin")
    [doc] = view["documents"]
    assert doc["title"] == "Apprenticeship agreement"
    assert doc["link"].startswith("apprenticeships:documents:")
    assert view["support"]["documents_withheld"] == 1
    text = repr(view)
    assert "f00.pdf" not in text and "Disclosure record" not in text


def test_learner_or_parent_view_hides_identifiers_and_support(db, systems, ada):
    view = _view(ada, db, systems, viewer_role="parent")
    assert "nhs_number" not in view["overview"]
    assert view["overview"]["date_of_birth"] == DOB
    assert view["support"] is None and view["lineage"] is None
    assert set(view["restricted_sections"]) == {"support", "lineage"}
    p2 = next(r for r in view["records"] if r["student_id"] == "P2")
    assert "send_status" not in p2["record"]


@pytest.mark.parametrize("role", ["employer", "end_point_assessor", "janitor"])
def test_external_and_unknown_roles_get_the_narrow_view(db, systems, ada, role):
    view = _view(ada, db, systems, viewer_role=role)
    assert view["viewer"]["tier"] == "external"
    assert view["timeline"] is None and view["records"] is None
    assert "date_of_birth" not in view["overview"]
    assert {a["system"] for a in view["attendance"]} == {"apprenticeships"}


def test_viewer_system_marks_cross_system_rows(db, systems, ada):
    view = _view(ada, db, systems, viewer_role="teacher",
                 viewer_system="sixth_form")
    marks = {r["system"]: r["cross_system"] for r in view["records"]}
    assert marks["sixth_form"] is False and marks["primary"] is True


def test_unknown_journey(db, systems):
    assert _view("ghost", db, systems) == {"journey_id": "ghost", "found": False}


# ── student_view compatibility ──────────────────────────────────────

def test_build_overview_keeps_its_contract(db, systems, ada):
    ov = student_view.build_overview(ada, db_paths=systems, auth_db=db)
    assert {"journey_id", "found", "person", "phases", "transitions",
            "learner_360"} <= set(ov)
    assert ov["person"]["full_name"] == "Ada Lovelace"
    assert ov["person"]["nhs_number"] == "9434765919"
    systems_seen = [p["system"] for p in ov["phases"]]
    assert systems_seen[:3] == ["nursery", "primary", "primary"]
    nursery = ov["phases"][0]
    assert nursery["attendance"]["total"] == 2
    assert "Ada Lovelace" in student_view.format_overview_text(ov)


# ── journey_service by journey_id ───────────────────────────────────

def test_get_journey_resolves_through_the_registry_not_names(db, systems, ada):
    svc = JourneyService(db_paths=systems, auth_db=db)
    journey = svc.get_journey(student_id="P2", system="primary")
    assert journey["matched_by"] == "journey_id"
    assert journey["journey_id"] == ada
    ids = [(s["system"], s["student_id"]) for s in journey["stages"]]
    assert ("primary", "P1") in ids and ("primary", "P2") in ids
    assert ("primary", "P9") not in ids      # same name, different person
    assert svc.get_journey(journey_id=ada)["journey_id"] == ada


def test_get_journey_falls_back_to_names_only_for_unlinked_records(db, systems):
    svc = JourneyService(db_paths=systems, auth_db=db)
    journey = svc.get_journey(student_id="P9", system="primary")
    assert journey["matched_by"] == "name"
    assert journey["journey_id"] is None
