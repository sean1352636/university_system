"""Tests for MessageService."""

import pytest


class TestMessageService:
    @pytest.fixture
    def message_service(self, db_path):
        from education_system.college_system.modules.domain.messaging.services.message_service import MessageService
        return MessageService(db_path)

    def test_send_message(self, message_service):
        msg = message_service.send_message(
            sender_id=1, recipient_id=2,
            subject="Hello", body="Test message",
        )
        assert msg["subject"] == "Hello"
        assert msg["is_read"] == 0

    def test_get_inbox(self, message_service):
        message_service.send_message(sender_id=1, recipient_id=2, subject="Msg 1", body="Body 1")
        message_service.send_message(sender_id=1, recipient_id=2, subject="Msg 2", body="Body 2")
        inbox = message_service.get_inbox(user_id=2)
        assert len(inbox) >= 2

    def test_get_inbox_unread_only(self, message_service):
        msg = message_service.send_message(sender_id=1, recipient_id=2, subject="Read me", body="Body")
        message_service.mark_read(msg["id"], user_id=2)
        message_service.send_message(sender_id=1, recipient_id=2, subject="Unread", body="Body")
        unread = message_service.get_inbox(user_id=2, unread_only=True)
        assert all(m["is_read"] == 0 for m in unread)

    def test_get_sent(self, message_service):
        message_service.send_message(sender_id=1, recipient_id=2, subject="Sent", body="Body")
        sent = message_service.get_sent(user_id=1)
        assert len(sent) >= 1

    def test_get_message(self, message_service):
        msg = message_service.send_message(sender_id=1, recipient_id=2, subject="Get me", body="Content")
        found = message_service.get_message(msg["id"], user_id=2)
        assert found is not None
        assert found["subject"] == "Get me"

    def test_mark_read(self, message_service):
        msg = message_service.send_message(sender_id=1, recipient_id=2, subject="Mark", body="Body")
        result = message_service.mark_read(msg["id"], user_id=2)
        assert result is True

    def test_count_unread(self, message_service):
        message_service.send_message(sender_id=1, recipient_id=2, subject="Unread 1", body="Body")
        message_service.send_message(sender_id=1, recipient_id=2, subject="Unread 2", body="Body")
        count = message_service.count_unread(user_id=2)
        assert count >= 2

    def test_delete_message(self, message_service):
        msg = message_service.send_message(sender_id=1, recipient_id=2, subject="Delete", body="Body")
        result = message_service.delete_message(msg["id"], user_id=2)
        assert result is True
