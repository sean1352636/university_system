"""Tests for PrintCreditService."""

import pytest
from education_system.college_system.core.exceptions import PrintCreditError, ValidationError


class TestPrintCreditService:
    """Test suite for PrintCreditService."""

    def test_create_account(self, print_credits_service):
        item = print_credits_service.create_account(student_id=1)
        assert item["id"] is not None

    def test_get_account(self, print_credits_service):
        item = print_credits_service.create_account(student_id=1)
        found = print_credits_service.get_account(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_accounts(self, print_credits_service):
        print_credits_service.create_account(student_id=1)
        items = print_credits_service.list_accounts()
        assert len(items) >= 1

    def test_update_account(self, print_credits_service):
        item = print_credits_service.create_account(student_id=1)
        updated = print_credits_service.update_account(item["id"], quota_reset_date="updated_value")
        assert updated["quota_reset_date"] == "updated_value"

    def test_delete_account(self, print_credits_service):
        item = print_credits_service.create_account(student_id=1)
        result = print_credits_service.delete_account(item["id"])
        assert result is True
        assert print_credits_service.get_account(item["id"]) is None

    def test_count_accounts(self, print_credits_service):
        print_credits_service.create_account(student_id=1)
        count = print_credits_service.count_accounts()
        assert count >= 1

    def test_delete_nonexistent_raises(self, print_credits_service):
        with pytest.raises(PrintCreditError):
            print_credits_service.delete_account(99999)
