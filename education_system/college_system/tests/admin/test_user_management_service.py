"""Tests for UserManagementService."""

import pytest
from education_system.college_system.core.exceptions import UserManagementError, ValidationError


class TestUserManagementService:
    """Test suite for UserManagementService."""

    def test_create_template(self, user_management_service):
        item = user_management_service.create_template(template_name="test_template_name", role="test_role")
        assert item["id"] is not None

    def test_get_template(self, user_management_service):
        item = user_management_service.create_template(template_name="test_template_name", role="test_role")
        found = user_management_service.get_template(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_templates(self, user_management_service):
        user_management_service.create_template(template_name="test_template_name", role="test_role")
        items = user_management_service.list_templates()
        assert len(items) >= 1

    def test_update_template(self, user_management_service):
        item = user_management_service.create_template(template_name="test_template_name", role="test_role")
        updated = user_management_service.update_template(item["id"], template_name="updated_value")
        assert updated["template_name"] == "updated_value"

    def test_delete_template(self, user_management_service):
        item = user_management_service.create_template(template_name="test_template_name", role="test_role")
        result = user_management_service.delete_template(item["id"])
        assert result is True
        assert user_management_service.get_template(item["id"]) is None

    def test_count_templates(self, user_management_service):
        user_management_service.create_template(template_name="test_template_name", role="test_role")
        count = user_management_service.count_templates()
        assert count >= 1

    def test_delete_nonexistent_raises(self, user_management_service):
        with pytest.raises(UserManagementError):
            user_management_service.delete_template(99999)
