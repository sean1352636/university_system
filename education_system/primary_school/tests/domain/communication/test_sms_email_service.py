"""Tests for SMS/Email service."""

import pytest


class TestCreate:
    """Tests for creating records."""

    def test_create_returns_dict(self, sms_email_service):
        """Creating a record should return a dict with an id."""
        result = sms_email_service.create(message_type="email", recipient="parent@example.com", subject="Newsletter", status="Sent")
        assert isinstance(result, dict)
        assert result["id"] is not None

    def test_create_stores_fields(self, sms_email_service):
        """Created record should contain the provided fields."""
        result = sms_email_service.create(message_type="email", recipient="parent@example.com", subject="Newsletter", status="Sent")
        assert result["message_type"] == "email"


class TestList:
    """Tests for listing records."""

    def test_list_empty(self, sms_email_service):
        """Listing with no records should return an empty list."""
        result = sms_email_service.list_all()
        assert isinstance(result, list)

    def test_list_after_create(self, sms_email_service):
        """Listing after creating a record should include it."""
        sms_email_service.create(message_type="email", recipient="parent@example.com", subject="Newsletter", status="Sent")
        result = sms_email_service.list_all()
        assert len(result) >= 1


class TestGet:
    """Tests for getting a single record."""

    def test_get_existing(self, sms_email_service):
        """Getting an existing record should return it."""
        created = sms_email_service.create(message_type="email", recipient="parent@example.com", subject="Newsletter", status="Sent")
        result = sms_email_service.get(created["id"])
        assert result is not None
        assert result["id"] == created["id"]

    def test_get_nonexistent(self, sms_email_service):
        """Getting a nonexistent record should return None."""
        result = sms_email_service.get(99999)
        assert result is None


class TestUpdate:
    """Tests for updating records."""

    def test_update_message_type(self, sms_email_service):
        """Updating a field should persist the change."""
        created = sms_email_service.create(message_type="email", recipient="parent@example.com", subject="Newsletter", status="Sent")
        sms_email_service.update(created["id"], message_type="Updated Value")
        result = sms_email_service.get(created["id"])
        assert result["message_type"] == "Updated Value"


class TestDelete:
    """Tests for deleting records."""

    def test_delete_existing(self, sms_email_service):
        """Deleting an existing record should remove it."""
        created = sms_email_service.create(message_type="email", recipient="parent@example.com", subject="Newsletter", status="Sent")
        sms_email_service.delete(created["id"])
        result = sms_email_service.get(created["id"])
        assert result is None
