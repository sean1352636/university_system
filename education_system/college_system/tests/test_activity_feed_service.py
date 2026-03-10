"""Tests for ActivityFeedService."""

import pytest
from education_system.college_system.core.exceptions import ActivityFeedError, ValidationError


class TestActivityFeedService:
    """Test suite for ActivityFeedService."""

    def test_create_feed_item(self, activity_feed_service):
        item = activity_feed_service.create_feed_item(user_id=1, activity_type="test_activity_type", title="test_title")
        assert item["id"] is not None

    def test_get_feed_item(self, activity_feed_service):
        item = activity_feed_service.create_feed_item(user_id=1, activity_type="test_activity_type", title="test_title")
        found = activity_feed_service.get_feed_item(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_feed_items(self, activity_feed_service):
        activity_feed_service.create_feed_item(user_id=1, activity_type="test_activity_type", title="test_title")
        items = activity_feed_service.list_feed_items()
        assert len(items) >= 1

    def test_update_feed_item(self, activity_feed_service):
        item = activity_feed_service.create_feed_item(user_id=1, activity_type="test_activity_type", title="test_title")
        updated = activity_feed_service.update_feed_item(item["id"], activity_type="updated_value")
        assert updated["activity_type"] == "updated_value"

    def test_delete_feed_item(self, activity_feed_service):
        item = activity_feed_service.create_feed_item(user_id=1, activity_type="test_activity_type", title="test_title")
        result = activity_feed_service.delete_feed_item(item["id"])
        assert result is True
        assert activity_feed_service.get_feed_item(item["id"]) is None

    def test_count_feed_items(self, activity_feed_service):
        activity_feed_service.create_feed_item(user_id=1, activity_type="test_activity_type", title="test_title")
        count = activity_feed_service.count_feed_items()
        assert count >= 1

    def test_delete_nonexistent_raises(self, activity_feed_service):
        with pytest.raises(ActivityFeedError):
            activity_feed_service.delete_feed_item(99999)
