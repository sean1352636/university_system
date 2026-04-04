"""Tests for AppraisalsService."""
import pytest
from education_system.secondary_school.modules.domain.staff.appraisals.services.appraisals_service import AppraisalsService


@pytest.fixture
def appraisals_service(db_path):
    return AppraisalsService(db_path)


class TestAppraisalsCRUD:
    def test_create(self, appraisals_service):
        r = appraisals_service.create(staff_id="STF001", appraiser_id="STF002",
                                       academic_year="2025/2026", meeting_date="2026-03-20")
        assert r["staff_id"] == "STF001"
        assert r["status"] == "scheduled"

    def test_list_all(self, appraisals_service):
        appraisals_service.create(staff_id="STF001", academic_year="2025/2026")
        appraisals_service.create(staff_id="STF002", academic_year="2025/2026")
        result = appraisals_service.list_all()
        assert len(result) >= 2

    def test_get(self, appraisals_service):
        r = appraisals_service.create(staff_id="STF001", academic_year="2025/2026")
        found = appraisals_service.get(r["id"])
        assert found is not None
        assert found["staff_id"] == "STF001"

    def test_update(self, appraisals_service):
        r = appraisals_service.create(staff_id="STF001", academic_year="2025/2026")
        updated = appraisals_service.update(r["id"], status="completed", overall_rating="good")
        assert updated["status"] == "completed"
        assert updated["overall_rating"] == "good"

    def test_delete(self, appraisals_service):
        r = appraisals_service.create(staff_id="STF001", academic_year="2025/2026")
        appraisals_service.delete(r["id"])
        assert appraisals_service.get(r["id"]) is None
