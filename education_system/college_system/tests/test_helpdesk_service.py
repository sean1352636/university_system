"""Tests for HelpdeskService."""

import pytest


class TestHelpdeskService:
    @pytest.fixture
    def helpdesk_service(self, db_path):
        from education_system.college_system.modules.domain.helpdesk.services.helpdesk_service import HelpdeskService
        return HelpdeskService(db_path)

    def test_create_ticket(self, helpdesk_service):
        ticket = helpdesk_service.create_ticket(
            user_id=1, subject="Can't access portal",
            description="Login page shows error",
            category="it",
        )
        assert ticket["subject"] == "Can't access portal"
        assert ticket["status"] == "open"

    def test_list_tickets(self, helpdesk_service):
        helpdesk_service.create_ticket(
            user_id=1, subject="Ticket 1", description="Desc 1", category="it",
        )
        helpdesk_service.create_ticket(
            user_id=1, subject="Ticket 2", description="Desc 2", category="facilities",
        )
        tickets = helpdesk_service.list_tickets(user_id=1)
        assert len(tickets) >= 2

    def test_get_ticket(self, helpdesk_service):
        created = helpdesk_service.create_ticket(
            user_id=1, subject="Get me", description="Test", category="it",
        )
        found = helpdesk_service.get_ticket(created["id"])
        assert found["subject"] == "Get me"

    def test_update_ticket(self, helpdesk_service):
        ticket = helpdesk_service.create_ticket(
            user_id=1, subject="Update test", description="Test", category="it",
        )
        updated = helpdesk_service.update_ticket(
            ticket["id"], status="in_progress",
        )
        assert updated["status"] == "in_progress"

    def test_add_response(self, helpdesk_service):
        ticket = helpdesk_service.create_ticket(
            user_id=1, subject="Need response", description="Help", category="it",
        )
        result = helpdesk_service.add_response(
            ticket_id=ticket["id"], user_id=2, message="Looking into it",
        )
        assert len(result["responses"]) >= 1
        assert result["responses"][0]["message"] == "Looking into it"

    def test_assign_ticket(self, helpdesk_service):
        ticket = helpdesk_service.create_ticket(
            user_id=1, subject="Assign test", description="Test", category="it",
        )
        assigned = helpdesk_service.assign_ticket(ticket["id"], assigned_to=2)
        assert assigned["assigned_to"] == 2
