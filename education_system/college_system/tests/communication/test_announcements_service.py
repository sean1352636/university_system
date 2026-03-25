"""Tests for AnnouncementService."""

import pytest
from education_system.college_system.core.exceptions import AnnouncementError, ValidationError


class TestAnnouncementService:
    """Test suite for AnnouncementService."""

    def test_create_announcement(self, announcements_service):
        item = announcements_service.create_announcement(title="test_title", content="test_content", author_id=1)
        assert item["id"] is not None

    def test_get_announcement(self, announcements_service):
        item = announcements_service.create_announcement(title="test_title", content="test_content", author_id=1)
        found = announcements_service.get_announcement(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_announcements(self, announcements_service):
        announcements_service.create_announcement(title="test_title", content="test_content", author_id=1)
        items = announcements_service.list_announcements()
        assert len(items) >= 1

    def test_update_announcement(self, announcements_service):
        item = announcements_service.create_announcement(title="test_title", content="test_content", author_id=1)
        updated = announcements_service.update_announcement(item["id"], title="updated_value")
        assert updated["title"] == "updated_value"

    def test_delete_announcement(self, announcements_service):
        item = announcements_service.create_announcement(title="test_title", content="test_content", author_id=1)
        result = announcements_service.delete_announcement(item["id"])
        assert result is True
        assert announcements_service.get_announcement(item["id"]) is None

    def test_count_announcements(self, announcements_service):
        announcements_service.create_announcement(title="test_title", content="test_content", author_id=1)
        count = announcements_service.count_announcements()
        assert count >= 1

    def test_delete_nonexistent_raises(self, announcements_service):
        with pytest.raises(AnnouncementError):
            announcements_service.delete_announcement(99999)
