"""learner_qualification: recording, projection (systems + handovers),
the transcript repointed to journey_id, and create-path registration.

Temp auth and system databases only.
"""

from __future__ import annotations

import sqlite3

import pytest

from education_system.platform.cross_system import (
    enrolment_schema,
    enrolments,
    identity_service,
    person,
    qualifications,
    transitions,
)
from education_system.platform.features.transcript.transcript_service import (
    TranscriptService,
)
from education_system.platform.identity.auth.db import connect

DOB = "2008-03-14"


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


def _events(db, name):
    conn = connect(db)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT event_name, payload_json FROM cross_system_event_outbox "
            "WHERE event_name = ? ORDER BY rowid", (name,)).fetchall()]
    finally:
        conn.close()


def _fe_db(path):
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT,
            last_name TEXT, date_of_birth TEXT, status TEXT);
        CREATE TABLE courses (course_id TEXT PRIMARY KEY, title TEXT,
            qualification_type TEXT, level TEXT, awarding_body TEXT);
        CREATE TABLE enrolments (enrolment_id INTEGER PRIMARY KEY,
            student_id TEXT, course_id TEXT, status TEXT, final_grade TEXT,
            end_date TEXT);
        INSERT INTO students VALUES ('FE1','Mary','Somerville','2008-03-14','enrolled');
        INSERT INTO students VALUES ('FE9','Unlinked','Person','2001-01-01','enrolled');
        INSERT INTO courses VALUES ('ENG3','Level 3 Engineering','BTEC','3','Pearson');
        INSERT INTO courses VALUES ('MAT2','Maths GCSE resit','GCSE','2','AQA');
        INSERT INTO enrolments VALUES (1,'FE1','ENG3','completed','Distinction','2026-07-01');
        INSERT INTO enrolments VALUES (2,'FE1','MAT2','completed','U','2026-07-01');
        INSERT INTO enrolments VALUES (3,'FE1','MAT2','active',NULL,NULL);
    """)
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def fe(tmp_path):
    return {"fe_college": _fe_db(tmp_path / "fe.db")}


@pytest.fixture
def mary(db):
    return identity_service.get_or_create_journey(
        first_name="Mary", last_name="Somerville", date_of_birth=DOB,
        system="fe_college", student_id="FE1", db_path=db)


# ── record_qualification ────────────────────────────────────────────

def test_recording_publishes_once_and_again_only_on_a_new_grade(db, mary):
    kw = dict(source_system="fe_college", title="Level 3 Engineering",
              level=3, grade="Merit", source_ref="fe_college:enrolments:1",
              db_path=db)
    first = qualifications.record_qualification(mary, **kw)
    qualifications.record_qualification(mary, **kw)          # re-sync
    assert len(_events(db, "qualification.awarded")) == 1
    remark = qualifications.record_qualification(mary, **{**kw, "grade": "Distinction"})
    assert remark["qualification_id"] == first["qualification_id"]
    assert len(_events(db, "qualification.awarded")) == 2
    [row] = qualifications.list_for_journey(mary, db_path=db)
    assert (row["grade"], row["level"]) == ("Distinction", "3")


def test_recording_requires_a_known_journey_and_a_title(db):
    with pytest.raises(ValueError):
        qualifications.record_qualification(
            "ghost", source_system="fe_college", title="x", db_path=db)
    with pytest.raises(ValueError):
        qualifications.record_qualification(
            "ghost", source_system="fe_college", title=" ", db_path=db)


# ── Projection from systems ─────────────────────────────────────────

def test_system_projection_keeps_passes_and_is_idempotent(db, fe, mary):
    derived = qualifications.collect_for_journey(mary, db_paths=fe, db_path=db)
    assert [q["title"] for q in derived] == ["Level 3 Engineering"]
    # Reading derived data wrote nothing.
    assert qualifications.list_for_journey(mary, db_path=db) == []

    assert qualifications.sync_journey(mary, db_paths=fe, db_path=db) == 1
    assert qualifications.sync_journey(mary, db_paths=fe, db_path=db) == 0
    [row] = qualifications.list_for_journey(mary, db_path=db)
    assert row["source_ref"] == "fe_college:enrolments:1"
    assert row["origin"] == "system"
    assert row["awarding_body"] == "Pearson"
    # Historic data catching up is not news.
    assert _events(db, "qualification.awarded") == []


def test_sync_all_maps_local_ids_and_counts_unmatched(db, fe, mary):
    summary = qualifications.sync_all(db_paths=fe, db_path=db)
    assert summary["fe_college"] == 1
    again = qualifications.sync_all(db_paths=fe, db_path=db)
    assert again["created"] == 0


# ── Projection from handovers ───────────────────────────────────────

def test_handover_results_are_projected_silently(db, mary):
    t = transitions.start_transition(journey_id=mary, source_system="fe_college",
                                     destination_system="university", db_path=db)
    transitions.approve_handover(
        t["transition_id"],
        {"gcse_results": {"maths": "8", "english": "U"},
         "predicted_grades": {"physics": "A*"},
         "reference": "confidential reference text"},
        db_path=db)
    created = qualifications.sync_journey(mary, db_paths={}, db_path=db)
    titles = {q["title"]: q for q in qualifications.list_for_journey(mary, db_path=db)}
    assert created == 1
    assert set(titles) == {"GCSE maths"}
    assert titles["GCSE maths"]["origin"] == "handover"
    # Handover data never goes on the bus, and predictions are not awards.
    assert _events(db, "qualification.awarded") == []
    conn = connect(db)
    try:
        blobs = " ".join(r[0] for r in conn.execute(
            "SELECT payload_json FROM cross_system_event_outbox"))
    finally:
        conn.close()
    assert "confidential reference text" not in blobs


def test_the_same_award_from_two_sources_is_one_qualification(db, mary):
    qualifications.record_qualification(
        mary, source_system="secondary", title="GCSE maths", grade="8",
        source_ref="secondary:exam_results:1", publish=False, db_path=db)
    t = transitions.start_transition(journey_id=mary, destination_system="sixth_form",
                                     db_path=db)
    transitions.approve_handover(t["transition_id"],
                                 {"gcse_results": {"maths": "8"}}, db_path=db)
    quals = qualifications.collect_for_journey(mary, db_paths={}, db_path=db)
    assert [(q["title"], q["origin"]) for q in quals] == [("GCSE maths", "recorded")]


def test_a_qualification_recorded_on_a_merged_id_lands_on_the_survivor(
        db, mary, tmp_path):
    dup = identity_service.get_or_create_journey(
        first_name="Mary", last_name="Somerville", date_of_birth=DOB,
        system="fe_college", student_id="FE2", db_path=db)
    assert dup != mary          # two open FE records: kept apart
    identity_service.merge_journeys(mary, dup, actor="admin", db_path=db,
                                    audit_db_path=str(tmp_path / "audit.db"))
    row = qualifications.record_qualification(
        dup, source_system="fe_college", title="First aid", db_path=db)
    assert row["journey_id"] == mary


# ── Transcript by journey_id ────────────────────────────────────────

def test_transcript_reads_by_journey_and_attaches_qualifications(db, fe, mary):
    svc = TranscriptService(db_paths=fe, auth_db=db)
    t = svc.generate_transcript(journey_id=mary)
    assert t["matched_by"] == "journey_id"
    assert t["student_name"] == "Mary Somerville"
    assert [(s["system"], s["student_id"]) for s in t["systems"]] == [
        ("fe_college", "FE1")]
    assert [q["title"] for q in t["qualifications"]] == ["Level 3 Engineering"]
    assert "QUALIFICATIONS" in svc.format_transcript(t)
    # A name that matches exactly one journey resolves to it too.
    assert svc.generate_transcript("mary  somerville")["journey_id"] == mary


def test_transcript_name_fallback_only_reads_unlinked_records(db, fe):
    svc = TranscriptService(db_paths=fe, auth_db=db)
    t = svc.generate_transcript("Unlinked Person")
    assert t["matched_by"] == "name"
    assert [s["student_id"] for s in t["systems"]] == ["FE9"]


# ── Create-path registration helper ─────────────────────────────────

def test_register_local_learner_links_stamps_annotates_and_announces_once(
        db, fe):
    jid = person.register_local_learner(
        "fe_college", student_id="FE1", first_name="Mary",
        last_name="Somerville", date_of_birth=DOB,
        programme="Level 3 Engineering", auth_db=db,
        system_db_path=fe["fe_college"])
    assert jid
    conn = sqlite3.connect(fe["fe_college"])
    assert conn.execute("SELECT journey_id FROM students WHERE student_id='FE1'"
                        ).fetchone()[0] == jid
    conn.close()
    [spell] = enrolments.list_enrolments(jid, db_path=db)
    assert (spell["programme"], spell["source_system"]) == (
        "Level 3 Engineering", "fe_college")
    again = person.register_local_learner(
        "fe_college", student_id="FE1", first_name="Mary",
        last_name="Somerville", date_of_birth=DOB, auth_db=db,
        system_db_path=fe["fe_college"])
    assert again == jid
    assert len(_events(db, "journey.registered")) == 1


def test_register_local_learner_without_dob_is_skipped_not_raised(db):
    assert person.register_local_learner(
        "apprenticeships", student_id="7", first_name="Ada",
        last_name="Lovelace", date_of_birth=None, auth_db=db) is None
