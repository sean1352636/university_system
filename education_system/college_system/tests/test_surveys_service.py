"""Tests for SurveyService."""

import pytest
from education_system.college_system.core.exceptions import SurveyError, ValidationError


class TestSurveyService:
    """Test suite for SurveyService."""

    def test_create_survey(self, surveys_service):
        item = surveys_service.create_survey(title="test_title", created_by=1)
        assert item["id"] is not None

    def test_get_survey(self, surveys_service):
        item = surveys_service.create_survey(title="test_title", created_by=1)
        found = surveys_service.get_survey(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_surveys(self, surveys_service):
        surveys_service.create_survey(title="test_title", created_by=1)
        items = surveys_service.list_surveys()
        assert len(items) >= 1

    def test_update_survey(self, surveys_service):
        item = surveys_service.create_survey(title="test_title", created_by=1)
        updated = surveys_service.update_survey(item["id"], title="updated_value")
        assert updated["title"] == "updated_value"

    def test_delete_survey(self, surveys_service):
        item = surveys_service.create_survey(title="test_title", created_by=1)
        result = surveys_service.delete_survey(item["id"])
        assert result is True
        assert surveys_service.get_survey(item["id"]) is None

    def test_count_surveys(self, surveys_service):
        surveys_service.create_survey(title="test_title", created_by=1)
        count = surveys_service.count_surveys()
        assert count >= 1

    def test_delete_nonexistent_raises(self, surveys_service):
        with pytest.raises(SurveyError):
            surveys_service.delete_survey(99999)
