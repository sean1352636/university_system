"""The workspace: tasks, the calendar, workloads, search and the dashboards.

The read models are tested pure. The services are driven on the
conftest's throwaway database, mostly to prove that each one stays inside
the actor's scope — a task list or a search that leaked another
organisation's apprentice would be worse than having neither.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from education_system import paths
from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.workspace.items import (
    CalendarEvent,
    Task,
    Workload,
    count_by_urgency,
    group_by_day,
    matches,
    sort_tasks,
    to_ics,
    within,
)
from education_system.systems.apprenticeships.application.learning import (
    learning_plan_service,
    training_service,
)
from education_system.systems.apprenticeships.application.workspace import (
    calendar_service,
    reporting_service,
    search_service,
    task_service,
    workload_service,
)
from education_system.systems.apprenticeships.application.security.access import PermissionDenied

TODAY = date(2026, 9, 10)


def _in(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


# ═════════════════════════════════════════════════════════════════════
# Read models
# ═════════════════════════════════════════════════════════════════════

class TestTasks:
    @pytest.mark.parametrize(("due", "urgency"), [
        ("2026-09-09", "Overdue"),
        ("2026-09-10", "Due soon"),
        ("2026-09-17", "Due soon"),
        ("2026-09-18", "Upcoming"),
        (None, "No date"),
    ])
    def test_urgency_follows_the_due_date(self, due, urgency):
        assert Task("Reviews", "x", due=due).urgency(TODAY) == urgency

    def test_most_urgent_first_then_soonest(self):
        tasks = [
            Task("A", "undated"), Task("A", "later", due="2026-10-30"),
            Task("A", "late", due="2026-09-01"), Task("A", "soon", due="2026-09-12"),
        ]
        assert [t.title for t in sort_tasks(tasks, TODAY)] == ["late", "soon", "later", "undated"]
        assert count_by_urgency(tasks, TODAY) == {
            "Overdue": 1, "Due soon": 1, "Upcoming": 1, "No date": 1,
        }


class TestCalendarModel:
    events = [
        CalendarEvent(day="2026-09-12", title="Review", kind="Review"),
        CalendarEvent(day="2026-09-11", time="14:00", title="Workshop", kind="Training"),
        CalendarEvent(day="2026-09-11", time="09:30", title="Induction", kind="Training"),
        CalendarEvent(day="2026-10-30", title="Too late", kind="Target"),
    ]

    def test_events_in_range_in_the_order_they_happen(self):
        kept = within(self.events, TODAY, date(2026, 9, 30))
        assert [e.title for e in kept] == ["Induction", "Workshop", "Review"]
        assert [(day, len(rows)) for day, rows in group_by_day(kept)] == [
            ("2026-09-11", 2), ("2026-09-12", 1),
        ]

    def test_ics_is_importable_shape(self):
        text = to_ics(
            [
                CalendarEvent(day="2026-09-11", title="All day, with; punctuation",
                              kind="Target", uid="t-1"),
                CalendarEvent(day="2026-09-12", time="10:00", title="Timed", kind="Review",
                              detail="x" * 200, uid="r-1"),
            ],
            name="Diary", stamp=datetime(2026, 9, 10, 8, 0, 0),
        )
        assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
        assert "DTSTART;VALUE=DATE:20260911\r\nDTEND;VALUE=DATE:20260912" in text
        assert "DTSTART:20260912T100000" in text
        assert "SUMMARY:All day\\, with\\; punctuation" in text
        assert "UID:t-1@apprenticeships" in text
        assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))


class TestWorkloadAndSearchModels:
    def test_workload_rag_uses_caseload_and_open_items(self):
        assert Workload(1, "Sam").rag == "Green"
        assert Workload(1, "Sam", evidence_to_assess=config.WORKLOAD_ITEMS_WARNING).rag == "Amber"
        assert Workload(1, "Sam", active=config.CASELOAD_MAXIMUM).rag == "Red"
        assert Workload(1, "Sam", other={"Assignments": 3}, hours_to_approve=2).open_items == 5

    def test_matches_ignores_case_and_blanks(self):
        assert matches("bell", None, "Jo Bell")
        assert not matches("bell", None, "")


# ═════════════════════════════════════════════════════════════════════
# Through the services
# ═════════════════════════════════════════════════════════════════════

class TestTaskList:
    def test_an_objective_due_soon_reaches_the_apprentice_and_their_tutor(self, cohort, admin):
        learning_plan_service.add_objective(admin, cohort["apprentice_id"], {
            "title": "Wire a consumer unit", "target_date": _in(3),
        })
        for actor in (cohort["learner"], cohort["tutor"]):
            titles = [t.title for t in task_service.my_tasks(actor)]
            assert "Objective due: Wire a consumer unit" in titles

    def test_draft_hours_prompt_the_apprentice_to_submit(self, cohort):
        training_service.log_hours(cohort["learner"], {
            "activity_date": date.today().isoformat(), "hours": 3,
            "activity_type": "Online learning", "description": "Module 2",
        })
        titles = [t.title for t in task_service.my_tasks(cohort["learner"])]
        assert "Submit 1 draft entry" in titles

    def test_another_employer_sees_none_of_it(self, cohort, admin):
        learning_plan_service.add_objective(admin, cohort["apprentice_id"], {
            "title": "Wire a consumer unit", "target_date": _in(3),
        })
        assert task_service.my_tasks(cohort["outsider"]) == []

    def test_the_end_point_assessor_gets_a_list_without_provider_work(self, cohort, assessor):
        assert all(t.category in ("Gateway", "End-point assessment")
                   for t in task_service.my_tasks(assessor))


class TestCalendar:
    def _session(self, admin, cohort, **extra):
        return training_service.create_session(admin, {
            "title": "Networking workshop", "session_date": _in(2), "start_time": "10:00",
            **extra,
        })

    def test_the_tutor_sees_what_they_deliver(self, cohort, admin):
        self._session(admin, cohort, trainer_id=cohort["tutor_id"])
        diary = calendar_service.events(
            cohort["tutor"], date_from=date.today(), date_to=date.today() + timedelta(days=7)
        )
        assert [e.title for e in diary if e.kind == "Training"] == ["Networking workshop"]

    def test_apprentice_and_employer_see_the_programme_timetable(self, cohort, admin):
        self._session(admin, cohort, programme_id=cohort["programme"].programme_id)
        window = {"date_from": date.today(), "date_to": date.today() + timedelta(days=7)}
        for actor in (cohort["learner"], cohort["employer_actor"]):
            assert "Networking workshop" in [
                e.title for e in calendar_service.events(actor, **window)
            ]
        assert calendar_service.events(cohort["outsider"], **window) == []

    def test_a_backwards_range_is_refused(self, cohort):
        with pytest.raises(ValidationError, match="before the start"):
            calendar_service.events(
                cohort["learner"], date_from=date.today(),
                date_to=date.today() - timedelta(days=1),
            )

    def test_export_writes_an_ics_file(self, cohort, admin, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "APPRENTICESHIPS_EXPORTS_DIR", tmp_path)
        self._session(admin, cohort, programme_id=cohort["programme"].programme_id)
        target = calendar_service.export_ics(
            cohort["learner"], date_from=date.today(),
            date_to=date.today() + timedelta(days=7),
        )
        assert target.parent == tmp_path
        assert "SUMMARY:Networking workshop" in target.read_text(encoding="utf-8")


class TestSearch:
    def test_finds_an_apprentice_by_name(self, cohort, admin):
        results = search_service.search(admin, "bell")
        assert ("Apprentice", "Jo Bell") in [(r.kind, r.title) for r in results]

    def test_another_employer_finds_nobody(self, cohort):
        assert not [r for r in search_service.search(cohort["outsider"], "bell")
                    if r.kind == "Apprentice"]

    def test_a_query_must_be_long_enough(self, cohort, admin):
        with pytest.raises(ValidationError, match="at least"):
            search_service.search(admin, "b")


class TestWorkload:
    def test_admin_sees_every_tutor(self, cohort, admin):
        loads = {w.name: w for w in workload_service.list_workloads(admin)}
        assert loads["Sam Okafor"].active == 1

    def test_a_tutor_sees_only_themselves(self, cohort):
        assert [w.name for w in workload_service.list_workloads(cohort["tutor"])] == ["Sam Okafor"]

    def test_apprentices_have_no_workload_view(self, cohort):
        with pytest.raises(PermissionDenied):
            workload_service.list_workloads(cohort["learner"])


class TestDashboardHeadlines:
    def test_each_dashboard_counts_tasks(self, cohort, admin):
        for data in (
            reporting_service.staff_dashboard(cohort["tutor"]),
            reporting_service.apprentice_dashboard(cohort["learner"]),
            reporting_service.employer_dashboard(cohort["employer_actor"]),
            reporting_service.admin_dashboard(admin),
        ):
            assert isinstance(dict(data["kpis"])["My tasks"], int)

    def test_the_apprentice_sees_next_review_and_epa(self, cohort):
        kpis = dict(reporting_service.apprentice_dashboard(cohort["learner"])["kpis"])
        assert kpis["EPA"] == "Not booked"
        assert "Next review" in kpis

    def test_the_employer_sees_compliance_and_breaks(self, cohort):
        kpis = dict(reporting_service.employer_dashboard(cohort["employer_actor"])["kpis"])
        assert kpis["On a break"] == 0
        assert kpis["Off-the-job compliance"].endswith("%")
