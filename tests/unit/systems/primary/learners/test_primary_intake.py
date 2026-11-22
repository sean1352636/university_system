"""Primary intake (domain.learners.pupils.primary_intake): nursery progression events."""

from __future__ import annotations

import pytest

from education_system.platform.cross_system import identity_service, person, progression
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.learners.pupils import primary_intake as PI


@pytest.fixture(autouse=True)
def _stamps_in_sandbox(monkeypatch):
    monkeypatch.setitem(person.SYSTEM_DB_PATHS, "primary", P.DB_PATH)


def _nursery_child(first="Ada", last="Lovelace", dob="2021-05-01"):
    return identity_service.get_or_create_journey(
        first_name=first, last_name=last, date_of_birth=dob,
        system="nursery", student_id="N1")


def _envelope(journey_id, target="primary", **payload):
    return {"event_id": "e1", "journey_id": journey_id, "target_system": target,
            "payload": payload}


def test_intake_is_wired_for_nursery_to_primary():
    assert PI.CONSUMER_SYSTEM == "primary"
    assert PI._intake.consumer_system == "primary"
    assert PI._intake.from_system == "nursery"


# ── _admit ───────────────────────────────────────────────────────────

def test_admit_uses_canonical_demographics_and_payload_extras():
    jid = _nursery_child()
    pid = PI._admit(jid, {"class_name": "RA", "parent_name": "Anne",
                          "parent_phone": "01234 567890", "medical_notes": "Peanuts"})
    p = P.get_pupil(pid)
    assert (p.full_name, p.date_of_birth) == ("Ada Lovelace", "2021-05-01")
    assert p.year_group == "R" and p.class_name == "RA"
    assert p.parent_name == "Anne" and p.medical_notes == "Peanuts"
    assert p.roll_status == "on_roll"


def test_admit_payload_names_win_over_the_journey():
    jid = _nursery_child()
    p = P.get_pupil(PI._admit(jid, {"first_name": "Addie", "year_group": "1"}))
    assert p.first_name == "Addie" and p.last_name == "Lovelace" and p.year_group == "1"


@pytest.mark.parametrize("year", ["", "7", "Nursery", None])
def test_admit_defaults_an_unusable_year_to_reception(year):
    jid = _nursery_child()
    assert P.get_pupil(PI._admit(jid, {"year_group": year})).year_group == "R"


def test_admit_unknown_journey_needs_the_name_in_the_payload():
    with pytest.raises(P.ValidationError, match="First name is required"):
        PI._admit("no-such-journey", {})
    pid = PI._admit("no-such-journey", {"first_name": "Cy", "last_name": "Day"})
    assert P.get_pupil(pid).full_name == "Cy Day"


# ── the bus handler ──────────────────────────────────────────────────

def test_handle_admits_links_the_journey_and_skips_a_redelivery():
    jid = _nursery_child()
    PI._intake.handle(_envelope(jid, class_name="RB"))
    pupils = P.list_pupils()
    assert [p.class_name for p in pupils] == ["RB"]
    journey = identity_service.get(jid)
    assert journey["primary_student_id"] == pupils[0].pupil_id
    assert journey["current_system"] == "primary"
    PI._intake.handle(_envelope(jid, class_name="RB"))
    assert len(P.list_pupils()) == 1


def test_handle_ignores_events_for_another_system_or_without_a_journey():
    jid = _nursery_child()
    PI._intake.handle(_envelope(jid, target="secondary"))
    PI._intake.handle({"event_id": "e2", "target_system": "primary", "payload": {}})
    assert P.list_pupils() == []


def test_drain_processes_a_published_progression_once():
    jid = _nursery_child()
    progression.publish_progression(journey_id=jid, source_system="nursery",
                                    source_module="test", class_name="RC")
    assert PI.drain_intake() >= 1
    assert [p.class_name for p in P.list_pupils()] == ["RC"]
    PI.drain_intake()
    assert len(P.list_pupils()) == 1


def test_drain_with_nothing_pending_admits_nobody():
    PI.register_intake_consumer()
    PI.drain_intake()
    assert P.list_pupils() == []
