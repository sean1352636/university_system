"""Tests for EmailService."""
import pytest


class TestEmail:
    def test_send_creates_email(self, email_service):
        # Users 1 (admin) and 2 (teacher) are seeded by default
        email = email_service.send(
            sender_id=1, recipient_id=2,
            subject="Hello", body="Test message",
        )
        assert email["subject"] == "Hello"
        assert email["sender_id"] == 1
        assert email["recipient_id"] == 2

    def test_get_inbox(self, email_service):
        email_service.send(1, 2, "Inbox Test", "Body")
        inbox = email_service.get_inbox(user_id=2)
        assert len(inbox) >= 1
        assert inbox[0]["subject"] == "Inbox Test"

    def test_get_sent(self, email_service):
        email_service.send(1, 2, "Sent Test", "Body")
        sent = email_service.get_sent(user_id=1)
        assert len(sent) >= 1
        assert sent[0]["subject"] == "Sent Test"

    def test_mark_read(self, email_service):
        email = email_service.send(1, 2, "Read Me", "Body")
        email_service.mark_read(email["id"], user_id=2)
        inbox = email_service.get_inbox(user_id=2)
        msg = [m for m in inbox if m["id"] == email["id"]][0]
        assert msg["is_read"] == 1

    def test_delete_email_removes_from_view(self, email_service):
        email = email_service.send(1, 2, "Delete Me", "Body")
        email_service.delete_email(email["id"], user_id=2)
        inbox = email_service.get_inbox(user_id=2)
        assert all(m["id"] != email["id"] for m in inbox)

    def test_get_unread_count(self, email_service):
        email_service.send(1, 2, "Unread 1", "Body")
        email_service.send(1, 2, "Unread 2", "Body")
        count = email_service.get_unread_count(user_id=2)
        assert count >= 2
