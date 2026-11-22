from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.adult_education.app import cli_main, routing
from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.modules import enrolments, learners, reports


def test_every_menu_key_has_a_page_and_a_cli_entry():
    gui_custom = {"learners", "add_learner", "learner_profile", "chronology", "take_register",
                  "due_report", "enrolment_report", "attendance_report", "funding_report",
                  "fees_report", "achievement_report", "destinations_report", "about"}
    for _label, key in routing.all_entries():
        assert key in r.REGISTRY or key in gui_custom, key
        assert key in r.REGISTRY or hasattr(cli_main.AdultCLI, f"do_{key}"), key
    for _label, key in routing.PROFILE_TABS:
        assert key in r.REGISTRY


def test_dashboard_figures(learner, make_class):
    cl = make_class(capacity=4)
    en = r.save(enrolments.ENROLMENTS, {"learner_id": learner, "class_id": cl, "fee_due": 120})
    r.save(enrolments.PAYMENTS, {"enrolment_id": en, "amount": 20})
    enrolments.save_register(cl, date.today() - timedelta(days=7), {learner: "Present"},
                             actor="t")
    d = reports.dashboard()
    assert d["active_learners"] == 1 and d["classes"] == 1
    assert (d["places"], d["enrolled"], d["waiting"]) == (4, 1, 0)
    assert d["attendance"] == 100 and d["owed"] == 100 and d["owed_count"] == 1
    assert reports.enrolment_summary()[0]["enrolled"] == 1
    assert reports.outstanding()[0]["balance"] == 100


def test_export_csv(learner, tmp_path):
    out = tmp_path / "x.csv"
    assert reports.export_csv(learners.LEARNERS, out) == 1
    assert "Bloggs" in out.read_text()
