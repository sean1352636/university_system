"""Destinations and outcomes: the learner_destination table, non-phase
transitions that complete, and the analytics summary.

Every case runs against an isolated temp auth DB.
"""

from __future__ import annotations

import json

import pytest

from education_system.platform.cross_system import (
    destinations,
    enrolment_schema,
    enrolments,
    identity_service,
    progression,
    transitions,
)
from education_system.platform.identity.auth.db import connect


@pytest.fixture
def db(tmp_path):
    """An isolated auth DB with the enrolment schema in place (the same
    fixture as test_enrolment_model.py)."""
    path = str(tmp_path / "auth.db")
    enrolment_schema.reset_schema_cache_for_test()
    destinations.reset_schema_cache_for_test()
    identity_service._initialised.clear()
    enrolment_schema.ensure_enrolment_schema(path)
    yield path
    enrolment_schema.reset_schema_cache_for_test()
    destinations.reset_schema_cache_for_test()
    identity_service._initialised.clear()


@pytest.fixture
def journey(db):
    return identity_service.get_or_create_journey(
        first_name="Grace", last_name="Hopper", date_of_birth="2007-12-09",
        system="sixth_form", student_id="SF100", db_path=db)


def _events(db):
    conn = connect(db)
    try:
        return [json.loads(r["payload_json"]) for r in conn.execute(
            "SELECT payload_json FROM cross_system_event_outbox "
            "WHERE event_name = 'destination.recorded'").fetchall()]
    finally:
        conn.close()


# ── Recording ───────────────────────────────────────────────────────

def test_record_and_read_back(db, journey):
    row = destinations.record_destination(
        journey, destination="employment", checkpoint="leaving",
        source_system="sixth_form", detail="Acme Engineering Ltd",
        recorded_by="careers", db_path=db)
    assert row["destination"] == "employment"
    assert row["checkpoint"] == "leaving"
    assert row["detail"] == "Acme Engineering Ltd"
    assert destinations.destinations_for(journey, db_path=db) == [row]
    event = _events(db)[0]
    assert event["destination"] == "employment"
    # The employer name stays in the table.
    assert "Acme" not in json.dumps(event)


def test_local_labels_are_normalised(db, journey):
    row = destinations.record_destination(
        journey, destination="Higher Education", checkpoint="PLUS_6",
        source_system="sixth_form", db_path=db)
    assert (row["destination"], row["checkpoint"]) == (
        "higher_education", "6_months")
    assert destinations.record_destination(
        journey, destination="NEET", checkpoint="+12 months",
        source_system="sixth_form", db_path=db)["destination"] == "neet"


def test_unknown_vocabulary_is_refused(db, journey):
    with pytest.raises(destinations.DestinationError):
        destinations.record_destination(
            journey, destination="astronaut", checkpoint="leaving",
            source_system="sixth_form", db_path=db)
    with pytest.raises(destinations.DestinationError):
        destinations.record_destination(
            journey, destination="employment", checkpoint="+3 months",
            source_system="sixth_form", db_path=db)


def test_recording_a_checkpoint_again_corrects_it(db, journey):
    first = destinations.record_destination(
        journey, destination="unknown", checkpoint="6_months",
        source_system="sixth_form", db_path=db)
    second = destinations.record_destination(
        journey, destination="apprenticeship", checkpoint="6_months",
        source_system="sixth_form", detail="BAE Systems", db_path=db)
    assert second["destination_id"] == first["destination_id"]
    rows = destinations.destinations_for(journey, db_path=db)
    assert [(r["checkpoint"], r["destination"]) for r in rows] == [
        ("6_months", "apprenticeship")]


def test_destinations_read_in_checkpoint_order(db, journey):
    for cp in ("12_months", "leaving", "6_months"):
        destinations.record_destination(
            journey, destination="employment", checkpoint=cp,
            source_system="sixth_form", db_path=db)
    assert [r["checkpoint"] for r in destinations.destinations_for(
        journey, db_path=db)] == ["leaving", "6_months", "12_months"]


# ── Outcome summary ─────────────────────────────────────────────────

def test_outcome_summary_counts_and_zero_fills(db, journey):
    other = identity_service.get_or_create_journey(
        first_name="Alan", last_name="Turing", date_of_birth="2007-06-23",
        system="sixth_form", student_id="SF101", db_path=db)
    destinations.record_destination(
        journey, destination="employment", checkpoint="leaving",
        source_system="sixth_form", recorded_on="2026-07-01", db_path=db)
    destinations.record_destination(
        other, destination="higher_education", checkpoint="leaving",
        source_system="sixth_form", recorded_on="2026-07-02", db_path=db)
    destinations.record_destination(
        journey, destination="employment", checkpoint="6_months",
        source_system="sixth_form", recorded_on="2027-01-05", db_path=db)

    summary = destinations.outcome_summary(db_path=db)
    assert summary["total"] == 3
    assert summary["learners"] == 2
    assert summary["by_destination"]["employment"] == 2
    assert summary["by_destination"]["neet"] == 0
    assert summary["by_checkpoint"] == {"leaving": 2, "6_months": 1,
                                        "12_months": 0}
    assert summary["by_checkpoint_destination"]["leaving"][
        "higher_education"] == 1

    later = destinations.outcome_summary(since="2027-01-01", db_path=db)
    assert later["total"] == 1 and later["learners"] == 1


# ── Non-phase transitions complete ──────────────────────────────────

def test_new_non_phase_destinations_are_offered():
    for label in ("training", "gap_year", "neet"):
        assert label in progression.NON_PHASE_DESTINATIONS
        assert label in progression.known_destinations("sixth_form")
        assert progression.is_non_phase_destination(label)
    assert not progression.is_non_phase_destination("university")


def test_completing_an_employment_transition_records_leaving(db, journey):
    source = enrolments.current_enrolment(journey, "sixth_form", db_path=db)
    t = transitions.start_transition(
        journey_id=journey, source_system="sixth_form",
        source_enrolment_id=source["enrolment_id"],
        destination_system="employment", reason="KS5 destination",
        db_path=db)
    done = transitions.complete_non_phase(
        t["transition_id"], detail="Acme Ltd", actor_user_id=3,
        effective_date="2026-07-20", db_path=db)
    assert done["status"] == "completed"
    assert done["effective_date"] == "2026-07-20"

    [row] = destinations.destinations_for(journey, db_path=db)
    assert (row["destination"], row["checkpoint"], row["detail"]) == (
        "employment", "leaving", "Acme Ltd")
    assert row["transition_id"] == t["transition_id"]
    assert row["recorded_on"] == "2026-07-20"
    src = enrolments.get_enrolment(source["enrolment_id"], db_path=db)
    assert src["status"] == "completed"
    assert src["end_date"] == "2026-07-20"


def test_plain_complete_also_records_for_non_phase(db, journey):
    t = transitions.start_transition(
        journey_id=journey, source_system="sixth_form",
        destination_system="gap_year", db_path=db)
    transitions.complete(t["transition_id"], close_source=False, db_path=db)
    assert [r["destination"] for r in destinations.destinations_for(
        journey, db_path=db)] == ["gap_year"]


def test_phase_and_unmapped_destinations_record_nothing(db, journey):
    t = transitions.start_transition(
        journey_id=journey, source_system="sixth_form",
        destination_system="home_education", db_path=db)
    transitions.complete(t["transition_id"], close_source=False, db_path=db)
    u = transitions.start_transition(
        journey_id=journey, source_system="sixth_form",
        destination_system="university", db_path=db)
    transitions.admit(u["transition_id"], local_student_id="U1", db_path=db)
    transitions.complete(u["transition_id"], close_source=False, db_path=db)
    assert destinations.destinations_for(journey, db_path=db) == []


def test_complete_non_phase_refuses_a_platform_system(db, journey):
    t = transitions.start_transition(
        journey_id=journey, source_system="sixth_form",
        destination_system="university", db_path=db)
    with pytest.raises(transitions.TransitionError):
        transitions.complete_non_phase(t["transition_id"], db_path=db)
