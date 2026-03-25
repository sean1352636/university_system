"""Tests for NotificationService."""

import pytest
from education_system.college_system.modules.domain.notifications.services.notification_service import NotificationService
from education_system.college_system.core.exceptions import NotificationError


class TestNotificationService:

    def test_send(self, notification_service, db_path):
        n = notification_service.send(1, "Test Title", "Test message", type="info")
        assert n["title"] == "Test Title"
        assert n["is_read"] == 0

    def test_count_unread(self, notification_service):
        notification_service.send(1, "Msg 1")
        notification_service.send(1, "Msg 2")
        assert notification_service.count_unread(1) == 2

    def test_mark_read(self, notification_service):
        n = notification_service.send(1, "Msg")
        notification_service.mark_read(n["id"], 1)
        assert notification_service.count_unread(1) == 0

    def test_mark_all_read(self, notification_service):
        notification_service.send(1, "Msg 1")
        notification_service.send(1, "Msg 2")
        notification_service.send(1, "Msg 3")
        count = notification_service.mark_all_read(1)
        assert count == 3
        assert notification_service.count_unread(1) == 0

    def test_send_bulk(self, notification_service, auth, db_path):
        # Create additional users so FK constraints are satisfied
        auth.create_user("user2", "Test@1234567", email="u2@test.com")
        auth.create_user("user3", "Test@1234567", email="u3@test.com")
        count = notification_service.send_bulk([1, 2, 3], "Bulk msg")
        assert count == 3

    def test_unread_only_filter(self, notification_service):
        notification_service.send(1, "Msg 1")
        n2 = notification_service.send(1, "Msg 2")
        notification_service.mark_read(n2["id"], 1)

        all_notifs = notification_service.get_notifications(1)
        unread_only = notification_service.get_notifications(1, unread_only=True)
        assert len(all_notifs) == 2
        assert len(unread_only) == 1
