"""Appeals: the window, the route, and who decides which.

The routing is the point. Both the provider admin and the end-point
assessor hold ``appeal.decide``, so these tests pin down that the
permission alone is not enough: an EPA-result appeal is the EPAO's to
see and decide, and every other appeal the provider's — consistent with
``config.EPAO_EXCLUSIVE``.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.quality import appeals as rules
from education_system.systems.apprenticeships.domain.quality.appeals import Appeal
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    epa_repository,
)
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.quality import appeal_service
from education_system.systems.apprenticeships.application.security.access import Actor, PermissionDenied

TODAY = date(2026, 9, 10)


def _epa_result(apprentice_id: int, *, days_ago: int = 3, grade: str = "Fail") -> int:
    """A graded sitting, written straight through the EPA repository."""
    booking_id = epa_repository.create_booking({
        "apprentice_id": apprentice_id, "method": "Knowledge test", "status": "Scheduled",
    })
    return epa_repository.record_result(
        booking_id=booking_id, apprentice_id=apprentice_id, method="Knowledge test",
        grade=grade, assessed_date=(date.today() - timedelta(days=days_ago)).isoformat(),
        assessor_name="A. Assessor", feedback=None, attempt=1,
    )


def _lodge_epa(cohort, result_id: int) -> Appeal:
    return appeal_service.lodge(cohort["learner"], {
        "appeal_type": "EPA result", "result_id": result_id,
        "grounds": "The marking scheme was applied wrongly to question 3.",
    })


def _lodge_gateway(cohort, *, days_ago: int = 5, **kwargs) -> Appeal:
    return appeal_service.lodge(cohort["learner"], {
        "appeal_type": "Gateway decision",
        "decision_ref": "Gateway refused: off-the-job hours",
        "decision_date": (date.today() - timedelta(days=days_ago)).isoformat(),
        "grounds": "My hours were logged but not yet approved.",
    }, **kwargs)


@pytest.fixture
def other_learner(cohort, admin) -> Actor:
    other = apprentice_service.create_apprentice(admin, {"given_name": "Ali", "family_name": "Khan"})
    return Actor(username="apprentice2", role="apprentice", apprentice_id=other.apprentice_id)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestRules:
    def test_epa_results_go_to_the_epao_and_the_rest_to_the_provider(self):
        assert rules.decider_role("EPA result") == config.END_POINT_ASSESSOR
        for appeal_type in config.APPEAL_TYPES:
            if appeal_type != "EPA result":
                assert rules.decider_role(appeal_type) == config.ADMIN

    def test_the_last_day_of_the_window_is_still_in_time(self):
        rules.check_window(TODAY - timedelta(days=config.APPEAL_WINDOW_DAYS), TODAY)

    def test_the_day_after_the_window_is_too_late(self):
        with pytest.raises(ValidationError, match=f"within {config.APPEAL_WINDOW_DAYS} days"):
            rules.check_window(TODAY - timedelta(days=config.APPEAL_WINDOW_DAYS + 1), TODAY)

    def test_a_decision_cannot_be_in_the_future(self):
        with pytest.raises(ValidationError, match="future"):
            rules.check_window(TODAY + timedelta(days=1), TODAY)

    @pytest.mark.parametrize(("current", "new"), [
        ("Lodged", "Under review"), ("Lodged", "Rejected"), ("Lodged", "Withdrawn"),
        ("Under review", "Upheld"), ("Under review", "Partially upheld"),
        ("Under review", "Withdrawn"),
    ])
    def test_open_appeals_may_move_on(self, current, new):
        rules.require_transition(current, new)

    @pytest.mark.parametrize("decided", ["Upheld", "Partially upheld", "Rejected", "Withdrawn"])
    def test_a_finished_appeal_cannot_change(self, decided):
        with pytest.raises(ValidationError, match="cannot change"):
            rules.require_transition(decided, "Under review")

    def test_under_review_cannot_go_back_to_lodged(self):
        with pytest.raises(ValidationError, match="cannot go from"):
            rules.require_transition("Under review", "Lodged")

    def test_withdrawn_is_not_a_decision(self):
        with pytest.raises(ValidationError, match="must be one of"):
            rules.validate_decision_status("Withdrawn")

    def test_an_open_appeal_past_its_deadline_is_overdue(self):
        appeal = Appeal(
            appeal_id=1, reference="APL-0001", apprentice_id=1, raised_by="a",
            appeal_type="Other", decision_date="2026-09-01", grounds="g",
            lodged_at="2026-09-02", deadline="2026-09-09",
        )
        assert appeal.is_overdue(TODAY)
        appeal.status = "Rejected"
        assert not appeal.is_overdue(TODAY)


# ═════════════════════════════════════════════════════════════════════
# Routing
# ═════════════════════════════════════════════════════════════════════

class TestRouting:
    def test_an_epa_result_appeal_is_the_epaos_alone(self, cohort, admin, assessor):
        appeal = _lodge_epa(cohort, _epa_result(cohort["apprentice_id"]))
        assert [a.appeal_id for a in appeal_service.list_appeals(assessor)] == [appeal.appeal_id]
        assert appeal_service.list_appeals(admin) == []
        assert appeal_service.list_appeals(admin, appeal_type="EPA result") == []
        with pytest.raises(PermissionDenied):
            appeal_service.get_appeal(admin, appeal.appeal_id)

    def test_the_admin_cannot_decide_an_epa_result_appeal(self, cohort, admin):
        appeal = _lodge_epa(cohort, _epa_result(cohort["apprentice_id"]))
        with pytest.raises(PermissionDenied, match="End-Point Assessment Organisation"):
            appeal_service.decide(admin, appeal.appeal_id, outcome="Upheld", decision="Agreed")
        with pytest.raises(PermissionDenied):
            appeal_service.start_review(admin, appeal.appeal_id)

    def test_the_epao_decides_an_epa_result_appeal(self, cohort, assessor):
        appeal = _lodge_epa(cohort, _epa_result(cohort["apprentice_id"]))
        decided = appeal_service.decide(assessor, appeal.appeal_id, outcome="partially upheld",
                                        decision="Question 3 re-marked; overall grade stands.")
        assert (decided.status, decided.decided_by) == ("Partially upheld", "assessor1")
        assert decided.decided_at == date.today().isoformat()

    def test_the_epao_cannot_decide_anything_else(self, cohort, assessor):
        appeal = _lodge_gateway(cohort)
        assert appeal_service.list_appeals(assessor) == []
        with pytest.raises(PermissionDenied, match="only appeals against EPA results"):
            appeal_service.decide(assessor, appeal.appeal_id, outcome="Upheld", decision="x")

    def test_the_admin_decides_the_rest(self, cohort, admin):
        appeal = _lodge_gateway(cohort)
        assert appeal_service.start_review(admin, appeal.appeal_id).status == "Under review"
        decided = appeal_service.decide(admin, appeal.appeal_id, outcome="Rejected",
                                        decision="Hours were not approved by the deadline.")
        assert decided.status == "Rejected"

    def test_a_decision_needs_reasons(self, cohort, admin):
        appeal = _lodge_gateway(cohort)
        with pytest.raises(ValidationError, match="reasons"):
            appeal_service.decide(admin, appeal.appeal_id, outcome="Rejected", decision=" ")

    def test_staff_have_no_view_of_appeals(self, cohort):
        _lodge_gateway(cohort)
        with pytest.raises(PermissionDenied):
            appeal_service.list_appeals(cohort["tutor"])

    def test_may_decide_matches_the_service(self, cohort, admin, assessor):
        epa = _lodge_epa(cohort, _epa_result(cohort["apprentice_id"]))
        gateway = _lodge_gateway(cohort)
        assert appeal_service.may_decide(assessor, epa) and not appeal_service.may_decide(
            admin, epa)
        assert appeal_service.may_decide(admin, gateway) and not appeal_service.may_decide(
            assessor, gateway)
        assert not appeal_service.may_decide(cohort["learner"], gateway)


# ═════════════════════════════════════════════════════════════════════
# Lodging
# ═════════════════════════════════════════════════════════════════════

class TestLodging:
    def test_an_epa_result_appeal_takes_its_details_from_the_record(self, cohort):
        result_id = _epa_result(cohort["apprentice_id"], days_ago=3)
        appeal = _lodge_epa(cohort, result_id)
        assert appeal.reference == "APL-0001"
        assert appeal.decision_ref_id == result_id
        assert appeal.decision_date == (date.today() - timedelta(days=3)).isoformat()
        assert "Knowledge test: Fail" in appeal.decision_ref
        assert appeal.deadline == rules.decision_deadline(date.today())

    def test_outside_the_window_is_refused(self, cohort):
        with pytest.raises(ValidationError, match=f"within {config.APPEAL_WINDOW_DAYS} days"):
            _lodge_gateway(cohort, days_ago=config.APPEAL_WINDOW_DAYS + 1)

    def test_an_old_epa_result_is_not_offered_and_cannot_be_appealed(self, cohort):
        old = _epa_result(cohort["apprentice_id"], days_ago=config.APPEAL_WINDOW_DAYS + 5)
        recent = _epa_result(cohort["apprentice_id"], days_ago=1)
        offered = appeal_service.appealable_epa_results(cohort["learner"])
        assert [r.result_id for r in offered] == [recent]
        with pytest.raises(ValidationError, match="within"):
            _lodge_epa(cohort, old)

    def test_apprentices_appeal_only_for_themselves(self, cohort, other_learner):
        with pytest.raises(PermissionDenied, match="made about you"):
            appeal_service.lodge(cohort["learner"], {
                "appeal_type": "Other", "apprentice_id": other_learner.apprentice_id,
                "decision_ref": "x", "decision_date": date.today().isoformat(), "grounds": "g",
            })

    def test_another_apprentices_epa_result_cannot_be_appealed(self, cohort, other_learner):
        theirs = _epa_result(cohort["apprentice_id"])
        with pytest.raises(PermissionDenied, match="not one of yours"):
            appeal_service.lodge(other_learner, {
                "appeal_type": "EPA result", "result_id": theirs, "grounds": "g",
            })

    def test_one_open_appeal_per_result(self, cohort):
        result_id = _epa_result(cohort["apprentice_id"])
        _lodge_epa(cohort, result_id)
        with pytest.raises(ValidationError, match="already have an open appeal"):
            _lodge_epa(cohort, result_id)

    def test_an_unlinked_login_has_nothing_to_appeal(self, db):
        with pytest.raises(ValidationError, match="not linked"):
            appeal_service.lodge(Actor(username="new", role="apprentice"), {
                "appeal_type": "Other", "decision_ref": "x",
                "decision_date": date.today().isoformat(), "grounds": "g",
            })

    def test_staff_cannot_lodge(self, cohort):
        with pytest.raises(PermissionDenied):
            appeal_service.lodge(cohort["tutor"], {"appeal_type": "Other"})

    def test_an_admin_has_no_decision_of_their_own_to_appeal(self, cohort, admin):
        """The admin holds every permission, but is nobody's apprentice."""
        with pytest.raises(ValidationError, match="not linked"):
            appeal_service.lodge(admin, {"appeal_type": "Other"})

    def test_each_apprentice_sees_only_their_own(self, cohort, other_learner):
        mine = _lodge_gateway(cohort)
        assert [a.appeal_id for a in appeal_service.list_appeals(cohort["learner"])] == [
            mine.appeal_id]
        assert appeal_service.list_appeals(other_learner) == []
        with pytest.raises(PermissionDenied):
            appeal_service.get_appeal(other_learner, mine.appeal_id)


class TestWithdrawing:
    def test_an_apprentice_withdraws_their_own_lodged_appeal(self, cohort):
        appeal = _lodge_gateway(cohort)
        withdrawn = appeal_service.withdraw(cohort["learner"], appeal.appeal_id,
                                            reason="Sorted out with my tutor")
        assert (withdrawn.status, withdrawn.decision) == ("Withdrawn", "Sorted out with my tutor")

    def test_a_decided_appeal_cannot_be_withdrawn(self, cohort, admin):
        appeal = _lodge_gateway(cohort)
        appeal_service.decide(admin, appeal.appeal_id, outcome="Upheld", decision="Agreed")
        with pytest.raises(ValidationError, match="cannot change"):
            appeal_service.withdraw(cohort["learner"], appeal.appeal_id)

    def test_nobody_else_may_withdraw_it(self, cohort, admin, other_learner):
        appeal = _lodge_gateway(cohort)
        with pytest.raises(PermissionDenied):
            appeal_service.withdraw(other_learner, appeal.appeal_id)
        with pytest.raises(PermissionDenied):
            appeal_service.withdraw(admin, appeal.appeal_id)


class TestWhatIsWaiting:
    def test_overdue_appeals_are_found(self, cohort, admin):
        lodged_on = date.today() - timedelta(days=config.APPEAL_DECISION_DAYS + 2)
        late = _lodge_gateway(cohort, days_ago=config.APPEAL_DECISION_DAYS + 4, today=lodged_on)
        _lodge_gateway(cohort)
        assert [a.appeal_id for a in appeal_service.list_appeals(admin, overdue_only=True)] == [
            late.appeal_id]

    def test_open_only_drops_the_finished(self, cohort, admin):
        done = _lodge_gateway(cohort)
        appeal_service.decide(admin, done.appeal_id, outcome="Rejected", decision="No")
        still = _lodge_gateway(cohort)
        assert [a.appeal_id for a in appeal_service.list_appeals(admin, open_only=True)] == [
            still.appeal_id]
