"""Tests for the GDPRService in the Primary School system."""

import pytest


class TestCreate:
    """Tests for creating GDPR request records."""

    def test_create_returns_id(self, gdpr_service):
        """Creating a GDPR request returns a positive integer ID."""
        record_id = gdpr_service.create(
            requester_name="Jane Doe",
            requester_email="jane@example.com",
            request_type="SAR",
            details="Subject access request for pupil data",
            status="pending",
            processed_by="DPO",
        )
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_create_persists(self, gdpr_service):
        """Created record can be retrieved by ID."""
        record_id = gdpr_service.create(
            requester_name="John Smith",
            requester_email="john@example.com",
            request_type="Erasure",
            status="pending",
        )
        fetched = gdpr_service.get(record_id)
        assert fetched is not None
        assert fetched["request_type"] == "Erasure"
        assert fetched["requester_name"] == "John Smith"

    def test_create_multiple(self, gdpr_service):
        """Multiple records receive distinct IDs."""
        id1 = gdpr_service.create(
            requester_name="A", request_type="SAR", status="pending",
        )
        id2 = gdpr_service.create(
            requester_name="B", request_type="Erasure", status="pending",
        )
        assert id1 != id2


class TestListAll:
    """Tests for listing GDPR request records."""

    def test_list_all_empty_db(self, gdpr_service):
        """Listing on an empty database returns an empty list."""
        assert gdpr_service.list_all() == []

    def test_list_all_returns_records(self, gdpr_service):
        """All created records appear in the list."""
        gdpr_service.create(
            requester_name="X", request_type="SAR", status="pending",
        )
        gdpr_service.create(
            requester_name="Y", request_type="Erasure", status="pending",
        )
        results = gdpr_service.list_all()
        assert len(results) == 2

    def test_list_all_with_filter(self, gdpr_service):
        """Filtering by status returns only matching records."""
        gdpr_service.create(
            requester_name="A", request_type="SAR", status="pending",
        )
        gdpr_service.create(
            requester_name="B", request_type="SAR", status="completed",
        )
        results = gdpr_service.list_all(status="completed")
        assert len(results) == 1
        assert results[0]["requester_name"] == "B"


class TestGet:
    """Tests for retrieving a single GDPR request."""

    def test_get_nonexistent_returns_none(self, gdpr_service):
        """Fetching a non-existent ID returns None."""
        assert gdpr_service.get(99999) is None


class TestUpdate:
    """Tests for updating GDPR request records."""

    def test_update_returns_true(self, gdpr_service):
        """Updating a record returns True."""
        record_id = gdpr_service.create(
            requester_name="Old", request_type="SAR", status="pending",
        )
        result = gdpr_service.update(record_id, status="in_progress")
        assert result is True

    def test_update_persists(self, gdpr_service):
        """Updated fields are reflected on retrieval."""
        record_id = gdpr_service.create(
            requester_name="Test", request_type="SAR",
            details="Original", status="pending",
        )
        gdpr_service.update(record_id, details="Updated", status="completed")
        fetched = gdpr_service.get(record_id)
        assert fetched["details"] == "Updated"
        assert fetched["status"] == "completed"

    def test_update_empty_kwargs_returns_false(self, gdpr_service):
        """Passing no fields returns False."""
        record_id = gdpr_service.create(
            requester_name="NoOp", request_type="SAR", status="pending",
        )
        result = gdpr_service.update(record_id)
        assert result is False


class TestDelete:
    """Tests for deleting GDPR request records."""

    def test_delete_existing(self, gdpr_service):
        """Deleting an existing record returns True and removes it."""
        record_id = gdpr_service.create(
            requester_name="Gone", request_type="Erasure", status="pending",
        )
        assert gdpr_service.delete(record_id) is True
        assert gdpr_service.get(record_id) is None

    def test_delete_does_not_affect_others(self, gdpr_service):
        """Deleting one record leaves other records intact."""
        id1 = gdpr_service.create(
            requester_name="Keep", request_type="SAR", status="pending",
        )
        id2 = gdpr_service.create(
            requester_name="Remove", request_type="SAR", status="pending",
        )
        gdpr_service.delete(id2)
        remaining = gdpr_service.list_all()
        assert len(remaining) == 1
        assert remaining[0]["id"] == id1
