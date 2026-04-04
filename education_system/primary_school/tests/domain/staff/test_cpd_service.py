"""Tests for the CPDService in the Primary School system."""

import pytest


class TestCreateRecord:
    """Tests for creating CPD records."""

    def test_create_record_returns_id(self, cpd_service, sample_staff):
        """Creating a CPD record returns a positive integer ID."""
        record_id = cpd_service.create_record(
            staff_id=sample_staff["staff_id"],
            title="Safeguarding Level 2",
            provider="Local Authority",
            hours=6,
            completion_date="2026-03-15",
            certificate="CERT-001",
        )
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_create_record_minimal_fields(self, cpd_service, sample_staff):
        """A record with only required fields is created successfully."""
        record_id = cpd_service.create_record(
            staff_id=sample_staff["staff_id"],
            title="First Aid Refresher",
        )
        assert record_id > 0

    def test_create_multiple_records(self, cpd_service, sample_staff):
        """Multiple CPD records for the same staff are stored independently."""
        id1 = cpd_service.create_record(
            staff_id=sample_staff["staff_id"], title="Course A",
        )
        id2 = cpd_service.create_record(
            staff_id=sample_staff["staff_id"], title="Course B",
        )
        assert id1 != id2


class TestGetRecords:
    """Tests for retrieving CPD records."""

    def test_get_records_empty_db(self, cpd_service):
        """Querying an empty database returns an empty list."""
        assert cpd_service.get_records() == []

    def test_get_records_by_staff(self, cpd_service, sample_staff):
        """Filtering by staff_id returns only that staff member's records."""
        sid = sample_staff["staff_id"]
        cpd_service.create_record(staff_id=sid, title="Phonics Training")
        records = cpd_service.get_records(staff_id=sid)
        assert len(records) == 1
        assert records[0]["title"] == "Phonics Training"

    def test_get_records_by_status(self, cpd_service, sample_staff):
        """Filtering by status returns only matching records."""
        sid = sample_staff["staff_id"]
        cpd_service.create_record(staff_id=sid, title="Planned", status="Planned")
        cpd_service.create_record(staff_id=sid, title="Done", status="Completed")
        planned = cpd_service.get_records(status="Planned")
        assert len(planned) == 1
        assert planned[0]["title"] == "Planned"

    def test_record_persists_all_fields(self, cpd_service, sample_staff):
        """All supplied fields are stored and retrievable."""
        sid = sample_staff["staff_id"]
        cpd_service.create_record(
            staff_id=sid, title="Maths Mastery",
            provider="NCETM", hours=12,
            completion_date="2026-02-20", certificate="NCETM-42",
        )
        records = cpd_service.get_records(staff_id=sid)
        rec = records[0]
        assert rec["provider"] == "NCETM"
        assert rec["hours"] == 12
        assert rec["certificate"] == "NCETM-42"


class TestUpdateRecord:
    """Tests for updating CPD records."""

    def test_update_record_field(self, cpd_service, sample_staff):
        """Updating a field persists the change."""
        rid = cpd_service.create_record(
            staff_id=sample_staff["staff_id"], title="Old Title",
        )
        result = cpd_service.update_record(rid, title="New Title")
        assert result is True
        records = cpd_service.get_records(staff_id=sample_staff["staff_id"])
        assert records[0]["title"] == "New Title"

    def test_update_with_no_valid_fields(self, cpd_service, sample_staff):
        """Passing no recognised fields returns None."""
        rid = cpd_service.create_record(
            staff_id=sample_staff["staff_id"], title="X",
        )
        result = cpd_service.update_record(rid, bogus_field="value")
        assert result is None


class TestDeleteRecord:
    """Tests for deleting CPD records."""

    def test_delete_existing_record(self, cpd_service, sample_staff):
        """Deleting an existing record returns True and removes it."""
        rid = cpd_service.create_record(
            staff_id=sample_staff["staff_id"], title="To Remove",
        )
        assert cpd_service.delete_record(rid) is True
        assert cpd_service.get_records(staff_id=sample_staff["staff_id"]) == []

    def test_delete_nonexistent_record(self, cpd_service):
        """Deleting a non-existent record returns False."""
        assert cpd_service.delete_record(99999) is False
