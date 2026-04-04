"""Tests for the AppraisalsService in the Primary School system."""

import pytest


class TestCreate:
    """Tests for creating appraisal records."""

    def test_create_returns_id(self, appraisals_service, sample_staff):
        """Creating an appraisal returns a positive integer ID."""
        record_id = appraisals_service.create(
            staff_id=sample_staff["staff_id"],
            appraiser_id="STF0099",
            academic_year="2025-26",
            meeting_date="2026-03-01",
            overall_rating="Good",
            summary="Strong planning evident across Year 2",
        )
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_create_minimal_fields(self, appraisals_service, sample_staff):
        """An appraisal with only staff_id can be created."""
        record_id = appraisals_service.create(
            staff_id=sample_staff["staff_id"],
        )
        assert record_id > 0

    def test_create_multiple_appraisals(self, appraisals_service, sample_staff):
        """Multiple appraisals for the same staff are stored independently."""
        id1 = appraisals_service.create(
            staff_id=sample_staff["staff_id"], academic_year="2024-25",
        )
        id2 = appraisals_service.create(
            staff_id=sample_staff["staff_id"], academic_year="2025-26",
        )
        assert id1 != id2


class TestListAll:
    """Tests for listing appraisal records."""

    def test_list_all_empty_db(self, appraisals_service):
        """Querying an empty database returns an empty list."""
        assert appraisals_service.list_all() == []

    def test_list_all_returns_created(self, appraisals_service, sample_staff):
        """Created appraisals appear in list_all."""
        appraisals_service.create(
            staff_id=sample_staff["staff_id"],
            overall_rating="Outstanding",
        )
        results = appraisals_service.list_all()
        assert len(results) == 1
        assert results[0]["overall_rating"] == "Outstanding"

    def test_list_all_filter_by_staff(self, appraisals_service, sample_staff, hr_service):
        """Filtering by staff_id returns only that staff's appraisals."""
        s2 = hr_service.create_staff(first_name="X", last_name="Y", role="TA")
        appraisals_service.create(staff_id=sample_staff["staff_id"])
        appraisals_service.create(staff_id=s2["staff_id"])
        results = appraisals_service.list_all(staff_id=sample_staff["staff_id"])
        assert len(results) == 1


class TestGet:
    """Tests for retrieving a single appraisal."""

    def test_get_existing(self, appraisals_service, sample_staff):
        """Retrieving an existing appraisal returns a dict with all fields."""
        rid = appraisals_service.create(
            staff_id=sample_staff["staff_id"],
            appraiser_id="STF0099",
            academic_year="2025-26",
            summary="Good progress on targets",
        )
        record = appraisals_service.get(rid)
        assert record is not None
        assert record["summary"] == "Good progress on targets"
        assert record["appraiser_id"] == "STF0099"

    def test_get_nonexistent(self, appraisals_service):
        """Retrieving a non-existent ID returns None."""
        assert appraisals_service.get(99999) is None


class TestUpdate:
    """Tests for updating appraisal records."""

    def test_update_field(self, appraisals_service, sample_staff):
        """Updating a field persists the change."""
        rid = appraisals_service.create(
            staff_id=sample_staff["staff_id"],
            overall_rating="Good",
        )
        result = appraisals_service.update(rid, overall_rating="Outstanding")
        assert result is True
        record = appraisals_service.get(rid)
        assert record["overall_rating"] == "Outstanding"

    def test_update_no_fields_returns_false(self, appraisals_service, sample_staff):
        """Passing no fields returns False."""
        rid = appraisals_service.create(
            staff_id=sample_staff["staff_id"],
        )
        result = appraisals_service.update(rid)
        assert result is False


class TestDelete:
    """Tests for deleting appraisal records."""

    def test_delete_existing(self, appraisals_service, sample_staff):
        """Deleting an existing record returns True and removes it."""
        rid = appraisals_service.create(
            staff_id=sample_staff["staff_id"],
        )
        assert appraisals_service.delete(rid) is True
        assert appraisals_service.get(rid) is None

    def test_delete_does_not_affect_others(self, appraisals_service, sample_staff):
        """Deleting one record leaves other records intact."""
        id1 = appraisals_service.create(
            staff_id=sample_staff["staff_id"], academic_year="2024-25",
        )
        id2 = appraisals_service.create(
            staff_id=sample_staff["staff_id"], academic_year="2025-26",
        )
        appraisals_service.delete(id2)
        assert appraisals_service.get(id1) is not None
        assert appraisals_service.get(id2) is None
