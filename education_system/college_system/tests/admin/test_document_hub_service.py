"""Tests for DocumentHubService."""

import pytest
from education_system.college_system.core.exceptions import DocumentHubError, ValidationError


class TestDocumentHubService:
    """Test suite for DocumentHubService."""

    def test_create_document(self, document_hub_service):
        item = document_hub_service.create_document(title="test_title", uploaded_by=1)
        assert item["id"] is not None

    def test_get_document(self, document_hub_service):
        item = document_hub_service.create_document(title="test_title", uploaded_by=1)
        found = document_hub_service.get_document(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_documents(self, document_hub_service):
        document_hub_service.create_document(title="test_title", uploaded_by=1)
        items = document_hub_service.list_documents()
        assert len(items) >= 1

    def test_update_document(self, document_hub_service):
        item = document_hub_service.create_document(title="test_title", uploaded_by=1)
        updated = document_hub_service.update_document(item["id"], title="updated_value")
        assert updated["title"] == "updated_value"

    def test_delete_document(self, document_hub_service):
        item = document_hub_service.create_document(title="test_title", uploaded_by=1)
        result = document_hub_service.delete_document(item["id"])
        assert result is True
        assert document_hub_service.get_document(item["id"]) is None

    def test_count_documents(self, document_hub_service):
        document_hub_service.create_document(title="test_title", uploaded_by=1)
        count = document_hub_service.count_documents()
        assert count >= 1

    def test_delete_nonexistent_raises(self, document_hub_service):
        with pytest.raises(DocumentHubError):
            document_hub_service.delete_document(99999)
