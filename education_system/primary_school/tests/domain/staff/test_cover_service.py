"""Tests for the CoverService in the Primary School system."""

import pytest


class TestCreateCover:
    """Tests for creating cover arrangements."""

    def test_create_cover_returns_id(self, cover_service, sample_staff):
        """Creating a cover arrangement returns a positive integer ID."""
        cover_id = cover_service.create_cover(
            absent_staff_id=sample_staff["staff_id"],
            class_name="1A",
            date="2026-04-07",
            period="AM",
            cover_notes="Supply teacher covering",
        )
        assert isinstance(cover_id, int)
        assert cover_id > 0

    def test_create_cover_with_cover_staff(self, cover_service, hr_service):
        """A cover arrangement can reference an internal cover staff member."""
        absent = hr_service.create_staff(
            first_name="Jo", last_name="Absent", role="Teacher",
        )
        covering = hr_service.create_staff(
            first_name="Sam", last_name="Cover", role="TA",
        )
        cover_id = cover_service.create_cover(
            absent_staff_id=absent["staff_id"],
            class_name="3B",
            date="2026-04-08",
            cover_staff_id=covering["staff_id"],
        )
        covers = cover_service.get_covers(date="2026-04-08")
        assert len(covers) == 1
        assert covers[0]["cover_staff_id"] == covering["staff_id"]

    def test_create_multiple_covers(self, cover_service, sample_staff):
        """Multiple cover records are stored independently."""
        id1 = cover_service.create_cover(
            absent_staff_id=sample_staff["staff_id"],
            class_name="1A", date="2026-04-07",
        )
        id2 = cover_service.create_cover(
            absent_staff_id=sample_staff["staff_id"],
            class_name="1A", date="2026-04-08",
        )
        assert id1 != id2


class TestGetCovers:
    """Tests for retrieving cover arrangements."""

    def test_get_covers_empty_db(self, cover_service):
        """Querying an empty database returns an empty list."""
        assert cover_service.get_covers() == []

    def test_get_covers_by_date(self, cover_service, sample_staff):
        """Filtering by date returns only matching covers."""
        sid = sample_staff["staff_id"]
        cover_service.create_cover(absent_staff_id=sid, class_name="1A", date="2026-04-07")
        cover_service.create_cover(absent_staff_id=sid, class_name="2B", date="2026-04-08")
        covers = cover_service.get_covers(date="2026-04-07")
        assert len(covers) == 1
        assert covers[0]["class_name"] == "1A"

    def test_get_covers_by_absent_staff(self, cover_service, hr_service):
        """Filtering by absent_staff_id returns only that staff's covers."""
        s1 = hr_service.create_staff(first_name="A", last_name="B", role="Teacher")
        s2 = hr_service.create_staff(first_name="C", last_name="D", role="Teacher")
        cover_service.create_cover(absent_staff_id=s1["staff_id"], class_name="1A", date="2026-04-07")
        cover_service.create_cover(absent_staff_id=s2["staff_id"], class_name="2B", date="2026-04-07")
        covers = cover_service.get_covers(absent_staff_id=s1["staff_id"])
        assert len(covers) == 1

    def test_cover_persists_all_fields(self, cover_service, sample_staff):
        """All supplied fields are stored and retrievable."""
        cover_service.create_cover(
            absent_staff_id=sample_staff["staff_id"],
            class_name="4C", date="2026-04-09",
            period="PM", subject_code="MAT",
            cover_notes="Pages 12-15",
        )
        covers = cover_service.get_covers(date="2026-04-09")
        c = covers[0]
        assert c["period"] == "PM"
        assert c["subject_code"] == "MAT"
        assert c["cover_notes"] == "Pages 12-15"


class TestUpdateCover:
    """Tests for updating cover arrangements."""

    def test_update_cover_field(self, cover_service, sample_staff):
        """Updating a field persists the change."""
        cid = cover_service.create_cover(
            absent_staff_id=sample_staff["staff_id"],
            class_name="1A", date="2026-04-07",
        )
        result = cover_service.update_cover(cid, cover_notes="Updated notes")
        assert result is True
        covers = cover_service.get_covers(date="2026-04-07")
        assert covers[0]["cover_notes"] == "Updated notes"

    def test_update_with_no_valid_fields(self, cover_service, sample_staff):
        """Passing no recognised fields returns None."""
        cid = cover_service.create_cover(
            absent_staff_id=sample_staff["staff_id"],
            class_name="1A", date="2026-04-07",
        )
        result = cover_service.update_cover(cid, bogus_field="value")
        assert result is None


class TestDeleteCover:
    """Tests for deleting cover arrangements."""

    def test_delete_existing_cover(self, cover_service, sample_staff):
        """Deleting an existing cover returns True and removes it."""
        cid = cover_service.create_cover(
            absent_staff_id=sample_staff["staff_id"],
            class_name="1A", date="2026-04-07",
        )
        assert cover_service.delete_cover(cid) is True
        assert cover_service.get_covers(date="2026-04-07") == []

    def test_delete_nonexistent_cover(self, cover_service):
        """Deleting a non-existent cover returns False."""
        assert cover_service.delete_cover(99999) is False
