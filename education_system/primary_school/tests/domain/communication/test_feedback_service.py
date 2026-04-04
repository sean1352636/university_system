"""Tests for the FeedbackService in the Primary School system."""

import pytest


class TestCreate:
    """Tests for creating feedback records."""

    def test_create_returns_id(self, feedback_service):
        """Creating a feedback record returns an integer ID."""
        record_id = feedback_service.create(
            user_id="USR001",
            category="Facilities",
            title="Playground Equipment",
            description="The playground equipment needs repair.",
            status="open",
        )
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_create_persists(self, feedback_service):
        """Created feedback can be retrieved by ID."""
        record_id = feedback_service.create(
            user_id="USR002",
            category="Teaching",
            title="Year 1 Teacher",
            description="Very happy with Year 1 teacher.",
            status="open",
        )
        fetched = feedback_service.get(record_id)
        assert fetched["user_id"] == "USR002"
        assert fetched["category"] == "Teaching"
        assert fetched["description"] == "Very happy with Year 1 teacher."
        assert fetched["status"] == "open"

    def test_create_with_response(self, feedback_service):
        """A feedback record with acknowledged status stores it correctly."""
        record_id = feedback_service.create(
            user_id="USR003",
            category="Communication",
            title="Newsletter Feedback",
            description="Newsletter was very informative.",
            status="acknowledged",
        )
        fetched = feedback_service.get(record_id)
        assert fetched["status"] == "acknowledged"
        assert fetched["title"] == "Newsletter Feedback"


class TestGet:
    """Tests for retrieving a single feedback record."""

    def test_get_nonexistent_returns_none(self, feedback_service):
        """Requesting a non-existent ID returns None."""
        assert feedback_service.get(99999) is None


class TestListAll:
    """Tests for listing feedback records."""

    def test_list_all_empty_db(self, feedback_service):
        """Listing on an empty database returns an empty list."""
        assert feedback_service.list_all() == []

    def test_list_all_returns_records(self, feedback_service):
        """Listing returns all created records."""
        feedback_service.create(
            user_id="P1", category="General", title="T1",
            description="M1", status="open")
        feedback_service.create(
            user_id="P2", category="General", title="T2",
            description="M2", status="open")
        results = feedback_service.list_all()
        assert len(results) == 2

    def test_list_all_with_filter(self, feedback_service):
        """Filtering by status returns only matching records."""
        feedback_service.create(
            user_id="P1", category="General", title="T1",
            description="M1", status="open")
        feedback_service.create(
            user_id="P2", category="General", title="T2",
            description="M2", status="closed")
        results = feedback_service.list_all(status="open")
        assert len(results) == 1
        assert results[0]["user_id"] == "P1"

    def test_list_all_respects_limit(self, feedback_service):
        """The limit parameter restricts the number of results."""
        for i in range(5):
            feedback_service.create(
                user_id=f"P{i}", category="General",
                title=f"T{i}", description=f"M{i}", status="open")
        results = feedback_service.list_all(limit=3)
        assert len(results) == 3


class TestUpdate:
    """Tests for updating feedback records."""

    def test_update_status(self, feedback_service):
        """Updating status persists the change."""
        record_id = feedback_service.create(
            user_id="P1", category="General", title="T1",
            description="M1", status="open")
        result = feedback_service.update(record_id, status="closed")
        assert result is True
        fetched = feedback_service.get(record_id)
        assert fetched["status"] == "closed"

    def test_update_response(self, feedback_service):
        """Updating category on existing feedback persists it."""
        record_id = feedback_service.create(
            user_id="P1", category="General", title="T1",
            description="M1", status="open")
        feedback_service.update(
            record_id, category="Teaching", status="acknowledged")
        fetched = feedback_service.get(record_id)
        assert fetched["category"] == "Teaching"
        assert fetched["status"] == "acknowledged"

    def test_update_no_fields_returns_false(self, feedback_service):
        """Passing no fields returns False."""
        record_id = feedback_service.create(
            user_id="P1", category="General", title="T1",
            description="M1", status="open")
        result = feedback_service.update(record_id)
        assert result is False


class TestDelete:
    """Tests for deleting feedback records."""

    def test_delete_existing(self, feedback_service):
        """Deleting an existing record returns True and removes it."""
        record_id = feedback_service.create(
            user_id="P1", category="General", title="T1",
            description="M1", status="open")
        assert feedback_service.delete(record_id) is True
        assert feedback_service.get(record_id) is None

    def test_delete_does_not_affect_others(self, feedback_service):
        """Deleting one record leaves other records intact."""
        id1 = feedback_service.create(
            user_id="Keep", category="General", title="T1",
            description="M1", status="open")
        id2 = feedback_service.create(
            user_id="Remove", category="General", title="T2",
            description="M2", status="open")
        feedback_service.delete(id2)
        remaining = feedback_service.list_all()
        assert len(remaining) == 1
        assert remaining[0]["id"] == id1
