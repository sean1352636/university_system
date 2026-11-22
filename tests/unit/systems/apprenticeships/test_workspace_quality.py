"""Complaints, appeals and surveys reaching the workspace.

A complaint is the handler's work, not the complainant's, and a survey
is the respondent's; the tests pin down who each one lands on.
"""

from __future__ import annotations

from education_system.systems.apprenticeships.application.quality import (
    complaint_service,
    survey_service,
)
from education_system.systems.apprenticeships.application.workspace import (
    reporting_service,
    search_service,
    task_service,
)


def _titles(actor) -> list[str]:
    return [t.title for t in task_service.my_tasks(actor)]


def _raise(actor):
    return complaint_service.raise_complaint(actor, {
        "category": "Assessment", "subject": "Late marking",
        "description": "My unit 3 work has waited six weeks for marking.",
    })


class TestComplaints:
    def test_a_new_complaint_asks_the_handler_to_acknowledge_it(self, cohort, admin):
        complaint = _raise(cohort["learner"])
        assert f"Acknowledge complaint {complaint.reference}" in _titles(admin)
        assert not [t for t in _titles(cohort["learner"]) if complaint.reference in t]

    def test_the_admin_dashboard_counts_it(self, cohort, admin):
        _raise(cohort["learner"])
        assert dict(reporting_service.admin_dashboard(admin)["kpis"])["Open complaints"] == 1

    def test_the_complainant_can_find_it_and_nobody_else_can(self, cohort):
        complaint = _raise(cohort["learner"])
        assert complaint.reference in " ".join(
            r.title for r in search_service.search(cohort["learner"], complaint.reference)
        )
        assert not [r for r in search_service.search(cohort["outsider"], complaint.reference)
                    if r.kind == "Complaint"]


class TestSurveys:
    def test_an_open_survey_is_a_task_until_answered(self, cohort, admin):
        survey = survey_service.create_survey(admin, {"title": "Autumn check-in",
                                                      "kind": "Training feedback"})
        survey = survey_service.open_survey(admin, survey.survey_id)
        assert "Complete survey: Autumn check-in" in _titles(cohort["learner"])

        survey_service.respond(
            cohort["learner"], survey.survey_id, {q: 4 for q in survey.questions}
        )
        assert "Complete survey: Autumn check-in" not in _titles(cohort["learner"])
