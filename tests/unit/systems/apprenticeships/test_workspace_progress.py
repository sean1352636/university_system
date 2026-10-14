"""Review actions and assignments reaching the workspace.

An action lands on whoever owns it; an assignment moves from the
apprentice's list to the marker's once it is handed in.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.apprenticeships.services import (
    assignment_service,
    calendar_service,
    reporting_service,
    review_service,
    search_service,
    task_service,
    workload_service,
)


def _days(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


def _titles(actor) -> list[str]:
    return [t.title for t in task_service.my_tasks(actor)]


def _set(cohort):
    return assignment_service.set_assignment(cohort["tutor"], cohort["apprentice_id"], {
        "title": "Network design report", "assignment_type": "Written assignment",
        "ksb_codes": "K1, S1", "due_date": _days(5),
    })


def _action(cohort, **overrides):
    review = review_service.schedule_review(
        cohort["tutor"], cohort["apprentice_id"], scheduled_date=_days(20)
    )
    payload = {"description": "Finish the network diagram", "due_date": _days(5)}
    payload.update(overrides)
    return review_service.add_target(cohort["tutor"], review.review_id, payload)


class TestAssignments:
    def test_work_moves_from_the_apprentice_to_the_marker(self, cohort):
        _set(cohort)
        assert "Submit: Network design report" in _titles(cohort["learner"])
        assert "Mark: Network design report" not in _titles(cohort["tutor"])

        item = assignment_service.list_assignments(cohort["learner"])[0]
        assignment_service.submit(cohort["learner"], item.assignment_id, body="My report")
        assert "Submit: Network design report" not in _titles(cohort["learner"])
        assert "Mark: Network design report" in _titles(cohort["tutor"])

    def test_the_due_date_is_in_the_apprentices_diary(self, cohort):
        _set(cohort)
        diary = calendar_service.events(
            cohort["learner"], date_from=date.today(), date_to=date.today() + timedelta(days=7)
        )
        assert "Assignment due: Network design report" in [e.title for e in diary]

    def test_submitted_work_counts_towards_the_tutors_workload(self, cohort):
        item = _set(cohort)
        assignment_service.submit(cohort["learner"], item.assignment_id, body="My report")
        (load,) = workload_service.list_workloads(cohort["tutor"])
        assert load.other.get("Assignments to mark") == 1

    def test_found_by_search_within_scope(self, cohort):
        _set(cohort)
        assert "Network design report" in [
            r.title for r in search_service.search(cohort["tutor"], "network design")
        ]
        assert not search_service.search(cohort["outsider"], "network design")


class TestActions:
    def test_an_action_lands_on_its_owner(self, cohort):
        _action(cohort, owner="Employer", description="Release Jo on Fridays")
        assert "Action: Release Jo on Fridays" in _titles(cohort["employer_actor"])
        assert "Action: Release Jo on Fridays" not in _titles(cohort["learner"])

    def test_the_dashboards_count_outstanding_actions(self, cohort):
        _action(cohort)
        apprentice = dict(reporting_service.apprentice_dashboard(cohort["learner"])["kpis"])
        staff = dict(reporting_service.staff_dashboard(cohort["tutor"])["kpis"])
        assert apprentice["Outstanding actions"] == 1
        assert staff["Overdue actions"] == 0
