"""Reasonable adjustments and support: review dates, history, and consent to share.

The review-date rules are tested pure. The rest runs through the service
on the conftest's throwaway database, because the feature's hardest
promise is a scoping one: an employer sees only what the apprentice has
agreed to share with them, and never the history or the enrolment notes.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.learner_support import (
    support_arrangements as rules,
)
from education_system.systems.apprenticeships.domain.learner_support.support_arrangements import (
    SupportArrangement,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    compliance_repository,
    support_repository,
)
from education_system.systems.apprenticeships.services import support_service
from education_system.systems.apprenticeships.services.access import Actor, PermissionDenied

TODAY = date(2026, 9, 10)


def _arrangement(**overrides) -> SupportArrangement:
    fields = dict(
        arrangement_id=1, apprentice_id=1, need_category="Learning difficulty",
        adjustment="25% extra time", review_date="2026-12-01",
    )
    fields.update(overrides)
    return SupportArrangement(**fields)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestReviewDates:
    def test_rag_follows_the_review_date(self):
        assert _arrangement(review_date="2026-09-01").rag(TODAY) == "Red"
        assert _arrangement(review_date="2026-09-20").rag(TODAY) == "Amber"
        assert _arrangement(review_date="2026-12-01").rag(TODAY) == "Green"

    def test_an_ended_arrangement_is_not_judged(self):
        ended = _arrangement(status="Ended", review_date="2026-01-01")
        assert ended.rag(TODAY) is None
        assert not ended.is_review_overdue(TODAY)

    def test_an_arrangement_in_force_needs_a_review_date(self):
        with pytest.raises(ValidationError, match="needs a review date"):
            rules.validate_review_date("", status="Active", today=TODAY)
        assert rules.validate_review_date("", status="Ended", today=TODAY) is None

    def test_a_new_review_date_cannot_already_have_passed(self):
        with pytest.raises(ValidationError, match="already have passed"):
            rules.validate_review_date("2026-09-01", status="Active", today=TODAY)

    def test_an_unchanged_overdue_date_does_not_block_an_edit(self):
        assert rules.validate_review_date(
            "2026-09-01", status="Active", today=TODAY, current="2026-09-01"
        ) == "2026-09-01"


# ═════════════════════════════════════════════════════════════════════
# Through the service
# ═════════════════════════════════════════════════════════════════════

def _add(actor, cohort, **overrides):
    payload = {
        "need_category": "Learning difficulty",
        "adjustment": "25% extra time in assessments",
        "arrangements": "Agreed with the EPAO in advance",
        "review_date": (date.today() + timedelta(days=60)).isoformat(),
        "share_with_employer": False,
    }
    payload.update(overrides)
    return support_service.add_arrangement(actor, cohort["apprentice_id"], payload)


class TestRecording:
    def test_the_tutor_who_records_it_owns_it(self, cohort):
        created = _add(cohort["tutor"], cohort)
        assert created.responsible_staff_id == cohort["tutor_id"]
        assert created.responsible_staff_name == "Sam Okafor"
        assert compliance_repository.list_audit(entity="support_arrangement")

    def test_the_audit_names_the_category_not_the_adjustment(self, cohort, admin):
        _add(admin, cohort, need_category="Mental health", adjustment="Quiet room for exams")
        (entry,) = compliance_repository.list_audit(entity="support_arrangement")
        assert "Mental health" in entry.detail
        assert "Quiet room" not in entry.detail

    def test_status_and_sharing_changes_are_written_into_the_history(self, cohort, admin):
        created = _add(admin, cohort)
        updated = support_service.update_arrangement(admin, created.arrangement_id, {
            "status": "Under review", "share_with_employer": True, "note": "Agreed with Jo",
        })
        (entry,) = updated.notes
        assert "Status Active -> Under review" in entry.body
        assert "Now shared with the employer" in entry.body
        assert "Agreed with Jo" in entry.body

    def test_a_review_moves_the_date_on_and_says_what_it_found(self, cohort, admin):
        created = _add(admin, cohort)
        next_date = (date.today() + timedelta(days=120)).isoformat()
        reviewed = support_service.record_review(
            admin, created.arrangement_id, outcome="Still needed", next_review_date=next_date,
        )
        assert reviewed.review_date == next_date
        assert reviewed.notes[0].body.startswith("Reviewed: Still needed")

    def test_a_review_that_keeps_it_in_force_needs_the_next_date(self, cohort, admin):
        created = _add(admin, cohort)
        with pytest.raises(ValidationError, match="review date"):
            support_service.record_review(
                admin, created.arrangement_id, outcome="Fine", next_review_date=None,
            )
        ended = support_service.record_review(
            admin, created.arrangement_id, outcome="No longer needed",
            next_review_date=None, status="Ended",
        )
        assert (ended.status, ended.review_date) == ("Ended", None)

    def test_overdue_reviews_are_flagged(self, cohort, admin):
        created = _add(admin, cohort)
        past = (date.today() - timedelta(days=3)).isoformat()
        support_repository.update_arrangement(created.arrangement_id, {"review_date": past})
        overdue = support_service.list_arrangements(admin, overdue_only=True)
        assert [a.arrangement_id for a in overdue] == [created.arrangement_id]
        assert overdue[0].rag(date.today()) == "Red"
        assert [a.arrangement_id for a in support_service.due_for_review(cohort["tutor"])] == [
            created.arrangement_id
        ]

    def test_a_responsible_member_of_staff_must_exist(self, cohort, admin):
        with pytest.raises(ValidationError, match="No member of staff"):
            _add(admin, cohort, responsible_staff_id=424242)


class TestConsentToShare:
    def test_an_employer_sees_only_shared_arrangements(self, cohort, admin):
        shared = _add(admin, cohort, share_with_employer=True, adjustment="Flexible start times")
        private = _add(admin, cohort, need_category="Mental health", adjustment="Weekly check-in")
        employer = cohort["employer_actor"]

        record = support_service.get_record(employer, cohort["apprentice_id"])
        assert [a.arrangement_id for a in record.arrangements] == [shared.arrangement_id]
        assert [a.arrangement_id for a in support_service.list_arrangements(employer)] == [
            shared.arrangement_id
        ]
        with pytest.raises(PermissionDenied):
            support_service.get_arrangement(employer, private.arrangement_id)

    def test_an_employer_never_gets_the_history_or_the_enrolment_notes(self, cohort, admin):
        apprentice_repository.update(cohort["apprentice_id"], {"support_needs": "Dyslexia"})
        created = _add(admin, cohort, share_with_employer=True)
        support_service.add_note(admin, created.arrangement_id, "Discussed privately")

        record = support_service.get_record(cohort["employer_actor"], cohort["apprentice_id"])
        assert record.support_needs is None
        assert record.arrangements[0].notes == []

    def test_the_apprentice_sees_all_of_their_own_with_the_history(self, cohort, admin):
        apprentice_repository.update(cohort["apprentice_id"], {"support_needs": "Dyslexia"})
        created = _add(admin, cohort)
        support_service.add_note(admin, created.arrangement_id, "Coloured overlays ordered")

        record = support_service.get_record(cohort["learner"], cohort["apprentice_id"])
        assert record.support_needs == "Dyslexia"
        assert [n.body for n in record.arrangements[0].notes] == ["Coloured overlays ordered"]
        with pytest.raises(PermissionDenied):
            _add(cohort["learner"], cohort)


class TestWhoMaySeeIt:
    def test_another_employer_is_refused(self, cohort, admin):
        _add(admin, cohort, share_with_employer=True)
        with pytest.raises(PermissionDenied):
            support_service.get_record(cohort["outsider"], cohort["apprentice_id"])
        assert support_service.list_arrangements(cohort["outsider"]) == []

    def test_the_end_point_assessor_is_refused(self, cohort, assessor):
        with pytest.raises(PermissionDenied):
            support_service.get_record(assessor, cohort["apprentice_id"])

    def test_a_tutor_off_the_caseload_is_refused(self, cohort, admin):
        created = _add(admin, cohort)
        stranger = Actor(username="other-tutor", role="staff", staff_id=9999)
        assert support_service.list_arrangements(stranger) == []
        with pytest.raises(PermissionDenied):
            support_service.update_arrangement(stranger, created.arrangement_id, {"note": "x"})
