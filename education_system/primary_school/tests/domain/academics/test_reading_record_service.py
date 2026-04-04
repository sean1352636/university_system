"""Tests for ReadingRecordService in the Primary School Management System."""

import pytest

from education_system.primary_school.core.exceptions import ReadingRecordError


class TestRecordReading:
    """Tests for recording reading entries."""

    def test_record_basic_reading(self, reading_record_service, sample_pupil):
        """Recording a reading session should return a valid record."""
        result = reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="The Gruffalo",
            book_level="Purple",
            pages_read=12,
            reading_date="2026-04-01",
        )
        assert result["record_id"] is not None
        assert result["pupil_id"] == sample_pupil["pupil_id"]
        assert result["book_title"] == "The Gruffalo"

    def test_record_reading_with_read_with(self, reading_record_service, sample_pupil):
        """Recording a guided reading session should persist read_with."""
        reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Biff and Chip",
            book_level="Yellow",
            pages_read=8,
            reading_date="2026-04-01",
            read_with="Mrs Taylor",
        )
        records = reading_record_service.get_records(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert len(records) == 1
        assert records[0]["read_with"] == "Mrs Taylor"

    def test_record_reading_with_notes(self, reading_record_service, sample_pupil):
        """Recording a reading with comments should persist them."""
        reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Room on the Broom",
            reading_date="2026-04-02",
            comments="Read with good expression",
            recorded_by="STF0001",
        )
        records = reading_record_service.get_records(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert records[0]["comments"] == "Read with good expression"
        assert records[0]["recorded_by"] == "STF0001"

    def test_record_reading_with_fluency_and_comprehension(
        self, reading_record_service, sample_pupil,
    ):
        """Fluency and comprehension scores should persist."""
        reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Stick Man",
            reading_date="2026-04-03",
            fluency="Good",
            comprehension="Developing",
        )
        records = reading_record_service.get_records(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert records[0]["fluency"] == "Good"
        assert records[0]["comprehension"] == "Developing"

    def test_record_reading_missing_pupil_id_raises(self, reading_record_service):
        """Missing pupil ID should raise ReadingRecordError."""
        with pytest.raises(ReadingRecordError):
            reading_record_service.record_reading(
                pupil_id=None,
                book_title="Some Book",
            )

    def test_record_independent_reading(self, reading_record_service, sample_pupil):
        """Default read_with should be 'Independent'."""
        reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Green Eggs and Ham",
            reading_date="2026-04-04",
        )
        records = reading_record_service.get_records(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert records[0]["read_with"] == "Independent"


class TestGetRecords:
    """Tests for retrieving reading records."""

    def test_get_by_pupil_id(self, reading_record_service, sample_pupil,
                              sample_pupil_ks1):
        """Filtering by pupil ID should return only that pupil's records."""
        reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Book A",
            reading_date="2026-04-01",
        )
        reading_record_service.record_reading(
            pupil_id=sample_pupil_ks1["pupil_id"],
            book_title="Book B",
            reading_date="2026-04-01",
        )
        records = reading_record_service.get_records(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert len(records) == 1
        assert records[0]["book_title"] == "Book A"

    def test_get_by_date_range(self, reading_record_service, sample_pupil):
        """Filtering by date range should return matching records."""
        reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Early Book",
            reading_date="2026-03-01",
        )
        reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Late Book",
            reading_date="2026-04-15",
        )
        records = reading_record_service.get_records(
            date_from="2026-04-01", date_to="2026-04-30",
        )
        assert len(records) == 1
        assert records[0]["book_title"] == "Late Book"

    def test_get_empty_results(self, reading_record_service):
        """Getting records from empty database should return empty list."""
        records = reading_record_service.get_records()
        assert records == []


class TestUpdateRecord:
    """Tests for updating reading records."""

    def test_update_book_title(self, reading_record_service, sample_pupil):
        """Updating the book title should persist."""
        result = reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Old Title",
            reading_date="2026-04-01",
        )
        updated = reading_record_service.update_record(
            result["record_id"], book_title="New Title",
        )
        assert updated["book_title"] == "New Title"

    def test_update_pages_and_level(self, reading_record_service, sample_pupil):
        """Updating pages_read and book_level should persist."""
        result = reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Test Book",
            book_level="Blue",
            pages_read=5,
            reading_date="2026-04-01",
        )
        updated = reading_record_service.update_record(
            result["record_id"], book_level="Green", pages_read=10,
        )
        assert updated["book_level"] == "Green"
        assert int(updated["pages_read"]) == 10

    def test_update_no_valid_fields(self, reading_record_service, sample_pupil):
        """Updating with no valid fields should return None."""
        result = reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Test",
            reading_date="2026-04-01",
        )
        updated = reading_record_service.update_record(
            result["record_id"], invalid_field="test",
        )
        assert updated is None


class TestDeleteRecord:
    """Tests for deleting reading records."""

    def test_delete_existing_record(self, reading_record_service, sample_pupil):
        """Deleting an existing record should return True."""
        result = reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Delete Me",
            reading_date="2026-04-01",
        )
        deleted = reading_record_service.delete_record(result["record_id"])
        assert deleted is True

    def test_delete_nonexistent_record(self, reading_record_service):
        """Deleting a non-existent record should return False."""
        deleted = reading_record_service.delete_record(99999)
        assert deleted is False

    def test_delete_removes_from_database(self, reading_record_service, sample_pupil):
        """Deleted record should no longer appear in get_records."""
        result = reading_record_service.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="Gone Book",
            reading_date="2026-04-01",
        )
        reading_record_service.delete_record(result["record_id"])
        records = reading_record_service.get_records(
            pupil_id=sample_pupil["pupil_id"],
        )
        assert records == []
