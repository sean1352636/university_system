"""Tests for the PupilWellbeingService in the Primary School system."""

import pytest


class TestCreate:
    """Tests for creating wellbeing concern records."""

    def test_create_returns_id(self, pupil_wellbeing_service, sample_pupil):
        """Creating a concern returns a valid integer ID."""
        record_id = pupil_wellbeing_service.create(
            pupil_id=sample_pupil["pupil_id"],
            concern_type="emotional",
            description="Pupil seems withdrawn in class",
            reported_by="STF0001",
            severity="Low",
            status="Open",
        )
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_create_persists_fields(self, pupil_wellbeing_service, sample_pupil):
        """All supplied fields are stored and retrievable."""
        pid = sample_pupil["pupil_id"]
        record_id = pupil_wellbeing_service.create(
            pupil_id=pid,
            concern_type="social",
            description="Difficulty making friends",
            reported_by="STF0002",
            severity="Medium",
            status="Open",
        )
        record = pupil_wellbeing_service.get(record_id)
        assert record["pupil_id"] == pid
        assert record["concern_type"] == "social"
        assert record["description"] == "Difficulty making friends"
        assert record["reported_by"] == "STF0002"
        assert record["severity"] == "Medium"
        assert record["status"] == "Open"

    def test_create_multiple_concerns(self, pupil_wellbeing_service, sample_pupil):
        """Multiple concerns for the same pupil are stored independently."""
        pid = sample_pupil["pupil_id"]
        id1 = pupil_wellbeing_service.create(
            pupil_id=pid, concern_type="emotional",
            description="D1", reported_by="STF0001",
            status="Open",
        )
        id2 = pupil_wellbeing_service.create(
            pupil_id=pid, concern_type="behavioural",
            description="D2", reported_by="STF0001",
            status="Open",
        )
        assert id1 != id2


class TestListAll:
    """Tests for listing wellbeing concerns."""

    def test_list_all_empty_db(self, pupil_wellbeing_service):
        """An empty database returns an empty list."""
        assert pupil_wellbeing_service.list_all() == []

    def test_list_all_returns_records(self, pupil_wellbeing_service, sample_pupil):
        """All created records appear in list_all."""
        pid = sample_pupil["pupil_id"]
        pupil_wellbeing_service.create(
            pupil_id=pid, concern_type="emotional",
            description="D1", reported_by="STF0001",
            status="Open",
        )
        pupil_wellbeing_service.create(
            pupil_id=pid, concern_type="social",
            description="D2", reported_by="STF0001",
            status="Open",
        )
        records = pupil_wellbeing_service.list_all()
        assert len(records) == 2

    def test_list_all_filter_by_status(self, pupil_wellbeing_service, sample_pupil):
        """Filtering by status returns only matching records."""
        pid = sample_pupil["pupil_id"]
        pupil_wellbeing_service.create(
            pupil_id=pid, concern_type="emotional",
            description="Open concern", reported_by="STF0001",
            status="Open",
        )
        pupil_wellbeing_service.create(
            pupil_id=pid, concern_type="social",
            description="Closed concern", reported_by="STF0001",
            status="Closed",
        )
        records = pupil_wellbeing_service.list_all(status="Open")
        assert len(records) == 1
        assert records[0]["description"] == "Open concern"

    def test_list_all_filter_by_pupil(
        self, pupil_wellbeing_service, sample_pupil, sample_pupil_ks1,
    ):
        """Filtering by pupil_id returns only that pupil's records."""
        pid = sample_pupil["pupil_id"]
        pupil_wellbeing_service.create(
            pupil_id=pid, concern_type="emotional",
            description="P1", reported_by="STF0001",
            status="Open",
        )
        pupil_wellbeing_service.create(
            pupil_id=sample_pupil_ks1["pupil_id"], concern_type="emotional",
            description="P2", reported_by="STF0001",
            status="Open",
        )
        records = pupil_wellbeing_service.list_all(pupil_id=pid)
        assert len(records) == 1
        assert records[0]["description"] == "P1"


class TestGet:
    """Tests for retrieving a single wellbeing concern."""

    def test_get_existing_record(self, pupil_wellbeing_service, sample_pupil):
        """Retrieving by ID returns the correct record."""
        record_id = pupil_wellbeing_service.create(
            pupil_id=sample_pupil["pupil_id"], concern_type="emotional",
            description="Specific concern", reported_by="STF0001",
            status="Open",
        )
        record = pupil_wellbeing_service.get(record_id)
        assert record is not None
        assert record["id"] == record_id
        assert record["description"] == "Specific concern"

    def test_get_nonexistent_record(self, pupil_wellbeing_service):
        """Retrieving a non-existent ID returns None."""
        assert pupil_wellbeing_service.get(99999) is None


class TestUpdate:
    """Tests for updating wellbeing concerns."""

    def test_update_description(self, pupil_wellbeing_service, sample_pupil):
        """Updating the description persists the change."""
        record_id = pupil_wellbeing_service.create(
            pupil_id=sample_pupil["pupil_id"], concern_type="emotional",
            description="Original", reported_by="STF0001",
            status="Open",
        )
        result = pupil_wellbeing_service.update(record_id, description="Updated")
        assert result is True
        record = pupil_wellbeing_service.get(record_id)
        assert record["description"] == "Updated"

    def test_update_status_and_severity(self, pupil_wellbeing_service, sample_pupil):
        """Updating status and severity together works correctly."""
        record_id = pupil_wellbeing_service.create(
            pupil_id=sample_pupil["pupil_id"], concern_type="social",
            description="D", reported_by="STF0001",
            severity="Low", status="Open",
        )
        pupil_wellbeing_service.update(
            record_id, status="Closed", severity="High",
        )
        record = pupil_wellbeing_service.get(record_id)
        assert record["status"] == "Closed"
        assert record["severity"] == "High"

    def test_update_no_fields_returns_false(self, pupil_wellbeing_service, sample_pupil):
        """Calling update with no keyword arguments returns False."""
        record_id = pupil_wellbeing_service.create(
            pupil_id=sample_pupil["pupil_id"], concern_type="emotional",
            description="D", reported_by="STF0001",
            status="Open",
        )
        result = pupil_wellbeing_service.update(record_id)
        assert result is False


class TestDelete:
    """Tests for deleting wellbeing concerns."""

    def test_delete_existing_record(self, pupil_wellbeing_service, sample_pupil):
        """Deleting an existing record returns True and removes it."""
        record_id = pupil_wellbeing_service.create(
            pupil_id=sample_pupil["pupil_id"], concern_type="emotional",
            description="To delete", reported_by="STF0001",
            status="Open",
        )
        assert pupil_wellbeing_service.delete(record_id) is True
        assert pupil_wellbeing_service.get(record_id) is None

    def test_delete_does_not_affect_other_records(
        self, pupil_wellbeing_service, sample_pupil,
    ):
        """Deleting one record leaves others intact."""
        pid = sample_pupil["pupil_id"]
        id1 = pupil_wellbeing_service.create(
            pupil_id=pid, concern_type="emotional",
            description="Keep", reported_by="STF0001",
            status="Open",
        )
        id2 = pupil_wellbeing_service.create(
            pupil_id=pid, concern_type="social",
            description="Remove", reported_by="STF0001",
            status="Open",
        )
        pupil_wellbeing_service.delete(id2)
        assert pupil_wellbeing_service.get(id1) is not None
        assert pupil_wellbeing_service.get(id2) is None
