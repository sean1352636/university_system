"""Year-group enrolment helpers (systems.primary.domain.admissions.enrolment.enrolment).

Roll by year, moving one pupil, end-of-year promotion and Year 6 leavers.
"""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.admissions.enrolment import enrolment as E
from education_system.systems.primary.domain.learners.pupils import pupils as P

_n = 0


def _pupil(year="3", class_name=None, **extra):
    global _n
    _n += 1
    data = {"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}", "year_group": year,
            "class_name": class_name, "date_of_birth": "2018-01-15"}
    data.update(extra)
    return P.create_pupil(data)


# ── roll by year ─────────────────────────────────────────────────────

def test_roll_by_year_empty_has_every_year():
    roll = E.roll_by_year()
    assert list(roll) == list(P.YEAR_GROUPS)
    assert all(v == [] for v in roll.values())


def test_roll_by_year_groups_on_roll_pupils_only():
    r = _pupil("R")
    a, b = _pupil("3"), _pupil("3")
    P.create_pupil({"first_name": "App", "last_name": "Licant", "year_group": "3"},
                   roll_status="applicant")
    roll = E.roll_by_year()
    assert [p.pupil_id for p in roll["R"]] == [r.pupil_id]
    assert sorted(p.pupil_id for p in roll["3"]) == sorted([a.pupil_id, b.pupil_id])
    assert roll["4"] == []


# ── moving one pupil ─────────────────────────────────────────────────

def test_move_pupil_bumps_the_class_name_with_the_year():
    p = _pupil("3", "3A", parent_name="Ann", medical_notes="asthma", send_status="yes")
    moved = E.move_pupil(p.pupil_id, "4")
    assert (moved.year_group, moved.class_name) == ("4", "4A")
    # every other field is carried over unchanged
    assert (moved.first_name, moved.date_of_birth, moved.parent_name,
            moved.medical_notes, moved.send_status) == (
        p.first_name, "2018-01-15", "Ann", "asthma", "yes")
    assert P.get_pupil(p.pupil_id).year_group == "4"


def test_move_pupil_explicit_class_wins():
    p = _pupil("3", "3A")
    assert E.move_pupil(p.pupil_id, "4", "Oak").class_name == "Oak"


def test_move_pupil_named_class_without_year_prefix_is_kept():
    p = _pupil("2", "Willow")
    assert E.move_pupil(p.pupil_id, "3").class_name == "Willow"


def test_move_pupil_no_class_stays_none():
    p = _pupil("2")
    assert E.move_pupil(p.pupil_id, "3").class_name is None


def test_move_pupil_same_year_keeps_class():
    p = _pupil("3", "3B")
    assert E.move_pupil(p.pupil_id, "3").class_name == "3B"


def test_move_pupil_validation():
    p = _pupil("3")
    with pytest.raises(E.ValidationError, match="Year group must be one of"):
        E.move_pupil(p.pupil_id, "7")
    with pytest.raises(E.ValidationError, match="No pupil with id P0000000"):
        E.move_pupil("P0000000", "4")
    assert P.get_pupil(p.pupil_id).year_group == "3"


def test_bump_class_helper():
    assert E._bump_class("3", "4", "3A") == "4A"
    assert E._bump_class("5", "6", "5") == "6"
    assert E._bump_class("3", "4", "Oak3") == "Oak3"
    assert E._bump_class("3", "3", "3A") == "3A"
    assert E._bump_class("3", "4", None) is None


# ── promotion ────────────────────────────────────────────────────────

def test_next_year_order():
    assert [E._next_year(y) for y in P.YEAR_GROUPS] == ["1", "2", "3", "4", "5", "6", None]
    with pytest.raises(E.ValidationError):
        E._next_year("7")


def test_promote_year_moves_every_pupil_up():
    a, b = _pupil("3", "3A"), _pupil("3", "3B")
    other = _pupil("4", "4A")
    s = E.promote_year("3")
    assert (s["from_year"], s["to_year"], s["count"], s["leavers"]) == ("3", "4", 2, [])
    assert sorted((p.pupil_id, p.class_name) for p in s["pupils"]) == sorted(
        [(a.pupil_id, "4A"), (b.pupil_id, "4B")])
    assert P.get_pupil(a.pupil_id).year_group == "4"
    assert P.get_pupil(other.pupil_id).year_group == "4"   # untouched
    assert E.roll_by_year()["3"] == []


def test_promote_reception_into_year_one():
    r = _pupil("R", "Robins")
    s = E.promote_year("R")
    assert (s["to_year"], s["count"]) == ("1", 1)
    got = P.get_pupil(r.pupil_id)
    assert (got.year_group, got.class_name) == ("1", "Robins")


def test_promote_dry_run_changes_nothing():
    a = _pupil("2", "2A")
    s = E.promote_year("2", dry_run=True)
    assert (s["to_year"], s["count"]) == ("3", 1)
    assert [p.pupil_id for p in s["pupils"]] == [a.pupil_id]
    assert P.get_pupil(a.pupil_id).year_group == "2"


def test_promote_year_six_lists_leavers_and_moves_nobody():
    y6 = _pupil("6", "6A")
    s = E.promote_year("6")
    assert (s["to_year"], s["count"], s["pupils"]) == (None, 0, [])
    assert [p.pupil_id for p in s["leavers"]] == [y6.pupil_id]
    assert P.get_pupil(y6.pupil_id).year_group == "6"


def test_promote_empty_year():
    s = E.promote_year("5")
    assert (s["count"], s["pupils"], s["leavers"]) == (0, [], [])


def test_promote_bad_year():
    with pytest.raises(E.ValidationError, match="Year group must be one of"):
        E.promote_year("Y3")


# ── leavers ──────────────────────────────────────────────────────────

def test_leavers_are_year_six_on_roll():
    assert E.leavers() == []
    a, b = _pupil("6"), _pupil("6")
    _pupil("5")
    assert sorted(p.pupil_id for p in E.leavers()) == sorted([a.pupil_id, b.pupil_id])
