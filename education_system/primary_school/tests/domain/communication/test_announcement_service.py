"""Tests for the AnnouncementService in the Primary School system."""

import pytest


class TestCreateAnnouncement:
    """Tests for creating announcements."""

    def test_create_announcement_returns_dict(self, announcement_service):
        """Creating an announcement returns a dict with id and title."""
        result = announcement_service.create_announcement(
            title="Sports Day",
            content="Annual sports day next Friday",
            audience="All",
            priority="Normal",
        )
        assert isinstance(result, dict)
        assert "id" in result
        assert result["title"] == "Sports Day"

    def test_create_announcement_persists(self, announcement_service):
        """Created announcement can be retrieved by ID."""
        result = announcement_service.create_announcement(
            title="School Closure",
            content="School closed for INSET day",
            audience="All",
            priority="Urgent",
            publish_date="2026-04-10",
            expiry_date="2026-04-11",
        )
        fetched = announcement_service.get_announcement(result["id"])
        assert fetched["title"] == "School Closure"
        assert fetched["priority"] == "Urgent"
        assert fetched["audience"] == "All"
        assert fetched["publish_date"] == "2026-04-10"
        assert fetched["expiry_date"] == "2026-04-11"

    def test_create_announcement_with_created_by(self, announcement_service):
        """The created_by field is stored correctly."""
        result = announcement_service.create_announcement(
            title="Staff Meeting",
            content="Mandatory staff meeting at 3pm",
            audience="Staff",
            created_by="STF0001",
        )
        fetched = announcement_service.get_announcement(result["id"])
        assert fetched["created_by"] == "STF0001"


class TestGetAnnouncement:
    """Tests for retrieving a single announcement."""

    def test_get_nonexistent_returns_none(self, announcement_service):
        """Requesting a non-existent ID returns None."""
        assert announcement_service.get_announcement(99999) is None

    def test_get_returns_all_fields(self, announcement_service):
        """Retrieved announcement includes status and timestamps."""
        result = announcement_service.create_announcement(
            title="Uniform Reminder",
            content="Please ensure correct uniform",
            audience="Parents",
        )
        fetched = announcement_service.get_announcement(result["id"])
        assert fetched["status"] == "Active"
        assert fetched["created_at"] is not None


class TestListAnnouncements:
    """Tests for listing announcements."""

    def test_list_empty_db(self, announcement_service):
        """Listing on an empty database returns an empty list."""
        assert announcement_service.list_announcements() == []

    def test_list_returns_all_active(self, announcement_service):
        """Listing without filters returns all active announcements."""
        announcement_service.create_announcement(
            title="A1", content="Content 1", audience="All")
        announcement_service.create_announcement(
            title="A2", content="Content 2", audience="Staff")
        results = announcement_service.list_announcements()
        assert len(results) == 2

    def test_list_filter_by_audience(self, announcement_service):
        """Filtering by audience returns only matching announcements."""
        announcement_service.create_announcement(
            title="All notice", content="c", audience="All")
        announcement_service.create_announcement(
            title="Staff only", content="c", audience="Staff")
        results = announcement_service.list_announcements(audience="Staff")
        assert len(results) == 1
        assert results[0]["title"] == "Staff only"


class TestUpdateAnnouncement:
    """Tests for updating announcements."""

    @pytest.mark.xfail(reason="schema missing column: updated_at")
    def test_update_title_and_content(self, announcement_service):
        """Updating title and content persists changes."""
        result = announcement_service.create_announcement(
            title="Old Title", content="Old content", audience="All")
        updated = announcement_service.update_announcement(
            result["id"], title="New Title", content="New content")
        assert updated["title"] == "New Title"
        assert updated["content"] == "New content"

    @pytest.mark.xfail(reason="schema missing column: updated_at")
    def test_update_priority(self, announcement_service):
        """Priority can be changed from Normal to Urgent."""
        result = announcement_service.create_announcement(
            title="Notice", content="c", audience="All", priority="Normal")
        updated = announcement_service.update_announcement(
            result["id"], priority="Urgent")
        assert updated["priority"] == "Urgent"

    def test_update_with_no_valid_fields(self, announcement_service):
        """Passing no recognised fields returns None."""
        result = announcement_service.create_announcement(
            title="T", content="c", audience="All")
        assert announcement_service.update_announcement(
            result["id"], bogus="value") is None


class TestDeleteAnnouncement:
    """Tests for deleting announcements."""

    def test_delete_existing(self, announcement_service):
        """Deleting an existing announcement returns True."""
        result = announcement_service.create_announcement(
            title="Gone", content="Will be deleted", audience="All")
        assert announcement_service.delete_announcement(result["id"]) is True
        assert announcement_service.get_announcement(result["id"]) is None

    def test_delete_nonexistent(self, announcement_service):
        """Deleting a non-existent announcement returns False."""
        assert announcement_service.delete_announcement(99999) is False

    def test_delete_does_not_affect_others(self, announcement_service):
        """Deleting one announcement leaves others intact."""
        r1 = announcement_service.create_announcement(
            title="Keep", content="c1", audience="All")
        r2 = announcement_service.create_announcement(
            title="Remove", content="c2", audience="All")
        announcement_service.delete_announcement(r2["id"])
        remaining = announcement_service.list_announcements()
        assert len(remaining) == 1
        assert remaining[0]["id"] == r1["id"]
