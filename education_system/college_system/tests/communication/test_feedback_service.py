"""Tests for FeedbackService."""

import pytest
from education_system.college_system.core.exceptions import FeedbackError, ValidationError


class TestFeedbackService:
    """Test suite for FeedbackService."""

    def test_create_feedback(self, feedback_service):
        item = feedback_service.create_feedback(title="test_title")
        assert item["id"] is not None

    def test_get_feedback(self, feedback_service):
        item = feedback_service.create_feedback(title="test_title")
        found = feedback_service.get_feedback(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_feedbacks(self, feedback_service):
        feedback_service.create_feedback(title="test_title")
        items = feedback_service.list_feedbacks()
        assert len(items) >= 1

    def test_update_feedback(self, feedback_service):
        item = feedback_service.create_feedback(title="test_title")
        updated = feedback_service.update_feedback(item["id"], title="updated_value")
        assert updated["title"] == "updated_value"

    def test_delete_feedback(self, feedback_service):
        item = feedback_service.create_feedback(title="test_title")
        result = feedback_service.delete_feedback(item["id"])
        assert result is True
        assert feedback_service.get_feedback(item["id"]) is None

    def test_count_feedbacks(self, feedback_service):
        feedback_service.create_feedback(title="test_title")
        count = feedback_service.count_feedbacks()
        assert count >= 1

    def test_delete_nonexistent_raises(self, feedback_service):
        with pytest.raises(FeedbackError):
            feedback_service.delete_feedback(99999)
