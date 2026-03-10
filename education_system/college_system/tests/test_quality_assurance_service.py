"""Tests for QualityAssuranceService."""

import pytest
from education_system.college_system.core.exceptions import QualityAssuranceError, ValidationError


class TestQualityAssuranceService:
    """Test suite for QualityAssuranceService."""

    def test_create_review(self, quality_assurance_service):
        item = quality_assurance_service.create_review(review_type="test_review_type", academic_year="test_academic_year", title="test_title")
        assert item["id"] is not None

    def test_get_review(self, quality_assurance_service):
        item = quality_assurance_service.create_review(review_type="test_review_type", academic_year="test_academic_year", title="test_title")
        found = quality_assurance_service.get_review(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_reviews(self, quality_assurance_service):
        quality_assurance_service.create_review(review_type="test_review_type", academic_year="test_academic_year", title="test_title")
        items = quality_assurance_service.list_reviews()
        assert len(items) >= 1

    def test_update_review(self, quality_assurance_service):
        item = quality_assurance_service.create_review(review_type="test_review_type", academic_year="test_academic_year", title="test_title")
        updated = quality_assurance_service.update_review(item["id"], review_type="updated_value")
        assert updated["review_type"] == "updated_value"

    def test_delete_review(self, quality_assurance_service):
        item = quality_assurance_service.create_review(review_type="test_review_type", academic_year="test_academic_year", title="test_title")
        result = quality_assurance_service.delete_review(item["id"])
        assert result is True
        assert quality_assurance_service.get_review(item["id"]) is None

    def test_count_reviews(self, quality_assurance_service):
        quality_assurance_service.create_review(review_type="test_review_type", academic_year="test_academic_year", title="test_title")
        count = quality_assurance_service.count_reviews()
        assert count >= 1

    def test_delete_nonexistent_raises(self, quality_assurance_service):
        with pytest.raises(QualityAssuranceError):
            quality_assurance_service.delete_review(99999)
