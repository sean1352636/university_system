"""Wellbeing check-ins (primary domain.pastoral.wellbeing.wellbeing)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.wellbeing import wellbeing as WB

_n = 0


def _pupil(year="3", first=None, last=None):
    global _n
    _n += 1
    return P.create_pupil({"first_name": first or f"Pupil{_n}",
                           "last_name": last or f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2018-01-01"})


def _checkin(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "checkin_date": "2026-10-05",
            "mood_rating": 4, "confidence_rating": 3, "connection_rating": 5,
            "recorded_by": "Mr Tutor", **extra}
    return WB.log_checkin(data)


# ── log / get ────────────────────────────────────────────────────────

def test_log_checkin_stores_values_and_defaults():
    ava = _pupil(year="5", first="Ava", last="Jones")
    c = _checkin(ava, stressors=" tests ", supports="friends",
                 follow_up_date="2026-10-12", follow_up_with="Mrs Pastoral",
                 notes="ok")
    assert c.checkin_id > 0 and c.pupil_id == ava.pupil_id
    assert (c.checkin_date, c.source, c.status) == (
        "2026-10-05", WB.DEFAULT_SOURCE, WB.DEFAULT_STATUS)
    assert (c.mood_rating, c.confidence_rating, c.connection_rating) == (4, 3, 5)
    assert (c.stressors, c.supports, c.recorded_by) == ("tests", "friends", "Mr Tutor")
    assert (c.follow_up_date, c.follow_up_with, c.notes) == (
        "2026-10-12", "Mrs Pastoral", "ok")
    assert c.action_needed is False and c.action_summary is None
    assert c.pupil_name == "Ava Jones" and c.pupil_year == "5"
    assert WB.get(c.checkin_id) == c


def test_ratings_accept_numeric_strings():
    c = _checkin(_pupil(), mood_rating="2", confidence_rating=" ", connection_rating="")
    assert (c.mood_rating, c.confidence_rating, c.connection_rating) == (2, None, None)


def test_blank_date_defaults_to_today():
    c = _checkin(_pupil(), checkin_date="", follow_up_date=None)
    assert c.checkin_date == dt.date.today().isoformat()


def test_text_only_checkin_is_allowed():
    c = _checkin(_pupil(), mood_rating=None, confidence_rating=None,
                 connection_rating=None, notes="Seemed quiet")
    assert c.average_rating is None and c.notes == "Seemed quiet"


def test_average_rating():
    ava = _pupil()
    assert _checkin(ava).average_rating == 4.0                       # (4+3+5)/3
    assert _checkin(ava, connection_rating=None).average_rating == 3.5
    assert _checkin(ava, mood_rating=1, confidence_rating=2,
                    connection_rating=2).average_rating == 1.67


def test_get_missing_is_none():
    assert WB.get(77) is None


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("bad, msg", [
    ({"pupil_id": ""}, "Pupil ID is required"),
    ({"pupil_id": "P0000000"}, "No pupil with id P0000000"),
    ({"checkin_date": "5/10/2026"}, "Check-in date must be YYYY-MM-DD"),
    ({"checkin_date": "2026-13-01"}, "not a real date"),
    ({"source": "Parent"}, "Source must be one of"),
    ({"mood_rating": 0}, "Mood rating must be between 1 and 5"),
    ({"confidence_rating": 6}, "Confidence rating must be between 1 and 5"),
    ({"connection_rating": "great"}, "Connection rating must be a whole number"),
    ({"status": "Done"}, "Status must be one of"),
    ({"follow_up_date": "2026/10/12"}, "Follow-up date must be YYYY-MM-DD"),
    ({"follow_up_date": "2026-10-04"}, "Follow-up date cannot be before check-in date"),
    ({"action_needed": True}, "Action summary is required"),
    ({"mood_rating": None, "confidence_rating": None, "connection_rating": None},
     "at least one rating or free-text"),
])
def test_log_refuses(bad, msg):
    ava = _pupil()
    with pytest.raises(WB.ValidationError, match=msg):
        _checkin(ava, **bad)
    assert WB.list_checkins() == []


def test_rating_bounds_inclusive_and_same_day_follow_up():
    c = _checkin(_pupil(), mood_rating=1, confidence_rating=5,
                 follow_up_date="2026-10-05")
    assert (c.mood_rating, c.confidence_rating, c.follow_up_date) == (1, 5, "2026-10-05")


def test_action_needed_with_summary():
    c = _checkin(_pupil(), action_needed=True, action_summary="Refer to ELSA")
    assert c.action_needed is True and c.action_summary == "Refer to ELSA"


# ── listing ──────────────────────────────────────────────────────────

def test_list_empty():
    assert WB.list_checkins() == []


def test_list_orders_newest_first_then_id():
    ava = _pupil()
    a = _checkin(ava, checkin_date="2026-10-01")
    b = _checkin(ava, checkin_date="2026-10-03")
    c = _checkin(ava, checkin_date="2026-10-03")
    assert [r.checkin_id for r in WB.list_checkins()] == [
        c.checkin_id, b.checkin_id, a.checkin_id]


def test_list_filters():
    ava, ben = _pupil(year="2"), _pupil(year="6")
    a = _checkin(ava, checkin_date="2026-09-20", source="Self check-in")
    b = _checkin(ava, checkin_date="2026-10-10", status="Escalated",
                 action_needed=True, action_summary="DSL informed")
    c = _checkin(ben, checkin_date="2026-10-20", source="Counsellor")
    ids = lambda rows: {r.checkin_id for r in rows}  # noqa: E731
    assert ids(WB.list_checkins(pupil_id=f" {ava.pupil_id} ")) == {a.checkin_id, b.checkin_id}
    assert ids(WB.list_checkins(year_group="6")) == {c.checkin_id}
    assert ids(WB.list_checkins(status="Escalated")) == {b.checkin_id}
    assert ids(WB.list_checkins(source="Counsellor")) == {c.checkin_id}
    assert ids(WB.list_checkins(action_needed=True)) == {b.checkin_id}
    assert ids(WB.list_checkins(action_needed=False)) == {a.checkin_id, c.checkin_id}
    assert ids(WB.list_checkins(date_from="2026-10-01")) == {b.checkin_id, c.checkin_id}
    assert ids(WB.list_checkins(date_to="2026-10-10")) == {a.checkin_id, b.checkin_id}


@pytest.mark.parametrize("kwargs, msg", [
    ({"year_group": "7"}, "Year filter must be one of"),
    ({"status": "Done"}, "Status filter must be one of"),
    ({"source": "Parent"}, "Source filter must be one of"),
    ({"date_from": "01-10-2026"}, "From date must be YYYY-MM-DD"),
    ({"date_to": "2026-02-30"}, "To date is not a real date"),
])
def test_list_refuses_bad_filters(kwargs, msg):
    with pytest.raises(WB.ValidationError, match=msg):
        WB.list_checkins(**kwargs)


# ── update / status / delete ─────────────────────────────────────────

def test_update_merges_existing_values():
    ava = _pupil()
    c = _checkin(ava, stressors="spelling test")
    upd = WB.update(c.checkin_id, {"mood_rating": 2, "notes": "low after test"})
    assert (upd.mood_rating, upd.notes) == (2, "low after test")
    assert (upd.confidence_rating, upd.stressors, upd.recorded_by) == (
        3, "spelling test", "Mr Tutor")


def test_update_revalidates_and_keeps_row_on_refusal():
    c = _checkin(_pupil())
    with pytest.raises(WB.ValidationError, match="Action summary is required"):
        WB.update(c.checkin_id, {"action_needed": True})
    with pytest.raises(WB.ValidationError, match="between 1 and 5"):
        WB.update(c.checkin_id, {"mood_rating": 9})
    assert WB.get(c.checkin_id) == c


def test_update_missing_refused():
    with pytest.raises(WB.ValidationError, match="No wellbeing check-in #5"):
        WB.update(5, {"notes": "x"})


def test_set_status():
    c = _checkin(_pupil())
    for status in ("InProgress", "Escalated", "Closed"):
        assert WB.set_status(c.checkin_id, status).status == status
    assert WB.get(c.checkin_id).status == "Closed"
    with pytest.raises(WB.ValidationError, match="Status must be one of"):
        WB.set_status(c.checkin_id, "Archived")


def test_delete():
    c = _checkin(_pupil())
    assert WB.delete(c.checkin_id) is True
    assert WB.get(c.checkin_id) is None
    assert WB.delete(c.checkin_id) is False


# ── summaries ────────────────────────────────────────────────────────

def test_pupil_summary():
    ava, ben = _pupil(), _pupil()
    _checkin(ava, checkin_date="2026-09-01", mood_rating=1, confidence_rating=1,
             connection_rating=1)                                        # outside window
    _checkin(ava, checkin_date="2026-10-01", mood_rating=2, confidence_rating=3,
             connection_rating=None)
    _checkin(ava, checkin_date="2026-10-02", mood_rating=5, confidence_rating=4,
             connection_rating=4, action_needed=True, action_summary="Praise",
             status="Closed")
    _checkin(ben, checkin_date="2026-10-02")
    s = WB.pupil_summary(f" {ava.pupil_id} ", date_from="2026-10-01", date_to="2026-10-31")
    assert s["pupil_id"] == ava.pupil_id and s["count"] == 2
    assert (s["avg_mood"], s["avg_confidence"], s["avg_connection"]) == (3.5, 3.5, 4.0)
    assert s["action_needed"] == 1
    assert s["by_status"] == {"Open": 1, "Closed": 1}
    assert [c.checkin_date for c in s["checkins"]] == ["2026-10-02", "2026-10-01"]
    assert WB.pupil_summary(ava.pupil_id)["count"] == 3


def test_pupil_summary_without_checkins():
    s = WB.pupil_summary(_pupil().pupil_id)
    assert (s["count"], s["avg_mood"], s["avg_confidence"], s["avg_connection"],
            s["action_needed"], s["by_status"], s["checkins"]) == (
        0, None, None, None, 0, {}, [])


def test_cohort_summary():
    ava, ben, cat = _pupil(year="1"), _pupil(year="1"), _pupil(year="4")
    _checkin(ava, mood_rating=1, confidence_rating=2, connection_rating=3,
             source="Self check-in")
    _checkin(ben, mood_rating=4, confidence_rating=None, connection_rating=5,
             status="InProgress", action_needed=True, action_summary="Monitor")
    _checkin(cat, mood_rating=5, confidence_rating=5, connection_rating=5)
    s = WB.cohort_summary(year_group="1")
    assert s["total"] == 2
    assert (s["avg_mood"], s["avg_confidence"], s["avg_connection"]) == (2.5, 2.0, 4.0)
    assert s["action_needed"] == 1
    assert s["by_status"] == {"Open": 1, "InProgress": 1}
    assert s["by_source"] == {"Self check-in": 1, "Form tutor": 1}
    whole = WB.cohort_summary()
    assert whole["total"] == 3 and whole["avg_mood"] == 3.33     # (1+4+5)/3


def test_cohort_summary_empty():
    assert WB.cohort_summary() == {"total": 0, "avg_mood": None, "avg_confidence": None,
                                   "avg_connection": None, "action_needed": 0,
                                   "by_status": {}, "by_source": {}}


# ── low wellbeing ────────────────────────────────────────────────────

def test_low_wellbeing_uses_latest_checkin_per_pupil():
    ava, ben, cat, dan = _pupil(year="2"), _pupil(year="2"), _pupil(year="5"), _pupil()
    _checkin(ava, checkin_date="2026-10-01", mood_rating=1)
    ava_latest = _checkin(ava, checkin_date="2026-10-08", mood_rating=4,
                          confidence_rating=2, connection_rating=4)
    _checkin(ben, checkin_date="2026-10-01", mood_rating=1)            # was low...
    _checkin(ben, checkin_date="2026-10-08", mood_rating=4,
             confidence_rating=4)                                  # ...now fine
    cat_c = _checkin(cat, mood_rating=3, confidence_rating=3, connection_rating=3)
    _checkin(dan, mood_rating=None, confidence_rating=None, connection_rating=None,
             notes="text only")                                        # no scores
    low = WB.low_wellbeing()
    assert set(low) == {ava.pupil_id}
    assert [c.checkin_id for c in low[ava.pupil_id]] == [ava_latest.checkin_id]
    assert set(WB.low_wellbeing(threshold=3)) == {ava.pupil_id, cat.pupil_id}
    assert low_ids(WB.low_wellbeing(threshold=3, year_group="5")) == [cat_c.checkin_id]
    assert WB.low_wellbeing(threshold=1) == {}


def low_ids(result):
    return [c.checkin_id for rows in result.values() for c in rows]


@pytest.mark.parametrize("threshold", [0, 6])
def test_low_wellbeing_threshold_bounds(threshold):
    with pytest.raises(WB.ValidationError, match="Threshold must be between 1 and 5"):
        WB.low_wellbeing(threshold=threshold)


def test_low_wellbeing_empty():
    assert WB.low_wellbeing() == {}
