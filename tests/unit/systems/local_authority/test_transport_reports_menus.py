"""Home-to-school transport, the reports and the menu wiring."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.local_authority.app import routing
from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.modules import reports, transport as T


def _ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


@pytest.mark.parametrize(("age", "grounds", "miles", "nearest", "want"), [
    (6, "Distance", 2.5, True, "Eligible"),
    (9, "Distance", 2.5, True, "Not eligible"),
    (9, "Distance", 3.5, False, "Not eligible"),
    (9, "Low income", 2.5, True, "Eligible"),
    (12, "Low income", 5.0, False, "Eligible"),
    (12, "Low income", 7.0, False, "Not eligible"),
    (12, "Unsafe walking route", None, True, "Eligible"),
    (12, "Distance", None, True, "Pending"),
])
def test_assess(age, grounds, miles, nearest, want):
    assert T.assess(age, grounds, miles, nearest) == want


def test_agreed_needs_eligibility_and_a_free_seat(world, make_child):
    route = r.save(T.ROUTES, {"code": "r 1", "operator": "Cabs Ltd", "seats": 1,
                              "daily_cost": 50})
    assert r.get(T.ROUTES, route)["code"] == "R1"
    a = make_child("A", "X", school_id=world.high)
    b = make_child("B", "X", school_id=world.high)
    near = r.save(T.TRANSPORT, {"learner_id": a, "school_id": world.high,
                                "applied_on": _ago(5), "distance_miles": 1.0})
    assert r.get(T.TRANSPORT, near)["decision"] == "Not eligible"
    with pytest.raises(r.ValidationError, match="only when eligible"):
        r.save(T.TRANSPORT, {"status": "Agreed", "route_id": route}, record_id=near)
    with pytest.raises(r.ValidationError, match="free school meals"):
        r.save(T.TRANSPORT, {"learner_id": b, "school_id": world.high,
                             "applied_on": _ago(5), "grounds": "Low income",
                             "distance_miles": 4})
    far = r.save(T.TRANSPORT, {"learner_id": b, "school_id": world.high,
                               "applied_on": _ago(5), "distance_miles": 4.0,
                               "status": "Agreed", "route_id": route})
    assert r.get(T.TRANSPORT, far)["start_date"] == date.today().isoformat()
    r.save(T.TRANSPORT, {"decision": "Discretionary - agreed"}, record_id=near)
    with pytest.raises(r.ValidationError, match="full"):
        r.save(T.TRANSPORT, {"status": "Agreed", "route_id": route}, record_id=near)
    with pytest.raises(r.ValidationError, match="at least"):
        r.save(T.ROUTES, {"seats": 0}, record_id=route)
    with pytest.raises(r.ValidationError, match="still use"):
        r.save(T.ROUTES, {"status": "Ended"}, record_id=route)
    cost = T.route_costs()[0]
    assert (cost["children"], cost["annual"], cost["per_child"]) == (1, 9500, 9500)


def test_dashboard_and_due_list(world, make_child):
    from education_system.systems.local_authority.modules import welfare
    c = make_child(school_id=world.oak)
    r.save(welfare.CME, {"learner_id": c, "reported_on": _ago(30),
                         "source": welfare.CME_SOURCES[0]})
    d = reports.dashboard()
    assert d["children"] == 1 and d["cme_open"] == 1 and d["not_in_education"] == 1
    due = reports.due_items()
    assert any(i.area == "cme" and i.overdue for i in due)
    assert d["overdue"] >= 1


def test_export_csv(tmp_path, world):
    from education_system.systems.local_authority.modules import schools
    n = reports.export_csv(schools.SCHOOLS, tmp_path / "s.csv")
    assert n == 4 and "Oak Primary" in (tmp_path / "s.csv").read_text()


def test_every_menu_item_opens_something():
    from education_system.systems.local_authority.app import cli_main, gui_main
    from education_system.systems.local_authority.ui.gui import pages
    keys = [key for _, items in routing.CATEGORIES for _, key in items]
    assert len(keys) == len(set(keys))
    for key in keys:
        in_kit = key in r.REGISTRY
        assert in_kit or key in pages.CUSTOM or hasattr(gui_main.LAMainGUI, f"open_{key}"), key
        assert in_kit or hasattr(cli_main.LACLI, f"do_{key}"), key
