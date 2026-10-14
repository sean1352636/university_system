"""The curriculum builder, and applying a curriculum to a learning plan.

Applying must be idempotent: running it twice, or after a module is
added, never duplicates an objective already on the plan.
"""

from __future__ import annotations

import pytest

from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.programmes import curriculum as rules
from education_system.systems.apprenticeships.domain.programmes.curriculum import (
    ProgrammeModule,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    staff_repository,
)
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    learning_plan_service,
    programme_service,
)
from education_system.systems.apprenticeships.services.access import Actor, PermissionDenied


def _module(module_id, stage, position, title="M"):
    return ProgrammeModule(module_id=module_id, programme_id=1, title=f"{title}{module_id}",
                           stage=stage, position=position)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestRules:
    def test_a_module_needs_a_title_and_a_stage(self):
        with pytest.raises(ValidationError, match="title"):
            rules.validate_title("  ")
        with pytest.raises(ValidationError, match="stage"):
            rules.validate_stage("")

    @pytest.mark.parametrize(("value", "expected"), [("", 1), (None, 1), ("3", 3)])
    def test_position(self, value, expected):
        assert rules.validate_position(value) == expected

    def test_position_and_hours_are_bounded(self):
        with pytest.raises(ValidationError, match="1 or more"):
            rules.validate_position("0")
        with pytest.raises(ValidationError, match="from 0"):
            rules.validate_planned_hours("-1")
        assert rules.validate_planned_hours("12.5") == 12.5

    def test_ksb_codes_are_normalised_and_checked(self):
        assert rules.normalise_ksb_codes("k1, s2 K1") == "K1, S2"
        assert rules.normalise_ksb_codes("") is None
        with pytest.raises(ValidationError, match="not a KSB on this standard"):
            rules.normalise_ksb_codes("K9", {"K1"})

    def test_stages_run_in_the_order_their_modules_do(self):
        modules = [_module(1, "Year 2", 5), _module(2, "Year 1", 1), _module(3, "Year 1", 9)]
        assert rules.stage_order(modules) == ["Year 1", "Year 2"]
        assert [m.module_id for m in rules.ordered(modules)] == [2, 3, 1]

    def test_the_programme_dates_are_split_across_the_stages(self):
        windows = rules.stage_windows(["Year 1", "Year 2"], "2026-01-01", "2027-01-01")
        assert windows["Year 1"] == ("2026-01-01", "2026-07-02")
        assert windows["Year 2"][1] == "2027-01-01"
        assert rules.stage_windows(["Year 1"], None, "2027-01-01") == {}

    def test_titles_match_ignoring_case_and_spacing(self):
        assert rules.title_key("  Team   Working ") == rules.title_key("team working")


# ═════════════════════════════════════════════════════════════════════
# Building the curriculum
# ═════════════════════════════════════════════════════════════════════

def _add(admin, cohort, title, **extra):
    payload = {"title": title, "stage": "Year 1"}
    payload.update(extra)
    return programme_service.add_module(admin, cohort["programme"].programme_id, payload)


class TestBuilding:
    def test_modules_are_placed_last_unless_told_otherwise(self, cohort, admin):
        first = _add(admin, cohort, "Coding")
        second = _add(admin, cohort, "Testing")
        assert (first.position, second.position) == (1, 2)

    def test_ksbs_must_belong_to_the_standard(self, cohort, admin):
        assert _add(admin, cohort, "Coding", ksb_codes="k1,s1").ksb_codes == "K1, S1"
        with pytest.raises(ValidationError, match="not a KSB"):
            _add(admin, cohort, "Other", ksb_codes="K7")

    def test_a_title_is_used_once_per_standard(self, cohort, admin):
        _add(admin, cohort, "Coding")
        with pytest.raises(ValidationError, match="already a module"):
            _add(admin, cohort, "coding")

    def test_modules_list_in_delivery_order(self, cohort, admin):
        _add(admin, cohort, "Later", stage="Year 2", position=1)
        _add(admin, cohort, "Sooner", stage="Year 1", position=2)
        titles = [m.title for m in programme_service.list_modules(
            admin, cohort["programme"].programme_id)]
        assert titles == ["Later", "Sooner"]  # Year 2 starts at position 1

    def test_editing_and_deleting_a_module(self, cohort, admin):
        module = _add(admin, cohort, "Coding")
        updated = programme_service.update_module(admin, module.module_id, {"planned_hours": 30})
        assert updated.planned_hours == 30.0
        programme_service.delete_module(admin, module.module_id, reason="Merged")
        assert programme_service.list_modules(admin, cohort["programme"].programme_id) == []

    def test_a_tutor_cannot_change_the_curriculum(self, cohort):
        with pytest.raises(PermissionDenied):
            _add(cohort["tutor"], cohort, "Coding")


# ═════════════════════════════════════════════════════════════════════
# Applying it to a learning plan
# ═════════════════════════════════════════════════════════════════════

class TestApplying:
    def test_one_objective_per_module_and_an_activity_for_planned_hours(self, cohort, admin):
        _add(admin, cohort, "Coding", ksb_codes="K1", planned_hours=40)
        _add(admin, cohort, "Teamwork", stage="Year 2")
        result = programme_service.apply_curriculum(admin, cohort["apprentice_id"])
        plan = learning_plan_service.get_plan(admin, cohort["apprentice_id"])

        assert result.created == ["Coding", "Teamwork"]
        assert [o.title for o in plan.objectives] == ["Coding", "Teamwork"]
        (activity,) = plan.activities
        coding = next(o for o in plan.objectives if o.title == "Coding")
        assert (activity.objective_id, activity.planned_hours) == (coding.objective_id, 40.0)
        assert coding.ksb_codes == "K1"

    def test_targets_follow_the_stages(self, cohort, admin):
        _add(admin, cohort, "Coding")
        _add(admin, cohort, "Teamwork", stage="Year 2")
        programme_service.apply_curriculum(admin, cohort["apprentice_id"])
        targets = {o.title: o.target_date for o in learning_plan_service.get_plan(
            admin, cohort["apprentice_id"]).objectives}
        record = cohort["apprentice"]
        assert record.start_date < targets["Coding"] < targets["Teamwork"]
        assert targets["Teamwork"] == record.planned_end_date

    def test_applying_again_adds_nothing(self, cohort, admin):
        _add(admin, cohort, "Coding", planned_hours=10)
        programme_service.apply_curriculum(admin, cohort["apprentice_id"])
        again = programme_service.apply_curriculum(admin, cohort["apprentice_id"])
        plan = learning_plan_service.get_plan(admin, cohort["apprentice_id"])
        assert (again.created, again.skipped) == ([], ["Coding"])
        assert (len(plan.objectives), len(plan.activities)) == (1, 1)

    def test_a_module_added_later_is_applied_on_the_next_run(self, cohort, admin):
        _add(admin, cohort, "Coding")
        programme_service.apply_curriculum(admin, cohort["apprentice_id"])
        _add(admin, cohort, "Security")
        result = programme_service.apply_curriculum(admin, cohort["apprentice_id"])
        assert (result.created, result.skipped) == (["Security"], ["Coding"])

    def test_an_objective_already_on_the_plan_is_linked_not_duplicated(self, cohort, admin):
        learning_plan_service.add_objective(admin, cohort["apprentice_id"], {"title": "coding"})
        _add(admin, cohort, "Coding")
        result = programme_service.apply_curriculum(admin, cohort["apprentice_id"])
        assert (result.created, result.linked) == ([], ["Coding"])
        assert len(learning_plan_service.get_plan(admin, cohort["apprentice_id"]).objectives) == 1

    def test_a_deleted_objective_is_not_put_back(self, cohort, admin):
        _add(admin, cohort, "Coding")
        programme_service.apply_curriculum(admin, cohort["apprentice_id"])
        (objective,) = learning_plan_service.get_plan(admin, cohort["apprentice_id"]).objectives
        learning_plan_service.delete_objective(admin, objective.objective_id, reason="Not needed")
        result = programme_service.apply_curriculum(admin, cohort["apprentice_id"])
        assert result.skipped == ["Coding"]
        assert learning_plan_service.get_plan(admin, cohort["apprentice_id"]).objectives == []

    def test_the_tutor_may_apply_it_to_their_own_caseload(self, cohort, admin):
        _add(admin, cohort, "Coding")
        result = programme_service.apply_curriculum(cohort["tutor"], cohort["apprentice_id"])
        assert result.created == ["Coding"]

    def test_nobody_else_may(self, cohort, admin):
        _add(admin, cohort, "Coding")
        other_id = staff_repository.create({"full_name": "Other", "username": "tutor2"})
        other = Actor(username="tutor2", role="staff", staff_id=other_id)
        with pytest.raises(PermissionDenied):
            programme_service.apply_curriculum(other, cohort["apprentice_id"])
        with pytest.raises(PermissionDenied):
            programme_service.apply_curriculum(cohort["employer_actor"], cohort["apprentice_id"])

    def test_an_apprentice_needs_a_programme(self, cohort, admin):
        loose = apprentice_service.create_apprentice(
            admin, {"given_name": "No", "family_name": "Programme"}
        )
        with pytest.raises(ValidationError, match="not on a programme"):
            programme_service.apply_curriculum(admin, loose.apprentice_id)

    def test_a_programme_needs_modules(self, cohort, admin):
        with pytest.raises(ValidationError, match="no curriculum modules"):
            programme_service.apply_curriculum(admin, cohort["apprentice_id"])

    def test_applying_to_everyone_on_the_programme(self, cohort, admin):
        _add(admin, cohort, "Coding")
        results = programme_service.apply_curriculum_to_cohort(
            admin, cohort["programme"].programme_id
        )
        assert [(r.apprentice_id, r.created) for r in results] == [
            (cohort["apprentice_id"], ["Coding"]),
        ]
