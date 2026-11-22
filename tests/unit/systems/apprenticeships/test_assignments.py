"""Assignments: setting, submitting, referral and resubmission, moderation.

The rules are tested pure. The flows run through the services on the
conftest's throwaway database: an attempt limit that can be exceeded, a
marker who can moderate their own work, or late work that goes
unrecorded would each make the assessment record untrustworthy.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.progress import assignments as rules
from education_system.systems.apprenticeships.domain.progress.assignments import (
    Assignment,
    AssignmentSubmission,
)
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.assessments import portfolio_service
from education_system.systems.apprenticeships.application.learning import assignment_service
from education_system.systems.apprenticeships.application.security.access import Actor, PermissionDenied

TODAY = date(2026, 9, 10)
MAX = config.ASSIGNMENT_MAX_ATTEMPTS


def _days(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


def _assignment(**overrides) -> Assignment:
    fields = dict(assignment_id=1, apprentice_id=1, title="Essay",
                  assignment_type="Written assignment", due_date="2026-10-01")
    fields.update(overrides)
    return Assignment(**fields)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestGradingRules:
    def test_a_refer_with_attempts_left_reopens_the_work(self):
        assert rules.status_after_mark("Refer", 1, 3) == "Referred"
        assert rules.status_after_mark("Refer", 3, 3) == "Marked"
        assert rules.status_after_mark("Pass", 1, 3) == "Marked"

    def test_moderation_never_takes_away_a_resubmission(self):
        assert rules.status_after_moderation("Refer", 1, 3) == "Referred"
        assert rules.status_after_moderation("Refer", 3, 3) == "Moderated"
        assert rules.status_after_moderation("Merit", 1, 3) == "Moderated"

    @pytest.mark.parametrize(("current", "target"), [
        ("Set", "Marked"), ("Moderated", "Referred"), ("Withdrawn", "Set"),
        ("Submitted", "Withdrawn"),
    ])
    def test_illegal_moves_are_refused(self, current, target):
        with pytest.raises(ValidationError, match="Cannot move an assignment"):
            rules.require_assignment_status(current, target)

    def test_nobody_moderates_their_own_marking(self):
        with pytest.raises(ValidationError, match="cannot moderate it"):
            rules.require_different_moderator("Tutor1", "tutor1")
        with pytest.raises(ValidationError, match="not been marked"):
            rules.require_different_moderator("tutor1", None)
        rules.require_different_moderator("iqa1", "tutor1")

    def test_work_due_today_is_on_time_and_tomorrow_it_is_late(self):
        assert not rules.submitted_late("2026-09-10", TODAY)
        assert rules.submitted_late("2026-09-09", TODAY)
        assert not rules.submitted_late(None, TODAY)


class TestVocabulary:
    def test_attempts_allowed_are_capped(self):
        assert rules.validate_max_attempts("") == MAX
        assert rules.validate_max_attempts("1") == 1
        for bad in ("0", str(MAX + 1), "lots"):
            with pytest.raises(ValidationError):
                rules.validate_max_attempts(bad)

    def test_ksb_codes_are_normalised_and_deduplicated(self):
        assert rules.parse_ksb_codes("k1, s3 ,K1; b02") == ["K1", "S3", "B2"]
        with pytest.raises(ValidationError):
            rules.parse_ksb_codes("K1, X9")

    def test_a_submission_needs_some_work_in_it(self):
        with pytest.raises(ValidationError, match="needs some work"):
            rules.validate_submission("  ", has_evidence=False)
        assert rules.validate_submission("", has_evidence=True) is None

    def test_type_and_grade_come_from_the_lists(self):
        assert rules.validate_assignment_type("project") == "Project"
        assert rules.validate_grade("DISTINCTION") == "Distinction"
        with pytest.raises(ValidationError):
            rules.validate_grade("A*")


class TestAssignment:
    def test_attempt_arithmetic(self):
        fresh = _assignment(status="Set", attempt=1, max_attempts=3)
        assert (fresh.attempts_used, fresh.attempts_left, fresh.next_attempt) == (0, 3, 1)
        referred = _assignment(status="Referred", attempt=1, max_attempts=3)
        assert (referred.attempts_used, referred.attempts_left, referred.next_attempt) == (1, 2, 2)

    def test_rag(self):
        assert _assignment(due_date="2026-09-01").rag(TODAY) == "Red"
        assert _assignment(due_date="2026-09-15").rag(TODAY) == "Amber"
        assert _assignment(status="Submitted", due_date="2026-09-01").rag(TODAY) == "Amber"
        assert _assignment(status="Marked", grade="Pass").rag(TODAY) == "Green"
        assert _assignment(status="Marked", grade="Refer", attempt=3).rag(TODAY) == "Red"

    def test_late_is_read_from_the_current_attempt(self):
        item = _assignment(status="Submitted", attempt=2, submissions=[
            AssignmentSubmission(1, 1, 1, "apprentice1", is_late=True),
            AssignmentSubmission(2, 1, 2, "apprentice1", is_late=False),
        ])
        assert not item.is_late


# ═════════════════════════════════════════════════════════════════════
# Through the services
# ═════════════════════════════════════════════════════════════════════

def _set(cohort, **overrides):
    payload = {"title": "Network design report", "assignment_type": "Written assignment",
               "ksb_codes": "K1, S1", "due_date": _days(14)}
    payload.update(overrides)
    return assignment_service.set_assignment(cohort["tutor"], cohort["apprentice_id"], payload)


def _submit(cohort, item, body="My report"):
    return assignment_service.submit(cohort["learner"], item.assignment_id, body=body)


class TestSetting:
    def test_a_tutor_sets_work_stamped_with_their_login(self, cohort):
        item = _set(cohort, ksb_codes="s1, k1")
        assert (item.status, item.attempt, item.max_attempts, item.set_by) == (
            "Set", 1, MAX, "tutor1",
        )
        assert item.ksb_codes == "S1, K1"

    def test_a_ksb_not_on_the_standard_is_refused(self, cohort):
        with pytest.raises(ValidationError, match="Not on this apprentice's standard: K9"):
            _set(cohort, ksb_codes="K1, K9")

    def test_the_brief_is_frozen_once_work_is_handed_in_but_the_date_can_move(self, cohort):
        item = _set(cohort)
        _submit(cohort, item)
        assignment_service.mark(cohort["tutor"], item.assignment_id, grade="Refer",
                                feedback="More depth")
        with pytest.raises(ValidationError, match="only the due date may change"):
            assignment_service.update_assignment(cohort["tutor"], item.assignment_id,
                                                 {"title": "Something else"})
        moved = assignment_service.update_assignment(cohort["tutor"], item.assignment_id,
                                                     {"due_date": _days(30)})
        assert moved.due_date == _days(30)

    def test_withdrawing_keeps_the_record(self, cohort):
        item = _set(cohort)
        withdrawn = assignment_service.withdraw_assignment(
            cohort["tutor"], item.assignment_id, reason="Set in error"
        )
        assert withdrawn.status == "Withdrawn"
        with pytest.raises(ValidationError):
            _submit(cohort, item)

    def test_the_apprentice_cannot_set_work(self, cohort):
        with pytest.raises(PermissionDenied):
            assignment_service.set_assignment(cohort["learner"], cohort["apprentice_id"],
                                              {"title": "Easy one", "assignment_type": "Test"})


class TestSubmitting:
    def test_late_work_is_accepted_and_flagged(self, cohort):
        item = _set(cohort, due_date=_days(-1))
        handed_in = _submit(cohort, item)
        assert handed_in.status == "Submitted"
        assert handed_in.is_late
        assert handed_in.current_submission.submitted_by == "apprentice1"

    def test_work_cannot_be_handed_in_twice_for_one_attempt(self, cohort):
        item = _set(cohort)
        _submit(cohort, item)
        with pytest.raises(ValidationError, match="not waiting for a submission"):
            _submit(cohort, item)

    def test_portfolio_evidence_can_be_the_submission(self, cohort):
        evidence = portfolio_service.add_evidence(cohort["learner"], {
            "title": "Topology diagram", "evidence_type": "Work product",
        })
        item = _set(cohort)
        handed_in = assignment_service.submit(
            cohort["learner"], item.assignment_id, evidence_id=evidence.evidence_id
        )
        assert handed_in.current_submission.evidence_title == "Topology diagram"

    def test_someone_elses_evidence_is_refused(self, cohort, admin):
        other = apprentice_service.create_apprentice(
            admin, {"given_name": "Ali", "family_name": "Khan"}
        )
        theirs = portfolio_service.add_evidence(admin, {
            "apprentice_id": other.apprentice_id, "title": "Not yours",
            "evidence_type": "Work product",
        })
        item = _set(cohort)
        with pytest.raises(ValidationError, match="not in this apprentice's portfolio"):
            assignment_service.submit(cohort["learner"], item.assignment_id,
                                      evidence_id=theirs.evidence_id)

    def test_staff_do_not_hand_in_work(self, cohort):
        item = _set(cohort)
        with pytest.raises(PermissionDenied):
            assignment_service.submit(cohort["tutor"], item.assignment_id, body="Done for you")


class TestReferral:
    def test_a_refer_needs_feedback(self, cohort):
        item = _set(cohort)
        _submit(cohort, item)
        with pytest.raises(ValidationError, match="Feedback is required"):
            assignment_service.mark(cohort["tutor"], item.assignment_id, grade="Refer")

    def test_a_refer_reopens_the_work_and_a_resubmission_keeps_the_history(self, cohort):
        item = _set(cohort)
        _submit(cohort, item, body="First go")
        referred = assignment_service.mark(
            cohort["tutor"], item.assignment_id, grade="Refer", feedback="More depth",
            resubmit_by=_days(21),
        )
        assert (referred.status, referred.due_date, referred.attempts_left) == (
            "Referred", _days(21), MAX - 1,
        )
        again = _submit(cohort, item, body="Second go")
        assert (again.status, again.attempt, again.grade) == ("Submitted", 2, None)
        assert [(s.attempt, s.grade, s.body) for s in again.submissions] == [
            (1, "Refer", "First go"), (2, None, "Second go"),
        ]
        passed = assignment_service.mark(cohort["tutor"], item.assignment_id, grade="Merit")
        assert passed.is_passed

    def test_a_refer_on_the_final_attempt_stands(self, cohort):
        item = _set(cohort, max_attempts=2)
        for attempt in (1, 2):
            _submit(cohort, item, body=f"Attempt {attempt}")
            marked = assignment_service.mark(cohort["tutor"], item.assignment_id,
                                             grade="Refer", feedback="Not there yet")
        assert (marked.status, marked.attempts_left) == ("Marked", 0)
        assert marked.is_failed
        with pytest.raises(ValidationError):
            _submit(cohort, item)

    def test_only_submitted_work_can_be_marked(self, cohort):
        item = _set(cohort)
        with pytest.raises(ValidationError, match="no submission waiting"):
            assignment_service.mark(cohort["tutor"], item.assignment_id, grade="Pass")


class TestModeration:
    def _marked(self, cohort, marker, grade="Pass", **overrides):
        item = _set(cohort, **overrides)
        _submit(cohort, item)
        return assignment_service.mark(marker, item.assignment_id, grade=grade,
                                       feedback="Feedback given")

    def test_the_marker_cannot_moderate_their_own_marking(self, cohort):
        item = self._marked(cohort, cohort["tutor"])
        with pytest.raises(ValidationError, match="cannot moderate it"):
            assignment_service.moderate(cohort["tutor"], item.assignment_id, outcome="Agreed")
        assert assignment_service.moderation_queue(cohort["tutor"]) == []

    def test_a_second_person_agrees_the_grade(self, cohort, admin):
        item = self._marked(cohort, cohort["tutor"])
        assert [a.assignment_id for a in assignment_service.moderation_queue(admin)] == [
            item.assignment_id
        ]
        agreed = assignment_service.moderate(admin, item.assignment_id, outcome="Agreed")
        assert (agreed.status, agreed.grade) == ("Moderated", "Pass")
        assert agreed.moderations[0].moderator == "admin5"
        assert assignment_service.moderation_queue(admin) == []

    def test_an_adjustment_must_change_the_grade_and_say_why(self, cohort, admin):
        item = self._marked(cohort, cohort["tutor"])
        with pytest.raises(ValidationError, match="must differ"):
            assignment_service.moderate(admin, item.assignment_id, outcome="Adjusted",
                                        adjusted_grade="Pass", notes="Same")
        with pytest.raises(ValidationError, match="Notes are required"):
            assignment_service.moderate(admin, item.assignment_id, outcome="Adjusted",
                                        adjusted_grade="Merit")
        adjusted = assignment_service.moderate(admin, item.assignment_id, outcome="Adjusted",
                                               adjusted_grade="Merit", notes="Exceeds criteria")
        assert (adjusted.grade, adjusted.moderations[0].original_grade) == ("Merit", "Pass")

    def test_adjusting_to_a_refer_with_attempts_left_reopens_the_work(self, cohort, admin):
        item = self._marked(cohort, cohort["tutor"])
        reopened = assignment_service.moderate(admin, item.assignment_id, outcome="Adjusted",
                                               adjusted_grade="Refer", notes="Criteria not met")
        assert reopened.status == "Referred"
        assert _submit(cohort, item).attempt == 2

    def test_an_attempt_is_moderated_once(self, cohort, admin):
        item = self._marked(cohort, cohort["tutor"], grade="Refer")
        assignment_service.moderate(admin, item.assignment_id, outcome="Agreed")
        with pytest.raises(ValidationError, match="already been moderated"):
            assignment_service.moderate(admin, item.assignment_id, outcome="Agreed")

    def test_the_tutor_moderates_what_an_administrator_marked(self, cohort, admin):
        item = self._marked(cohort, admin)
        assert assignment_service.moderate(
            cohort["tutor"], item.assignment_id, outcome="Agreed"
        ).status == "Moderated"


class TestScope:
    def test_the_employer_and_the_assessor_do_not_see_assignments(self, cohort, assessor):
        item = _set(cohort)
        for outsider in (cohort["employer_actor"], cohort["outsider"], assessor):
            with pytest.raises(PermissionDenied):
                assignment_service.list_assignments(outsider)
            with pytest.raises(PermissionDenied):
                assignment_service.get_assignment(outsider, item.assignment_id)

    def test_a_tutor_outside_the_caseload_sees_nothing_and_cannot_mark(self, cohort):
        item = _set(cohort)
        _submit(cohort, item)
        stranger = Actor(username="other-tutor", role="staff", staff_id=9999)
        assert assignment_service.list_assignments(stranger) == []
        assert assignment_service.marking_queue(stranger) == []
        with pytest.raises(PermissionDenied):
            assignment_service.mark(stranger, item.assignment_id, grade="Pass")

    def test_the_apprentice_sees_only_their_own(self, cohort, admin):
        other = apprentice_service.create_apprentice(
            admin, {"given_name": "Ali", "family_name": "Khan"}
        )
        theirs = assignment_service.set_assignment(admin, other.apprentice_id, {
            "title": "Theirs", "assignment_type": "Test",
        })
        mine = _set(cohort)
        assert [a.assignment_id for a in assignment_service.list_assignments(
            cohort["learner"])] == [mine.assignment_id]
        with pytest.raises(PermissionDenied):
            assignment_service.submit(cohort["learner"], theirs.assignment_id, body="Sneaky")

    def test_due_and_overdue_filters(self, cohort):
        late = _set(cohort, title="Late", due_date=_days(-2))
        soon = _set(cohort, title="Soon", due_date=_days(3))
        _set(cohort, title="Later", due_date=_days(40))
        tutor = cohort["tutor"]
        assert [a.assignment_id for a in assignment_service.list_assignments(
            tutor, overdue_only=True)] == [late.assignment_id]
        assert [a.assignment_id for a in assignment_service.list_assignments(
            tutor, due_within_days=config.ASSIGNMENT_DUE_SOON_DAYS)] == [
            late.assignment_id, soon.assignment_id,
        ]
        summary = assignment_service.assignment_summary(tutor)
        assert (summary["with_apprentice"], summary["overdue"], summary["due_soon"]) == (3, 1, 1)
