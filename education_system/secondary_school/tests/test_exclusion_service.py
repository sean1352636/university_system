"""Tests for ExclusionService."""
import pytest
from education_system.secondary_school.core.exceptions import ExclusionError


class TestCreateExclusion:
    def test_create_fixed_term(self, exclusion_service, sample_student):
        e = exclusion_service.create_exclusion(
            student_id=sample_student["id"], reason="Persistent disruption",
            exclusion_type="fixed_term", start_date="2026-03-20",
            end_date="2026-03-22", days=3,
        )
        assert e["student_id"] == sample_student["id"]
        assert e["exclusion_type"] == "fixed_term"
        assert e["reason"] == "Persistent disruption"
        assert e["days"] == 3
        assert e["status"] == "active"

    def test_create_permanent(self, exclusion_service, sample_student):
        e = exclusion_service.create_exclusion(
            student_id=sample_student["id"], reason="Serious incident",
            exclusion_type="permanent", category="physical_assault_adult",
            start_date="2026-03-20", excluded_by="Headteacher",
        )
        assert e["exclusion_type"] == "permanent"
        assert e["category"] == "physical_assault_adult"
        assert e["excluded_by"] == "Headteacher"


class TestListExclusions:
    def test_list_returns_exclusions(self, exclusion_service, sample_student):
        exclusion_service.create_exclusion(
            sample_student["id"], "Reason 1", start_date="2026-03-18",
        )
        exclusion_service.create_exclusion(
            sample_student["id"], "Reason 2", start_date="2026-03-20",
        )
        result = exclusion_service.list_exclusions()
        assert len(result) >= 2

    def test_list_filter_by_student(self, exclusion_service, sample_student, sample_student_ks4):
        exclusion_service.create_exclusion(
            sample_student["id"], "R1", start_date="2026-03-18",
        )
        exclusion_service.create_exclusion(
            sample_student_ks4["id"], "R2", start_date="2026-03-20",
        )
        result = exclusion_service.list_exclusions(student_id=sample_student["id"])
        assert len(result) == 1
        assert result[0]["student_id"] == sample_student["id"]

    def test_list_filter_by_type(self, exclusion_service, sample_student):
        exclusion_service.create_exclusion(
            sample_student["id"], "R1", exclusion_type="fixed_term",
            start_date="2026-03-18",
        )
        exclusion_service.create_exclusion(
            sample_student["id"], "R2", exclusion_type="internal",
            start_date="2026-03-20",
        )
        result = exclusion_service.list_exclusions(exclusion_type="internal")
        assert len(result) == 1
        assert result[0]["exclusion_type"] == "internal"


class TestExclusionActions:
    def test_update_notifications(self, exclusion_service, sample_student):
        e = exclusion_service.create_exclusion(
            sample_student["id"], "Reason", start_date="2026-03-20",
        )
        exclusion_service.update_notifications(
            e["id"], parent_notified=True, la_notified=True,
        )
        result = exclusion_service.list_exclusions()
        rec = [x for x in result if x["id"] == e["id"]][0]
        assert rec["parent_notified"] == 1
        assert rec["la_notified"] == 1

    def test_update_reintegration(self, exclusion_service, sample_student):
        e = exclusion_service.create_exclusion(
            sample_student["id"], "Reason", start_date="2026-03-20",
        )
        exclusion_service.update_reintegration(e["id"], "2026-03-25")
        result = exclusion_service.list_exclusions()
        rec = [x for x in result if x["id"] == e["id"]][0]
        assert rec["reintegration_date"] == "2026-03-25"

    def test_close_exclusion(self, exclusion_service, sample_student):
        e = exclusion_service.create_exclusion(
            sample_student["id"], "Reason", start_date="2026-03-20",
        )
        exclusion_service.close_exclusion(e["id"])
        # Closed exclusions should not appear in active-only listing
        active = exclusion_service.list_exclusions(status="active")
        assert all(x["id"] != e["id"] for x in active)
        # But should appear when filtering for closed
        closed = exclusion_service.list_exclusions(status="closed")
        assert any(x["id"] == e["id"] for x in closed)

    def test_delete_exclusion(self, exclusion_service, sample_student):
        e = exclusion_service.create_exclusion(
            sample_student["id"], "Reason", start_date="2026-03-20",
        )
        exclusion_service.delete_exclusion(e["id"])
        result = exclusion_service.list_exclusions(status=None)
        assert all(x["id"] != e["id"] for x in result)


class TestExclusionSummary:
    def test_summary_returns_counts(self, exclusion_service, sample_student):
        exclusion_service.create_exclusion(
            sample_student["id"], "R1", exclusion_type="fixed_term",
            start_date="2026-03-18", days=2,
        )
        exclusion_service.create_exclusion(
            sample_student["id"], "R2", exclusion_type="fixed_term",
            start_date="2026-03-20", days=3,
        )
        exclusion_service.create_exclusion(
            sample_student["id"], "R3", exclusion_type="internal",
            start_date="2026-03-22", days=1,
        )
        summary = exclusion_service.summary()
        assert len(summary) >= 1
        ft = [s for s in summary if s["exclusion_type"] == "fixed_term"]
        assert len(ft) == 1
        assert ft[0]["cnt"] == 2
        assert ft[0]["total_days"] == 5
