"""Tests for PortfolioService in the Primary School Management System."""

import pytest


class TestCreate:
    """Tests for creating portfolio items."""

    def test_create_portfolio_item(self, portfolio_service, sample_pupil):
        """Creating a portfolio item should return its ID."""
        record_id = portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="My First Painting",
            description="Watercolour of a rainbow",
            subject="Art",
            term="Spring",
        )
        assert record_id is not None
        assert isinstance(record_id, int)

    def test_create_with_teacher_comment(self, portfolio_service, sample_pupil):
        """Creating a portfolio item with a teacher comment should persist."""
        record_id = portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="Science Experiment Write-up",
            subject="Science",
            term="Autumn",
            teacher_comment="Excellent observation skills",
        )
        item = portfolio_service.get(record_id)
        assert item is not None
        assert item["teacher_comment"] == "Excellent observation skills"

    def test_create_minimal_fields(self, portfolio_service, sample_pupil):
        """Creating with minimal fields should succeed."""
        record_id = portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="Quick Note",
        )
        assert record_id is not None


class TestGet:
    """Tests for retrieving portfolio items."""

    def test_get_by_id(self, portfolio_service, sample_pupil):
        """Getting a portfolio item by ID should return the correct record."""
        record_id = portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="Maths Challenge",
            subject="Mathematics",
            term="Spring",
        )
        item = portfolio_service.get(record_id)
        assert item is not None
        assert item["title"] == "Maths Challenge"
        assert item["subject"] == "Mathematics"
        assert item["pupil_id"] == sample_pupil["pupil_id"]

    def test_get_nonexistent_returns_none(self, portfolio_service):
        """Getting a non-existent item should return None."""
        item = portfolio_service.get(99999)
        assert item is None


class TestListAll:
    """Tests for listing portfolio items."""

    def test_list_all_returns_items(self, portfolio_service, sample_pupil):
        """Listing all items should return created records."""
        portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="Item A",
            term="Autumn",
        )
        portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="Item B",
            term="Spring",
        )
        items = portfolio_service.list_all()
        assert len(items) == 2

    def test_list_all_with_filter(self, portfolio_service, sample_pupil,
                                   sample_pupil_ks1):
        """Filtering by pupil_id should return only that pupil's items."""
        portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="Pupil A Work",
        )
        portfolio_service.create(
            pupil_id=sample_pupil_ks1["pupil_id"],
            title="Pupil B Work",
        )
        items = portfolio_service.list_all(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert len(items) == 1
        assert items[0]["title"] == "Pupil A Work"

    def test_list_all_empty(self, portfolio_service):
        """Listing from empty database should return empty list."""
        items = portfolio_service.list_all()
        assert items == []

    def test_list_all_with_limit(self, portfolio_service, sample_pupil):
        """Listing with a limit should respect the limit."""
        for i in range(5):
            portfolio_service.create(
                pupil_id=sample_pupil["pupil_id"],
                title=f"Item {i}",
            )
        items = portfolio_service.list_all(limit=3)
        assert len(items) == 3


class TestUpdate:
    """Tests for updating portfolio items."""

    def test_update_title(self, portfolio_service, sample_pupil):
        """Updating the title should persist."""
        record_id = portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="Old Title",
        )
        result = portfolio_service.update(record_id, title="New Title")
        assert result is True
        item = portfolio_service.get(record_id)
        assert item["title"] == "New Title"

    def test_update_description_and_subject(self, portfolio_service, sample_pupil):
        """Updating multiple fields should persist."""
        record_id = portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="My Work",
            description="Original description",
            subject="English",
        )
        portfolio_service.update(
            record_id, description="Updated description", subject="Maths",
        )
        item = portfolio_service.get(record_id)
        assert item["description"] == "Updated description"
        assert item["subject"] == "Maths"

    def test_update_no_fields_returns_false(self, portfolio_service, sample_pupil):
        """Updating with no kwargs should return False."""
        record_id = portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="Test",
        )
        result = portfolio_service.update(record_id)
        assert result is False


class TestDelete:
    """Tests for deleting portfolio items."""

    def test_delete_existing_item(self, portfolio_service, sample_pupil):
        """Deleting an existing item should return True."""
        record_id = portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="Delete Me",
        )
        deleted = portfolio_service.delete(record_id)
        assert deleted is True

    def test_delete_removes_from_database(self, portfolio_service, sample_pupil):
        """Deleted item should no longer be retrievable."""
        record_id = portfolio_service.create(
            pupil_id=sample_pupil["pupil_id"],
            title="Gone Item",
        )
        portfolio_service.delete(record_id)
        item = portfolio_service.get(record_id)
        assert item is None
