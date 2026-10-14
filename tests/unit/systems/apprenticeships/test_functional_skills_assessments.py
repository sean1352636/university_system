"""Functional skills: initial and diagnostic assessments beside the current position.

The rules — what counts as below target, what an assessment must carry —
are tested pure. Recording and reading run through the services on the
conftest's throwaway database, because who may record an assessment,
and who may change the gateway position, is most of the feature.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.compliance.eligibility import (
    FunctionalSkill,
)
from education_system.systems.apprenticeships.domain.learner_support import (
    skills_assessments as rules,
)
from education_system.systems.apprenticeships.domain.learner_support.skills_assessments import (
    SkillsAssessment,
    SkillsProfile,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    compliance_repository,
)
from education_system.systems.apprenticeships.services import skills_service
from education_system.systems.apprenticeships.services.access import Actor, PermissionDenied

TODAY = date(2026, 9, 10)


def _assessment(**overrides) -> SkillsAssessment:
    fields = dict(
        assessment_id=1, apprentice_id=1, subject="Maths", kind="Initial",
        assessed_on="2026-01-10", level="Level 1",
    )
    fields.update(overrides)
    return SkillsAssessment(**fields)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestVocabulary:
    def test_digital_is_assessed_but_is_not_a_gateway_subject(self):
        """Gateway and compliance read FUNCTIONAL_SKILLS; Digital must stay out of it."""
        assert "Digital" in config.SKILLS_ASSESSMENT_SUBJECTS
        assert "Digital" not in config.FUNCTIONAL_SKILLS
        assert set(config.FUNCTIONAL_SKILLS) <= set(config.SKILLS_ASSESSMENT_SUBJECTS)


class TestBelowTarget:
    @pytest.mark.parametrize(("level", "below"), [
        ("Entry 3", True), ("Level 1", True), ("Level 2", False), ("Level 3", False),
        (None, False), ("Something else", False),
    ])
    def test_judged_against_the_gateway_level(self, level, below):
        assert rules.is_below(level, config.SKILLS_TARGET_LEVEL) is below

    def test_digital_is_never_below_target(self):
        assert not _assessment(subject="Digital", level="Entry 1").is_below_target

    def test_an_english_placing_below_level_2_is_flagged(self):
        assert _assessment(subject="English", level="Entry 3").is_below_target


class TestValidation:
    @pytest.mark.parametrize(("value", "expected"), [
        ("62", 62.0), ("62.44%", 62.4), ("", None), (None, None), (0, 0.0),
    ])
    def test_a_score_is_a_percentage(self, value, expected):
        assert rules.validate_score(value) == expected

    @pytest.mark.parametrize("value", ["-1", "101", "most"])
    def test_a_score_outside_0_to_100_is_refused(self, value):
        with pytest.raises(ValidationError, match="Score"):
            rules.validate_score(value)

    def test_an_assessment_cannot_be_dated_in_the_future(self):
        with pytest.raises(ValidationError, match="future"):
            rules.validate_assessed_on("2026-09-11", TODAY)
        assert rules.validate_assessed_on("2026-09-10", TODAY) == "2026-09-10"

    def test_an_assessment_has_to_have_found_something(self):
        with pytest.raises(ValidationError, match="level"):
            rules.require_result(None, None)
        rules.require_result(None, 55.0)
        rules.require_result("Entry 2", None)

    def test_subject_and_kind_are_matched_ignoring_case(self):
        assert rules.validate_subject("digital") == "Digital"
        assert rules.validate_kind("DIAGNOSTIC") == "Diagnostic"
        with pytest.raises(ValidationError, match="must be one of"):
            rules.validate_subject("Science")


class TestProfile:
    profile = SkillsProfile(
        apprentice_id=1,
        skills=[
            FunctionalSkill(subject="English", status="Exempt"),
            FunctionalSkill(subject="Maths", status="In progress"),
        ],
        assessments=[
            _assessment(assessment_id=3, subject="Maths", kind="Diagnostic",
                        assessed_on="2026-03-01", level="Level 1"),
            _assessment(assessment_id=2, subject="English", level="Entry 3"),
            _assessment(assessment_id=1, subject="Maths", level="Entry 3"),
        ],
    )

    def test_study_is_needed_only_where_the_subject_is_not_yet_satisfied(self):
        """English was assessed low, but an exemption means no study."""
        assert self.profile.needs_study == ["Maths"]

    def test_the_latest_assessment_of_a_kind(self):
        assert self.profile.latest("Maths").assessment_id == 3
        assert self.profile.latest("Maths", "Initial").assessment_id == 1

    def test_starting_points_and_gaps(self):
        assert self.profile.starting_points() == {
            "English": "Entry 3", "Maths": "Entry 3", "Digital": None,
        }
        assert self.profile.unassessed == ["Digital"]
        assert not self.profile.gateway_satisfied
        assert self.profile.outstanding == ["Maths"]


# ═════════════════════════════════════════════════════════════════════
# Through the services
# ═════════════════════════════════════════════════════════════════════

def _record(actor, cohort, **overrides):
    payload = {
        "subject": "Maths", "kind": "Initial",
        "assessed_on": (date.today() - timedelta(days=30)).isoformat(),
        "level": "Entry 3", "score": "48",
    }
    payload.update(overrides)
    return skills_service.record_assessment(actor, cohort["apprentice_id"], payload)


class TestRecording:
    def test_a_tutor_records_an_assessment_the_apprentice_can_see(self, cohort):
        created = _record(cohort["tutor"], cohort)
        assert (created.assessed_by, created.level, created.score) == ("tutor1", "Entry 3", 48.0)

        profile = skills_service.get_profile(cohort["learner"], cohort["apprentice_id"])
        assert [a.assessment_id for a in profile.assessments] == [created.assessment_id]
        assert profile.needs_study == ["Maths"]
        # The current position comes from compliance, blank until someone sets it.
        assert [s.subject for s in profile.skills] == list(config.FUNCTIONAL_SKILLS)

    def test_every_write_is_audited(self, cohort, admin):
        created = _record(admin, cohort)
        skills_service.update_assessment(admin, created.assessment_id, {"notes": "Calculator"})
        skills_service.delete_assessment(admin, created.assessment_id, reason="Duplicate")
        actions = [e.action for e in compliance_repository.list_audit(entity="skills_assessment")]
        assert sorted(actions) == ["create", "delete", "update"]

    def test_a_partial_edit_keeps_the_rest(self, cohort, admin):
        created = _record(admin, cohort)
        updated = skills_service.update_assessment(
            admin, created.assessment_id, {"notes": "Struggled with fractions"}
        )
        assert (updated.level, updated.score, updated.notes) == (
            "Entry 3", 48.0, "Struggled with fractions",
        )

    def test_an_edit_cannot_leave_the_assessment_with_no_result(self, cohort, admin):
        created = _record(admin, cohort, score="")
        with pytest.raises(ValidationError, match="level"):
            skills_service.update_assessment(admin, created.assessment_id, {"level": ""})

    def test_deleting_needs_a_reason(self, cohort, admin):
        created = _record(admin, cohort)
        with pytest.raises(ValidationError, match="reason"):
            skills_service.delete_assessment(admin, created.assessment_id, reason=" ")


class TestWhoMayDoWhat:
    def test_the_apprentice_and_employer_read_but_do_not_record(self, cohort):
        aid = cohort["apprentice_id"]
        assert skills_service.get_profile(cohort["employer_actor"], aid).apprentice_id == aid
        with pytest.raises(PermissionDenied):
            _record(cohort["learner"], cohort)
        with pytest.raises(PermissionDenied):
            _record(cohort["employer_actor"], cohort)

    def test_another_employer_is_refused(self, cohort):
        with pytest.raises(PermissionDenied):
            skills_service.get_profile(cohort["outsider"], cohort["apprentice_id"])

    def test_the_end_point_assessor_has_no_view_of_it(self, cohort, assessor):
        with pytest.raises(PermissionDenied):
            skills_service.get_profile(assessor, cohort["apprentice_id"])

    def test_a_tutor_sees_only_their_caseload(self, cohort, admin):
        _record(admin, cohort)
        stranger = Actor(username="other-tutor", role="staff", staff_id=9999)
        assert skills_service.list_assessments(stranger) == []
        assert len(skills_service.list_assessments(cohort["tutor"])) == 1
        with pytest.raises(PermissionDenied):
            skills_service.get_profile(stranger, cohort["apprentice_id"])


class TestTheGatewayPosition:
    def test_a_tutor_cannot_change_it(self, cohort):
        """Status and exemptions go through compliance, which needs compliance.manage."""
        assert not skills_service.can_change_status(cohort["tutor"])
        with pytest.raises(PermissionDenied):
            skills_service.set_status(
                cohort["tutor"], cohort["apprentice_id"], "English",
                status="Exempt", exemption_reason=config.EXEMPTION_REASONS[0],
            )

    def test_an_administrator_records_an_exemption_through_compliance(self, cohort, admin):
        aid = cohort["apprentice_id"]
        skills_service.set_status(
            admin, aid, "English", status="Exempt",
            exemption_reason="Prior GCSE grade 4/C or above",
        )
        profile = skills_service.get_profile(cohort["learner"], aid)
        assert {s.subject: s.status for s in profile.skills}["English"] == "Exempt"
        assert profile.outstanding == ["Maths"]
        assert compliance_repository.list_audit(entity="functional_skill")

    def test_an_exemption_still_needs_its_reason(self, cohort, admin):
        with pytest.raises(ValidationError, match="reason"):
            skills_service.set_status(admin, cohort["apprentice_id"], "Maths", status="Exempt")
