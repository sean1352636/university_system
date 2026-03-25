"""Tests for CPDService."""
import pytest
from education_system.secondary_school.core.exceptions import CPDError


class TestAddRecord:
    def test_add_record_basic(self, cpd_service):
        rec = cpd_service.add_record(
            staff_name="Jane Smith",
            training_title="Safeguarding Level 1",
            date="2026-03-01",
        )
        assert rec["staff_name"] == "Jane Smith"
        assert rec["training_title"] == "Safeguarding Level 1"
        assert rec["category"] == "general"

    def test_add_record_full_details(self, cpd_service):
        rec = cpd_service.add_record(
            staff_name="John Doe",
            training_title="First Aid at Work",
            date="2026-02-15",
            category="first_aid",
            provider="Red Cross",
            duration_hours=8,
            cost=150.00,
            certificate=True,
            impact="Can now act as first aider",
            notes="Renewal due 2029",
        )
        assert rec["category"] == "first_aid"
        assert rec["provider"] == "Red Cross"
        assert rec["duration_hours"] == 8
        assert rec["cost"] == 150.00
        assert rec["certificate"] == 1
        assert rec["impact"] == "Can now act as first aider"


class TestListRecords:
    def test_list_records_returns_created(self, cpd_service):
        cpd_service.add_record(staff_name="A Staff", training_title="Course A", date="2026-01-01")
        cpd_service.add_record(staff_name="B Staff", training_title="Course B", date="2026-02-01")
        records = cpd_service.list_records()
        titles = [r["training_title"] for r in records]
        assert "Course A" in titles
        assert "Course B" in titles

    def test_list_records_filter_by_staff_name(self, cpd_service):
        cpd_service.add_record(staff_name="Alice", training_title="C1", date="2026-01-01")
        cpd_service.add_record(staff_name="Bob", training_title="C2", date="2026-01-02")
        result = cpd_service.list_records(staff_name="Alice")
        assert len(result) == 1
        assert result[0]["staff_name"] == "Alice"

    def test_list_records_filter_by_category(self, cpd_service):
        cpd_service.add_record(staff_name="A", training_title="SG1", date="2026-01-01", category="safeguarding")
        cpd_service.add_record(staff_name="A", training_title="FA1", date="2026-01-02", category="first_aid")
        result = cpd_service.list_records(category="safeguarding")
        assert all(r["category"] == "safeguarding" for r in result)
        assert len(result) >= 1


class TestDeleteRecord:
    def test_delete_record_removes_it(self, cpd_service):
        rec = cpd_service.add_record(staff_name="X", training_title="Del", date="2026-01-01")
        cpd_service.delete_record(rec["id"])
        remaining = cpd_service.list_records(staff_name="X")
        assert len(remaining) == 0


class TestStaffSummary:
    def test_staff_summary_aggregates(self, cpd_service):
        cpd_service.add_record(staff_name="Alice", training_title="C1", date="2026-01-01", duration_hours=4)
        cpd_service.add_record(staff_name="Alice", training_title="C2", date="2026-02-01", duration_hours=6)
        cpd_service.add_record(staff_name="Bob", training_title="C3", date="2026-03-01", duration_hours=2)
        summary = cpd_service.staff_summary()
        alice = [s for s in summary if s["staff_name"] == "Alice"]
        bob = [s for s in summary if s["staff_name"] == "Bob"]
        assert len(alice) == 1
        assert alice[0]["courses"] == 2
        assert alice[0]["total_hours"] == 10
        assert len(bob) == 1
        assert bob[0]["courses"] == 1
        assert bob[0]["total_hours"] == 2
