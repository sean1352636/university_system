"""Tests for the ComplaintsService in the Primary School system."""

import pytest


class TestCreate:
    """Tests for creating complaint records."""

    def test_create_returns_id(self, complaints_service):
        """Creating a complaint returns a positive integer ID."""
        record_id = complaints_service.create(
            complainant_id="PAR001",
            category="Facilities",
            subject="Broken playground equipment",
            description="The climbing frame has a loose bolt",
            status="open",
            priority="high",
        )
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_create_persists(self, complaints_service):
        """Created record can be retrieved by ID."""
        record_id = complaints_service.create(
            complainant_id="PAR002",
            category="Teaching",
            subject="Homework concern",
            description="Too much homework for Year 2",
            status="open",
        )
        fetched = complaints_service.get(record_id)
        assert fetched is not None
        assert fetched["complainant_id"] == "PAR002"
        assert fetched["category"] == "Teaching"

    def test_create_multiple(self, complaints_service):
        """Multiple records receive distinct IDs."""
        id1 = complaints_service.create(
            complainant_id="A", category="X",
            subject="S1", description="D1", status="open",
        )
        id2 = complaints_service.create(
            complainant_id="B", category="Y",
            subject="S2", description="D2", status="open",
        )
        assert id1 != id2


class TestListAll:
    """Tests for listing complaint records."""

    def test_list_all_empty_db(self, complaints_service):
        """Listing on an empty database returns an empty list."""
        assert complaints_service.list_all() == []

    def test_list_all_returns_records(self, complaints_service):
        """All created records appear in the list."""
        complaints_service.create(
            complainant_id="P1", category="C1",
            subject="S1", description="D1", status="open",
        )
        complaints_service.create(
            complainant_id="P2", category="C2",
            subject="S2", description="D2", status="open",
        )
        results = complaints_service.list_all()
        assert len(results) == 2

    def test_list_all_with_filter(self, complaints_service):
        """Filtering by status returns only matching records."""
        complaints_service.create(
            complainant_id="A", category="X",
            subject="S", description="D", status="open",
        )
        complaints_service.create(
            complainant_id="B", category="Y",
            subject="S", description="D", status="resolved",
        )
        results = complaints_service.list_all(status="resolved")
        assert len(results) == 1
        assert results[0]["complainant_id"] == "B"


class TestGet:
    """Tests for retrieving a single complaint."""

    def test_get_nonexistent_returns_none(self, complaints_service):
        """Fetching a non-existent ID returns None."""
        assert complaints_service.get(99999) is None


class TestUpdate:
    """Tests for updating complaint records."""

    def test_update_returns_true(self, complaints_service):
        """Updating a record returns True."""
        record_id = complaints_service.create(
            complainant_id="T", category="General",
            subject="Issue", description="Details", status="open",
        )
        result = complaints_service.update(record_id, status="in_progress")
        assert result is True

    def test_update_persists(self, complaints_service):
        """Updated fields are reflected on retrieval."""
        record_id = complaints_service.create(
            complainant_id="T", category="General",
            subject="Issue", description="Details", status="open",
            priority="normal",
        )
        complaints_service.update(record_id, status="resolved", priority="high")
        fetched = complaints_service.get(record_id)
        assert fetched["status"] == "resolved"
        assert fetched["priority"] == "high"

    def test_update_empty_kwargs_returns_false(self, complaints_service):
        """Passing no fields returns False."""
        record_id = complaints_service.create(
            complainant_id="NoOp", category="X",
            subject="S", description="D", status="open",
        )
        result = complaints_service.update(record_id)
        assert result is False


class TestDelete:
    """Tests for deleting complaint records."""

    def test_delete_existing(self, complaints_service):
        """Deleting an existing record returns True and removes it."""
        record_id = complaints_service.create(
            complainant_id="Gone", category="X",
            subject="S", description="D", status="open",
        )
        assert complaints_service.delete(record_id) is True
        assert complaints_service.get(record_id) is None

    def test_delete_does_not_affect_others(self, complaints_service):
        """Deleting one record leaves other records intact."""
        id1 = complaints_service.create(
            complainant_id="Keep", category="A",
            subject="S1", description="D1", status="open",
        )
        id2 = complaints_service.create(
            complainant_id="Remove", category="B",
            subject="S2", description="D2", status="open",
        )
        complaints_service.delete(id2)
        remaining = complaints_service.list_all()
        assert len(remaining) == 1
        assert remaining[0]["id"] == id1
