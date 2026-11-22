from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.alternative_provision.app import cli_main, routing
from education_system.systems.alternative_provision.core import dates
from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.modules import (
    attendance,
    learners,
    reports,
    safeguarding,
)

TODAY = date.today()



def test_every_menu_key_has_a_page_and_a_cli_entry():
    gui_custom = {"learners", "add_learner", "learner_profile", "chronology", "take_register",
                  "due_report", "roll_report", "attendance_report", "behaviour_report",
                  "costs_report", "outcomes_report", "about"}
    for _label, key in routing.all_entries():
        assert key in r.REGISTRY or key in gui_custom, key
        assert key in r.REGISTRY or hasattr(cli_main.APCLI, f"do_{key}"), key
    for _label, key in routing.PROFILE_TABS:
        assert key in r.REGISTRY


def test_dashboard_and_due(pupil, placement):  # noqa: ARG001
    day = dates.next_weekday(TODAY - timedelta(days=6))
    attendance.save_register(day, "AM", {pupil: ("Unauthorised absence (O)", "")}, actor="t")
    r.save(safeguarding.CONCERNS, {"learner_id": pupil, "raised_by": "x",
                                   "category": "Neglect", "details": "x"})
    d = reports.dashboard()
    assert (d["on_roll"], d["placements"], d["part_time"]) == (1, 1, 1)
    assert d["attendance"] == 0 and d["persistent_absence"] == 1 and d["concerns_open"] == 1
    whats = {i.what for i in d["due"]}
    assert {"DSL review of a concern", "Placement review", "Part-time timetable review"} <= whats
    assert reports.placement_costs()[0]["weekly"] == 600


def test_export_csv(pupil, tmp_path):  # noqa: ARG001
    out = tmp_path / "x.csv"
    assert reports.export_csv(learners.LEARNERS, out) == 1
    assert "Jones" in out.read_text()
