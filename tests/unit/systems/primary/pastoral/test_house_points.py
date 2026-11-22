"""House points (systems.primary.domain.pastoral.house_points.house_points)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.house_points import house_points as HP

TODAY = dt.date.today().isoformat()


def _pupil(first="Ada", last="Lovelace", year="4"):
    return P.create_pupil({"first_name": first, "last_name": last,
                           "year_group": year, "date_of_birth": "2017-05-01"})


def _house(name="Falcon", **extra):
    return HP.create_house({"name": name, **extra})


def _award(house, points=5, **extra):
    return HP.award_points({"house_id": house.house_id, "points": points,
                            "awarded_on": "2026-10-01", **extra})


# ── houses ───────────────────────────────────────────────────────────

def test_create_house_stores_values():
    h = _house(" Falcon ", colour="Red", motto="Fly high", notes="n")
    assert h.house_id > 0
    assert h.name == "Falcon"
    assert h.colour == "Red"
    assert h.motto == "Fly high"
    assert h.notes == "n"
    assert h.is_active is True
    assert HP.get_house(h.house_id) == h
    assert HP.get_house_by_name("  Falcon ") == h


def test_create_house_inactive_and_blank_optionals():
    h = _house("Owl", is_active=False, colour="  ")
    assert h.is_active is False
    assert h.colour is None


def test_house_name_required():
    with pytest.raises(HP.ValidationError, match="House name is required"):
        HP.create_house({"name": "  "})


def test_house_name_max_40():
    assert len(_house("x" * 40).name) == 40
    with pytest.raises(HP.ValidationError, match="40 characters"):
        _house("y" * 41)


def test_duplicate_house_name_refused():
    _house("Dragon")
    with pytest.raises(HP.ValidationError, match="already exists"):
        _house("Dragon")


def test_get_missing_house():
    assert HP.get_house(99) is None
    assert HP.get_house_by_name("Nobody") is None


def test_list_houses_sorted_case_insensitive_and_active_filter():
    _house("owl")
    _house("Falcon")
    _house("dragon", is_active=False)
    assert [h.name for h in HP.list_houses()] == ["dragon", "Falcon", "owl"]
    assert [h.name for h in HP.list_houses(active_only=True)] == ["Falcon", "owl"]


def test_list_houses_empty():
    assert HP.list_houses() == []


def test_update_house_merges():
    h = _house("Falcon", colour="Red", motto="M")
    up = HP.update_house(h.house_id, {"colour": "Blue"})
    assert up.colour == "Blue"
    assert up.motto == "M"
    assert up.name == "Falcon"
    assert HP.update_house(h.house_id, {"name": "Hawk"}).name == "Hawk"


def test_update_house_refusals():
    a = _house("A")
    _house("B")
    with pytest.raises(HP.ValidationError, match="already exists"):
        HP.update_house(a.house_id, {"name": "B"})
    with pytest.raises(HP.ValidationError, match="No house #77"):
        HP.update_house(77, {"name": "C"})
    # renaming to its own name is fine
    assert HP.update_house(a.house_id, {"name": "A"}).name == "A"


def test_toggle_house_active():
    h = _house()
    assert HP.toggle_house_active(h.house_id).is_active is False
    assert HP.toggle_house_active(h.house_id).is_active is True
    with pytest.raises(HP.ValidationError, match="No house #5"):
        HP.toggle_house_active(5)


def test_delete_house_without_awards():
    h = _house()
    assert HP.delete_house(h.house_id) is True
    assert HP.get_house(h.house_id) is None
    assert HP.delete_house(h.house_id) is False


def test_delete_house_with_awards_refused():
    h = _house()
    _award(h)
    _award(h)
    with pytest.raises(HP.ValidationError, match="has 2 award\\(s\\)"):
        HP.delete_house(h.house_id)
    assert HP.get_house(h.house_id) is not None


# ── awards ───────────────────────────────────────────────────────────

def test_award_points_house_level():
    h = _house()
    a = _award(h, 10, reason=" Tidy room ", awarded_by="Ms Smith", notes="n")
    assert a.award_id > 0
    assert a.house_id == h.house_id
    assert a.pupil_id is None
    assert a.points == 10
    assert a.reason == "Tidy room"
    assert a.awarded_by == "Ms Smith"
    assert a.awarded_on == "2026-10-01"
    assert HP.get_award(a.award_id) == a


def test_award_points_to_pupil_and_default_date():
    h = _house()
    p = _pupil()
    a = HP.award_points({"house_id": str(h.house_id), "pupil_id": p.pupil_id,
                         "points": "3"})
    assert a.pupil_id == p.pupil_id
    assert a.points == 3
    # date('now') in SQLite is the UTC date; either side of midnight is fine
    assert a.awarded_on in {TODAY, dt.datetime.now(dt.timezone.utc).date().isoformat()}


def test_deduction_allowed():
    assert _award(_house(), -4).points == -4


def test_points_bounds_inclusive():
    h = _house()
    assert _award(h, HP.POINTS_MAX).points == 50
    assert _award(h, HP.POINTS_MIN).points == -50


@pytest.mark.parametrize("data,msg", [
    ({"points": 5}, "House is required"),
    ({"house_id": "abc", "points": 5}, "House ID must be an integer"),
    ({"house_id": 1}, "Points are required"),
    ({"house_id": 1, "points": "lots"}, "Points must be an integer"),
    ({"house_id": 1, "points": 0}, "Points cannot be zero"),
    ({"house_id": 1, "points": 51}, "between -50 and 50"),
    ({"house_id": 1, "points": -51}, "between -50 and 50"),
    ({"house_id": 1, "points": 1, "awarded_on": "1/10/2026"}, "Awarded-on date"),
])
def test_award_validation(data, msg):
    _house()
    with pytest.raises(HP.ValidationError, match=msg):
        HP.award_points(data)


def test_award_unknown_house_refused():
    with pytest.raises(HP.ValidationError, match="No house #9"):
        HP.award_points({"house_id": 9, "points": 1})


def test_award_unknown_pupil_refused():
    h = _house()
    with pytest.raises(HP.ValidationError, match="No pupil with id GHOST"):
        _award(h, pupil_id="GHOST")


def test_get_award_missing():
    assert HP.get_award(1) is None


def test_update_award_merges_and_keeps_date():
    h1, h2 = _house("A"), _house("B")
    p = _pupil()
    a = _award(h1, 5, pupil_id=p.pupil_id, reason="r")
    up = HP.update_award(a.award_id, {"house_id": h2.house_id, "points": 8,
                                       "awarded_on": ""})
    assert up.house_id == h2.house_id
    assert up.points == 8
    assert up.pupil_id == p.pupil_id
    assert up.reason == "r"
    assert up.awarded_on == "2026-10-01"
    cleared = HP.update_award(a.award_id, {"pupil_id": ""})
    assert cleared.pupil_id is None


def test_update_award_refusals():
    h = _house()
    a = _award(h)
    with pytest.raises(HP.ValidationError, match="No award #50"):
        HP.update_award(50, {"points": 1})
    with pytest.raises(HP.ValidationError, match="No house #99"):
        HP.update_award(a.award_id, {"house_id": 99})
    with pytest.raises(HP.ValidationError, match="No pupil with id X1"):
        HP.update_award(a.award_id, {"pupil_id": "X1"})
    with pytest.raises(HP.ValidationError, match="Points cannot be zero"):
        HP.update_award(a.award_id, {"points": 0})


def test_delete_award():
    a = _award(_house())
    assert HP.delete_award(a.award_id) is True
    assert HP.get_award(a.award_id) is None
    assert HP.delete_award(a.award_id) is False


# ── list_awards ──────────────────────────────────────────────────────

def test_list_awards_empty():
    assert HP.list_awards() == []


def test_list_awards_order_tuples_and_filters():
    h1, h2 = _house("A"), _house("B")
    p = _pupil()
    a1 = _award(h1, 1, awarded_on="2026-09-01", awarded_by="Mr Brown")
    a2 = _award(h2, 2, awarded_on="2026-10-01", pupil_id=p.pupil_id)
    a3 = _award(h1, 3, awarded_on="2026-10-01", awarded_by="Ms Brownlow")

    rows = HP.list_awards()
    assert [a.award_id for a, _, _ in rows] == [a3.award_id, a2.award_id, a1.award_id]
    award, house, pupil = rows[1]
    assert house.name == "B"
    assert pupil.pupil_id == p.pupil_id
    assert rows[0][2] is None

    def ids(**kw):
        return [a.award_id for a, _, _ in HP.list_awards(**kw)]

    assert ids(house_id=h1.house_id) == [a3.award_id, a1.award_id]
    assert ids(pupil_id=p.pupil_id) == [a2.award_id]
    assert ids(awarded_by="brown") == [a3.award_id, a1.award_id]
    assert ids(from_date="2026-09-15") == [a3.award_id, a2.award_id]
    assert ids(to_date="2026-09-30") == [a1.award_id]
    assert ids(limit=2) == [a3.award_id, a2.award_id]
    assert len(ids(limit=0)) == 3


def test_list_awards_bad_dates():
    with pytest.raises(HP.ValidationError, match="From-date"):
        HP.list_awards(from_date="2026/1/1")
    with pytest.raises(HP.ValidationError, match="To-date"):
        HP.list_awards(to_date="yesterday")


# ── totals ───────────────────────────────────────────────────────────

def test_house_totals_include_every_house_sorted_desc():
    a, b, c = _house("Alpha"), _house("Bravo"), _house("Charlie", is_active=False)
    _award(a, 10, awarded_on="2026-09-01")
    _award(a, -3, awarded_on="2026-10-01")       # a = 7
    _award(b, 20, awarded_on="2026-10-02")       # b = 20
    totals = [(h.name, t) for h, t in HP.house_totals()]
    assert totals == [("Bravo", 20), ("Alpha", 7), ("Charlie", 0)]
    assert [(h.name, t) for h, t in HP.house_totals(from_date="2026-10-01")] == [
        ("Bravo", 20), ("Charlie", 0), ("Alpha", -3)]
    assert [(h.name, t) for h, t in HP.house_totals(to_date="2026-09-30")] == [
        ("Alpha", 10), ("Bravo", 0), ("Charlie", 0)]
    assert c.house_id in {h.house_id for h, _ in HP.house_totals()}


def test_house_totals_bad_dates():
    with pytest.raises(HP.ValidationError, match="From-date"):
        HP.house_totals(from_date="x")
    with pytest.raises(HP.ValidationError, match="To-date"):
        HP.house_totals(to_date="x")


def test_house_totals_empty():
    assert HP.house_totals() == []


def test_pupil_totals_and_pupil_total():
    a, b = _house("A"), _house("B")
    p1, p2, p3 = _pupil("One", "P"), _pupil("Two", "P"), _pupil("Three", "P")
    _award(a, 5, pupil_id=p1.pupil_id)
    _award(a, 5, pupil_id=p1.pupil_id)            # p1 = 10, 2 awards
    _award(b, 10, pupil_id=p2.pupil_id)           # p2 = 10, 1 award
    _award(a, 3, pupil_id=p3.pupil_id)
    _award(b, -1, pupil_id=p3.pupil_id)           # p3 = 2 over both houses
    _award(a, 40)                                 # house-only: not a pupil row
    assert HP.pupil_totals() == [(p1.pupil_id, 10, 2), (p2.pupil_id, 10, 1),
                                 (p3.pupil_id, 2, 2)]
    assert HP.pupil_totals(house_id=b.house_id) == [(p2.pupil_id, 10, 1),
                                                    (p3.pupil_id, -1, 1)]
    assert HP.pupil_totals(limit=1) == [(p1.pupil_id, 10, 2)]
    assert HP.pupil_total(p3.pupil_id) == 2
    assert HP.pupil_total(_pupil("No", "Points").pupil_id) == 0


def test_pupil_total_unknown_pupil():
    with pytest.raises(HP.ValidationError, match="No pupil with id NOPE"):
        HP.pupil_total("NOPE")


def test_pupil_totals_empty():
    assert HP.pupil_totals() == []
