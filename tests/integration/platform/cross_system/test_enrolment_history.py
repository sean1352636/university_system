"""learner_enrolment programme/outcome/source_system, year-group history,
and the enrolment.ended / learner.updated events. Temp auth DB only.
"""

from __future__ import annotations

import json

import pytest

from education_system.platform.cross_system import (
    enrolment_schema,
    enrolments,
    identity_service,
    person,
)
from education_system.platform.identity.auth.db import connect


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "auth.db")
    enrolment_schema.reset_schema_cache_for_test()
    identity_service._initialised.clear()
    enrolment_schema.ensure_enrolment_schema(path)
    yield path
    enrolment_schema.reset_schema_cache_for_test()
    identity_service._initialised.clear()


@pytest.fixture
def journey(db):
    return identity_service.get_or_create_journey(
        first_name="Ada", last_name="Lovelace", date_of_birth="2010-12-10",
        system="secondary", student_id="S1", db_path=db)


def _events(db, name):
    conn = connect(db)
    try:
        return [json.loads(r[0]) for r in conn.execute(
            "SELECT payload_json FROM cross_system_event_outbox "
            "WHERE event_name = ? ORDER BY rowid", (name,)).fetchall()]
    finally:
        conn.close()


def test_new_columns_and_source_system_default(db, journey):
    e = enrolments.create_enrolment(
        journey_id=journey, system="fe_college", local_student_id="FE1",
        status="active", programme="Level 3 Engineering", db_path=db)
    assert e["programme"] == "Level 3 Engineering"
    assert e["source_system"] == "fe_college"
    mirrored = enrolments.current_enrolment(journey, "secondary", db_path=db)
    assert mirrored["source_system"] == "secondary"


def test_closing_records_the_outcome_and_publishes_enrolment_ended(db, journey):
    e = enrolments.current_enrolment(journey, "secondary", db_path=db)
    closed = enrolments.close_enrolment(
        e["enrolment_id"], reason="finished Year 11", outcome="9 GCSEs",
        db_path=db)
    assert closed["outcome"] == "9 GCSEs"
    [ended] = _events(db, "enrolment.ended")
    assert ended["enrolment_id"] == e["enrolment_id"]
    assert ended["status"] == "completed"
    # Re-closing is not a second event.
    enrolments.close_enrolment(e["enrolment_id"], reason="again", db_path=db)
    assert len(_events(db, "enrolment.ended")) == 1


def test_end_local_enrolment_finds_the_open_spell(db, journey):
    closed = enrolments.end_local_enrolment(
        "secondary", "S1", reason="withdrawn", status="withdrawn", db_path=db)
    assert closed["status"] == "withdrawn"
    assert enrolments.end_local_enrolment(
        "secondary", "S1", reason="again", status="withdrawn", db_path=db) is None


def test_a_repeated_year_is_kept_in_the_history(db, journey):
    e = enrolments.create_enrolment(
        journey_id=journey, system="primary", local_student_id="P1",
        status="active", year_group="5", db_path=db)
    enrolments.set_year_group(e["enrolment_id"], "6", db_path=db)
    enrolments.set_year_group(e["enrolment_id"], "6", academic_year="2021/22",
                              note="held back", db_path=db)
    history = enrolments.year_group_history(enrolment_id=e["enrolment_id"],
                                            db_path=db)
    assert [(h["from_year_group"], h["to_year_group"], h["change_type"])
            for h in history] == [(None, "5", "started"),
                                  ("5", "6", "promoted"),
                                  ("6", "6", "repeated")]
    assert history[-1]["academic_year"] == "2021/22"
    # Still one enrolment: a repeat is not a new spell.
    assert len(enrolments.list_enrolments(journey, system="primary",
                                          db_path=db)) == 1
    updates = _events(db, "learner.updated")
    assert [u["year_change"] for u in updates] == ["promoted", "repeated"]


def test_programme_change_publishes_learner_updated(db, journey):
    e = enrolments.current_enrolment(journey, "secondary", db_path=db)
    enrolments.update_enrolment(e["enrolment_id"], programme="GCSE pathway",
                                db_path=db)
    [update] = _events(db, "learner.updated")
    assert update["changes"] == {"programme": "GCSE pathway"}


def test_link_fills_blanks_but_never_overwrites(db, journey):
    enrolments.link_local_enrolment(
        journey_id=journey, system="secondary", local_student_id="S1",
        programme="A", db_path=db)
    again = enrolments.link_local_enrolment(
        journey_id=journey, system="secondary", local_student_id="S1",
        programme="B", db_path=db)
    assert again["programme"] == "A"


def test_demographic_correction_announces_field_names_only(db, journey):
    person.update_demographics(journey, legal_last_name="King", db_path=db)
    [update] = _events(db, "learner.updated")
    assert update["changed_fields"] == ["legal_last_name"]
    assert "King" not in json.dumps(update)
