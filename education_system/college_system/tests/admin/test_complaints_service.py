"""Tests for ComplaintService."""

import pytest
from education_system.college_system.core.exceptions import ComplaintError


class TestComplaintService:
    """Test suite for ComplaintService."""

    # --- Complaints ---

    def test_create_complaint(self, complaints_service):
        item = complaints_service.create_complaint(
            "John Parent", "Grade dispute", "Disagrees with final grade",
            complainant_type="parent", category="academic",
        )
        assert item["id"] is not None
        assert item["subject"] == "Grade dispute"

    def test_get_complaint(self, complaints_service):
        item = complaints_service.create_complaint("John", "Issue", "Details")
        found = complaints_service.get_complaint(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_get_complaint_nonexistent(self, complaints_service):
        assert complaints_service.get_complaint(99999) is None

    def test_list_complaints(self, complaints_service):
        complaints_service.create_complaint("John", "Issue", "Details")
        items = complaints_service.list_complaints()
        assert len(items) >= 1

    def test_list_complaints_filter_status(self, complaints_service):
        complaints_service.create_complaint("John", "Issue", "Details")
        items = complaints_service.list_complaints(status="open")
        assert all(c["status"] == "open" for c in items)

    def test_list_complaints_filter_category(self, complaints_service):
        complaints_service.create_complaint(
            "John", "Issue", "Details", category="academic",
        )
        items = complaints_service.list_complaints(category="academic")
        assert all(c["category"] == "academic" for c in items)

    def test_list_complaints_search(self, complaints_service):
        complaints_service.create_complaint("UniqueComplainant", "UniqueSub", "Details")
        items = complaints_service.list_complaints(search="UniqueComplainant")
        assert len(items) >= 1

    def test_update_complaint(self, complaints_service):
        item = complaints_service.create_complaint("John", "Issue", "Details")
        updated = complaints_service.update_complaint(item["id"], category="facilities")
        assert updated["category"] == "facilities"

    def test_delete_complaint(self, complaints_service):
        item = complaints_service.create_complaint("John", "Issue", "Details")
        result = complaints_service.delete_complaint(item["id"])
        assert result is True
        assert complaints_service.get_complaint(item["id"]) is None

    def test_delete_nonexistent(self, complaints_service):
        result = complaints_service.delete_complaint(99999)
        assert result is True or result is False

    # --- Escalation Workflow ---

    def test_escalate(self, complaints_service):
        item = complaints_service.create_complaint("John", "Issue", "Details")
        escalated = complaints_service.escalate(item["id"])
        assert escalated["stage"] == "formal_stage_1"

    def test_escalate_through_stages(self, complaints_service):
        item = complaints_service.create_complaint("John", "Issue", "Details")
        stages = ["formal_stage_1", "formal_stage_2", "panel_hearing", "appeal"]
        for expected_stage in stages:
            item = complaints_service.escalate(item["id"])
            assert item["stage"] == expected_stage

    def test_resolve(self, complaints_service):
        item = complaints_service.create_complaint("John", "Issue", "Details")
        resolved = complaints_service.resolve(item["id"], "Resolved amicably")
        assert resolved["status"] == "resolved"

    # --- Responses ---

    def test_add_response(self, complaints_service):
        item = complaints_service.create_complaint("John", "Issue", "Details")
        resp = complaints_service.add_response(
            item["id"], "Investigation complete", response_type="investigation",
        )
        assert resp["id"] is not None

    def test_list_responses(self, complaints_service):
        item = complaints_service.create_complaint("John", "Issue", "Details")
        complaints_service.add_response(item["id"], "Noted")
        responses = complaints_service.list_responses(item["id"])
        assert len(responses) >= 1

    def test_delete_response(self, complaints_service):
        item = complaints_service.create_complaint("John", "Issue", "Details")
        resp = complaints_service.add_response(item["id"], "Noted")
        result = complaints_service.delete_response(resp["id"])
        assert result is True

    def test_delete_complaint_cascades_responses(self, complaints_service):
        item = complaints_service.create_complaint("John", "Issue", "Details")
        complaints_service.add_response(item["id"], "Noted")
        complaints_service.delete_complaint(item["id"])
        responses = complaints_service.list_responses(item["id"])
        assert len(responses) == 0

    # --- Statistics ---

    def test_get_stats(self, complaints_service):
        complaints_service.create_complaint("John", "Issue", "Details")
        stats = complaints_service.get_stats()
        assert stats["total"] >= 1
        assert "by_category" in stats
        assert "by_stage" in stats
