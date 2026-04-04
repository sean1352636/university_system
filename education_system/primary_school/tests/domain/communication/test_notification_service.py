"""Tests for the NotificationService in the Primary School system."""

import pytest


@pytest.fixture
def test_user(user_service):
    """Create a test user and return the user dict with 'id'."""
    return user_service.create_user(
        username="notif_test_user", password="TestPass123",
        role="teacher", display_name="Test User")


@pytest.fixture
def test_user2(user_service):
    """Create a second test user."""
    return user_service.create_user(
        username="notif_test_user2", password="TestPass123",
        role="teacher", display_name="Test User 2")


class TestCreateNotification:
    """Tests for creating notifications."""

    def test_create_notification_returns_dict(self, notification_service,
                                               test_user):
        """Creating a notification returns a dict with id and user_id."""
        result = notification_service.create_notification(
            user_id=test_user["id"],
            title="New Message",
            message="You have a new message from the office.",
            notification_type="Info",
        )
        assert isinstance(result, dict)
        assert "id" in result
        assert result["user_id"] == test_user["id"]

    def test_create_notification_persists(self, notification_service,
                                           test_user):
        """Created notification can be retrieved via get_notifications."""
        notification_service.create_notification(
            user_id=test_user["id"],
            title="Attendance Warning",
            message="Pupil below 90% attendance",
            notification_type="Warning",
        )
        notes = notification_service.get_notifications(test_user["id"])
        assert len(notes) == 1
        assert notes[0]["title"] == "Attendance Warning"
        assert notes[0]["notification_type"] == "Warning"
        assert notes[0]["is_read"] == 0

    def test_create_with_link(self, notification_service, test_user):
        """A notification with a link stores it correctly."""
        result = notification_service.create_notification(
            user_id=test_user["id"],
            title="Report Ready",
            message="Your report is available",
            link="/reports/123",
        )
        notes = notification_service.get_notifications(test_user["id"])
        match = [n for n in notes if n["id"] == result["id"]]
        assert match[0]["link"] == "/reports/123"


class TestGetNotifications:
    """Tests for retrieving notifications."""

    def test_get_empty_returns_empty(self, notification_service):
        """Querying a user with no notifications returns an empty list."""
        assert notification_service.get_notifications(999) == []

    def test_get_unread_only(self, notification_service, test_user):
        """unread_only filter excludes read notifications."""
        notification_service.create_notification(
            user_id=test_user["id"], title="N1", message="m1")
        r2 = notification_service.create_notification(
            user_id=test_user["id"], title="N2", message="m2")
        notification_service.mark_read(r2["id"])
        unread = notification_service.get_notifications(
            test_user["id"], unread_only=True)
        assert len(unread) == 1
        assert unread[0]["title"] == "N1"

    def test_get_notifications_only_for_user(self, notification_service,
                                              test_user, test_user2):
        """Notifications for other users are not returned."""
        notification_service.create_notification(
            user_id=test_user["id"], title="For user 1")
        notification_service.create_notification(
            user_id=test_user2["id"], title="For user 2")
        notes = notification_service.get_notifications(test_user["id"])
        assert len(notes) == 1


class TestMarkRead:
    """Tests for marking notifications as read."""

    def test_mark_read_returns_true(self, notification_service, test_user):
        """Marking an existing notification as read returns True."""
        result = notification_service.create_notification(
            user_id=test_user["id"], title="Test")
        assert notification_service.mark_read(result["id"]) is True

    def test_mark_read_persists(self, notification_service, test_user):
        """After marking read, is_read is 1."""
        result = notification_service.create_notification(
            user_id=test_user["id"], title="Test")
        notification_service.mark_read(result["id"])
        notes = notification_service.get_notifications(test_user["id"])
        assert notes[0]["is_read"] == 1

    def test_mark_read_nonexistent(self, notification_service):
        """Marking a non-existent notification returns False."""
        assert notification_service.mark_read(99999) is False


class TestMarkAllRead:
    """Tests for marking all notifications as read."""

    def test_mark_all_read(self, notification_service, test_user):
        """mark_all_read marks all unread notifications for a user."""
        notification_service.create_notification(
            user_id=test_user["id"], title="N1")
        notification_service.create_notification(
            user_id=test_user["id"], title="N2")
        count = notification_service.mark_all_read(test_user["id"])
        assert count == 2
        unread = notification_service.get_notifications(
            test_user["id"], unread_only=True)
        assert len(unread) == 0

    def test_mark_all_read_no_unread(self, notification_service):
        """mark_all_read returns 0 when there are no unread notifications."""
        assert notification_service.mark_all_read(999) == 0


class TestDeleteNotification:
    """Tests for deleting notifications."""

    def test_delete_existing(self, notification_service, test_user):
        """Deleting an existing notification returns True."""
        result = notification_service.create_notification(
            user_id=test_user["id"], title="Gone")
        assert notification_service.delete_notification(result["id"]) is True
        assert notification_service.get_notifications(test_user["id"]) == []

    def test_delete_nonexistent(self, notification_service):
        """Deleting a non-existent notification returns False."""
        assert notification_service.delete_notification(99999) is False


class TestGetUnreadCount:
    """Tests for getting unread notification count."""

    def test_unread_count_zero(self, notification_service):
        """A user with no notifications has unread count 0."""
        assert notification_service.get_unread_count(999) == 0

    def test_unread_count_increments(self, notification_service, test_user):
        """Unread count reflects the number of unread notifications."""
        notification_service.create_notification(
            user_id=test_user["id"], title="N1")
        notification_service.create_notification(
            user_id=test_user["id"], title="N2")
        assert notification_service.get_unread_count(test_user["id"]) == 2

    def test_unread_count_decrements_after_read(self, notification_service,
                                                 test_user):
        """Marking a notification as read decreases the unread count."""
        r1 = notification_service.create_notification(
            user_id=test_user["id"], title="N1")
        notification_service.create_notification(
            user_id=test_user["id"], title="N2")
        notification_service.mark_read(r1["id"])
        assert notification_service.get_unread_count(test_user["id"]) == 1
