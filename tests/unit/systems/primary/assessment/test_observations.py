"""Lesson observations (domain.assessment.observations.observations)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.academics.subjects import subjects as SB
from education_system.systems.primary.domain.assessment.observations import observations as OB
from education_system.systems.primary.domain.learners.pupils import pupils as P


def _obs(**extra):
    data = {"teacher": "Ms Teach", "observer": "Head", "observation_date": "2025-10-07"}
    data.update(extra)
    return OB.create(data)


def _subject(code="ENGL", name="English"):
    return SB.create({"code": code, "name": name, "key_stage": "All"})


# ── create / get ─────────────────────────────────────────────────────

def test_create_applies_defaults():
    o = _obs()
    assert (o.observation_type, o.judgement, o.status) == (
        "Learning walk", "Not judged", "Scheduled")
    assert o.subject_id is None and o.period is None and o.year_group is None
    assert OB.get(o.observation_id) == o


def test_create_stores_every_field_and_joins_subject():
    s = _subject()
    o = _obs(subject_id=str(s.subject_id), year_group="4", form_group="4B", period="3",
             observation_type="Formal", focus=" Questioning ", judgement="Good",
             strengths="Pace", development_areas="Challenge", action_points="Stretch HA",
             follow_up_date="2025-11-07", status="Complete", notes="n")
    got = OB.get(o.observation_id)
    assert (got.subject_id, got.subject_code, got.subject_name) == (s.subject_id, "ENGL", "English")
    assert (got.year_group, got.form_group, got.period) == ("4", "4B", 3)
    assert (got.observation_type, got.focus, got.judgement, got.status) == (
        "Formal", "Questioning", "Good", "Complete")
    assert (got.strengths, got.development_areas, got.action_points) == (
        "Pace", "Challenge", "Stretch HA")
    assert (got.follow_up_date, got.notes) == ("2025-11-07", "n")


def test_missing_date_defaults_to_today():
    o = OB.create({"teacher": "T", "observer": "O"})
    assert o.observation_date == dt.date.today().isoformat()


def test_get_unknown_is_none():
    assert OB.get(99) is None


@pytest.mark.parametrize("period", [1, 8, "5"])
def test_period_range_inclusive(period):
    assert _obs(period=period).period == int(period)


def test_follow_up_may_be_same_day():
    assert _obs(follow_up_date="2025-10-07").follow_up_date == "2025-10-07"


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("field, value, message", [
    ("teacher", "", "Teacher is required"),
    ("teacher", "t" * 65, "64 characters or fewer"),
    ("subject_id", "ten", "Subject ID must be a number"),
    ("subject_id", 404, "No subject #404"),
    ("year_group", "7", "Year group must be one of"),
    ("observation_date", "07/10/2025", "Observation date must be YYYY-MM-DD"),
    ("observation_date", "2025-09-31", "Observation date is not a real date"),
    ("period", "first", "Period must be a number"),
    ("period", 0, "Period must be between 1 and 8"),
    ("period", 9, "Period must be between 1 and 8"),
    ("observer", " ", "Observer is required"),
    ("observation_type", "Drop-in", "Observation type must be one of"),
    ("judgement", "Excellent", "Judgement must be one of"),
    ("status", "Done", "Status must be one of"),
    ("follow_up_date", "2025-10-06", "Follow-up date cannot be before observation date"),
    ("follow_up_date", "soon", "Follow-up date must be YYYY-MM-DD"),
])
def test_create_refuses_invalid(field, value, message):
    with pytest.raises(P.ValidationError, match=message):
        _obs(**{field: value})
    assert OB.list_observations() == []


def test_complete_needs_a_judgement():
    with pytest.raises(P.ValidationError, match="Judgement is required when status is Complete"):
        _obs(status="Complete")
    assert _obs(status="Complete", judgement="Requires improvement").status == "Complete"


# ── update / status / delete ─────────────────────────────────────────

def test_update_merges_fields():
    o = _obs(focus="f", notes="keep")
    up = OB.update(o.observation_id, {"judgement": "Outstanding", "focus": "Feedback"})
    assert (up.judgement, up.focus, up.notes) == ("Outstanding", "Feedback", "keep")


def test_update_unknown_and_invalid():
    with pytest.raises(P.ValidationError, match="No observation #12"):
        OB.update(12, {"teacher": "x"})
    o = _obs()
    with pytest.raises(P.ValidationError, match="Period must be between"):
        OB.update(o.observation_id, {"period": 12})
    assert OB.get(o.observation_id).period is None


def test_set_status_workflow():
    o = _obs()
    with pytest.raises(P.ValidationError, match="Judgement is required"):
        OB.set_status(o.observation_id, "Complete")
    OB.update(o.observation_id, {"judgement": "Good"})
    assert OB.set_status(o.observation_id, "Complete").status == "Complete"
    assert OB.set_status(o.observation_id, "FollowUp").status == "FollowUp"
    assert OB.set_status(o.observation_id, "Closed").status == "Closed"
    with pytest.raises(P.ValidationError, match="Status must be one of"):
        OB.set_status(o.observation_id, "Archived")


def test_delete():
    o = _obs()
    assert OB.delete(o.observation_id) is True
    assert OB.get(o.observation_id) is None
    assert OB.delete(o.observation_id) is False


# ── listing ──────────────────────────────────────────────────────────

def _seed():
    a = _obs(teacher="Ann", observer="Head", observation_date="2025-09-10", year_group="3",
             observation_type="Formal", judgement="Good", status="Complete")
    b = _obs(teacher="Ann", observer="Deputy", observation_date="2025-10-01", year_group="3",
             judgement="Requires improvement", status="FollowUp")
    c = _obs(teacher="Bob", observer="Head", observation_date="2025-10-01", year_group="5",
             observation_type="Peer")
    d = _obs(teacher="Bob", observer="Head", observation_date="2025-11-20",
             observation_type="Formal", judgement="Outstanding", status="Closed")
    return a, b, c, d


def test_list_newest_first_ties_by_id():
    a, b, c, d = _seed()
    assert [o.observation_id for o in OB.list_observations()] == [
        d.observation_id, c.observation_id, b.observation_id, a.observation_id]


def test_list_filters():
    a, b, c, d = _seed()

    def ids(**kw):
        return {o.observation_id for o in OB.list_observations(**kw)}

    assert ids(teacher="Ann") == {a.observation_id, b.observation_id}
    assert ids(observer="Deputy") == {b.observation_id}
    assert ids(observation_type="Formal") == {a.observation_id, d.observation_id}
    assert ids(judgement="Not judged") == {c.observation_id}
    assert ids(status="FollowUp") == {b.observation_id}
    assert ids(year_group="5") == {c.observation_id}
    assert ids(date_from="2025-10-01") == {b.observation_id, c.observation_id, d.observation_id}
    assert ids(date_to="2025-10-01") == {a.observation_id, b.observation_id, c.observation_id}
    assert ids(teacher="Bob", date_from="2025-11-01") == {d.observation_id}


@pytest.mark.parametrize("kwargs, message", [
    ({"observation_type": "x"}, "Type filter"),
    ({"judgement": "x"}, "Judgement filter"),
    ({"status": "x"}, "Status filter"),
    ({"year_group": "x"}, "Year filter"),
    ({"date_to": "2025-13-01"}, "To date is not a real date"),
])
def test_list_refuses_bad_filters(kwargs, message):
    with pytest.raises(P.ValidationError, match=message):
        OB.list_observations(**kwargs)


# ── summaries ────────────────────────────────────────────────────────

def test_teacher_summary():
    a, b, _c, _d = _seed()
    s = OB.teacher_summary("Ann")
    assert s["teacher"] == "Ann" and s["total"] == 2
    assert s["by_judgement"] == {"Good": 1, "Requires improvement": 1}
    assert s["by_status"] == {"Complete": 1, "FollowUp": 1}
    assert s["by_type"] == {"Formal": 1, "Learning walk": 1}
    assert [o.observation_id for o in s["observations"]] == [b.observation_id, a.observation_id]


def test_teacher_summary_unknown_teacher_is_empty():
    _seed()
    s = OB.teacher_summary("Nobody")
    assert s["total"] == 0 and s["observations"] == [] and s["by_judgement"] == {}


def test_cohort_summary():
    _seed()
    s = OB.cohort_summary()
    assert s["total"] == 4
    assert s["by_judgement"] == {"Good": 1, "Requires improvement": 1, "Not judged": 1,
                                 "Outstanding": 1}
    assert s["by_status"] == {"Complete": 1, "FollowUp": 1, "Scheduled": 1, "Closed": 1}
    assert s["by_type"] == {"Formal": 2, "Learning walk": 1, "Peer": 1}
    assert s["follow_ups"] == 1


def test_empty_cohort_summary():
    assert OB.cohort_summary() == {"total": 0, "by_judgement": {}, "by_status": {},
                                   "by_type": {}, "follow_ups": 0}
