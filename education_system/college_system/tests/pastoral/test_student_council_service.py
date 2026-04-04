"""Tests for StudentCouncilService."""

import pytest


class TestStudentCouncilService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.student_council.services.student_council_service import StudentCouncilService
        return StudentCouncilService(db_path)

    def test_create_member(self, service):
        member = service.create_member(
            student_id=1, role="president",
            year_group="13", department="Student Union",
        )
        assert member is not None

    def test_list_members(self, service):
        service.create_member(student_id=1, role="representative")
        members = service.list_members()
        assert len(members) >= 1

    def test_get_member(self, service):
        member = service.create_member(student_id=1)
        mid = member if isinstance(member, int) else member.get("id", member)
        found = service.get_member(mid)
        assert found is not None

    def test_update_member(self, service):
        member = service.create_member(student_id=1)
        mid = member if isinstance(member, int) else member.get("id", member)
        updated = service.update_member(mid, role="vice_president")
        assert updated is not None

    def test_delete_member(self, service):
        member = service.create_member(student_id=1)
        mid = member if isinstance(member, int) else member.get("id", member)
        result = service.delete_member(mid)
        assert result is True or result is None

    def test_create_meeting(self, service):
        meeting = service.create_meeting(
            meeting_date="2026-05-01",
            agenda="Budget allocation, event planning",
        )
        assert meeting is not None

    def test_list_meetings(self, service):
        service.create_meeting(meeting_date="2026-05-01")
        meetings = service.list_meetings()
        assert len(meetings) >= 1

    def test_complete_meeting(self, service):
        meeting = service.create_meeting(meeting_date="2026-05-01")
        mid = meeting if isinstance(meeting, int) else meeting.get("id", meeting)
        result = service.complete_meeting(
            mid, minutes="Discussed budget allocation",
            attendees="Alice, Bob, Charlie",
        )
        assert result is not None

    def test_create_proposal(self, service):
        proposal = service.create_proposal(
            title="New common room furniture",
            description="Replace worn sofas",
            category="facilities",
        )
        assert proposal is not None

    def test_list_proposals(self, service):
        service.create_proposal(title="Proposal A")
        proposals = service.list_proposals()
        assert len(proposals) >= 1

    def test_record_votes(self, service):
        proposal = service.create_proposal(title="Vote test")
        pid = proposal if isinstance(proposal, int) else proposal.get("id", proposal)
        result = service.record_votes(
            pid, vote_for=15, vote_against=3,
            vote_abstain=2, outcome="approved",
        )
        assert result is not None

    def test_respond_to_proposal(self, service):
        proposal = service.create_proposal(title="Response test")
        pid = proposal if isinstance(proposal, int) else proposal.get("id", proposal)
        result = service.respond_to_proposal(
            pid, management_response="Approved, budget allocated",
            implementation_status="in_progress",
        )
        assert result is not None

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
