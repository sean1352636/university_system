"""Action plans: owners, priorities, carrying forward, and who may move what.

The rules are tested pure. Carrying forward and ownership run through the
services on the conftest's throwaway database, because an action that
lapses between reviews, or that the wrong person can tick off, is exactly
the failure the action plan exists to prevent.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.reviews import action_plans as rules
from education_system.systems.apprenticeships.domain.reviews.progress_reviews import ReviewTarget
from education_system.systems.apprenticeships.services import (
    action_plan_service,
    review_service,
)
from education_system.systems.apprenticeships.services.access import Actor, PermissionDenied

TODAY = date(2026, 9, 10)


def _target(**overrides) -> ReviewTarget:
    fields = dict(target_id=1, review_id=1, description="Write the report",
                  due_date="2026-12-01")
    fields.update(overrides)
    return ReviewTarget(**fields)


def _days(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestRag:
    def test_overdue_is_red_and_due_within_the_week_is_amber(self):
        assert _target(due_date="2026-09-09").rag(TODAY) == "Red"
        assert _target(due_date="2026-09-17").rag(TODAY) == "Amber"
        assert _target(due_date="2026-09-18").rag(TODAY) is None

    def test_due_today_is_amber_not_red(self):
        assert _target(due_date="2026-09-10").rag(TODAY) == "Amber"

    def test_met_is_green_and_other_closed_actions_are_untagged(self):
        assert _target(status="Met", due_date="2026-01-01").rag(TODAY) == "Green"
        assert _target(status="Not Met", due_date="2026-01-01").rag(TODAY) is None
        assert _target(status="Carried Forward", due_date="2026-01-01").rag(TODAY) is None

    def test_an_undated_action_is_never_overdue(self):
        undated = _target(due_date=None)
        assert not undated.overdue_on(TODAY)
        assert not undated.is_due_soon(TODAY)


class TestVocabulary:
    def test_owner_is_matched_ignoring_case_and_defaults_when_blank(self):
        assert rules.validate_owner("employer") == "Employer"
        assert rules.validate_owner("") == config.ACTION_DEFAULT_OWNER
        with pytest.raises(ValidationError, match="must be one of"):
            rules.validate_owner("Mentor")

    def test_priority_comes_from_the_list(self):
        assert rules.validate_priority("HIGH") == "High"
        assert rules.validate_priority(None) == config.ACTION_DEFAULT_PRIORITY
        with pytest.raises(ValidationError, match="must be one of"):
            rules.validate_priority("Urgent")

    def test_a_note_needs_words_and_a_limit(self):
        assert rules.validate_note("  Booked the course  ") == "Booked the course"
        with pytest.raises(ValidationError, match="empty"):
            rules.validate_note(" ")
        with pytest.raises(ValidationError, match="characters or fewer"):
            rules.validate_note("x" * (config.ACTION_NOTE_MAX_LENGTH + 1))


class TestWhoMayMove:
    @pytest.mark.parametrize(("role", "owner", "allowed"), [
        (config.ADMIN, "Employer", True),
        (config.STAFF, "Apprentice", True),
        (config.APPRENTICE, "Apprentice", True),
        (config.APPRENTICE, "Employer", False),
        (config.APPRENTICE, "Tutor", False),
        (config.EMPLOYER, "Employer", True),
        (config.EMPLOYER, "Apprentice", False),
        (config.END_POINT_ASSESSOR, "Apprentice", False),
    ])
    def test_owners_move_their_own_and_the_provider_moves_anything(self, role, owner, allowed):
        assert rules.may_move(role, owner) is allowed


class TestStatusMoves:
    def test_carried_forward_is_never_set_by_hand(self):
        with pytest.raises(ValidationError, match="not marked as carried by hand"):
            rules.require_action_status_move("Open", "Carried Forward")

    def test_a_carried_action_is_finished_with(self):
        with pytest.raises(ValidationError, match="carried forward to a later review"):
            rules.require_action_status_move("Carried Forward", "Met")

    def test_a_no_op_move_is_refused_and_reopening_is_allowed(self):
        with pytest.raises(ValidationError, match="already Met"):
            rules.require_action_status_move("Met", "Met")
        rules.require_action_status_move("Met", "Open")

    def test_completion_is_stamped_on_settling_kept_between_outcomes_and_cleared_on_reopen(self):
        assert rules.completed_at_after("Open", "Met", None, "T1") == "T1"
        assert rules.completed_at_after("Met", "Not Met", "T1", "T2") == "T1"
        assert rules.completed_at_after("Met", "Open", "T1", "T2") is None

    def test_the_carried_copy_keeps_what_was_agreed_and_counts_the_carry(self):
        original = _target(target_id=7, owner="Employer", priority="High", carry_count=1,
                           ksb_codes="S2")
        copy = rules.carry_payload(original, to_review_id=9)
        assert copy == {
            "review_id": 9, "description": "Write the report", "due_date": "2026-12-01",
            "ksb_codes": "S2", "owner": "Employer", "priority": "High", "status": "Open",
            "carried_from": 7, "carry_count": 2,
        }


# ═════════════════════════════════════════════════════════════════════
# Through the services
# ═════════════════════════════════════════════════════════════════════

def _held_review(cohort, *, days_ago: int = 90):
    """A review held *days_ago*, written up and awaiting signatures."""
    when = _days(-days_ago)
    review = review_service.schedule_review(cohort["tutor"], cohort["apprentice_id"],
                                            scheduled_date=when)
    return review_service.record_review(cohort["tutor"], review.review_id, {
        "held_date": when, "progress_rating": "Green",
    })


def _complete(cohort, review) -> None:
    for who in (cohort["tutor"], cohort["learner"], cohort["employer_actor"]):
        review_service.sign_review(who, review.review_id)


def _action(cohort, review, **overrides):
    payload = {"description": "Finish the network diagram", "due_date": _days(30)}
    payload.update(overrides)
    return review_service.add_target(cohort["tutor"], review.review_id, payload)


class TestActionFields:
    def test_a_new_action_defaults_to_the_apprentice_at_normal_priority(self, cohort):
        action = _action(cohort, _held_review(cohort))
        assert (action.owner, action.priority, action.status) == (
            config.ACTION_DEFAULT_OWNER, config.ACTION_DEFAULT_PRIORITY, "Open",
        )
        assert action.apprentice_name == "Jo Bell"

    def test_owner_and_priority_are_kept_and_can_be_edited(self, cohort):
        action = _action(cohort, _held_review(cohort), owner="employer", priority="high")
        assert (action.owner, action.priority) == ("Employer", "High")
        edited = review_service.update_target(cohort["tutor"], action.target_id,
                                              {"owner": "Tutor", "priority": "Low"})
        assert (edited.owner, edited.priority, edited.description) == (
            "Tutor", "Low", "Finish the network diagram",
        )

    def test_a_new_action_starts_open_whatever_the_form_posted(self, cohort):
        action = _action(cohort, _held_review(cohort), status="Met")
        assert action.status == "Open"
        assert action.completed_at is None

    def test_closing_stamps_completion_and_reopening_clears_it(self, cohort):
        action = _action(cohort, _held_review(cohort))
        closed = review_service.close_target(cohort["tutor"], action.target_id, status="Met")
        assert closed.completed_at
        reopened = review_service.update_target(cohort["tutor"], action.target_id,
                                                {"status": "Open"})
        assert (reopened.status, reopened.completed_at) == ("Open", None)

    def test_an_unknown_owner_is_refused(self, cohort):
        with pytest.raises(ValidationError, match="Action owner must be one of"):
            _action(cohort, _held_review(cohort), owner="Mentor")


class TestCarryingForward:
    def test_open_actions_follow_the_apprentice_into_the_next_review(self, cohort):
        first = _held_review(cohort)
        open_one = _action(cohort, first, description="Book the maths resit", owner="Apprentice")
        met_one = _action(cohort, first, description="Set up a mentor")
        review_service.close_target(cohort["tutor"], met_one.target_id, status="Met")
        _complete(cohort, first)

        second = review_service.schedule_next(cohort["tutor"], cohort["apprentice_id"])
        assert review_service.get_review(cohort["tutor"], second.review_id).targets == []

        started = review_service.start_review(cohort["tutor"], second.review_id)
        (copy,) = started.targets
        assert (copy.description, copy.status, copy.carried_from, copy.carry_count) == (
            "Book the maths resit", "Open", open_one.target_id, 1,
        )
        original = action_plan_service.get_action(cohort["tutor"], open_one.target_id)
        assert original.status == "Carried Forward"
        assert "Carried forward to the review of" in (original.outcome_note or "")
        settled = action_plan_service.get_action(cohort["tutor"], met_one.target_id)
        assert settled.status == "Met"

    def test_carrying_is_idempotent(self, cohort):
        first = _held_review(cohort)
        _action(cohort, first)
        _complete(cohort, first)
        second = review_service.schedule_next(cohort["tutor"], cohort["apprentice_id"])
        review_service.start_review(cohort["tutor"], second.review_id)
        assert review_service.carry_forward(cohort["tutor"], second.review_id) == []
        review_service.record_review(cohort["tutor"], second.review_id, {"summary": "Fine"})
        assert len(review_service.get_review(cohort["tutor"], second.review_id).targets) == 1

    def test_actions_on_a_later_review_are_not_pulled_backwards(self, cohort):
        earlier = review_service.schedule_review(
            cohort["tutor"], cohort["apprentice_id"], scheduled_date=_days(-10)
        )
        later = review_service.schedule_review(
            cohort["tutor"], cohort["apprentice_id"], scheduled_date=_days(60)
        )
        pending = _action(cohort, later)
        assert review_service.carry_forward(cohort["tutor"], earlier.review_id) == []
        assert action_plan_service.get_action(cohort["tutor"], pending.target_id).review_id == (
            later.review_id
        )

    def test_closing_as_carried_forward_moves_it_onto_the_next_review_now(self, cohort):
        first = _held_review(cohort)
        action = _action(cohort, first)
        _complete(cohort, first)
        second = review_service.schedule_next(cohort["tutor"], cohort["apprentice_id"])

        closed = review_service.close_target(cohort["tutor"], action.target_id,
                                             status="Carried Forward", note="Course full")
        assert closed.status == "Carried Forward"
        assert "Course full" in closed.outcome_note
        (copy,) = review_service.get_review(cohort["tutor"], second.review_id).targets
        assert copy.carried_from == action.target_id
        # Starting the review later does not carry it a second time.
        review_service.start_review(cohort["tutor"], second.review_id)
        assert len(review_service.get_review(cohort["tutor"], second.review_id).targets) == 1

    def test_carrying_with_no_later_review_is_refused(self, cohort):
        action = _action(cohort, _held_review(cohort))
        with pytest.raises(ValidationError, match="no later review"):
            review_service.close_target(cohort["tutor"], action.target_id,
                                        status="Carried Forward")
        assert action_plan_service.get_action(cohort["tutor"], action.target_id).is_open

    def test_the_carry_count_grows_each_time_an_action_slips(self, cohort):
        first = _held_review(cohort, days_ago=180)
        _action(cohort, first)
        _complete(cohort, first)
        second = review_service.schedule_next(cohort["tutor"], cohort["apprentice_id"])
        (copy_one,) = review_service.start_review(cohort["tutor"], second.review_id).targets
        review_service.record_review(cohort["tutor"], second.review_id,
                                     {"held_date": second.scheduled_date})
        _complete(cohort, second)
        third = review_service.schedule_next(cohort["tutor"], cohort["apprentice_id"])
        (copy_two,) = review_service.start_review(cohort["tutor"], third.review_id).targets
        assert (copy_two.carry_count, copy_two.carried_from) == (2, copy_one.target_id)
        assert copy_two.is_carried

    def test_a_carried_action_cannot_be_moved_or_annotated(self, cohort):
        first = _held_review(cohort)
        action = _action(cohort, first)
        _complete(cohort, first)
        review_service.start_review(
            cohort["tutor"], review_service.schedule_next(cohort["tutor"],
                                                          cohort["apprentice_id"]).review_id
        )
        with pytest.raises(ValidationError, match="carried forward"):
            action_plan_service.update_status(cohort["learner"], action.target_id, status="Met")
        with pytest.raises(ValidationError, match="carried forward"):
            action_plan_service.add_note(cohort["learner"], action.target_id, "Done it")

    def test_the_history_follows_the_action_across_reviews(self, cohort):
        first = _held_review(cohort)
        action = _action(cohort, first)
        action_plan_service.add_note(cohort["learner"], action.target_id, "Emailed the college")
        _complete(cohort, first)
        second = review_service.schedule_next(cohort["tutor"], cohort["apprentice_id"])
        (copy,) = review_service.start_review(cohort["tutor"], second.review_id).targets
        action_plan_service.add_note(cohort["learner"], copy.target_id, "Place confirmed")
        bodies = [n.body for n in action_plan_service.history(cohort["learner"], copy.target_id)]
        assert bodies == ["Place confirmed", "Emailed the college"]


class TestWhoMayMoveWhat:
    def test_the_apprentice_moves_their_own_action_and_the_move_is_recorded(self, cohort):
        action = _action(cohort, _held_review(cohort), owner="Apprentice")
        moved = action_plan_service.update_status(
            cohort["learner"], action.target_id, status="Met", note="Handed it in"
        )
        assert moved.status == "Met" and moved.completed_at
        (entry,) = action_plan_service.history(cohort["learner"], action.target_id)
        assert (entry.from_status, entry.to_status, entry.body, entry.author_role) == (
            "Open", "Met", "Handed it in", "apprentice",
        )

    def test_a_move_with_no_words_still_says_what_moved(self, cohort):
        action = _action(cohort, _held_review(cohort))
        action_plan_service.update_status(cohort["learner"], action.target_id, status="Not Met")
        (entry,) = action_plan_service.history(cohort["tutor"], action.target_id)
        assert entry.body == "Status changed from Open to Not Met"

    def test_the_apprentice_cannot_move_the_employers_action(self, cohort):
        action = _action(cohort, _held_review(cohort), owner="Employer")
        with pytest.raises(PermissionDenied, match="employer's to do"):
            action_plan_service.update_status(cohort["learner"], action.target_id, status="Met")
        with pytest.raises(PermissionDenied):
            action_plan_service.add_note(cohort["learner"], action.target_id, "Nudged them")

    def test_the_employer_moves_employer_actions_only(self, cohort):
        review = _held_review(cohort)
        theirs = _action(cohort, review, owner="Employer")
        not_theirs = _action(cohort, review, owner="Apprentice")
        assert action_plan_service.update_status(
            cohort["employer_actor"], theirs.target_id, status="Met"
        ).status == "Met"
        with pytest.raises(PermissionDenied):
            action_plan_service.update_status(
                cohort["employer_actor"], not_theirs.target_id, status="Met"
            )

    def test_the_tutor_moves_anything_on_their_caseload(self, cohort):
        action = _action(cohort, _held_review(cohort), owner="Employer")
        assert action_plan_service.update_status(
            cohort["tutor"], action.target_id, status="Met"
        ).status == "Met"

    def test_another_organisation_sees_and_moves_nothing(self, cohort):
        action = _action(cohort, _held_review(cohort), owner="Employer")
        outsider = cohort["outsider"]
        assert action_plan_service.list_actions(outsider) == []
        with pytest.raises(PermissionDenied):
            action_plan_service.get_action(outsider, action.target_id)
        with pytest.raises(PermissionDenied):
            action_plan_service.update_status(outsider, action.target_id, status="Met")

    def test_a_tutor_outside_the_caseload_sees_nothing(self, cohort):
        _action(cohort, _held_review(cohort))
        stranger = Actor(username="other-tutor", role="staff", staff_id=9999)
        assert action_plan_service.list_actions(stranger) == []

    def test_the_end_point_assessor_is_kept_out_of_the_action_plan(self, cohort, assessor):
        action = _action(cohort, _held_review(cohort))
        with pytest.raises(PermissionDenied):
            action_plan_service.list_actions(assessor)
        with pytest.raises(PermissionDenied):
            action_plan_service.update_status(assessor, action.target_id, status="Met")

    def test_only_those_who_conduct_reviews_add_actions(self, cohort):
        review = _held_review(cohort)
        for who in (cohort["learner"], cohort["employer_actor"]):
            with pytest.raises(PermissionDenied):
                action_plan_service.add_action(who, review.review_id, {"description": "Mine"})


class TestListing:
    def test_overdue_and_due_soon_filters(self, cohort):
        review = _held_review(cohort)
        late = _action(cohort, review, description="Late", due_date=_days(-2))
        soon = _action(cohort, review, description="Soon", due_date=_days(3))
        _action(cohort, review, description="Later", due_date=_days(40))
        tutor = cohort["tutor"]
        assert [a.target_id for a in action_plan_service.list_actions(
            tutor, overdue_only=True)] == [late.target_id]
        assert [a.target_id for a in action_plan_service.list_actions(
            tutor, due_within_days=config.ACTION_DUE_SOON_DAYS)] == [late.target_id,
                                                                       soon.target_id]

    def test_mine_only_follows_the_actors_role(self, cohort):
        review = _held_review(cohort)
        _action(cohort, review, owner="Apprentice")
        employer_one = _action(cohort, review, owner="Employer")
        mine = action_plan_service.list_actions(cohort["employer_actor"], mine_only=True)
        assert [a.target_id for a in mine] == [employer_one.target_id]

    def test_the_apprentice_filter_cannot_widen_an_employers_scope(self, cohort, admin):
        from education_system.systems.apprenticeships.services import apprentice_service

        other = apprentice_service.create_apprentice(
            admin, {"given_name": "Ali", "family_name": "Khan"}
        )
        with pytest.raises(PermissionDenied):
            action_plan_service.list_actions(cohort["employer_actor"],
                                             apprentice_id=other.apprentice_id)

    def test_the_summary_counts_open_actions(self, cohort):
        review = _held_review(cohort)
        _action(cohort, review, due_date=_days(-1))
        _action(cohort, review, due_date=_days(2), owner="Employer")
        done = _action(cohort, review)
        review_service.close_target(cohort["tutor"], done.target_id, status="Met")
        summary = action_plan_service.action_summary(cohort["employer_actor"])
        assert summary == {"open": 2, "overdue": 1, "due_soon": 1, "mine": 1, "carried": 0}

    def test_the_repository_answers_what_is_due_in_a_scope_in_one_call(self, cohort):
        from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (  # noqa: E501
            review_repository,
        )

        review = _held_review(cohort)
        _action(cohort, review, due_date=_days(-1))
        _action(cohort, review, due_date=_days(90))
        assert review_repository.count_targets(
            tutor_id=cohort["tutor_id"], open_only=True, due_before=_days(7)
        ) == 1
        assert review_repository.count_targets(
            employer_id=cohort["employer"].employer_id, overdue_on=date.today().isoformat()
        ) == 1
