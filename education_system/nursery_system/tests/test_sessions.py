"""Tests for the Nursery Sessions & Bookings domain.

Covers the booking calendar's core job: resolving a date from the contracted
weekly patterns, the ad-hoc extras and cancellations layered on top, and the
closures that wipe a day out entirely.
"""

from __future__ import annotations

import datetime as _dt

import pytest


@pytest.fixture
def sessions(fresh_data_dir):
    """The sessions domain wired to a throwaway database."""
    import importlib

    from education_system.nursery_system.core import database as db_mod
    importlib.reload(db_mod)
    from education_system.nursery_system.modules.domain.sessions import (
        sessions as mod,
    )
    importlib.reload(mod)
    mod.init_db()
    return mod


def _next_weekday(weekday: int) -> str:
    """The next date (today or later) falling on ``weekday``."""
    day = _dt.date.today()
    while day.weekday() != weekday:
        day += _dt.timedelta(days=1)
    return day.isoformat()


# ── Contracted patterns ──────────────────────────────────────────────────────

def test_create_pattern_fills_default_times(sessions):
    p = sessions.create_pattern({
        "pupil_id": "NCH001", "weekday": 0, "session_type": "am",
        "start_date": "2025-01-06"})
    assert (p.start_time, p.end_time) == sessions.DEFAULT_TIMES["am"]
    assert p.weekday_name == "Monday"
    assert p.hours == 5.0


def test_create_pattern_accepts_day_names(sessions):
    p = sessions.create_pattern({
        "pupil_id": "NCH001", "weekday": "Wednesday", "session_type": "pm",
        "start_date": "2025-01-06"})
    assert p.weekday == 2


def test_create_pattern_rejects_unknown_child(sessions):
    with pytest.raises(sessions.ValidationError):
        sessions.create_pattern({"pupil_id": "NOPE", "weekday": 0,
                                 "start_date": "2025-01-06"})


def test_create_pattern_rejects_bad_weekday(sessions):
    with pytest.raises(sessions.ValidationError):
        sessions.create_pattern({"pupil_id": "NCH001", "weekday": "9",
                                 "start_date": "2025-01-06"})


def test_create_pattern_rejects_end_before_start(sessions):
    with pytest.raises(sessions.ValidationError):
        sessions.create_pattern({
            "pupil_id": "NCH001", "weekday": 0, "start_date": "2025-06-01",
            "end_date": "2025-05-01"})


def test_duplicate_pattern_is_rejected(sessions):
    fields = {"pupil_id": "NCH005", "weekday": 4, "session_type": "am",
              "start_date": "2025-01-06"}
    sessions.create_pattern(fields)
    with pytest.raises(sessions.ValidationError):
        sessions.create_pattern(fields)


def test_end_pattern_marks_it_ended(sessions):
    p = sessions.create_pattern({"pupil_id": "NCH001", "weekday": 5,
                                 "start_date": "2025-01-06"})
    ended = sessions.end_pattern(p.pattern_id, "2025-07-18")
    assert ended.status == "ended"
    assert ended.end_date == "2025-07-18"


# ── Resolving a day ──────────────────────────────────────────────────────────

def test_day_sessions_includes_contracted_children(sessions):
    monday = _next_weekday(0)
    sessions.create_pattern({"pupil_id": "NCH005", "weekday": 0,
                             "session_type": "am", "room": "Preschool Room",
                             "start_date": "2020-01-01"})
    booked = {s.pupil_id for s in sessions.day_sessions(monday)}
    assert "NCH005" in booked


def test_day_sessions_drops_cancellations(sessions):
    tuesday = _next_weekday(1)
    sessions.create_pattern({"pupil_id": "NCH005", "weekday": 1,
                             "session_type": "am", "start_date": "2020-01-01"})
    assert any(s.pupil_id == "NCH005"
               for s in sessions.day_sessions(tuesday))

    sessions.cancel_session("NCH005", tuesday, "am", reason="Unwell")
    assert not any(s.pupil_id == "NCH005" and s.session_type == "am"
                   for s in sessions.day_sessions(tuesday))


def test_day_sessions_adds_extras(sessions):
    saturday = _next_weekday(5)
    assert not any(s.pupil_id == "NCH002"
                   for s in sessions.day_sessions(saturday))

    sessions.book_extra_session("NCH002", saturday, "pm",
                                room="Preschool Room")
    extra = [s for s in sessions.day_sessions(saturday)
             if s.pupil_id == "NCH002"]
    assert len(extra) == 1
    assert extra[0].source == "extra"
    assert extra[0].start_time == sessions.DEFAULT_TIMES["pm"][0]


def test_declined_extra_is_not_booked_in(sessions):
    saturday = _next_weekday(5)
    sessions.create_booking({"pupil_id": "NCH003", "session_date": saturday,
                             "session_type": "am", "kind": "extra",
                             "status": "declined"})
    assert not any(s.pupil_id == "NCH003"
                   for s in sessions.day_sessions(saturday))


def test_pattern_outside_its_date_window_is_ignored(sessions):
    # Monday-am is not part of the demo seed, so it can only appear from the
    # pattern created here — which expired years ago.
    monday = _next_weekday(0)
    sessions.create_pattern({
        "pupil_id": "NCH005", "weekday": 0, "session_type": "am",
        "start_date": "2020-01-01", "end_date": "2020-12-31",
        "status": "active"})
    assert not any(s.pupil_id == "NCH005" and s.session_type == "am"
                   for s in sessions.day_sessions(monday))


# ── Closures ─────────────────────────────────────────────────────────────────

def test_whole_setting_closure_empties_the_day(sessions):
    monday = _next_weekday(0)
    sessions.create_pattern({"pupil_id": "NCH005", "weekday": 0,
                             "start_date": "2020-01-01"})
    assert sessions.day_sessions(monday)

    sessions.create_closure({"name": "Emergency closure", "start_date": monday,
                             "closure_type": "emergency"})
    assert sessions.is_closed(monday)
    assert sessions.day_sessions(monday) == []
    assert sessions.summary(monday)["closed"] is True


def test_room_closure_only_empties_that_room(sessions):
    monday = _next_weekday(0)
    sessions.create_pattern({"pupil_id": "NCH005", "weekday": 0,
                             "room": "Preschool Room",
                             "start_date": "2020-01-01"})
    sessions.create_pattern({"pupil_id": "NCH003", "weekday": 0,
                             "room": "Baby Room", "start_date": "2020-01-01"})
    sessions.create_closure({"name": "Boiler repair", "start_date": monday,
                             "room": "Preschool Room",
                             "closure_type": "emergency"})

    assert sessions.is_closed(monday) is False        # setting is still open
    assert sessions.is_closed(monday, "Preschool Room") is True
    rooms = {s.room for s in sessions.day_sessions(monday)}
    assert "Preschool Room" not in rooms
    assert "Baby Room" in rooms


def test_closure_rejects_end_before_start(sessions):
    with pytest.raises(sessions.ValidationError):
        sessions.create_closure({"name": "Bad", "start_date": "2025-08-10",
                                 "end_date": "2025-08-01"})


# ── Capacity ─────────────────────────────────────────────────────────────────

def test_room_day_capacity_flags_over_booking(sessions):
    saturday = _next_weekday(5)  # nobody is contracted at the weekend
    def _baby():
        return next(r for r in sessions.room_day_capacity(saturday)
                    if r.room == "Baby Room")

    assert _baby().booked == 0
    for pupil in ("NCH001", "NCH002", "NCH003"):
        sessions.book_extra_session(pupil, saturday, "all-day",
                                    room="Baby Room")
    assert _baby().booked == 3
    assert _baby().over_capacity is False  # demo capacity is 12

    with sessions.connect() as conn:
        conn.execute("UPDATE rooms SET capacity = 1 WHERE name = 'Baby Room'")
        conn.commit()
    assert _baby().over_capacity is True
    assert _baby().free == -2
    assert sessions.summary(saturday)["over_capacity_rooms"] >= 1


def test_contracted_hours_totals_live_patterns(sessions):
    before = sessions.contracted_hours("NCH005")
    sessions.create_pattern({"pupil_id": "NCH005", "weekday": 5,
                             "session_type": "all-day",
                             "start_date": "2020-01-01"})
    sessions.create_pattern({"pupil_id": "NCH005", "weekday": 6,
                             "session_type": "am", "start_date": "2020-01-01"})
    assert sessions.contracted_hours("NCH005") == before + 15.0


def test_week_sessions_covers_seven_days(sessions):
    monday = _next_weekday(0)
    week = sessions.week_sessions(monday)
    assert len(week) == 7
    assert monday in week
