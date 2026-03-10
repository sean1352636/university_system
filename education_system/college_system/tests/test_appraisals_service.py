"""Tests for AppraisalService."""

import pytest
from education_system.college_system.core.exceptions import AppraisalError, ValidationError


class TestAppraisalService:
    """Test suite for AppraisalService."""

    def test_create_appraisal(self, appraisals_service):
        item = appraisals_service.create_appraisal(staff_id=1, academic_year="test_academic_year")
        assert item["id"] is not None

    def test_get_appraisal(self, appraisals_service):
        item = appraisals_service.create_appraisal(staff_id=1, academic_year="test_academic_year")
        found = appraisals_service.get_appraisal(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_appraisals(self, appraisals_service):
        appraisals_service.create_appraisal(staff_id=1, academic_year="test_academic_year")
        items = appraisals_service.list_appraisals()
        assert len(items) >= 1

    def test_update_appraisal(self, appraisals_service):
        item = appraisals_service.create_appraisal(staff_id=1, academic_year="test_academic_year")
        updated = appraisals_service.update_appraisal(item["id"], academic_year="updated_value")
        assert updated["academic_year"] == "updated_value"

    def test_delete_appraisal(self, appraisals_service):
        item = appraisals_service.create_appraisal(staff_id=1, academic_year="test_academic_year")
        result = appraisals_service.delete_appraisal(item["id"])
        assert result is True
        assert appraisals_service.get_appraisal(item["id"]) is None

    def test_count_appraisals(self, appraisals_service):
        appraisals_service.create_appraisal(staff_id=1, academic_year="test_academic_year")
        count = appraisals_service.count_appraisals()
        assert count >= 1

    def test_delete_nonexistent_raises(self, appraisals_service):
        with pytest.raises(AppraisalError):
            appraisals_service.delete_appraisal(99999)
