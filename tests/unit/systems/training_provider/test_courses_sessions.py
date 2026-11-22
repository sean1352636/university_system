"""Courses, trainers, venues and session scheduling rules."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.modules import courses, sessions


def _day(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


def test_accredited_course_needs_awarding_body():
    with pytest.raises(r.ValidationError, match="awarding body"):
        r.save(courses.COURSES, {"code": "X", "title": "X", "category": "Other",
                                 "kind": courses.KINDS[0], "price": 1})


def test_course_code_upper_cased(world):
    assert r.get(courses.COURSES, world.faw)["code"] == "FAW"


def test_dbs_renewal_three_years(world):
    row = r.get(courses.TRAINERS, world.trainer)
    assert courses.dbs_due(row) > date.today()


def test_session_end_and_capacity_default(world):
    s = r.get(sessions.SESSIONS, world.session)
    assert len(sessions.session_days(s)) == 3
    assert s["capacity"] == 3          # course max; online venue has no room limit


def test_trainer_needs_an_approval(world):
    other = r.save(courses.TRAINERS, {"name": "New"})
    with pytest.raises(r.ValidationError, match="approval"):
        r.save(sessions.SESSIONS, {"course_id": world.faw, "start_date": _day(30),
                                   "venue_id": world.online, "trainer_id": other})


def test_trainer_cannot_be_double_booked(world):
    with pytest.raises(r.ValidationError, match="already teaching"):
        r.save(sessions.SESSIONS, {"course_id": world.cpd, "start_date": _day(-9),
                                   "venue_id": world.room, "trainer_id": world.trainer})


def test_room_capacity_and_double_booking(world):
    with pytest.raises(r.ValidationError, match="holds 2"):
        r.save(sessions.SESSIONS, {"course_id": world.faw, "start_date": _day(30),
                                   "venue_id": world.room, "capacity": 3})
    r.save(sessions.SESSIONS, {"course_id": world.cpd, "start_date": _day(30),
                               "venue_id": world.room})
    with pytest.raises(r.ValidationError, match="already booked"):
        r.save(sessions.SESSIONS, {"course_id": world.cpd, "start_date": _day(30),
                                   "venue_id": world.room})


def test_online_venue_can_run_two_sessions_at_once(world):
    r.save(sessions.SESSIONS, {"course_id": world.cpd, "start_date": _day(-10),
                               "venue_id": world.online})


def test_closed_session_needs_a_client(world):
    with pytest.raises(r.ValidationError, match="closed session"):
        r.save(sessions.SESSIONS, {"course_id": world.cpd, "start_date": _day(30),
                                   "venue_id": world.online, "kind": sessions.SESSION_KINDS[1]})


def test_completed_only_after_last_day(world):
    sid = r.save(sessions.SESSIONS, {"course_id": world.cpd, "start_date": _day(30),
                                     "venue_id": world.online})
    with pytest.raises(r.ValidationError, match="Completed"):
        r.save(sessions.SESSIONS, {"status": "Completed"}, record_id=sid)


def test_retired_course_cannot_be_scheduled(world):
    r.save(courses.COURSES, {"status": "Retired"}, record_id=world.cpd)
    with pytest.raises(r.ValidationError, match="retired"):
        r.save(sessions.SESSIONS, {"course_id": world.cpd, "start_date": _day(30),
                                   "venue_id": world.online})
