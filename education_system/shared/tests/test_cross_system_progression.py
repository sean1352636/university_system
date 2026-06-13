"""Tests for the cross-system progression engine (the K-12 pipeline spine).

Covers:
  * register_local_student anchors a canonical journey on create.
  * Two phases registering the same person (name+DOB) land on ONE journey
    with both slots filled — i.e. the phases auto-link.
  * announce_progression links the target slot, records a transition and
    publishes a durable progression event.
  * ProgressionIntake admits via its callback, is idempotent on a filled
    slot and on bus re-delivery, and ignores events not addressed to it.
"""

import pytest

from education_system.shared.auth.schema import initialise_auth_db
from education_system.shared.cross_system import identity_service
from education_system.shared.cross_system import progression
from education_system.shared.integrations import cross_system_bus


@pytest.fixture()
def auth_db(tmp_path):
    """An isolated, initialised auth.db with the journey + bus tables."""
    path = str(tmp_path / "auth.db")
    initialise_auth_db(path)
    # identity_service caches "already initialised" per path; harmless here.
    identity_service._initialised.discard(path)
    return path


@pytest.fixture(autouse=True)
def _clean_bus():
    cross_system_bus.clear_subscribers_for_test()
    yield
    cross_system_bus.clear_subscribers_for_test()


# ── The spine ────────────────────────────────────────────────────────────

def test_register_local_student_creates_journey(auth_db):
    jid = progression.register_local_student(
        "nursery", student_id="N001", first_name="Ada",
        last_name="Lovelace", date_of_birth="2021-12-10", db_path=auth_db)
    assert jid
    journey = identity_service.get(jid, db_path=auth_db)
    assert journey["nursery_student_id"] == "N001"
    assert journey["current_system"] == "nursery"


def test_register_skips_without_dob(auth_db):
    assert progression.register_local_student(
        "nursery", student_id="N002", first_name="No",
        last_name="Dob", date_of_birth=None, db_path=auth_db) is None


def test_same_person_two_phases_one_journey(auth_db):
    """The heart of the spine: a child created in nursery and then in
    primary (same name+DOB) shares a single journey with both slots."""
    j1 = progression.register_local_student(
        "nursery", student_id="N010", first_name="Grace",
        last_name="Hopper", date_of_birth="2019-12-09", db_path=auth_db)
    j2 = progression.register_local_student(
        "primary", student_id="P010", first_name="Grace",
        last_name="Hopper", date_of_birth="2019-12-09", db_path=auth_db)
    assert j1 == j2
    journey = identity_service.get(j1, db_path=auth_db)
    assert journey["nursery_student_id"] == "N010"
    assert journey["primary_student_id"] == "P010"


# ── Producer: announce_progression ───────────────────────────────────────

def test_announce_links_target_and_publishes(auth_db):
    jid = progression.announce_progression(
        source_system="nursery",
        source_module="test",
        first_name="Alan", last_name="Turing",
        date_of_birth="2018-06-23",
        source_student_id="N100",
        target_student_id="P100",
        db_path=auth_db)
    assert jid
    journey = identity_service.get(jid, db_path=auth_db)
    assert journey["nursery_student_id"] == "N100"
    assert journey["primary_student_id"] == "P100"
    assert journey["current_system"] == "primary"

    # A durable event was queued for the next phase ("primary").
    from education_system.shared.auth.db import connect
    conn = connect(auth_db)
    try:
        row = conn.execute(
            "SELECT event_name, target_system FROM cross_system_event_outbox "
            "WHERE journey_id = ?", (jid,)).fetchone()
    finally:
        conn.close()
    assert row["event_name"] == cross_system_bus.EVENT_STUDENT_PROGRESSION_COMPLETED
    assert row["target_system"] == "primary"

    # And the transition was audited.
    conn = connect(auth_db)
    try:
        t = conn.execute(
            "SELECT from_system, to_system FROM student_journey_transitions "
            "WHERE journey_id = ?", (jid,)).fetchone()
    finally:
        conn.close()
    assert (t["from_system"], t["to_system"]) == ("nursery", "primary")


# ── Consumer: ProgressionIntake ──────────────────────────────────────────

def _make_intake(consumer_system, from_system, auth_db, admitted):
    def admit(journey_id, payload):
        new_id = f"{consumer_system[:1].upper()}999"
        admitted.append((journey_id, new_id, payload))
        return new_id
    return progression.ProgressionIntake(
        consumer_system, admit,
        handler_name=f"test.{consumer_system}.intake",
        from_system=from_system, db_path=auth_db)


def test_intake_admits_when_slot_empty(auth_db):
    # A nursery child with only the nursery slot, then a published event.
    jid = progression.register_local_student(
        "nursery", student_id="N200", first_name="Edith",
        last_name="Clarke", date_of_birth="2018-02-10", db_path=auth_db)
    progression.publish_progression(
        journey_id=jid, source_system="nursery", source_module="test",
        target_system="primary", first_name="Edith", last_name="Clarke",
        date_of_birth="2018-02-10", db_path=auth_db)

    admitted = []
    intake = _make_intake("primary", "nursery", auth_db, admitted)
    n = intake.drain()
    assert n == 1
    assert len(admitted) == 1
    journey = identity_service.get(jid, db_path=auth_db)
    assert journey["primary_student_id"] == "P999"
    assert journey["current_system"] == "primary"


def test_intake_idempotent_on_redelivery(auth_db):
    jid = progression.register_local_student(
        "nursery", student_id="N210", first_name="Mary",
        last_name="Somerville", date_of_birth="2018-12-26", db_path=auth_db)
    progression.publish_progression(
        journey_id=jid, source_system="nursery", source_module="test",
        target_system="primary", first_name="Mary", last_name="Somerville",
        date_of_birth="2018-12-26", db_path=auth_db)

    admitted = []
    intake = _make_intake("primary", "nursery", auth_db, admitted)
    assert intake.drain() == 1
    # Second drain: the bus ack table drops re-delivery → no new admit.
    assert intake.drain() == 0
    assert len(admitted) == 1


def test_intake_skips_when_target_slot_filled(auth_db):
    """The in-process transfer already created+linked the pupil; the bus
    event must not create a duplicate."""
    jid = progression.register_local_student(
        "nursery", student_id="N220", first_name="Dorothy",
        last_name="Hodgkin", date_of_birth="2018-05-12", db_path=auth_db)
    # Simulate the synchronous transfer having linked the primary slot.
    identity_service.link_system(jid, "primary", student_id="P220",
                                 db_path=auth_db)
    progression.publish_progression(
        journey_id=jid, source_system="nursery", source_module="test",
        target_system="primary", first_name="Dorothy", last_name="Hodgkin",
        date_of_birth="2018-05-12", db_path=auth_db)

    admitted = []
    intake = _make_intake("primary", "nursery", auth_db, admitted)
    # The event is dispatched (counts as handled) but admit is NOT called.
    intake.drain()
    assert admitted == []
    journey = identity_service.get(jid, db_path=auth_db)
    assert journey["primary_student_id"] == "P220"


def test_intake_ignores_events_for_other_systems(auth_db):
    """A primary intake must ignore a university-targeted event even though
    both subscribe to the same event name in one process."""
    jid = progression.register_local_student(
        "college", student_id="C300", first_name="Rosalind",
        last_name="Franklin", date_of_birth="2006-07-25", db_path=auth_db)
    progression.publish_progression(
        journey_id=jid, source_system="college", source_module="test",
        target_system="university", first_name="Rosalind",
        last_name="Franklin", date_of_birth="2006-07-25", db_path=auth_db)

    admitted = []
    intake = _make_intake("primary", "nursery", auth_db, admitted)
    intake.drain()
    assert admitted == []
    journey = identity_service.get(jid, db_path=auth_db)
    assert journey["primary_student_id"] is None


# ── Phase-order helpers ──────────────────────────────────────────────────

def test_phase_order_helpers():
    assert progression.next_phase("nursery") == "primary"
    assert progression.next_phase("college") == "university"
    assert progression.next_phase("university") is None
    assert progression.previous_phase("nursery") is None
    assert progression.previous_phase("university") == "college"
