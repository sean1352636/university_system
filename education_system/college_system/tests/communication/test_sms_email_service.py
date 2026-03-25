"""Tests for SmsEmailService."""

import pytest
from education_system.college_system.core.exceptions import SmsEmailError, ValidationError


class TestSmsEmailService:
    """Test suite for SmsEmailService."""

    def test_create_preference(self, sms_email_service):
        item = sms_email_service.create_preference(user_id=1)
        assert item["id"] is not None

    def test_get_preference(self, sms_email_service):
        item = sms_email_service.create_preference(user_id=1)
        found = sms_email_service.get_preference(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_preferences(self, sms_email_service):
        sms_email_service.create_preference(user_id=1)
        items = sms_email_service.list_preferences()
        assert len(items) >= 1

    def test_update_preference(self, sms_email_service):
        item = sms_email_service.create_preference(user_id=1)
        updated = sms_email_service.update_preference(item["id"], phone_number="updated_value")
        assert updated["phone_number"] == "updated_value"

    def test_delete_preference(self, sms_email_service):
        item = sms_email_service.create_preference(user_id=1)
        result = sms_email_service.delete_preference(item["id"])
        assert result is True
        assert sms_email_service.get_preference(item["id"]) is None

    def test_count_preferences(self, sms_email_service):
        sms_email_service.create_preference(user_id=1)
        count = sms_email_service.count_preferences()
        assert count >= 1

    def test_delete_nonexistent_raises(self, sms_email_service):
        with pytest.raises(SmsEmailError):
            sms_email_service.delete_preference(99999)
