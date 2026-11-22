"""Year-group configuration (domain.academics.year_groups.year_groups)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.academics.year_groups import year_groups as YG
from education_system.systems.primary.domain.learners.pupils import pupils as P


def _pupil(year="3", first="Ada"):
    return P.create_pupil({"first_name": first, "last_name": "Test",
                           "year_group": year, "date_of_birth": "2018-01-01"})


# ── empty database ──

def test_list_all_on_empty_db_gives_one_default_per_year():
    rows = YG.list_all()
    assert [r.year_group for r in rows] == ["R", "1", "2", "3", "4", "5", "6"]
    assert all(r.head_of_year is None and r.capacity is None and r.notes is None
               for r in rows)


def test_get_missing_and_blank_return_none():
    assert YG.get("4") is None
    assert YG.get("") is None
    assert YG.get(None) is None


def test_pupil_counts_on_empty_db_are_all_zero():
    assert YG.pupil_counts() == {yg: 0 for yg in ("R", "1", "2", "3", "4", "5", "6")}


# ── upsert ──

def test_upsert_creates_then_updates_one_row():
    rec = YG.upsert({"year_group": "3", "head_of_year": " Mrs Oak ",
                     "capacity": "60", "notes": "Two classes"})
    assert (rec.year_group, rec.head_of_year, rec.capacity, rec.notes) == (
        "3", "Mrs Oak", 60, "Two classes")
    again = YG.upsert({"year_group": "3", "head_of_year": "Mr Ash"})
    assert again.head_of_year == "Mr Ash"
    assert again.capacity is None   # upsert replaces every field
    assert again.notes is None
    assert YG.get("3") == again


def test_list_all_merges_saved_rows_with_defaults():
    YG.upsert({"year_group": "R", "capacity": 30})
    rows = {r.year_group: r for r in YG.list_all()}
    assert rows["R"].capacity == 30
    assert rows["6"].capacity is None
    assert len(rows) == 7


def test_blank_strings_become_none():
    rec = YG.upsert({"year_group": "1", "head_of_year": "  ", "capacity": "",
                     "notes": ""})
    assert (rec.head_of_year, rec.capacity, rec.notes) == (None, None, None)


# ── validation ──

def test_year_group_required():
    with pytest.raises(YG.ValidationError, match="Year group is required"):
        YG.upsert({"year_group": " "})


def test_year_group_must_be_primary():
    with pytest.raises(YG.ValidationError, match="Year group must be one of"):
        YG.upsert({"year_group": "7"})


def test_capacity_must_be_whole_number():
    with pytest.raises(YG.ValidationError, match="whole number"):
        YG.upsert({"year_group": "2", "capacity": "lots"})


@pytest.mark.parametrize("cap", [-1, 1001])
def test_capacity_range(cap):
    with pytest.raises(YG.ValidationError, match="between 0 and 1000"):
        YG.upsert({"year_group": "2", "capacity": cap})


@pytest.mark.parametrize("cap", [0, 1000])
def test_capacity_bounds_accepted(cap):
    assert YG.upsert({"year_group": "2", "capacity": cap}).capacity == cap


# ── pupil counts ──

def test_pupil_counts_per_year():
    _pupil("3")
    _pupil("3", "Bea")
    _pupil("R", "Cy")
    counts = YG.pupil_counts()
    assert counts["3"] == 2
    assert counts["R"] == 1
    assert counts["6"] == 0
    assert sum(counts.values()) == 3


# ── delete ──

def test_delete_clears_config():
    YG.upsert({"year_group": "5", "capacity": 45})
    assert YG.delete("5") is True
    assert YG.get("5") is None
    assert YG.delete("5") is False
