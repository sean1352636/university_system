from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.special_education.app import routing
from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.modules import ehcp, provision, reports


def test_every_menu_key_has_a_page():
    custom = {"learners", "add_learner", "learner_profile", "chronology", "due_report",
              "register_report", "timeliness_report", "costs_report", "about"}
    for _label, key in routing.all_entries():
        assert key in r.REGISTRY or key in custom, key
    for _label, key in routing.PROFILE_TABS:
        assert key in r.REGISTRY


def test_dashboard_and_due(learner):
    r.save(ehcp.EHCPS, {"learner_id": learner,
                        "request_date": (date.today() - timedelta(weeks=9)).isoformat()})
    r.save(provision.PROVISION, {"learner_id": learner, "name": "PT",
                                 "provision_type": "Therapy", "hours_per_week": 1.5,
                                 "cost_per_week": 30})
    d = reports.dashboard()
    assert d["on_register"] == 1 and d["assessing"] == 1 and d["assessing_overdue"] == 1
    assert d["provision_hours"] == 1.5 and d["overdue"] >= 1
    assert reports.provision_costs()[0]["weekly"] == 30


def test_export_csv(learner, tmp_path):
    out = tmp_path / "x.csv"
    from education_system.systems.special_education.modules import learners
    assert reports.export_csv(learners.LEARNERS, out) == 1
    assert "Amy" in out.read_text()
