"""Admissions stages: Application -> Offer -> Enrolment, inside admissions.

The stages are not apprentice statuses — the person stays 'Applicant'
until accepted — so the existing accept / decline behaviour has to keep
working exactly as before, with accept settling the stage at Enrolment.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.admissions import stages as rules
from education_system.systems.apprenticeships.domain.admissions.stages import AdmissionStage
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.application.apprentices import (
    admissions_service,
    apprentice_service,
)
from education_system.systems.apprenticeships.application.programmes import programme_service
from education_system.systems.apprenticeships.application.security.access import PermissionDenied

TODAY = date.today().isoformat()


def _applicant(admin, cohort, **overrides):
    payload = {
        "given_name": "Ali", "family_name": "Khan", "date_of_birth": "2004-01-01",
        "employer_id": cohort["employer"].employer_id,
        "programme_id": cohort["programme"].programme_id,
    }
    payload.update(overrides)
    return apprentice_service.create_apprentice(admin, payload)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestStageRules:
    def test_the_stages_come_in_order(self):
        assert config.ADMISSION_STAGES == ("Application", "Offer", "Enrolment")

    @pytest.mark.parametrize(("current", "target"), [
        ("Application", "Offer"), ("Offer", "Offer"), ("Offer", "Enrolment"),
    ])
    def test_allowed_moves(self, current, target):
        assert rules.require_move(current, target) == target

    @pytest.mark.parametrize(("current", "target", "message"), [
        ("Application", "Enrolment", "offer before"),
        ("Enrolment", "Offer", "enrolled"),
        ("Enrolment", "Enrolment", "already"),
    ])
    def test_refused_moves(self, current, target, message):
        with pytest.raises(ValidationError, match=message):
            rules.require_move(current, target)

    def test_a_stage_is_matched_ignoring_case(self):
        assert rules.validate_stage("offer") == "Offer"
        assert rules.validate_stage(None) == "Application"
        with pytest.raises(ValidationError, match="must be one of"):
            rules.validate_stage("Interview")

    def test_a_conditional_offer_says_so(self):
        assert AdmissionStage(1, stage="Offer", offer_conditions="References").label == (
            "Offer (conditional)"
        )
        assert AdmissionStage(1).step == 1


# ═════════════════════════════════════════════════════════════════════
# Offer and enrolment
# ═════════════════════════════════════════════════════════════════════

class TestOfferAndEnrolment:
    def test_a_new_applicant_is_at_application(self, cohort, admin):
        applicant = _applicant(admin, cohort)
        (entry,) = admissions_service.list_applications(admin)
        assert entry.apprentice_id == applicant.apprentice_id
        assert (entry.stage, entry.stage_name) == (None, "Application")

    def test_an_offer_records_its_date_and_conditions(self, cohort, admin):
        applicant = _applicant(admin, cohort)
        stage = admissions_service.make_offer(
            admin, applicant.apprentice_id, offer_date=TODAY, conditions="Two references"
        )
        assert (stage.stage, stage.offer_date, stage.offer_conditions, stage.updated_by) == (
            "Offer", TODAY, "Two references", "admin5",
        )
        assert admissions_service.get_application(admin, applicant.apprentice_id).stage_label \
            == "Offer (conditional)"

    def test_an_offer_can_be_amended_while_it_stands(self, cohort, admin):
        applicant = _applicant(admin, cohort)
        admissions_service.make_offer(admin, applicant.apprentice_id, conditions="References")
        amended = admissions_service.make_offer(admin, applicant.apprentice_id, conditions="")
        assert (amended.stage, amended.offer_conditions) == ("Offer", None)

    def test_enrolment_needs_an_offer_first(self, cohort, admin):
        applicant = _applicant(admin, cohort)
        with pytest.raises(ValidationError, match="offer before"):
            admissions_service.record_enrolment(admin, applicant.apprentice_id)

    def test_enrolment_cannot_predate_the_offer(self, cohort, admin):
        applicant = _applicant(admin, cohort)
        admissions_service.make_offer(admin, applicant.apprentice_id, offer_date=TODAY)
        earlier = (date.today() - timedelta(days=3)).isoformat()
        with pytest.raises(ValidationError, match="before the offer"):
            admissions_service.record_enrolment(
                admin, applicant.apprentice_id, enrolment_date=earlier
            )

    def test_enrolling_keeps_them_an_applicant_in_the_queue(self, cohort, admin):
        applicant = _applicant(admin, cohort)
        admissions_service.make_offer(admin, applicant.apprentice_id)
        stage = admissions_service.record_enrolment(admin, applicant.apprentice_id)
        assert (stage.stage, stage.enrolment_date) == ("Enrolment", TODAY)
        (entry,) = admissions_service.list_applications(admin)
        assert entry.summary.apprentice.status == "Applicant"
        assert entry.stage_name == "Enrolment"

    def test_staff_see_the_queue_but_cannot_move_anyone_on(self, cohort, admin):
        applicant = _applicant(admin, cohort, tutor_id=cohort["tutor_id"])
        tutor = cohort["tutor"]
        assert admissions_service.get_stage(tutor, applicant.apprentice_id).stage == "Application"
        with pytest.raises(PermissionDenied):
            admissions_service.make_offer(tutor, applicant.apprentice_id)
        with pytest.raises(PermissionDenied):
            admissions_service.record_enrolment(tutor, applicant.apprentice_id)

    def test_only_an_applicant_can_be_offered_a_place(self, cohort, admin):
        with pytest.raises(ValidationError, match="not an applicant"):
            admissions_service.make_offer(admin, cohort["apprentice_id"])


# ═════════════════════════════════════════════════════════════════════
# The existing decisions still work
# ═════════════════════════════════════════════════════════════════════

class TestAcceptAndDecline:
    def test_accept_takes_them_on_programme_and_settles_enrolment(self, cohort, admin):
        applicant = _applicant(admin, cohort)
        decision = admissions_service.accept(admin, applicant.apprentice_id, start_date=TODAY)
        assert decision.status == "On Programme"
        stage = admissions_service.get_stage(admin, applicant.apprentice_id)
        assert (stage.stage, stage.enrolment_date) == ("Enrolment", TODAY)
        assert admissions_service.list_applications(admin) == []

    def test_accept_keeps_an_enrolment_already_recorded(self, cohort, admin):
        applicant = _applicant(admin, cohort)
        earlier = (date.today() - timedelta(days=2)).isoformat()
        admissions_service.make_offer(admin, applicant.apprentice_id, offer_date=earlier)
        admissions_service.record_enrolment(admin, applicant.apprentice_id, enrolment_date=earlier)
        admissions_service.accept(admin, applicant.apprentice_id, start_date=TODAY)
        assert admissions_service.get_stage(admin, applicant.apprentice_id).enrolment_date \
            == earlier

    def test_accept_still_takes_its_keyword_arguments(self, cohort, admin):
        applicant = _applicant(admin, cohort, employer_id=None, programme_id=None)
        decision = admissions_service.accept(
            admin, applicant.apprentice_id, start_date=TODAY,
            programme_id=cohort["programme"].programme_id,
            employer_id=cohort["employer"].employer_id, workplace_id=None,
            tutor_id=cohort["tutor_id"], notes="Strong interview",
        )
        record = apprentice_service.get_apprentice(admin, applicant.apprentice_id).apprentice
        assert (decision.status, record.tutor_id) == ("On Programme", cohort["tutor_id"])
        assert "Strong interview" in (record.notes or "")

    def test_accept_still_requires_an_employer(self, cohort, admin):
        applicant = _applicant(admin, cohort, employer_id=None)
        with pytest.raises(ValidationError, match="employer is required"):
            admissions_service.accept(admin, applicant.apprentice_id, start_date=TODAY)

    def test_new_starts_go_onto_the_active_version(self, cohort, admin):
        applicant = _applicant(admin, cohort)
        newer = programme_service.new_version(admin, cohort["programme"].programme_id)
        with pytest.raises(ValidationError, match="Superseded"):
            admissions_service.accept(admin, applicant.apprentice_id, start_date=TODAY)
        decision = admissions_service.accept(
            admin, applicant.apprentice_id, start_date=TODAY, programme_id=newer.programme_id
        )
        assert decision.status == "On Programme"

    def test_decline_keeps_the_record_and_the_reason(self, cohort, admin):
        applicant = _applicant(admin, cohort)
        admissions_service.make_offer(admin, applicant.apprentice_id)
        decision = admissions_service.decline(
            admin, applicant.apprentice_id, reason="No vacancy", effective_date=TODAY
        )
        assert decision.status == "Withdrawn"
        history = apprentice_service.status_history(admin, applicant.apprentice_id)
        assert any("No vacancy" in (change.reason or "") for change in history)

    def test_decline_still_needs_a_reason(self, cohort, admin):
        applicant = _applicant(admin, cohort)
        with pytest.raises(ValidationError, match="reason is required"):
            admissions_service.decline(admin, applicant.apprentice_id, reason="  ")

    def test_only_an_applicant_can_be_accepted_or_declined(self, cohort, admin):
        with pytest.raises(ValidationError, match="only an"):
            admissions_service.accept(admin, cohort["apprentice_id"], start_date=TODAY)
        with pytest.raises(ValidationError, match="only an applicant"):
            admissions_service.decline(admin, cohort["apprentice_id"], reason="x")
