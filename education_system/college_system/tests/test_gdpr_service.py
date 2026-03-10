"""Tests for GDPRService."""

import pytest
from education_system.college_system.core.exceptions import GDPRError, ValidationError


class TestGDPRService:
    """Test suite for GDPRService."""

    def test_create_subject(self, gdpr_service):
        item = gdpr_service.create_subject(user_id=1)
        assert item["id"] is not None

    def test_get_subject(self, gdpr_service):
        item = gdpr_service.create_subject(user_id=1)
        found = gdpr_service.get_subject(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_subjects(self, gdpr_service):
        gdpr_service.create_subject(user_id=1)
        items = gdpr_service.list_subjects()
        assert len(items) >= 1

    def test_update_subject(self, gdpr_service):
        item = gdpr_service.create_subject(user_id=1)
        updated = gdpr_service.update_subject(item["id"], erasure_completed_at="updated_value")
        assert updated["erasure_completed_at"] == "updated_value"

    def test_delete_subject(self, gdpr_service):
        item = gdpr_service.create_subject(user_id=1)
        result = gdpr_service.delete_subject(item["id"])
        assert result is True
        assert gdpr_service.get_subject(item["id"]) is None

    def test_count_subjects(self, gdpr_service):
        gdpr_service.create_subject(user_id=1)
        count = gdpr_service.count_subjects()
        assert count >= 1

    def test_delete_nonexistent_raises(self, gdpr_service):
        with pytest.raises(GDPRError):
            gdpr_service.delete_subject(99999)
