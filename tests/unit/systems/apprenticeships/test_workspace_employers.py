"""Employer follow-ups, commitments and admissions reaching the workspace."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.employers import employer_contact_service
from education_system.systems.apprenticeships.application.programmes import programme_service
from education_system.systems.apprenticeships.application.workspace import (
    calendar_service,
    reporting_service,
    task_service,
)


def _in(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _titles(actor) -> list[str]:
    return [t.title for t in task_service.my_tasks(actor) if t.category == "Employers"]


class TestEmployerWork:
    def test_a_promised_follow_up_reaches_the_tutor(self, cohort):
        employer_id = cohort["employer"].employer_id
        employer_contact_service.log_contact(cohort["tutor"], employer_id, {
            "contacted_on": date.today().isoformat(), "channel": "Phone",
            "summary": "Agreed Friday release", "follow_up_date": _in(3),
        })
        assert "Follow up with Acme Ltd" in _titles(cohort["tutor"])
        diary = calendar_service.events(
            cohort["tutor"], date_from=date.today(), date_to=date.today() + timedelta(days=7)
        )
        assert "Follow up: Acme Ltd" in [e.title for e in diary]

    def test_a_commitment_due_reaches_the_employer_who_made_it(self, cohort, admin):
        employer_contact_service.add_commitment(admin, cohort["employer"].employer_id, {
            "commitment": "Release Jo for Friday workshops",
            "category": "Release for off-the-job training", "due_date": _in(5),
        })
        assert "Commitment: Release Jo for Friday workshops" in _titles(cohort["employer_actor"])
        assert not _titles(cohort["outsider"])

    def test_the_admin_dashboard_rates_employers(self, cohort, admin):
        kpis = dict(reporting_service.admin_dashboard(admin)["kpis"])
        assert isinstance(kpis["High-risk employers"], int)


class TestProgrammeVersions:
    def test_a_superseded_version_takes_no_new_starts(self, cohort, admin):
        programme = cohort["programme"]
        programme_service.new_version(admin, programme.programme_id)
        newcomer = apprentice_service.create_apprentice(admin, {
            "given_name": "Ali", "family_name": "Khan", "date_of_birth": "2004-01-01",
        })
        with pytest.raises(ValidationError, match="only an Active programme"):
            apprentice_service.start_programme(
                admin, newcomer.apprentice_id, start_date=date.today().isoformat(),
                programme_id=programme.programme_id,
            )
