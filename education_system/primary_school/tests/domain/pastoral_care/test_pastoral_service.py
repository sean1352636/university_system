"""Tests for the PastoralService in the Primary School system."""

import pytest


class TestCreateNote:
    """Tests for creating pastoral notes."""

    def test_create_note_returns_id(self, pastoral_service, sample_pupil):
        """Creating a pastoral note returns a valid integer ID."""
        note_id = pastoral_service.create_note(
            pupil_id=sample_pupil["pupil_id"],
            note_type="welfare",
            subject="Home situation",
            details="Parent reported change in circumstances",
            recorded_by="STF0001",
        )
        assert isinstance(note_id, int)
        assert note_id > 0

    def test_create_note_with_follow_up(self, pastoral_service, sample_pupil):
        """A note with follow-up fields persists correctly."""
        pid = sample_pupil["pupil_id"]
        note_id = pastoral_service.create_note(
            pupil_id=pid,
            note_type="family",
            subject="Custody change",
            details="New custody arrangement in place",
            recorded_by="STF0001",
            follow_up_required=1,
            follow_up_date="2026-04-18",
        )
        notes = pastoral_service.get_notes(pupil_id=pid)
        note = next(n for n in notes if n["id"] == note_id)
        assert note["follow_up_required"] == 1
        assert note["follow_up_date"] == "2026-04-18"

    def test_create_multiple_notes(self, pastoral_service, sample_pupil):
        """Multiple notes for the same pupil are stored independently."""
        pid = sample_pupil["pupil_id"]
        id1 = pastoral_service.create_note(
            pupil_id=pid, note_type="welfare",
            subject="Note 1", details="First note",
        )
        id2 = pastoral_service.create_note(
            pupil_id=pid, note_type="medical",
            subject="Note 2", details="Second note",
        )
        assert id1 != id2
        notes = pastoral_service.get_notes(pupil_id=pid)
        assert len(notes) == 2


class TestGetNotes:
    """Tests for retrieving pastoral notes."""

    def test_get_notes_empty_db(self, pastoral_service):
        """Querying an empty database returns an empty list."""
        assert pastoral_service.get_notes() == []

    def test_get_notes_by_pupil(self, pastoral_service, sample_pupil, sample_pupil_ks1):
        """Filtering by pupil_id returns only that pupil's notes."""
        pid = sample_pupil["pupil_id"]
        pastoral_service.create_note(
            pupil_id=pid, note_type="welfare",
            subject="A", details="Note for pupil 1",
        )
        pastoral_service.create_note(
            pupil_id=sample_pupil_ks1["pupil_id"], note_type="behaviour",
            subject="B", details="Note for pupil 2",
        )
        notes = pastoral_service.get_notes(pupil_id=pid)
        assert len(notes) == 1
        assert notes[0]["details"] == "Note for pupil 1"

    def test_get_notes_by_type(self, pastoral_service, sample_pupil):
        """Filtering by note_type returns only matching notes."""
        pid = sample_pupil["pupil_id"]
        pastoral_service.create_note(
            pupil_id=pid, note_type="academic",
            subject="Maths", details="Struggling with addition",
        )
        pastoral_service.create_note(
            pupil_id=pid, note_type="welfare",
            subject="Home", details="All fine",
        )
        notes = pastoral_service.get_notes(note_type="academic")
        assert len(notes) == 1
        assert notes[0]["note_type"] == "academic"

    def test_get_notes_combined_filters(self, pastoral_service, sample_pupil, sample_pupil_ks2):
        """Combining pupil_id and note_type narrows results correctly."""
        pid = sample_pupil["pupil_id"]
        pastoral_service.create_note(
            pupil_id=pid, note_type="behaviour",
            subject="X", details="d1",
        )
        pastoral_service.create_note(
            pupil_id=sample_pupil_ks2["pupil_id"], note_type="behaviour",
            subject="Y", details="d2",
        )
        pastoral_service.create_note(
            pupil_id=pid, note_type="medical",
            subject="Z", details="d3",
        )
        notes = pastoral_service.get_notes(
            pupil_id=pid, note_type="behaviour",
        )
        assert len(notes) == 1
        assert notes[0]["subject"] == "X"


class TestUpdateNote:
    """Tests for updating pastoral notes."""

    def test_update_note_details(self, pastoral_service, sample_pupil):
        """Updating a note's details persists the change."""
        pid = sample_pupil["pupil_id"]
        note_id = pastoral_service.create_note(
            pupil_id=pid, note_type="welfare",
            subject="Initial", details="Original details",
        )
        result = pastoral_service.update_note(note_id, details="Updated details")
        assert result is True
        notes = pastoral_service.get_notes(pupil_id=pid)
        assert notes[0]["details"] == "Updated details"

    def test_update_note_type(self, pastoral_service, sample_pupil):
        """The note_type field can be changed via update."""
        pid = sample_pupil["pupil_id"]
        note_id = pastoral_service.create_note(
            pupil_id=pid, note_type="welfare",
            subject="Test", details="d",
        )
        pastoral_service.update_note(note_id, note_type="medical")
        notes = pastoral_service.get_notes(pupil_id=pid)
        assert notes[0]["note_type"] == "medical"

    def test_update_with_no_valid_fields(self, pastoral_service, sample_pupil):
        """Passing no recognised fields returns None."""
        note_id = pastoral_service.create_note(
            pupil_id=sample_pupil["pupil_id"], note_type="welfare",
            subject="S", details="d",
        )
        result = pastoral_service.update_note(note_id, bogus_field="value")
        assert result is None


class TestDeleteNote:
    """Tests for deleting pastoral notes."""

    def test_delete_existing_note(self, pastoral_service, sample_pupil):
        """Deleting an existing note returns True and removes it."""
        pid = sample_pupil["pupil_id"]
        note_id = pastoral_service.create_note(
            pupil_id=pid, note_type="welfare",
            subject="Gone", details="Will be deleted",
        )
        assert pastoral_service.delete_note(note_id) is True
        assert pastoral_service.get_notes(pupil_id=pid) == []

    def test_delete_nonexistent_note(self, pastoral_service):
        """Deleting a non-existent note returns False."""
        assert pastoral_service.delete_note(99999) is False

    def test_delete_does_not_affect_other_notes(self, pastoral_service, sample_pupil):
        """Deleting one note leaves other notes intact."""
        pid = sample_pupil["pupil_id"]
        id1 = pastoral_service.create_note(
            pupil_id=pid, note_type="welfare",
            subject="Keep", details="Stays",
        )
        id2 = pastoral_service.create_note(
            pupil_id=pid, note_type="academic",
            subject="Remove", details="Goes",
        )
        pastoral_service.delete_note(id2)
        remaining = pastoral_service.get_notes(pupil_id=pid)
        assert len(remaining) == 1
        assert remaining[0]["id"] == id1
