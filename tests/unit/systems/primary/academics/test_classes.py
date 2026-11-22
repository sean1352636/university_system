"""Classes (domain.academics.classes.classes)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.academics.classes import classes as C
from education_system.systems.primary.domain.learners.pupils import pupils as P


def _class(name="3 Maple", year="3", **extra):
    return C.create({"name": name, "year_group": year, **extra})


def _pupil(class_name, first="Ada", last="Test", year="3"):
    return P.create_pupil({"first_name": first, "last_name": last, "year_group": year,
                           "class_name": class_name, "date_of_birth": "2018-01-01"})


# ── empty database ──

def test_empty_db():
    assert C.list_all() == []
    assert C.get(1) is None
    assert C.get_by_name("3 Maple") is None
    assert C.counts() == {"total": 0, "active": 0, "inactive": 0}
    assert C.pupils_in_class("3 Maple") == []
    assert C.delete(99) is False


# ── create / read ──

def test_create_stores_every_field():
    rec = _class(teacher=" Mrs Oak ", room="B2", capacity="30", notes="Upstairs")
    assert rec.class_id > 0
    assert (rec.name, rec.year_group, rec.teacher, rec.room, rec.capacity,
            rec.is_active, rec.notes) == ("3 Maple", "3", "Mrs Oak", "B2", 30, True,
                                          "Upstairs")
    assert C.get(rec.class_id) == rec
    assert C.get_by_name(" 3 Maple ") == rec


def test_create_defaults():
    rec = _class()
    assert (rec.teacher, rec.room, rec.capacity, rec.notes, rec.is_active) == (
        None, None, None, None, True)


def test_create_inactive():
    assert _class(is_active=False).is_active is False


# ── validation ──

def test_name_required():
    with pytest.raises(C.ValidationError, match="Class name is required"):
        _class(name="  ")


def test_name_length():
    with pytest.raises(C.ValidationError, match="64 characters"):
        _class(name="x" * 65)


def test_year_group_required():
    with pytest.raises(C.ValidationError, match="Year group is required"):
        _class(year="")


def test_year_group_must_be_primary():
    with pytest.raises(C.ValidationError, match="Year group must be one of"):
        _class(year="9")


def test_capacity_must_be_integer():
    with pytest.raises(C.ValidationError, match="Capacity must be an integer"):
        _class(capacity="thirty")


@pytest.mark.parametrize("cap", [-1, 201])
def test_capacity_range(cap):
    with pytest.raises(C.ValidationError, match="between 0 and 200"):
        _class(capacity=cap)


def test_duplicate_name_refused():
    _class()
    with pytest.raises(C.ValidationError, match="already exists"):
        _class(year="4")


# ── listing ──

def test_list_filters_and_order():
    _class("4 Birch", "4")
    _class("3 Oak", "3")
    _class("3 ash", "3", is_active=False)
    assert [c.name for c in C.list_all()] == ["3 ash", "3 Oak", "4 Birch"]
    assert [c.name for c in C.list_all(year_group="3")] == ["3 ash", "3 Oak"]
    assert [c.name for c in C.list_all(active_only=True)] == ["3 Oak", "4 Birch"]
    assert [c.name for c in C.list_all(year_group="3", active_only=True)] == ["3 Oak"]


def test_list_year_filter_validated():
    with pytest.raises(C.ValidationError, match="Year filter"):
        C.list_all(year_group="10")


def test_counts():
    _class("1 A", "1")
    _class("1 B", "1", is_active=False)
    _class("2 A", "2")
    assert C.counts() == {"total": 3, "active": 2, "inactive": 1}


# ── update / toggle ──

def test_update_merges_given_fields():
    rec = _class(teacher="Mrs Oak", room="B2")
    out = C.update(rec.class_id, {"room": "C1", "capacity": 28})
    assert (out.teacher, out.room, out.capacity) == ("Mrs Oak", "C1", 28)


def test_update_rename_to_existing_refused():
    _class("3 Elm")
    rec = _class()
    with pytest.raises(C.ValidationError, match="already exists"):
        C.update(rec.class_id, {"name": "3 Elm"})


def test_update_keeping_own_name_allowed():
    rec = _class()
    assert C.update(rec.class_id, {"name": "3 Maple", "notes": "x"}).notes == "x"


def test_update_unknown_class():
    with pytest.raises(C.ValidationError, match="No class #42"):
        C.update(42, {"room": "A"})


def test_update_still_validates():
    rec = _class()
    with pytest.raises(C.ValidationError, match="between 0 and 200"):
        C.update(rec.class_id, {"capacity": 500})


def test_toggle_active_flips_both_ways():
    rec = _class()
    assert C.toggle_active(rec.class_id).is_active is False
    assert C.toggle_active(rec.class_id).is_active is True


def test_toggle_unknown_class():
    with pytest.raises(C.ValidationError, match="No class #7"):
        C.toggle_active(7)


# ── pupils in class / delete ──

def test_pupils_in_class_sorted_by_surname():
    _class()
    _pupil("3 Maple", "Zed", "Brown")
    _pupil("3 Maple", "Amy", "Adams")
    _pupil("3 Oak", "Other", "Kid")
    names = [(p.last_name, p.first_name) for p in C.pupils_in_class(" 3 Maple ")]
    assert names == [("Adams", "Amy"), ("Brown", "Zed")]
    assert C.pupils_in_class("") == []


def test_delete_empty_class():
    rec = _class()
    assert C.delete(rec.class_id) is True
    assert C.get(rec.class_id) is None


def test_delete_refused_while_pupils_assigned():
    rec = _class()
    _pupil("3 Maple")
    with pytest.raises(C.ValidationError, match="1 pupil"):
        C.delete(rec.class_id)
    assert C.get(rec.class_id) is not None
