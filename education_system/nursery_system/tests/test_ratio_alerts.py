"""Tests for the Nursery Live Ratio Alerts domain.

Covers the four things the board is meant to warn about — staff absence, child
movement, age-band changes and late collection — plus the underlying ratio and
capacity maths and the closure short-circuit.
"""

from __future__ import annotations

import datetime as _dt

import pytest


@pytest.fixture
def alerts(fresh_data_dir):
    """The ratio-alerts domain wired to a throwaway database."""
    import importlib

    from education_system.nursery_system.core import database as db_mod
    importlib.reload(db_mod)
    from education_system.nursery_system.modules.domain.sessions import (
        sessions as sessions_mod,
    )
    importlib.reload(sessions_mod)
    from education_system.nursery_system.modules.domain.ratio_alerts import (
        ratio_alerts as mod,
    )
    importlib.reload(mod)
    mod.init_db()
    mod.sessions = sessions_mod  # keep both views of the DB in step
    return mod


@pytest.fixture
def sessions(alerts):
    from education_system.nursery_system.modules.domain.sessions import (
        sessions as mod,
    )
    return mod


def _next_saturday() -> str:
    """A day nobody is contracted for, so a test controls the whole headcount."""
    day = _dt.date.today()
    while day.weekday() != 5:
        day += _dt.timedelta(days=1)
    return day.isoformat()


def _kinds(rows) -> set[str]:
    return {a.category for a in rows}


# ── Room state ───────────────────────────────────────────────────────────────

def test_room_states_cover_every_room(alerts):
    states = alerts.room_states(_next_saturday())
    assert {s.room for s in states} >= {"Baby Room", "Toddler Room",
                                        "Preschool Room"}


def test_quiet_day_has_no_ratio_breach(alerts):
    saturday = _next_saturday()
    assert alerts.summary(saturday)["rooms_in_breach"] == 0
    assert not [a for a in alerts.list_alerts(saturday)
                if a.category == "ratio" and a.severity == "breach"]


def test_headline_is_empty_when_compliant(alerts):
    # Age-band drift in the fixed demo DOBs can raise warnings, but nothing
    # should be an outright breach on an empty day.
    assert "breach" not in alerts.headline(_next_saturday())


# ── Ratio breaches ───────────────────────────────────────────────────────────

def test_too_many_children_for_the_staff_is_a_breach(alerts, sessions):
    saturday = _next_saturday()
    # Baby Room is 1:3 with one practitioner based there in the demo data.
    for pupil in ("NCH001", "NCH002", "NCH003", "NCH004", "NCH005"):
        sessions.book_extra_session(pupil, saturday, "all-day",
                                    room="Baby Room")

    baby = next(s for s in alerts.room_states(saturday)
                if s.room == "Baby Room")
    assert baby.children_counted == 5
    assert baby.required_staff == 2      # ceil(5 / 3)
    assert baby.staff_available == 1
    assert baby.compliant is False
    assert baby.shortfall == 1
    assert baby.spare_places == -2

    breaches = [a for a in alerts.breaches(saturday) if a.category == "ratio"]
    assert breaches, "expected a ratio breach alert"
    assert "under ratio" in breaches[0].message
    assert alerts.summary(saturday)["rooms_in_breach"] >= 1
    assert "breach" in alerts.headline(saturday)


def test_room_with_no_ratio_set_is_flagged(alerts):
    saturday = _next_saturday()
    with alerts.connect() as conn:
        conn.execute("UPDATE rooms SET staff_ratio = NULL "
                     "WHERE name = 'Baby Room'")
        conn.commit()
    setup = [a for a in alerts.list_alerts(saturday)
             if a.category == "setup" and a.room == "Baby Room"]
    assert setup and "no staff:child ratio" in setup[0].message


def test_over_capacity_booking_is_flagged(alerts, sessions):
    saturday = _next_saturday()
    with alerts.connect() as conn:
        conn.execute("UPDATE rooms SET capacity = 1 WHERE name = 'Baby Room'")
        conn.commit()
    for pupil in ("NCH001", "NCH002"):
        sessions.book_extra_session(pupil, saturday, "all-day",
                                    room="Baby Room")
    assert "capacity" in _kinds(alerts.list_alerts(saturday))


# ── Staff absence ────────────────────────────────────────────────────────────

def test_staff_absence_removes_an_adult_and_raises_an_alert(
        alerts, sessions, monkeypatch):
    saturday = _next_saturday()
    # Three children in Baby Room at 1:3 needs one adult — exactly what's there.
    for pupil in ("NCH001", "NCH002", "NCH003"):
        sessions.book_extra_session(pupil, saturday, "all-day",
                                    room="Baby Room")
    baby = next(s for s in alerts.room_states(saturday)
                if s.room == "Baby Room")
    assert baby.compliant is True

    # NST004 is the Baby Room practitioner in the demo data.
    monkeypatch.setattr(alerts, "absent_staff_today", lambda day=None: {
        "NST004": {"type": "Sickness", "since": saturday,
                   "cover_source": "Pending", "cover_required": True}})

    baby = next(s for s in alerts.room_states(saturday)
                if s.room == "Baby Room")
    assert baby.staff_absent == 1
    assert baby.staff_available == 0
    assert baby.compliant is False

    absence = [a for a in alerts.list_alerts(saturday)
               if a.category == "staff-absence"]
    assert absence
    assert absence[0].severity == "breach"
    assert "no cover arranged" in absence[0].detail


def test_absent_staff_today_survives_a_missing_absence_module(
        alerts, monkeypatch):
    import builtins
    real_import = builtins.__import__

    def _boom(name, *args, **kwargs):
        if "staff_absence" in name:
            raise ImportError("absence module unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _boom)
    assert alerts.absent_staff_today() == {}


# ── Child movement ───────────────────────────────────────────────────────────

def test_child_in_a_different_room_today_is_reported(alerts, sessions):
    saturday = _next_saturday()
    # NCH003 is based in the Baby Room; book them into the Toddler Room.
    sessions.book_extra_session("NCH003", saturday, "all-day",
                                room="Toddler Room")
    movement = [a for a in alerts.list_alerts(saturday)
                if a.category == "child-movement"]
    assert any("not their usual Baby Room" in a.message for a in movement)


def test_booking_into_an_undefined_room_is_reported(alerts, sessions):
    saturday = _next_saturday()
    sessions.book_extra_session("NCH003", saturday, "all-day",
                                room="Garden Annexe")
    movement = [a for a in alerts.list_alerts(saturday)
                if a.category == "child-movement"]
    assert any("not a defined room" in a.message for a in movement)


def test_extra_session_with_no_headroom_is_reported(alerts, sessions):
    saturday = _next_saturday()
    for pupil in ("NCH001", "NCH002", "NCH003"):
        sessions.book_extra_session(pupil, saturday, "all-day",
                                    room="Baby Room")
    movement = [a for a in alerts.list_alerts(saturday)
                if a.category == "child-movement"]
    assert any("no ratio headroom" in a.message for a in movement)


# ── Age bands ────────────────────────────────────────────────────────────────

def test_child_aged_out_of_their_room_is_reported(alerts):
    saturday = _next_saturday()
    four_years_ago = (_dt.date.today() - _dt.timedelta(days=4 * 365)).isoformat()
    with alerts.connect() as conn:
        conn.execute(
            "INSERT INTO pupils (pupil_id, first_name, last_name, "
            "date_of_birth, room, status) "
            "VALUES ('NCH900', 'Too', 'Big', ?, 'Baby Room', 'active')",
            (four_years_ago,))
        conn.commit()
    age = [a for a in alerts.list_alerts(saturday) if a.category == "age-band"]
    assert any(a.subject_id == "NCH900" and "aged out" in a.message
               for a in age)


def test_child_below_their_room_band_is_reported(alerts):
    saturday = _next_saturday()
    three_months_ago = (_dt.date.today() - _dt.timedelta(days=90)).isoformat()
    with alerts.connect() as conn:
        conn.execute(
            "INSERT INTO pupils (pupil_id, first_name, last_name, "
            "date_of_birth, room, status) "
            "VALUES ('NCH901', 'Too', 'Small', ?, 'Preschool Room', 'active')",
            (three_months_ago,))
        conn.commit()
    age = [a for a in alerts.list_alerts(saturday) if a.category == "age-band"]
    assert any(a.subject_id == "NCH901" and "younger than" in a.message
               for a in age)


# ── Late collection ──────────────────────────────────────────────────────────

def test_child_still_on_site_after_their_session_is_reported(alerts, sessions):
    today = _dt.date.today().isoformat()
    sessions.create_booking({
        "pupil_id": "NCH001", "session_date": today, "session_type": "all-day",
        "kind": "extra", "start_time": "08:00", "end_time": "18:00",
        "room": "Toddler Room"})
    with alerts.connect() as conn:
        conn.execute(
            "INSERT INTO sign_in_out_log (event_id, pupil_id, event_date, "
            "event_time, direction, person_name, relationship) "
            "VALUES ('NSO900', 'NCH001', ?, '08:05', 'in', 'Sarah Hughes', "
            "'Parent')", (today,))
        conn.commit()

    late = [a for a in alerts.list_alerts(today, now="19:05")
            if a.category == "late-collection"]
    assert late, "expected a late-collection alert"
    assert late[0].subject_id == "NCH001"
    assert "65 minutes past" in late[0].message
    assert "uncollected-child procedure" in late[0].detail


def test_within_the_grace_period_is_not_late(alerts, sessions):
    today = _dt.date.today().isoformat()
    sessions.create_booking({
        "pupil_id": "NCH001", "session_date": today, "session_type": "all-day",
        "kind": "extra", "start_time": "08:00", "end_time": "18:00",
        "room": "Toddler Room"})
    with alerts.connect() as conn:
        conn.execute(
            "INSERT INTO sign_in_out_log (event_id, pupil_id, event_date, "
            "event_time, direction, person_name) "
            "VALUES ('NSO901', 'NCH001', ?, '08:05', 'in', 'Sarah Hughes')",
            (today,))
        conn.commit()
    assert not [a for a in alerts.list_alerts(today, now="18:05")
                if a.category == "late-collection"]


def test_late_collection_is_not_reported_for_other_days(alerts):
    assert alerts._late_collection_alerts([], _next_saturday(), "23:00") == []


# ── Closures ─────────────────────────────────────────────────────────────────

def test_a_closed_day_short_circuits_every_rule(alerts, sessions):
    saturday = _next_saturday()
    for pupil in ("NCH001", "NCH002", "NCH003", "NCH004", "NCH005"):
        sessions.book_extra_session(pupil, saturday, "all-day",
                                    room="Baby Room")
    sessions.create_closure({"name": "Bank holiday", "start_date": saturday,
                             "closure_type": "bank-holiday"})

    rows = alerts.list_alerts(saturday)
    assert len(rows) == 1
    assert rows[0].severity == "info"
    assert "closed" in rows[0].message
    assert alerts.summary(saturday)["breaches"] == 0


# ── Filtering & validation ───────────────────────────────────────────────────

def test_alerts_are_sorted_worst_first(alerts, sessions):
    saturday = _next_saturday()
    for pupil in ("NCH001", "NCH002", "NCH003", "NCH004", "NCH005"):
        sessions.book_extra_session(pupil, saturday, "all-day",
                                    room="Baby Room")
    severities = [a.severity for a in alerts.list_alerts(saturday)]
    ranks = [alerts.SEVERITIES.index(s) for s in severities]
    assert ranks == sorted(ranks)


def test_category_filter_narrows_the_list(alerts):
    saturday = _next_saturday()
    rows = alerts.list_alerts(saturday, category="age-band")
    assert all(a.category == "age-band" for a in rows)


def test_bad_date_is_rejected(alerts):
    with pytest.raises(alerts.ValidationError):
        alerts.list_alerts("not-a-date")
