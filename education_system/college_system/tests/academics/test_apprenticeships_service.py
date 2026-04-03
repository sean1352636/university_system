"""Tests for ApprenticeshipService."""

import pytest
from education_system.college_system.core.exceptions import ApprenticeshipError


class TestApprenticeshipService:
    """Test suite for ApprenticeshipService."""

    # --- Standards ---

    def test_create_standard(self, apprenticeships_service):
        item = apprenticeships_service.create_standard("Business Admin", 3, sector="Business")
        assert item["id"] is not None
        assert item["standard_name"] == "Business Admin"
        assert item["level"] == 3

    def test_list_standards(self, apprenticeships_service):
        apprenticeships_service.create_standard("Business Admin", 3)
        items = apprenticeships_service.list_standards()
        assert len(items) >= 1

    # --- Enrollments ---

    def test_enroll(self, apprenticeships_service, sample_student):
        std = apprenticeships_service.create_standard("Business Admin", 3)
        item = apprenticeships_service.enroll(
            sample_student["id"], std["id"], "Acme Corp",
            employer_contact="contact@acme.com",
        )
        assert item["id"] is not None

    def test_get_enrollment(self, apprenticeships_service, sample_student):
        std = apprenticeships_service.create_standard("Business Admin", 3)
        item = apprenticeships_service.enroll(sample_student["id"], std["id"], "Acme Corp")
        found = apprenticeships_service.get_enrollment(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_enrollments(self, apprenticeships_service, sample_student):
        std = apprenticeships_service.create_standard("Business Admin", 3)
        apprenticeships_service.enroll(sample_student["id"], std["id"], "Acme Corp")
        items = apprenticeships_service.list_enrollments()
        assert len(items) >= 1

    def test_list_enrollments_filter_standard(self, apprenticeships_service, sample_student):
        std = apprenticeships_service.create_standard("Business Admin", 3)
        apprenticeships_service.enroll(sample_student["id"], std["id"], "Acme Corp")
        items = apprenticeships_service.list_enrollments(standard_id=std["id"])
        assert len(items) >= 1

    def test_update_enrollment(self, apprenticeships_service, sample_student):
        std = apprenticeships_service.create_standard("Business Admin", 3)
        item = apprenticeships_service.enroll(sample_student["id"], std["id"], "Acme Corp")
        updated = apprenticeships_service.update_enrollment(item["id"], employer_name="New Corp")
        assert updated["employer_name"] == "New Corp"

    # --- Off-the-Job Hours ---

    def test_log_otj(self, apprenticeships_service, sample_student):
        std = apprenticeships_service.create_standard("Business Admin", 3)
        enr = apprenticeships_service.enroll(sample_student["id"], std["id"], "Acme Corp")
        log = apprenticeships_service.log_otj(enr["id"], "2024-03-01", 4.0, activity_type="training")
        assert log["id"] is not None
        assert log["hours"] == 4.0

    def test_list_otj_logs(self, apprenticeships_service, sample_student):
        std = apprenticeships_service.create_standard("Business Admin", 3)
        enr = apprenticeships_service.enroll(sample_student["id"], std["id"], "Acme Corp")
        apprenticeships_service.log_otj(enr["id"], "2024-03-01", 4.0)
        logs = apprenticeships_service.list_otj_logs(enr["id"])
        assert len(logs) >= 1

    # --- Reviews ---

    def test_add_review(self, apprenticeships_service, sample_student):
        std = apprenticeships_service.create_standard("Business Admin", 3)
        enr = apprenticeships_service.enroll(sample_student["id"], std["id"], "Acme Corp")
        review = apprenticeships_service.add_review(
            enr["id"], "2024-03-15",
            progress_summary="On track", targets_set="Complete unit 2",
        )
        assert review["id"] is not None
