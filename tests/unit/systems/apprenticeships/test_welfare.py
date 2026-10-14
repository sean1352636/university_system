"""Welfare concerns, case notes and the risk profile.

The status and risk rules are tested pure. The rest runs through the
service on the conftest's throwaway database, because the restriction
is the feature: no apprentice, employer or end-point assessor may see a
welfare record, and a tutor only for their own caseload.

The conftest apprentice started 400 days ago and has logged no
off-the-job hours, so they are already behind: every profile below
starts from that one point.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.learner_support import welfare as rules
from education_system.systems.apprenticeships.domain.learner_support.welfare import (
    WelfareConcern,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    compliance_repository,
    learning_plan_repository,
    review_repository,
)
from education_system.systems.apprenticeships.services import welfare_service
from education_system.systems.apprenticeships.services.access import Actor, PermissionDenied


def _concern(**overrides) -> WelfareConcern:
    fields = dict(
        concern_id=1, apprentice_id=1, category="Wellbeing", severity="Medium",
        description="Seems withdrawn",
    )
    fields.update(overrides)
    return WelfareConcern(**fields)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

class TestTransitions:
    def test_escalating_says_who_to(self):
        with pytest.raises(ValidationError, match="escalated to"):
            rules.check_transition("Open", "Escalated", escalated_to=None, outcome=None)
        rules.check_transition("Open", "Escalated", escalated_to="DSL", outcome=None)

    def test_closing_records_the_outcome(self):
        with pytest.raises(ValidationError, match="outcome"):
            rules.check_transition("Monitoring", "Closed", escalated_to=None, outcome=None)

    def test_a_closed_concern_can_be_reopened(self):
        rules.check_transition("Closed", "Open", escalated_to=None, outcome=None)

    def test_moving_to_the_same_status_is_refused(self):
        with pytest.raises(ValidationError, match="already Open"):
            rules.check_transition("Open", "Open", escalated_to=None, outcome=None)


class TestRisk:
    def test_nothing_flagged_is_low(self):
        profile = rules.assess_risk(1)
        assert (profile.level, profile.score, profile.reasons) == ("Low", 0, [])

    def test_lagging_on_hours_alone_is_still_low(self):
        assert rules.assess_risk(1, otj_behind=True).level == "Low"

    def test_an_attendance_concern_alone_is_medium(self):
        profile = rules.assess_risk(1, attendance_concern="3 unauthorised absences in a row")
        assert profile.level == "Medium"
        assert profile.reasons == ["3 unauthorised absences in a row"]

    def test_a_critical_concern_alone_is_high(self):
        assert rules.assess_risk(1, open_concerns=[_concern(severity="Critical")]).level == "High"

    def test_the_worst_open_concern_counts_not_the_sum(self):
        profile = rules.assess_risk(1, open_concerns=[
            _concern(concern_id=1, severity="Low"), _concern(concern_id=2, severity="Medium"),
        ])
        assert profile.score == config.RISK_POINTS_WELFARE["Medium"]
        assert "2 open welfare concerns, worst Medium" in profile.reasons[0]

    def test_closed_concerns_do_not_count(self):
        assert rules.assess_risk(
            1, open_concerns=[_concern(status="Closed", severity="Critical")]
        ).score == 0

    def test_one_overdue_objective_is_ordinary_a_pattern_is_not(self):
        assert rules.assess_risk(1, overdue_objectives=1).score == 0
        assert rules.assess_risk(
            1, overdue_objectives=config.RISK_OVERDUE_OBJECTIVES_MIN
        ).score == config.RISK_POINTS_OVERDUE_OBJECTIVES

    def test_signs_add_up(self):
        profile = rules.assess_risk(
            1, otj_behind=True, overdue_reviews=1, overdue_objectives=3,
            attendance_concern="Attendance 70.0%, below 80%",
        )
        assert profile.score == 5
        assert profile.level == "High"
        assert profile.rag == "Red"


# ═════════════════════════════════════════════════════════════════════
# Through the service
# ═════════════════════════════════════════════════════════════════════

def _raise(actor, cohort, **overrides):
    payload = {
        "category": "Financial hardship", "severity": "Medium",
        "description": "Cannot afford the bus fare to college",
    }
    payload.update(overrides)
    return welfare_service.raise_concern(actor, cohort["apprentice_id"], payload)


class TestNobodyOutsideTheProviderSeesIt:
    @pytest.mark.parametrize("who", ["learner", "employer_actor", "outsider"])
    def test_apprentice_and_employers_are_refused(self, cohort, admin, who):
        _raise(admin, cohort)
        actor = cohort[who]
        with pytest.raises(PermissionDenied):
            welfare_service.list_concerns(actor)
        with pytest.raises(PermissionDenied):
            welfare_service.list_concerns(actor, apprentice_id=cohort["apprentice_id"])
        with pytest.raises(PermissionDenied):
            welfare_service.risk_profile(actor, cohort["apprentice_id"])
        with pytest.raises(PermissionDenied):
            welfare_service.at_risk(actor)

    def test_the_end_point_assessor_is_refused(self, cohort, admin, assessor):
        concern = _raise(admin, cohort)
        with pytest.raises(PermissionDenied):
            welfare_service.get_concern(assessor, concern.concern_id)
        with pytest.raises(PermissionDenied):
            welfare_service.at_risk(assessor)

    def test_a_broader_grant_in_config_still_does_not_open_it(self, cohort, admin, monkeypatch):
        """The provider check stands even if someone grants welfare.view by mistake."""
        _raise(admin, cohort)
        widened = config.ROLE_PERMISSIONS[config.EMPLOYER] | {"welfare.view"}
        monkeypatch.setitem(config.ROLE_PERMISSIONS, config.EMPLOYER, widened)
        with pytest.raises(PermissionDenied, match="provider staff"):
            welfare_service.list_concerns(cohort["employer_actor"])

    def test_a_tutor_only_for_their_own_caseload(self, cohort, admin):
        concern = _raise(admin, cohort)
        stranger = Actor(username="other-tutor", role="staff", staff_id=9999)
        assert welfare_service.list_concerns(stranger) == []
        assert welfare_service.at_risk(stranger, include_low=True) == []
        with pytest.raises(PermissionDenied):
            welfare_service.get_concern(stranger, concern.concern_id)
        with pytest.raises(PermissionDenied):
            _raise(stranger, cohort)
        assert [c.concern_id for c in welfare_service.list_concerns(cohort["tutor"])] == [
            concern.concern_id
        ]


class TestConcerns:
    def test_the_tutor_who_raises_it_holds_it(self, cohort):
        concern = _raise(cohort["tutor"], cohort)
        assert (concern.status, concern.assigned_to, concern.raised_by) == (
            "Open", cohort["tutor_id"], "tutor1",
        )

    def test_the_audit_never_carries_the_description(self, cohort, admin):
        _raise(admin, cohort, description="Sofa-surfing since the eviction")
        (entry,) = compliance_repository.list_audit(entity="welfare_concern")
        assert "Financial hardship" in entry.detail
        assert "eviction" not in entry.detail

    def test_an_edit_is_written_into_the_case_notes(self, cohort, admin):
        concern = _raise(admin, cohort)
        updated = welfare_service.update_concern(
            admin, concern.concern_id, {"severity": "High", "note": "Rent arrears too"}
        )
        assert updated.severity == "High"
        assert "Severity Medium -> High" in updated.notes[-1].note
        assert "Rent arrears too" in updated.notes[-1].note

    def test_status_is_not_changed_by_an_edit(self, cohort, admin):
        concern = _raise(admin, cohort)
        with pytest.raises(ValidationError, match="change_status"):
            welfare_service.update_concern(admin, concern.concern_id, {"status": "Closed"})

    def test_escalate_close_and_reopen_keep_the_whole_story(self, cohort, admin):
        concern = _raise(admin, cohort)
        escalated = welfare_service.change_status(
            admin, concern.concern_id, "Escalated", escalated_to="Designated safeguarding lead",
        )
        assert escalated.escalated_to == "Designated safeguarding lead"
        assert escalated.escalated_at

        with pytest.raises(ValidationError, match="outcome"):
            welfare_service.change_status(admin, concern.concern_id, "Closed")
        closed = welfare_service.change_status(
            admin, concern.concern_id, "Closed", outcome="Hardship fund award made",
        )
        assert (closed.status, closed.outcome) == ("Closed", "Hardship fund award made")
        assert closed.closed_at

        reopened = welfare_service.change_status(
            admin, concern.concern_id, "Open", note="Fares have gone up again",
        )
        assert (reopened.closed_at, reopened.outcome) == (None, None)
        assert "previous outcome was: Hardship fund award made" in reopened.notes[-1].note
        assert [n.note.split(";")[0] for n in reopened.notes] == [
            "Status Open -> Escalated", "Status Escalated -> Closed", "Status Closed -> Open",
        ]

    def test_case_notes_read_oldest_first(self, cohort, admin):
        concern = _raise(admin, cohort)
        welfare_service.add_note(admin, concern.concern_id, "Spoke to Jo")
        welfare_service.add_note(admin, concern.concern_id, "Referred to hardship fund")
        notes = welfare_service.get_concern(admin, concern.concern_id).notes
        assert [n.note for n in notes] == ["Spoke to Jo", "Referred to hardship fund"]

    def test_an_empty_case_note_is_refused(self, cohort, admin):
        concern = _raise(admin, cohort)
        with pytest.raises(ValidationError, match="empty"):
            welfare_service.add_note(admin, concern.concern_id, "   ")


class TestRiskProfile:
    def test_the_baseline_is_the_hours_they_are_behind_on(self, cohort, admin):
        profile = welfare_service.risk_profile(admin, cohort["apprentice_id"])
        assert profile.level == "Low"
        assert [f.key for f in profile.factors] == ["otj"]

    def test_signs_from_other_modules_are_read(self, cohort, admin):
        aid = cohort["apprentice_id"]
        past = (date.today() - timedelta(days=20)).isoformat()
        review_repository.create({"apprentice_id": aid, "scheduled_date": past})
        for title in ("Build a network", "Write a test plan"):
            learning_plan_repository.create_objective(
                {"apprentice_id": aid, "title": title, "target_date": past}
            )
        profile = welfare_service.risk_profile(cohort["tutor"], aid)
        assert sorted(f.key for f in profile.factors) == ["objectives", "otj", "reviews"]
        assert profile.level == "Medium"

    def test_an_open_concern_raises_the_level_and_the_at_risk_list_follows(self, cohort, admin):
        assert welfare_service.at_risk(admin) == []
        _raise(admin, cohort, severity="High")
        (profile,) = welfare_service.at_risk(admin)
        assert profile.apprentice_name == "Jo Bell"
        assert profile.level == "High"  # 1 for hours + 3 for a High concern
        assert any("open welfare concern" in r for r in profile.reasons)

    def test_include_low_lists_everyone_on_the_caseload(self, cohort):
        profiles = welfare_service.at_risk(cohort["tutor"], include_low=True)
        assert [p.apprentice_id for p in profiles] == [cohort["apprentice_id"]]
