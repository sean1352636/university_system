"""The individual learning plan: objectives, progress, activities and comments.

The rules are tested pure. Building and discussing a plan runs through
the services on the conftest's throwaway database, because who may do
what to a plan is most of what makes it trustworthy.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.training import learning_plan as rules
from education_system.systems.apprenticeships.domain.training.learning_plan import (
    LearningObjective,
    LearningPlan,
)
from education_system.systems.apprenticeships.domain.training.sessions import TrainingPlanItem
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.learning import (
    learning_plan_service,
    training_service,
)
from education_system.systems.apprenticeships.application.security.access import PermissionDenied

TODAY = date(2026, 9, 10)


def _objective(**overrides) -> LearningObjective:
    fields = dict(
        objective_id=1, apprentice_id=1, title="Configure a small network",
        target_date="2026-12-01", status="In progress", progress=40,
    )
    fields.update(overrides)
    return LearningObjective(**fields)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestStatusAndProgress:
    @pytest.mark.parametrize(("status", "progress", "expected"), [
        ("Not started", 0, ("Not started", 0)),
        ("Not started", 30, ("In progress", 30)),
        ("In progress", 100, ("Achieved", 100)),
        ("Achieved", 60, ("Achieved", 100)),
        ("Deferred", 100, ("Deferred", 100)),
    ])
    def test_status_and_progress_are_made_to_agree(self, status, progress, expected):
        assert rules.settle(status, progress) == expected

    def test_lowering_progress_reopens_an_achieved_objective(self):
        assert rules.status_after_progress("Achieved", 70) == ("In progress", 70)

    def test_an_explicit_status_wins(self):
        assert rules.status_after_progress("In progress", 50, "Deferred") == ("Deferred", 50)

    @pytest.mark.parametrize(("value", "expected"), [
        ("45", 45), ("45%", 45), (" 99.6 ", 100), ("", 0), (None, 0), (80, 80),
    ])
    def test_progress_is_a_whole_percentage(self, value, expected):
        assert rules.validate_progress(value) == expected

    @pytest.mark.parametrize("value", ["-1", "101", "lots"])
    def test_progress_outside_0_to_100_is_refused(self, value):
        with pytest.raises(ValidationError, match="0 to 100"):
            rules.validate_progress(value)

    def test_objective_status_is_matched_ignoring_case(self):
        assert rules.validate_objective_status("in PROGRESS") == "In progress"
        with pytest.raises(ValidationError, match="must be one of"):
            rules.validate_objective_status("Nearly")


class TestObjective:
    def test_rag_follows_the_target_date(self):
        assert _objective(target_date="2026-09-01").rag(TODAY) == "Red"
        assert _objective(target_date="2026-09-20").rag(TODAY) == "Amber"
        assert _objective(target_date="2026-12-01").rag(TODAY) == "Green"

    def test_an_achieved_objective_is_green_whatever_the_date(self):
        assert _objective(status="Achieved", target_date="2026-01-01").rag(TODAY) == "Green"

    def test_a_deferred_objective_is_not_judged(self):
        paused = _objective(status="Deferred", target_date="2026-01-01")
        assert paused.rag(TODAY) is None
        assert not paused.is_overdue(TODAY)


class TestPlan:
    plan = LearningPlan(
        apprentice_id=1,
        objectives=[
            _objective(objective_id=1, progress=50, target_date="2026-10-01"),
            _objective(objective_id=2, status="Achieved", progress=100,
                       target_date="2026-06-01"),
            _objective(objective_id=3, status="Withdrawn", progress=0,
                       target_date="2026-08-01"),
            _objective(objective_id=4, progress=20, target_date="2026-09-01"),
        ],
        activities=[
            TrainingPlanItem(item_id=1, apprentice_id=1, title="Cabling", objective_id=1),
            TrainingPlanItem(item_id=2, apprentice_id=1, title="Induction"),
        ],
    )

    def test_withdrawn_objectives_do_not_count_towards_progress(self):
        assert self.plan.overall_progress == 56.7   # (50 + 100 + 20) / 3
        assert self.plan.achieved == 1

    def test_overdue_and_next_target(self):
        assert [o.objective_id for o in self.plan.overdue(TODAY)] == [4]
        assert self.plan.next_target(TODAY).objective_id == 4

    def test_activities_hang_off_their_objective(self):
        assert [a.title for a in self.plan.activities_for(1)] == ["Cabling"]
        assert [a.title for a in self.plan.unlinked_activities] == ["Induction"]


class TestCommentsAndActivityStatuses:
    def test_a_comment_needs_words_and_a_limit(self):
        assert rules.validate_comment("  Going well  ") == "Going well"
        with pytest.raises(ValidationError, match="empty"):
            rules.validate_comment("   ")
        with pytest.raises(ValidationError, match="characters or fewer"):
            rules.validate_comment("x" * (config.PLAN_COMMENT_MAX_LENGTH + 1))

    def test_activity_status_comes_from_the_list(self):
        assert rules.validate_plan_item_status("in progress") == "In Progress"
        assert rules.validate_plan_item_status(None) == "Planned"
        with pytest.raises(ValidationError, match="must be one of"):
            rules.validate_plan_item_status("Bogus")

    def test_an_older_free_text_status_survives_an_edit(self):
        assert rules.validate_plan_item_status("On hold", current="On hold") == "On hold"
        assert rules.validate_plan_item_status("", current="Complete") == "Complete"


# ═════════════════════════════════════════════════════════════════════
# Through the services
# ═════════════════════════════════════════════════════════════════════

def _add(actor, cohort, **overrides):
    payload = {
        "title": "Build a small network",
        "ksb_codes": "K1, S1",
        "target_date": (date.today() + timedelta(days=60)).isoformat(),
    }
    payload.update(overrides)
    return learning_plan_service.add_objective(actor, cohort["apprentice_id"], payload)


class TestBuildingAPlan:
    def test_a_tutor_puts_an_activity_under_an_objective(self, cohort):
        tutor, aid = cohort["tutor"], cohort["apprentice_id"]
        objective = _add(tutor, cohort)
        item = training_service.add_plan_item(tutor, aid, {
            "title": "Cabling workshop", "objective_id": objective.objective_id,
        })
        plan = learning_plan_service.get_plan(tutor, aid)
        assert [a.item_id for a in plan.activities_for(objective.objective_id)] == [item.item_id]
        assert objective.created_by == "tutor1"

    def test_an_activity_cannot_deliver_another_apprentices_objective(self, cohort, admin):
        other = apprentice_service.create_apprentice(
            admin, {"given_name": "Ali", "family_name": "Khan"}
        )
        theirs = learning_plan_service.add_objective(
            admin, other.apprentice_id, {"title": "Their objective"}
        )
        with pytest.raises(ValidationError, match="different apprentice"):
            training_service.add_plan_item(admin, cohort["apprentice_id"], {
                "title": "Mine", "objective_id": theirs.objective_id,
            })

    def test_new_activity_statuses_come_from_the_list(self, cohort, admin):
        with pytest.raises(ValidationError, match="must be one of"):
            training_service.add_plan_item(
                admin, cohort["apprentice_id"], {"title": "Odd one", "status": "Bogus"}
            )

    def test_deleting_an_objective_keeps_its_activities(self, cohort, admin):
        objective = _add(admin, cohort)
        item = training_service.add_plan_item(admin, cohort["apprentice_id"], {
            "title": "Cabling workshop", "objective_id": objective.objective_id,
        })
        learning_plan_service.delete_objective(admin, objective.objective_id, reason="Duplicate")
        plan = learning_plan_service.get_plan(admin, cohort["apprentice_id"])
        assert plan.objectives == []
        assert [a.item_id for a in plan.activities] == [item.item_id]


class TestProgress:
    def test_reaching_100_achieves_it_and_leaves_a_history(self, cohort, admin):
        objective = _add(admin, cohort)
        updated = learning_plan_service.record_progress(
            admin, objective.objective_id, progress=100, comment="Network built and documented",
        )
        assert (updated.status, updated.progress) == ("Achieved", 100)
        assert updated.achieved_at == date.today().isoformat()
        plan = learning_plan_service.get_plan(admin, cohort["apprentice_id"])
        (entry,) = plan.comments_for(objective.objective_id)
        assert (entry.progress, entry.body, entry.author_role) == (
            100, "Network built and documented", "admin",
        )

    def test_an_update_with_no_words_still_says_what_moved(self, cohort, admin):
        objective = _add(admin, cohort)
        updated = learning_plan_service.record_progress(admin, objective.objective_id, progress=30)
        assert updated.status == "In progress"
        plan = learning_plan_service.get_plan(admin, cohort["apprentice_id"])
        assert plan.comments_for(objective.objective_id)[0].body == "Progress updated to 30%"

    def test_editing_progress_down_reopens_an_achieved_objective(self, cohort, admin):
        objective = _add(admin, cohort, status="Achieved")
        assert objective.progress == 100
        reopened = learning_plan_service.update_objective(
            admin, objective.objective_id, {"progress": 60}
        )
        assert (reopened.status, reopened.progress, reopened.achieved_at) == (
            "In progress", 60, None,
        )


class TestWhoMayDoWhat:
    def test_the_apprentice_and_employer_can_comment_but_not_rewrite(self, cohort, admin):
        aid = cohort["apprentice_id"]
        mine = learning_plan_service.add_comment(cohort["learner"], aid, "I'd like more on VLANs")
        theirs = learning_plan_service.add_comment(
            cohort["employer_actor"], aid, "Happy to release Jo on Fridays"
        )
        assert (mine.author_role, theirs.author_role) == ("apprentice", "employer")
        with pytest.raises(PermissionDenied):
            learning_plan_service.add_objective(cohort["learner"], aid, {"title": "Mine now"})

    def test_the_end_point_assessor_cannot_see_the_plan(self, cohort, assessor):
        with pytest.raises(PermissionDenied):
            learning_plan_service.get_plan(assessor, cohort["apprentice_id"])

    def test_another_employer_cannot_see_the_plan(self, cohort):
        with pytest.raises(PermissionDenied):
            learning_plan_service.get_plan(cohort["outsider"], cohort["apprentice_id"])

    def test_a_comment_must_be_about_an_objective_on_this_plan(self, cohort, admin):
        other = apprentice_service.create_apprentice(
            admin, {"given_name": "Ali", "family_name": "Khan"}
        )
        theirs = learning_plan_service.add_objective(
            admin, other.apprentice_id, {"title": "Their objective"}
        )
        with pytest.raises(ValidationError, match="not on this apprentice's plan"):
            learning_plan_service.add_comment(
                admin, cohort["apprentice_id"], "Wrong plan",
                objective_id=theirs.objective_id,
            )

    def test_the_apprentice_can_read_their_review_history(self, cohort):
        assert learning_plan_service.review_history(
            cohort["learner"], cohort["apprentice_id"]
        ) == []
