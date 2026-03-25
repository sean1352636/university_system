"""Tests for SafeguardingService."""

import pytest


class TestSafeguardingService:
    @pytest.fixture
    def safeguarding_service(self, db_path):
        from education_system.college_system.modules.domain.safeguarding.services.safeguarding_service import SafeguardingService
        return SafeguardingService(db_path)

    def test_report_concern(self, safeguarding_service, sample_student):
        concern = safeguarding_service.report_concern(
            student_id=sample_student["id"],
            reported_by=1,
            category="other",
            description="Student disclosed difficulties at home",
        )
        assert concern["category"] == "other"
        assert concern["status"] == "reported"

    def test_list_concerns(self, safeguarding_service, sample_student):
        safeguarding_service.report_concern(
            student_id=sample_student["id"], reported_by=1,
            category="neglect", description="Concern 1",
        )
        concerns = safeguarding_service.list_concerns()
        assert len(concerns) >= 1

    def test_list_concerns_filter_status(self, safeguarding_service, sample_student):
        safeguarding_service.report_concern(
            student_id=sample_student["id"], reported_by=1,
            category="other", description="Reported concern",
        )
        reported = safeguarding_service.list_concerns(status="reported")
        assert all(c["status"] == "reported" for c in reported)

    def test_get_concern(self, safeguarding_service, sample_student):
        created = safeguarding_service.report_concern(
            student_id=sample_student["id"], reported_by=1,
            category="exploitation", description="Online issue",
        )
        found = safeguarding_service.get_concern(created["id"])
        assert found["category"] == "exploitation"

    def test_update_concern(self, safeguarding_service, sample_student):
        concern = safeguarding_service.report_concern(
            student_id=sample_student["id"], reported_by=1,
            category="other", description="Initial report",
        )
        updated = safeguarding_service.update_concern(
            concern["id"], status="under_review",
        )
        assert updated["status"] == "under_review"

    def test_get_student_concerns(self, safeguarding_service, sample_student):
        safeguarding_service.report_concern(
            student_id=sample_student["id"], reported_by=1,
            category="other", description="Concern A",
        )
        student_concerns = safeguarding_service.get_student_concerns(sample_student["id"])
        assert len(student_concerns) >= 1
