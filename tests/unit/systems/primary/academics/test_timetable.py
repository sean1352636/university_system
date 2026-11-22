"""Weekly timetable slots (domain.academics.timetable.timetable)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.academics.subjects import subjects as S
from education_system.systems.primary.domain.academics.timetable import timetable as TT


def _subject(code="MATH", name="Maths", **extra):
    return S.create({"code": code, "name": name, "key_stage": "All", **extra})


def _slot(subject, day="Mon", period=1, year="3", **extra):
    return TT.create_slot({"year_group": year, "subject_id": subject.subject_id,
                           "day_of_week": day, "period": period, **extra})


# ── empty database ──

def test_empty_db():
    assert TT.list_slots() == []
    assert TT.get_slot(1) is None
    assert TT.delete_slot(1) is False
    assert TT.weekly_grid() == {}
    assert TT.counts() == {"total": 0, "teachers": 0}


# ── create ──

def test_create_slot_with_subject_join():
    sub = _subject()
    s = _slot(sub, day="Tuesday", period="2", form_group=" 3 Maple ", start_time="09:00",
              end_time="10:00", room=" B2 ", teacher=" Mrs Oak ", notes=" ")
    assert (s.year_group, s.form_group, s.day_of_week, s.period, s.start_time,
            s.end_time, s.room, s.teacher, s.notes) == (
        "3", "3 Maple", "Tue", 2, "09:00", "10:00", "B2", "Mrs Oak", None)
    assert (s.subject_code, s.subject_name) == ("MATH", "Maths")
    assert TT.get_slot(s.slot_id) == s


# ── validation ──

def test_year_group_rules():
    sub = _subject()
    with pytest.raises(TT.ValidationError, match="Year group is required"):
        _slot(sub, year="")
    with pytest.raises(TT.ValidationError, match="Year group must be one of"):
        _slot(sub, year="Y3")


def test_subject_rules():
    sub = _subject()
    with pytest.raises(TT.ValidationError, match="Subject is required"):
        TT.create_slot({"year_group": "3", "day_of_week": "Mon", "period": 1})
    with pytest.raises(TT.ValidationError, match="Subject ID must be a number"):
        TT.create_slot({"year_group": "3", "subject_id": "maths", "day_of_week": "Mon",
                        "period": 1})
    with pytest.raises(TT.ValidationError, match="No subject #77"):
        TT.create_slot({"year_group": "3", "subject_id": 77, "day_of_week": "Mon",
                        "period": 1})
    S.toggle_active(sub.subject_id)
    with pytest.raises(TT.ValidationError, match="MATH is inactive"):
        _slot(sub)


@pytest.mark.parametrize("day", ["Sat", "Saturday", "mon", ""])
def test_day_must_be_a_weekday(day):
    with pytest.raises(TT.ValidationError, match="Day must be one of"):
        _slot(_subject(), day=day)


def test_period_rules():
    sub = _subject()
    with pytest.raises(TT.ValidationError, match="Period is required"):
        _slot(sub, period="")
    with pytest.raises(TT.ValidationError, match="Period must be a number"):
        _slot(sub, period="first")
    with pytest.raises(TT.ValidationError, match="between 1 and 8"):
        _slot(sub, period=0)
    with pytest.raises(TT.ValidationError, match="between 1 and 8"):
        _slot(sub, period=9)
    assert _slot(sub, period=8).period == 8


def test_time_rules():
    sub = _subject()
    with pytest.raises(TT.ValidationError, match="Start time must be HH:MM"):
        _slot(sub, start_time="9:00")
    with pytest.raises(TT.ValidationError, match="End time must be HH:MM"):
        _slot(sub, end_time="24:00")
    with pytest.raises(TT.ValidationError, match="End time must be after start time"):
        _slot(sub, start_time="10:00", end_time="10:00")


# ── clashes ──

def test_same_class_same_period_clashes():
    sub = _subject()
    _slot(sub, form_group="3 Maple")
    with pytest.raises(TT.ValidationError, match="Slot clash: Year 3/3 Maple"):
        _slot(sub, form_group="3 Maple")


def test_whole_year_slots_clash_with_each_other():
    sub = _subject()
    _slot(sub)
    with pytest.raises(TT.ValidationError, match="Slot clash: Year 3 already has"):
        _slot(sub)


def test_different_class_day_or_period_do_not_clash():
    sub = _subject()
    _slot(sub, form_group="3 Maple")
    _slot(sub, form_group="3 Oak")
    _slot(sub, form_group="3 Maple", day="Wed")
    _slot(sub, form_group="3 Maple", period=2)
    _slot(sub, year="4", form_group="3 Maple")
    assert TT.counts()["total"] == 5


def test_teacher_cannot_be_in_two_places():
    sub = _subject()
    _slot(sub, form_group="3 Maple", teacher="Mrs Oak")
    with pytest.raises(TT.ValidationError, match="Teacher clash: Mrs Oak"):
        _slot(sub, year="4", form_group="4 Elm", teacher="Mrs Oak")
    _slot(sub, year="4", form_group="4 Elm", teacher="Mr Ash")


# ── listing / grid / counts ──

def test_list_sorted_by_day_then_period_and_filtered():
    maths, eng = _subject(), _subject("ENGL", "English")
    fri = _slot(maths, day="Fri", period=1, teacher="Mrs Oak")
    mon2 = _slot(eng, day="Mon", period=2, form_group="3 Maple")
    mon1 = _slot(maths, day="Mon", period=1, year="4", teacher="Mr Ash")
    ids = lambda xs: [x.slot_id for x in xs]  # noqa: E731
    assert ids(TT.list_slots()) == [mon1.slot_id, mon2.slot_id, fri.slot_id]
    assert ids(TT.list_slots(year_group="3")) == [mon2.slot_id, fri.slot_id]
    assert ids(TT.list_slots(form_group=" 3 Maple ")) == [mon2.slot_id]
    assert ids(TT.list_slots(day_of_week="Friday")) == [fri.slot_id]
    assert ids(TT.list_slots(teacher="Mr Ash")) == [mon1.slot_id]
    with pytest.raises(TT.ValidationError, match="Year filter"):
        TT.list_slots(year_group="7")
    with pytest.raises(TT.ValidationError, match="Day filter"):
        TT.list_slots(day_of_week="Sun")


def test_weekly_grid_groups_by_day_and_period():
    maths, eng = _subject(), _subject("ENGL", "English")
    a = _slot(maths, form_group="3 Maple")
    b = _slot(eng, form_group="3 Oak")
    c = _slot(maths, day="Tue", period=3, form_group="3 Maple")
    grid = TT.weekly_grid(year_group="3")
    assert set(grid) == {("Mon", 1), ("Tue", 3)}
    assert {s.slot_id for s in grid[("Mon", 1)]} == {a.slot_id, b.slot_id}
    assert [s.slot_id for s in grid[("Tue", 3)]] == [c.slot_id]
    assert set(TT.weekly_grid(form_group="3 Oak")) == {("Mon", 1)}


def test_counts_distinct_teachers():
    sub = _subject()
    _slot(sub, teacher="Mrs Oak")
    _slot(sub, day="Tue", teacher="Mrs Oak")
    _slot(sub, day="Wed", teacher="Mr Ash")
    _slot(sub, day="Thu")
    assert TT.counts() == {"total": 4, "teachers": 2}


# ── update / delete ──

def test_update_slot_merges_and_rechecks_clash():
    sub = _subject()
    a = _slot(sub, form_group="3 Maple", room="B2")
    b = _slot(sub, form_group="3 Maple", period=2)
    out = TT.update_slot(a.slot_id, {"room": "Hall", "teacher": "Mrs Oak"})
    assert (out.room, out.teacher, out.period) == ("Hall", "Mrs Oak", 1)
    assert TT.update_slot(a.slot_id, {"period": 1}).period == 1     # no self-clash
    with pytest.raises(TT.ValidationError, match="Slot clash"):
        TT.update_slot(b.slot_id, {"period": 1})
    with pytest.raises(TT.ValidationError, match="No timetable slot #99"):
        TT.update_slot(99, {})


def test_delete_slot_and_subject_in_use():
    sub = _subject()
    s = _slot(sub)
    assert S.is_in_use(sub.subject_id) is True
    assert TT.delete_slot(s.slot_id) is True
    assert TT.get_slot(s.slot_id) is None
    assert S.is_in_use(sub.subject_id) is False
