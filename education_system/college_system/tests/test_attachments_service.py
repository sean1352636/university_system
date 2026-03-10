"""Tests for AttachmentService."""

import pytest
from education_system.college_system.core.exceptions import AttachmentError, ValidationError


class TestAttachmentService:
    """Test suite for AttachmentService."""

    def test_create_attachment(self, attachments_service):
        item = attachments_service.create_attachment(uploaded_by=1, filename="test_filename", original_filename="test_original_filename", file_path="test_file_path")
        assert item["id"] is not None

    def test_get_attachment(self, attachments_service):
        item = attachments_service.create_attachment(uploaded_by=1, filename="test_filename", original_filename="test_original_filename", file_path="test_file_path")
        found = attachments_service.get_attachment(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_attachments(self, attachments_service):
        attachments_service.create_attachment(uploaded_by=1, filename="test_filename", original_filename="test_original_filename", file_path="test_file_path")
        items = attachments_service.list_attachments()
        assert len(items) >= 1

    def test_update_attachment(self, attachments_service):
        item = attachments_service.create_attachment(uploaded_by=1, filename="test_filename", original_filename="test_original_filename", file_path="test_file_path")
        updated = attachments_service.update_attachment(item["id"], filename="updated_value")
        assert updated["filename"] == "updated_value"

    def test_delete_attachment(self, attachments_service):
        item = attachments_service.create_attachment(uploaded_by=1, filename="test_filename", original_filename="test_original_filename", file_path="test_file_path")
        result = attachments_service.delete_attachment(item["id"])
        assert result is True
        assert attachments_service.get_attachment(item["id"]) is None

    def test_count_attachments(self, attachments_service):
        attachments_service.create_attachment(uploaded_by=1, filename="test_filename", original_filename="test_original_filename", file_path="test_file_path")
        count = attachments_service.count_attachments()
        assert count >= 1

    def test_delete_nonexistent_raises(self, attachments_service):
        with pytest.raises(AttachmentError):
            attachments_service.delete_attachment(99999)
