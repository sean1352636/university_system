"""Tests for NotificationService."""
import pytest


class TestNotification:
    def test_create(self, notification_service):
        notification_service.create(user_id=1, title="Test", message="Hello")
        notifications = notification_service.list_notifications(user_id=1)
        assert len(notifications) >= 1
        assert notifications[0]["title"] == "Test"

    def test_list_notifications(self, notification_service):
        notification_service.create(1, "Note 1", "Msg 1")
        notification_service.create(1, "Note 2", "Msg 2")
        notifications = notification_service.list_notifications(user_id=1)
        assert len(notifications) >= 2

    def test_list_notifications_unread_only(self, notification_service):
        notification_service.create(1, "Unread", "Msg")
        notification_service.create(1, "Read Later", "Msg")
        # Mark one as read
        all_notifs = notification_service.list_notifications(user_id=1)
        notification_service.mark_read(all_notifs[0]["id"])
        unread = notification_service.list_notifications(user_id=1, unread_only=True)
        assert all(n["is_read"] == 0 for n in unread)

    def test_mark_read(self, notification_service):
        notification_service.create(1, "Mark Me", "Msg")
        notifs = notification_service.list_notifications(user_id=1)
        notification_service.mark_read(notifs[0]["id"])
        updated = notification_service.list_notifications(user_id=1)
        marked = [n for n in updated if n["id"] == notifs[0]["id"]][0]
        assert marked["is_read"] == 1

    def test_mark_all_read(self, notification_service):
        notification_service.create(1, "A", "Msg")
        notification_service.create(1, "B", "Msg")
        notification_service.mark_all_read(user_id=1)
        unread = notification_service.list_notifications(user_id=1, unread_only=True)
        assert len(unread) == 0

    def test_delete_notification(self, notification_service):
        notification_service.create(1, "Del Me", "Msg")
        notifs = notification_service.list_notifications(user_id=1)
        nid = notifs[0]["id"]
        notification_service.delete_notification(nid)
        after = notification_service.list_notifications(user_id=1)
        assert all(n["id"] != nid for n in after)

    def test_unread_count(self, notification_service):
        notification_service.create(1, "A", "Msg")
        notification_service.create(1, "B", "Msg")
        count = notification_service.unread_count(user_id=1)
        assert count >= 2
