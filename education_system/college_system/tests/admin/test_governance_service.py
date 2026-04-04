"""Tests for GovernanceService."""

import pytest


class TestGovernanceService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.governance.services.governance_service import GovernanceService
        return GovernanceService(db_path)

    def test_add_governor(self, service):
        gov = service.add_governor(
            first_name="Jane", last_name="Smith",
            governor_type="community", email="jane@example.com",
            role_on_board="Chair",
        )
        assert gov is not None

    def test_list_governors(self, service):
        service.add_governor(first_name="A", last_name="B")
        service.add_governor(first_name="C", last_name="D")
        governors = service.list_governors()
        assert len(governors) >= 2

    def test_update_governor(self, service):
        gov = service.add_governor(first_name="Ed", last_name="Fox")
        gov_id = gov if isinstance(gov, int) else gov.get("id", gov)
        result = service.update_governor(gov_id, role_on_board="Vice Chair")
        assert result is not None

    def test_create_meeting(self, service):
        meeting = service.create_meeting(
            meeting_date="2026-05-01",
            meeting_type="full_board",
            location="Board Room",
        )
        assert meeting is not None

    def test_list_meetings(self, service):
        service.create_meeting(meeting_date="2026-05-01")
        meetings = service.list_meetings()
        assert len(meetings) >= 1

    def test_add_action(self, service):
        meeting = service.create_meeting(meeting_date="2026-05-01")
        meeting_id = meeting if isinstance(meeting, int) else meeting.get("id", meeting)
        action = service.add_action(
            meeting_id=meeting_id,
            action_description="Review finance policy",
            due_date="2026-06-01",
        )
        assert action is not None

    def test_list_actions(self, service):
        meeting = service.create_meeting(meeting_date="2026-05-01")
        meeting_id = meeting if isinstance(meeting, int) else meeting.get("id", meeting)
        service.add_action(meeting_id, "Action 1")
        actions = service.list_actions(meeting_id=meeting_id)
        assert len(actions) >= 1

    def test_add_strategic_plan(self, service):
        plan = service.add_strategic_plan(
            title="Improve Student Outcomes",
            priority_area="Teaching & Learning",
            objective="Increase value-added scores",
            academic_year="2025/26",
        )
        assert plan is not None

    def test_list_strategic_plans(self, service):
        service.add_strategic_plan(title="Plan A")
        plans = service.list_strategic_plans()
        assert len(plans) >= 1
