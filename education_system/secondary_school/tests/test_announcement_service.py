"""Tests for AnnouncementService."""
import pytest


class TestAnnouncement:
    def test_create(self, announcement_service):
        ann = announcement_service.create(
            title="Welcome Back", body="Term starts Monday.",
            audience="all", created_by="admin",
        )
        assert ann["title"] == "Welcome Back"
        assert ann["audience"] == "all"

    def test_list_announcements(self, announcement_service):
        announcement_service.create("Ann 1", "Body 1")
        announcement_service.create("Ann 2", "Body 2")
        anns = announcement_service.list_announcements()
        assert len(anns) >= 2

    def test_list_announcements_filters_by_audience(self, announcement_service):
        announcement_service.create("Staff Only", "Staff info", audience="staff")
        announcement_service.create("Students Only", "Student info", audience="students")
        anns = announcement_service.list_announcements(audience="staff")
        # Should include staff-audience and all-audience announcements
        assert all(a["audience"] in ("staff", "all") for a in anns)

    def test_toggle_publish_unpublishes(self, announcement_service):
        ann = announcement_service.create("Toggle Me", "Body")
        assert ann["published"] == 1
        announcement_service.toggle_publish(ann["id"])
        # After unpublishing, published_only listing should not include it
        anns = announcement_service.list_announcements(published_only=True)
        assert all(a["id"] != ann["id"] for a in anns)

    def test_delete(self, announcement_service):
        ann = announcement_service.create("Delete Me", "Body")
        announcement_service.delete(ann["id"])
        anns = announcement_service.list_announcements()
        assert all(a["id"] != ann["id"] for a in anns)
