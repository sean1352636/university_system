"""Qualifications: prior, in progress, achieved — and recognised prior learning.

The date and prior-learning rules are tested pure. Recording and
reading run through the service on the conftest's throwaway database,
where the scope rules — own record, own apprentices, own caseload — are
what matters.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.learner_support import (
    qualifications as rules,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    compliance_repository,
)
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.assessments import qualification_service
from education_system.systems.apprenticeships.application.security.access import Actor, PermissionDenied

TODAY = date(2026, 9, 10)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestDates:
    def test_an_achievement_is_stamped_today_when_undated(self):
        assert rules.settle_dates("Achieved", None, None, TODAY) == "2026-09-10"

    def test_a_qualification_in_progress_carries_no_achieved_date(self):
        assert rules.settle_dates("In progress", "2026-01-01", "2026-05-01", TODAY) is None

    def test_a_prior_qualification_keeps_whatever_date_it_has(self):
        assert rules.settle_dates("Held (prior)", None, "2019-08-20", TODAY) == "2019-08-20"
        assert rules.settle_dates("Held (prior)", None, None, TODAY) is None

    def test_nothing_is_achieved_in_the_future(self):
        with pytest.raises(ValidationError, match="future"):
            rules.settle_dates("Achieved", None, "2026-09-11", TODAY)

    def test_nothing_is_achieved_before_it_started(self):
        with pytest.raises(ValidationError, match="before it was started"):
            rules.settle_dates("Achieved", "2026-03-01", "2026-02-01", TODAY)


class TestPriorLearning:
    def test_only_a_prior_qualification_can_count(self):
        rules.check_prior_learning("Held (prior)", True)
        rules.check_prior_learning("In progress", False)
        for status in ("In progress", "Achieved"):
            with pytest.raises(ValidationError, match="before the programme"):
                rules.check_prior_learning(status, True)


class TestVocabulary:
    def test_status_and_level_are_matched_ignoring_case(self):
        assert rules.validate_status("held (PRIOR)") == "Held (prior)"
        assert rules.validate_level("level 3") == "Level 3"
        assert rules.validate_level("") is None
        with pytest.raises(ValidationError, match="must be one of"):
            rules.validate_status("Pending")
        with pytest.raises(ValidationError, match="must be one of"):
            rules.validate_level("Level 9")


# ═════════════════════════════════════════════════════════════════════
# Through the service
# ═════════════════════════════════════════════════════════════════════

def _gcse(actor, cohort, **overrides):
    payload = {
        "title": "GCSE Mathematics", "level": "Level 2", "awarding_body": "AQA",
        "status": "Held (prior)", "grade": "5", "achieved_date": "2019-08-22",
        "relevant_prior_learning": True,
    }
    payload.update(overrides)
    return qualification_service.add_qualification(actor, cohort["apprentice_id"], payload)


class TestRecording:
    def test_a_tutor_records_a_prior_qualification_counted_as_prior_learning(self, cohort):
        created = _gcse(cohort["tutor"], cohort)
        assert (created.status, created.relevant_prior_learning, created.recorded_by) == (
            "Held (prior)", True, "tutor1",
        )
        assert compliance_repository.list_audit(entity="qualification")

    def test_prior_learning_is_refused_on_one_taken_during_the_programme(self, cohort, admin):
        with pytest.raises(ValidationError, match="before the programme"):
            _gcse(admin, cohort, status="In progress", achieved_date="")

    def test_achieving_stamps_the_date_and_reopening_clears_it(self, cohort, admin):
        created = qualification_service.add_qualification(admin, cohort["apprentice_id"], {
            "title": "Level 3 Diploma in Software Development", "status": "In progress",
            "start_date": (date.today() - timedelta(days=200)).isoformat(),
        })
        assert created.achieved_date is None
        achieved = qualification_service.update_qualification(
            admin, created.qualification_id, {"status": "Achieved", "grade": "Merit"}
        )
        assert (achieved.achieved_date, achieved.grade) == (date.today().isoformat(), "Merit")
        assert achieved.awaiting_certificate
        reopened = qualification_service.update_qualification(
            admin, created.qualification_id, {"status": "In progress"}
        )
        assert reopened.achieved_date is None
        assert reopened.grade == "Merit"  # untouched by a partial edit

    def test_moving_a_prior_learning_qualification_off_prior_needs_the_flag_cleared(
        self, cohort, admin
    ):
        created = _gcse(admin, cohort)
        with pytest.raises(ValidationError, match="before the programme"):
            qualification_service.update_qualification(
                admin, created.qualification_id, {"status": "Achieved"}
            )
        moved = qualification_service.update_qualification(
            admin, created.qualification_id,
            {"status": "Achieved", "relevant_prior_learning": False},
        )
        assert moved.status == "Achieved"

    def test_deleting_needs_a_reason(self, cohort, admin):
        created = _gcse(admin, cohort)
        with pytest.raises(ValidationError, match="reason"):
            qualification_service.delete_qualification(admin, created.qualification_id, reason="")
        qualification_service.delete_qualification(
            admin, created.qualification_id, reason="Entered twice"
        )
        assert qualification_service.list_qualifications(
            admin, apprentice_id=cohort["apprentice_id"]
        ) == []


class TestWhoMaySeeWhat:
    def test_the_apprentice_sees_their_own_but_cannot_record(self, cohort, admin):
        created = _gcse(admin, cohort)
        mine = qualification_service.list_qualifications(cohort["learner"])
        assert [q.qualification_id for q in mine] == [created.qualification_id]
        with pytest.raises(PermissionDenied):
            _gcse(cohort["learner"], cohort)

    def test_the_employer_sees_their_apprentices(self, cohort, admin):
        _gcse(admin, cohort)
        assert len(qualification_service.list_qualifications(cohort["employer_actor"])) == 1

    def test_another_employer_sees_nothing_and_is_refused_by_id(self, cohort, admin):
        created = _gcse(admin, cohort)
        assert qualification_service.list_qualifications(cohort["outsider"]) == []
        with pytest.raises(PermissionDenied):
            qualification_service.get_qualification(cohort["outsider"], created.qualification_id)

    def test_a_tutor_sees_their_caseload_and_an_administrator_everyone(self, cohort, admin):
        other = apprentice_service.create_apprentice(
            admin, {"given_name": "Ali", "family_name": "Khan"}
        )
        _gcse(admin, cohort)
        qualification_service.add_qualification(
            admin, other.apprentice_id, {"title": "BTEC Level 3 IT", "status": "Held (prior)"}
        )
        assert len(qualification_service.list_qualifications(admin)) == 2
        assert len(qualification_service.list_qualifications(cohort["tutor"])) == 1
        stranger = Actor(username="other-tutor", role="staff", staff_id=9999)
        assert qualification_service.list_qualifications(stranger) == []

    def test_the_end_point_assessor_is_refused(self, cohort, assessor):
        with pytest.raises(PermissionDenied):
            qualification_service.list_qualifications(
                assessor, apprentice_id=cohort["apprentice_id"]
            )
