"""Service-layer behaviour for the apprenticeships system.

Concentrates on the two things that would be most damaging to get
wrong: the role boundaries (five roles share one database, and three of
them are outsiders) and the rules that decide whether someone may
finish — off-the-job hours, portfolio coverage, gateway and EPA.
"""

from __future__ import annotations

from datetime import date

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    compliance_service,
    epa_service,
    funding_service,
    gateway_service,
    portfolio_service,
    reporting_service,
    review_service,
    training_service,
)
from education_system.systems.apprenticeships.services.access import PermissionDenied


# ═════════════════════════════════════════════════════════════════════
# Scoping — who can see whom
# ═════════════════════════════════════════════════════════════════════

class TestScoping:
    def test_each_role_sees_its_own_slice(self, cohort, admin):
        assert len(apprentice_service.list_apprentices(admin)) == 1
        assert len(apprentice_service.list_apprentices(cohort["tutor"])) == 1
        assert len(apprentice_service.list_apprentices(cohort["employer_actor"])) == 1
        assert len(apprentice_service.list_apprentices(cohort["learner"])) == 1

    def test_a_rival_employer_sees_nothing(self, cohort):
        assert apprentice_service.list_apprentices(cohort["outsider"]) == []

    def test_a_rival_employer_cannot_open_the_record(self, cohort):
        with pytest.raises(PermissionDenied):
            apprentice_service.get_apprentice(cohort["outsider"], cohort["apprentice_id"])

    def test_an_unlinked_actor_is_scoped_to_nothing_not_everything(self, cohort):
        """An employer login with no manager record must see zero rows.

        The failure mode this guards against is the scope falling back to
        "no filter" and quietly exposing the whole cohort.
        """
        from education_system.systems.apprenticeships.services.access import Actor

        unlinked = Actor(username="nobody", role="employer", employer_id=None)
        assert apprentice_service.list_apprentices(unlinked) == []

    def test_apprentice_cannot_enrol_anyone(self, cohort):
        with pytest.raises(PermissionDenied):
            apprentice_service.create_apprentice(
                cohort["learner"], {"given_name": "Mal", "family_name": "Ory"}
            )

    def test_only_admin_reads_the_audit_trail(self, cohort, admin):
        assert compliance_service.audit_trail(admin, limit=10) is not None
        with pytest.raises(PermissionDenied):
            compliance_service.audit_trail(cohort["tutor"])


# ═════════════════════════════════════════════════════════════════════
# Lifecycle
# ═════════════════════════════════════════════════════════════════════

class TestLifecycle:
    def test_new_apprentices_start_as_applicants(self, db, admin):
        created = apprentice_service.create_apprentice(
            admin, {"given_name": "New", "family_name": "Starter"}
        )
        assert created.status == "Applicant"

    def test_illegal_transitions_are_refused(self, cohort, admin):
        with pytest.raises(ValidationError, match="Cannot move"):
            apprentice_service.change_status(admin, cohort["apprentice_id"], "Completed")

    def test_withdrawal_requires_a_reason(self, cohort, admin):
        with pytest.raises(ValidationError, match="reason"):
            apprentice_service.change_status(admin, cohort["apprentice_id"], "Withdrawn")

    def test_a_break_can_be_taken_and_returned_from(self, cohort, admin):
        apprentice_id = cohort["apprentice_id"]
        apprentice_service.change_status(
            admin, apprentice_id, "Break in Learning", reason="Long-term sickness"
        )
        assert len(apprentice_service.list_breaks(admin, apprentice_id)) == 1
        back = apprentice_service.change_status(admin, apprentice_id, "On Programme")
        assert back.status == "On Programme"
        breaks = apprentice_service.list_breaks(admin, apprentice_id)
        assert breaks[0]["actual_return"] is not None

    def test_planned_end_is_derived_not_typed(self, cohort):
        """A part-time apprentice gets a proportionally longer programme."""
        apprentice = cohort["apprentice"]
        assert apprentice.planned_end_date is not None
        assert apprentice.planned_end_date > apprentice.start_date

    def test_duplicate_uln_is_rejected(self, cohort, admin):
        with pytest.raises(ValidationError, match="ULN"):
            apprentice_service.create_apprentice(admin, {
                "given_name": "Clone", "family_name": "Bell", "uln": "1234567890",
            })


# ═════════════════════════════════════════════════════════════════════
# Off-the-job hours
# ═════════════════════════════════════════════════════════════════════

class TestOffTheJobHours:
    def test_target_comes_from_the_programme_dates(self, cohort, admin):
        summary = training_service.otj_summary(admin, cohort["apprentice_id"])
        assert summary.target_hours > 200

    def test_only_approved_hours_count(self, cohort, admin):
        entry = training_service.log_hours(cohort["learner"], {
            "activity_date": date.today().isoformat(), "hours": 6,
            "activity_type": "Online learning", "description": "Module 1",
        })
        assert training_service.otj_summary(admin, cohort["apprentice_id"]).approved_hours == 0
        training_service.submit_hours(cohort["learner"], entry.entry_id)
        training_service.approve_hours(cohort["employer_actor"], entry.entry_id)
        assert training_service.otj_summary(admin, cohort["apprentice_id"]).approved_hours == 6

    def test_an_apprentice_cannot_approve_their_own_hours(self, cohort):
        entry = training_service.log_hours(cohort["learner"], {
            "activity_date": date.today().isoformat(), "hours": 3,
            "activity_type": "Shadowing", "description": "Sat with the team",
        })
        training_service.submit_hours(cohort["learner"], entry.entry_id)
        with pytest.raises(PermissionDenied):
            training_service.approve_hours(cohort["learner"], entry.entry_id)

    def test_absurd_hours_are_rejected(self, cohort):
        with pytest.raises(ValidationError):
            training_service.log_hours(cohort["learner"], {
                "activity_date": date.today().isoformat(), "hours": 70,
                "activity_type": "Online learning", "description": "Typo",
            })


# ═════════════════════════════════════════════════════════════════════
# Portfolio
# ═════════════════════════════════════════════════════════════════════

class TestPortfolio:
    def test_an_apprentice_cannot_mark_themselves_competent(self, cohort):
        from education_system.systems.apprenticeships.services import programme_service

        evidence = portfolio_service.add_evidence(cohort["learner"], {
            "title": "Payment service", "evidence_type": "Work product",
        })
        ksb = programme_service.list_ksbs(
            cohort["tutor"], cohort["programme"].programme_id
        )[0]
        with pytest.raises((PermissionDenied, ValidationError)):
            portfolio_service.map_to_ksb(
                cohort["learner"], evidence.evidence_id, ksb.ksb_id, coverage="Competent"
            )

    def test_referring_evidence_requires_feedback(self, cohort):
        evidence = portfolio_service.add_evidence(cohort["learner"], {
            "title": "Thin evidence", "evidence_type": "Reflective account",
        })
        portfolio_service.submit_evidence(cohort["learner"], evidence.evidence_id)
        with pytest.raises(ValidationError):
            portfolio_service.assess_evidence(
                cohort["tutor"], evidence.evidence_id, outcome="Referred"
            )

    def test_coverage_rolls_up_only_from_accepted_evidence(self, cohort, admin):
        from education_system.systems.apprenticeships.services import programme_service

        evidence = portfolio_service.add_evidence(cohort["learner"], {
            "title": "Project", "evidence_type": "Work product",
        })
        ksbs = programme_service.list_ksbs(admin, cohort["programme"].programme_id)
        for ksb in ksbs:
            portfolio_service.map_to_ksb(
                cohort["learner"], evidence.evidence_id, ksb.ksb_id, coverage="Developing"
            )
        portfolio = portfolio_service.get_portfolio(admin, cohort["apprentice_id"])
        assert portfolio.competent_ksbs == 0

        portfolio_service.submit_evidence(cohort["learner"], evidence.evidence_id)
        portfolio_service.assess_evidence(
            cohort["tutor"], evidence.evidence_id, outcome="Accepted", feedback="Good"
        )
        stored = portfolio_service.get_evidence(cohort["tutor"], evidence.evidence_id)
        for mapping in stored.mappings:
            portfolio_service.update_mapping(
                cohort["tutor"], mapping.map_id, coverage="Competent"
            )
        portfolio = portfolio_service.get_portfolio(admin, cohort["apprentice_id"])
        assert portfolio.is_complete


# ═════════════════════════════════════════════════════════════════════
# Reviews
# ═════════════════════════════════════════════════════════════════════

class TestReviews:
    def _held_review(self, cohort, admin):
        review = review_service.schedule_review(
            admin, cohort["apprentice_id"],
            scheduled_date=date.today().isoformat(), conducted_by=cohort["tutor_id"],
        )
        review_service.record_review(cohort["tutor"], review.review_id, {
            "held_date": date.today().isoformat(),
            "progress_rating": "Green", "summary": "On track",
        })
        return review

    def test_nobody_signs_someone_elses_line(self, cohort, admin):
        review = self._held_review(cohort, admin)
        with pytest.raises(PermissionDenied):
            review_service.sign_review(
                cohort["employer_actor"], review.review_id, signatory="apprentice"
            )

    def test_completes_only_on_the_third_signature(self, cohort, admin):
        review = self._held_review(cohort, admin)
        review_service.sign_review(cohort["tutor"], review.review_id)
        partial = review_service.sign_review(cohort["learner"], review.review_id)
        assert partial.status != "Complete"
        final = review_service.sign_review(cohort["employer_actor"], review.review_id)
        assert final.status == "Complete"
        assert final.is_fully_signed


# ═════════════════════════════════════════════════════════════════════
# Gateway and EPA — the independence rules
# ═════════════════════════════════════════════════════════════════════

def _make_ready(cohort, admin):
    """Satisfy every gateway requirement for the cohort apprentice."""
    from education_system.systems.apprenticeships.services import programme_service

    apprentice_id = cohort["apprentice_id"]

    for subject in config.FUNCTIONAL_SKILLS:
        compliance_service.set_functional_skill(
            admin, apprentice_id, subject, status="Achieved", level="Level 2"
        )

    evidence = portfolio_service.add_evidence(cohort["learner"], {
        "title": "Portfolio", "evidence_type": "Work product",
    })
    for ksb in programme_service.list_ksbs(admin, cohort["programme"].programme_id):
        portfolio_service.map_to_ksb(
            cohort["learner"], evidence.evidence_id, ksb.ksb_id, coverage="Developing"
        )
    portfolio_service.submit_evidence(cohort["learner"], evidence.evidence_id)
    portfolio_service.assess_evidence(
        cohort["tutor"], evidence.evidence_id, outcome="Accepted", feedback="Strong"
    )
    stored = portfolio_service.get_evidence(cohort["tutor"], evidence.evidence_id)
    for mapping in stored.mappings:
        portfolio_service.update_mapping(cohort["tutor"], mapping.map_id, coverage="Competent")

    review = review_service.schedule_review(
        admin, apprentice_id, scheduled_date=date.today().isoformat(),
        conducted_by=cohort["tutor_id"],
    )
    review_service.record_review(cohort["tutor"], review.review_id, {
        "held_date": date.today().isoformat(), "progress_rating": "Green",
        "summary": "Ready",
    })
    for who in (cohort["tutor"], cohort["learner"], cohort["employer_actor"]):
        review_service.sign_review(who, review.review_id)

    target = training_service.otj_summary(admin, apprentice_id).target_hours
    remaining = target
    while remaining > 0:
        chunk = min(24, remaining)
        entry = training_service.log_hours(cohort["learner"], {
            "activity_date": date.today().isoformat(), "hours": chunk,
            "activity_type": "Practical training", "description": "Workplace training",
        })
        training_service.submit_hours(cohort["learner"], entry.entry_id)
        training_service.approve_hours(cohort["employer_actor"], entry.entry_id)
        remaining -= chunk

    gateway_service.set_employer_sign_off(
        cohort["employer_actor"], apprentice_id, confirmed=True, note="Ready"
    )


class TestGateway:
    def test_blocked_until_every_requirement_is_met(self, cohort, admin):
        record = gateway_service.evaluate_gateway(admin, cohort["apprentice_id"])
        assert not record.is_ready
        assert record.outstanding

    def test_the_refusal_names_what_is_outstanding(self, cohort, admin):
        with pytest.raises(ValidationError) as excinfo:
            gateway_service.request_gateway(admin, cohort["apprentice_id"])
        assert "outstanding" in str(excinfo.value).lower()

    def test_ready_once_everything_is_satisfied(self, cohort, admin):
        _make_ready(cohort, admin)
        record = gateway_service.evaluate_gateway(admin, cohort["apprentice_id"])
        assert record.is_ready, [c.requirement_key for c in record.outstanding]

    def test_the_provider_cannot_approve_its_own_gateway(self, cohort, admin, assessor):
        """Independence: only the EPAO decides an apprentice is ready.

        A provider admin holding this would make the whole gateway step
        ceremonial.
        """
        _make_ready(cohort, admin)
        gateway_service.request_gateway(admin, cohort["apprentice_id"])
        with pytest.raises(PermissionDenied):
            gateway_service.approve_gateway(admin, cohort["apprentice_id"])
        gateway_service.approve_gateway(assessor, cohort["apprentice_id"])
        assert gateway_service.evaluate_gateway(
            admin, cohort["apprentice_id"]
        ).status == "Approved"


class TestEndPointAssessment:
    def _at_epa(self, cohort, admin, assessor):
        _make_ready(cohort, admin)
        gateway_service.request_gateway(admin, cohort["apprentice_id"])
        gateway_service.approve_gateway(assessor, cohort["apprentice_id"])
        bookings = []
        for method in ("Knowledge test", "Project with report"):
            booking = epa_service.book_assessment(
                assessor, cohort["apprentice_id"], {"method": method}
            )
            epa_service.schedule_assessment(
                assessor, booking["booking_id"],
                scheduled_date=date.today().isoformat(),
                assessor_name="A. Assessor", assessor_username="assessor1",
            )
            bookings.append(booking)
        return bookings

    def test_booking_requires_an_approved_gateway(self, cohort, assessor):
        with pytest.raises(ValidationError):
            epa_service.book_assessment(
                assessor, cohort["apprentice_id"], {"method": "Knowledge test"}
            )

    def test_the_provider_cannot_grade(self, cohort, admin, assessor):
        """The organisation that trained them does not decide the grade."""
        bookings = self._at_epa(cohort, admin, assessor)
        with pytest.raises(PermissionDenied):
            epa_service.record_result(admin, bookings[0]["booking_id"], grade="Pass")

    def test_overall_grade_is_the_lowest_achieved(self, cohort, admin, assessor):
        bookings = self._at_epa(cohort, admin, assessor)
        epa_service.record_result(assessor, bookings[0]["booking_id"], grade="Distinction")
        epa_service.record_result(assessor, bookings[1]["booking_id"], grade="Pass")
        progress = epa_service.epa_progress(admin, cohort["apprentice_id"])
        assert progress.is_complete
        assert progress.overall == "Pass"

    def test_passing_everything_completes_the_apprenticeship(self, cohort, admin, assessor):
        bookings = self._at_epa(cohort, admin, assessor)
        for booking in bookings:
            epa_service.record_result(assessor, booking["booking_id"], grade="Pass")
        final = apprentice_service.get_apprentice(admin, cohort["apprentice_id"])
        assert final.apprentice.status == "Completed"


# ═════════════════════════════════════════════════════════════════════
# Funding
# ═════════════════════════════════════════════════════════════════════

class TestFunding:
    def test_small_non_levy_employer_co_invests(self, cohort, admin):
        funding_service.set_funding(admin, cohort["apprentice_id"], {
            "negotiated_price": 18000.0,
        })
        summary = funding_service.get_funding(admin, cohort["apprentice_id"])
        assert summary.record is not None
        assert summary.record.government_contribution == pytest.approx(17100.0)
        assert summary.record.employer_contribution == pytest.approx(900.0)

    def test_price_above_the_band_cap_is_refused(self, cohort, admin):
        with pytest.raises(ValidationError, match="exceeds"):
            funding_service.set_funding(admin, cohort["apprentice_id"], {
                "negotiated_price": 999_999.0,
            })

    def test_schedule_holds_back_a_completion_payment(self, cohort, admin):
        funding_service.set_funding(admin, cohort["apprentice_id"], {
            "negotiated_price": 18000.0,
        })
        summary = funding_service.get_funding(admin, cohort["apprentice_id"])
        completion = [p for p in summary.payments if p.payment_type == "Completion"]
        assert len(completion) == 1
        assert completion[0].amount == pytest.approx(18000.0 * config.COMPLETION_PAYMENT_SHARE)


# ═════════════════════════════════════════════════════════════════════
# Dashboards
# ═════════════════════════════════════════════════════════════════════

class TestDashboards:
    def test_every_role_gets_a_dashboard(self, cohort, admin, assessor):
        for actor in (admin, cohort["tutor"], cohort["learner"],
                      cohort["employer_actor"], assessor):
            data = reporting_service.dashboard(actor)
            assert isinstance(data, dict)
            assert "kpis" in data

    def test_an_unlinked_login_is_told_so_rather_than_crashing(self, db):
        from education_system.systems.apprenticeships.services.access import Actor

        data = reporting_service.dashboard(
            Actor(username="ghost", role="apprentice", apprentice_id=None)
        )
        assert data["unlinked"] is True
