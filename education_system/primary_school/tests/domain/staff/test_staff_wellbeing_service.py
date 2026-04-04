"""Tests for the StaffWellbeingService in the Primary School system."""

import pytest


class TestCreate:
    """Tests for creating staff wellbeing survey records."""

    def test_create_returns_id(self, staff_wellbeing_service):
        """Creating a wellbeing survey returns a positive integer ID."""
        record_id = staff_wellbeing_service.create(
            title="Spring Term Wellbeing Check",
            description="Termly staff wellbeing survey",
            created_by="STF0001",
        )
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_create_minimal_fields(self, staff_wellbeing_service):
        """A survey with only the required title can be created."""
        record_id = staff_wellbeing_service.create(
            title="Quick Pulse Survey",
        )
        assert record_id > 0

    def test_create_multiple_surveys(self, staff_wellbeing_service):
        """Multiple surveys are stored independently."""
        id1 = staff_wellbeing_service.create(title="Survey A")
        id2 = staff_wellbeing_service.create(title="Survey B")
        assert id1 != id2


class TestListAll:
    """Tests for listing wellbeing survey records."""

    def test_list_all_empty_db(self, staff_wellbeing_service):
        """Querying an empty database returns an empty list."""
        assert staff_wellbeing_service.list_all() == []

    def test_list_all_returns_created(self, staff_wellbeing_service):
        """Created surveys appear in list_all."""
        staff_wellbeing_service.create(
            title="Autumn Check", description="End of autumn term",
        )
        results = staff_wellbeing_service.list_all()
        assert len(results) == 1
        assert results[0]["title"] == "Autumn Check"

    def test_list_all_filter_by_status(self, staff_wellbeing_service):
        """Filtering by status returns only matching surveys."""
        staff_wellbeing_service.create(title="Draft One", status="draft")
        staff_wellbeing_service.create(title="Active One", status="active")
        results = staff_wellbeing_service.list_all(status="active")
        assert len(results) == 1
        assert results[0]["title"] == "Active One"


class TestGet:
    """Tests for retrieving a single wellbeing survey."""

    def test_get_existing(self, staff_wellbeing_service):
        """Retrieving an existing survey returns a dict with all fields."""
        rid = staff_wellbeing_service.create(
            title="Summer Wellbeing",
            description="End of year survey",
            created_by="STF0002",
        )
        record = staff_wellbeing_service.get(rid)
        assert record is not None
        assert record["title"] == "Summer Wellbeing"
        assert record["description"] == "End of year survey"
        assert record["created_by"] == "STF0002"

    def test_get_nonexistent(self, staff_wellbeing_service):
        """Retrieving a non-existent ID returns None."""
        assert staff_wellbeing_service.get(99999) is None


class TestUpdate:
    """Tests for updating wellbeing survey records."""

    def test_update_field(self, staff_wellbeing_service):
        """Updating a field persists the change."""
        rid = staff_wellbeing_service.create(
            title="Old Title",
        )
        result = staff_wellbeing_service.update(rid, title="New Title")
        assert result is True
        record = staff_wellbeing_service.get(rid)
        assert record["title"] == "New Title"

    def test_update_status(self, staff_wellbeing_service):
        """The status field can be changed via update."""
        rid = staff_wellbeing_service.create(title="Survey X")
        staff_wellbeing_service.update(rid, status="active")
        record = staff_wellbeing_service.get(rid)
        assert record["status"] == "active"

    def test_update_no_fields_returns_false(self, staff_wellbeing_service):
        """Passing no fields returns False."""
        rid = staff_wellbeing_service.create(title="Survey Y")
        result = staff_wellbeing_service.update(rid)
        assert result is False


class TestDelete:
    """Tests for deleting wellbeing survey records."""

    def test_delete_existing(self, staff_wellbeing_service):
        """Deleting an existing record returns True and removes it."""
        rid = staff_wellbeing_service.create(title="To Delete")
        assert staff_wellbeing_service.delete(rid) is True
        assert staff_wellbeing_service.get(rid) is None

    def test_delete_does_not_affect_others(self, staff_wellbeing_service):
        """Deleting one survey leaves other surveys intact."""
        id1 = staff_wellbeing_service.create(title="Keep This")
        id2 = staff_wellbeing_service.create(title="Remove This")
        staff_wellbeing_service.delete(id2)
        assert staff_wellbeing_service.get(id1) is not None
        assert staff_wellbeing_service.get(id2) is None
