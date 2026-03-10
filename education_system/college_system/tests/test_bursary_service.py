"""Tests for BursaryService."""

import pytest


class TestBursaryService:
    @pytest.fixture
    def bursary_service(self, db_path):
        from education_system.college_system.modules.domain.bursary.services.bursary_service import BursaryService
        return BursaryService(db_path)

    def test_create_bursary(self, bursary_service, sample_student):
        bursary = bursary_service.create_bursary(
            student_id=sample_student["id"],
            bursary_type="discretionary",
            amount=1200.00,
        )
        assert bursary["bursary_type"] == "discretionary"
        assert bursary["amount"] == 1200.00

    def test_list_bursaries(self, bursary_service, sample_student):
        bursary_service.create_bursary(
            student_id=sample_student["id"],
            bursary_type="vulnerable", amount=2400.00,
        )
        bursaries = bursary_service.list_bursaries()
        assert len(bursaries) >= 1

    def test_get_bursary(self, bursary_service, sample_student):
        created = bursary_service.create_bursary(
            student_id=sample_student["id"],
            bursary_type="discretionary", amount=500.00,
        )
        found = bursary_service.get_bursary(created["id"])
        assert found["amount"] == 500.00

    def test_update_bursary(self, bursary_service, sample_student):
        bursary = bursary_service.create_bursary(
            student_id=sample_student["id"],
            bursary_type="discretionary", amount=1000.00,
        )
        updated = bursary_service.update_bursary(
            bursary["id"], amount=1500.00, status="approved",
        )
        assert updated["amount"] == 1500.00

    def test_get_student_bursary(self, bursary_service, sample_student):
        created = bursary_service.create_bursary(
            student_id=sample_student["id"],
            bursary_type="vulnerable", amount=1200.00,
        )
        bursary_service.update_bursary(created["id"], status="approved")
        found = bursary_service.get_student_bursary(sample_student["id"])
        assert found is not None
