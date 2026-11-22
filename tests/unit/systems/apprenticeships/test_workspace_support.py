"""Learner-support work reaching the workspace: tasks, calendar, search.

Support reviews and welfare concerns are provider work, and welfare is
restricted, so the point of these tests is as much who does *not* see
them as who does.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.application.assessments import qualification_service
from education_system.systems.apprenticeships.application.support import (
    support_service,
    welfare_service,
)
from education_system.systems.apprenticeships.application.workspace import (
    calendar_service,
    reporting_service,
    search_service,
    task_service,
    workload_service,
)


def _in(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _categories(actor) -> set[str]:
    return {t.category for t in task_service.my_tasks(actor)}


def _support(admin, cohort):
    return support_service.add_arrangement(admin, cohort["apprentice_id"], {
        "need_category": config.SUPPORT_NEED_CATEGORIES[0],
        "adjustment": "Extra time in written assessments",
        "review_date": _in(5),
    })


def _concern(cohort):
    return welfare_service.raise_concern(cohort["tutor"], cohort["apprentice_id"], {
        "category": config.WELFARE_CATEGORIES[0],
        "severity": "High",
        "description": "Disclosed money worries at review",
    })


class TestSupportReviews:
    def test_due_reviews_reach_the_tutor_and_their_diary(self, cohort, admin):
        _support(admin, cohort)
        assert "Support" in _categories(cohort["tutor"])
        diary = calendar_service.events(
            cohort["tutor"], date_from=date.today(), date_to=date.today() + timedelta(days=14)
        )
        assert "Support" in {e.kind for e in diary}

    def test_they_stay_off_the_apprentice_and_employer_lists(self, cohort, admin):
        _support(admin, cohort)
        for actor in (cohort["learner"], cohort["employer_actor"]):
            assert "Support" not in _categories(actor)


class TestWelfare:
    def test_an_open_concern_reaches_the_tutor_without_its_description(self, cohort):
        _concern(cohort)
        welfare = [t for t in task_service.my_tasks(cohort["tutor"]) if t.category == "Welfare"]
        assert len(welfare) == 1
        assert "money" not in welfare[0].title + welfare[0].detail

    def test_nobody_outside_the_provider_hears_of_it(self, cohort, assessor):
        _concern(cohort)
        for actor in (cohort["learner"], cohort["employer_actor"], assessor):
            assert "Welfare" not in _categories(actor)

    def test_it_counts_towards_the_tutors_workload(self, cohort):
        _concern(cohort)
        (load,) = workload_service.list_workloads(cohort["tutor"])
        assert load.other.get("Welfare") == 1

    def test_the_staff_dashboard_counts_who_is_at_risk(self, cohort):
        _concern(cohort)
        kpis = dict(reporting_service.staff_dashboard(cohort["tutor"])["kpis"])
        assert isinstance(kpis["At risk"], int) and kpis["At risk"] >= 1


class TestQualificationSearch:
    def test_found_by_title_within_scope(self, cohort, admin):
        qualification_service.add_qualification(admin, cohort["apprentice_id"], {
            "title": "GCSE Mathematics", "status": config.QUALIFICATION_STATUSES[0],
        })
        assert "GCSE Mathematics" in [
            r.title for r in search_service.search(cohort["learner"], "mathem")
        ]
        assert not [r for r in search_service.search(cohort["outsider"], "mathem")
                    if r.kind == "Qualification"]
