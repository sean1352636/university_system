"""Tests for the ParentsEveningService in the Primary School system."""

import pytest

from education_system.primary_school.core.exceptions import ParentsEveningError


class TestCreateEvent:
    """Tests for creating parents evening events."""

    def test_create_event_returns_dict(self, parents_evening_service):
        """Creating an event returns a dict with id, title, and event_date."""
        result = parents_evening_service.create_event(
            title="Spring Parents Evening",
            event_date="2026-04-22",
            start_time="15:30",
            end_time="19:00",
            slot_duration=10,
        )
        assert isinstance(result, dict)
        assert "id" in result
        assert result["title"] == "Spring Parents Evening"

    def test_create_event_persists(self, parents_evening_service):
        """Created event can be retrieved with all fields intact."""
        result = parents_evening_service.create_event(
            title="Autumn Parents Evening",
            event_date="2026-11-10",
            start_time="16:00",
            end_time="20:00",
            slot_duration=15,
            year_groups="Year 1,Year 2",
        )
        fetched = parents_evening_service.get_event(result["id"])
        assert fetched["title"] == "Autumn Parents Evening"
        assert fetched["slot_duration"] == 15
        assert fetched["year_groups"] == "Year 1,Year 2"
        assert fetched["status"] == "Scheduled"


class TestGetEvent:
    """Tests for retrieving a single parents evening event."""

    def test_get_nonexistent_returns_none(self, parents_evening_service):
        """Requesting a non-existent event ID returns None."""
        assert parents_evening_service.get_event(99999) is None


class TestListEvents:
    """Tests for listing parents evening events."""

    def test_list_empty_db(self, parents_evening_service):
        """Listing on an empty database returns an empty list."""
        assert parents_evening_service.list_events() == []

    def test_list_returns_all(self, parents_evening_service):
        """Listing without filters returns all events."""
        parents_evening_service.create_event(
            title="PE1", event_date="2026-04-22")
        parents_evening_service.create_event(
            title="PE2", event_date="2026-11-10")
        results = parents_evening_service.list_events()
        assert len(results) == 2

    def test_list_filter_by_status(self, parents_evening_service):
        """Filtering by status returns only matching events."""
        parents_evening_service.create_event(
            title="PE1", event_date="2026-04-22")
        results = parents_evening_service.list_events(status="Scheduled")
        assert len(results) == 1
        assert results[0]["status"] == "Scheduled"


class TestUpdateEvent:
    """Tests for updating parents evening events."""

    def test_update_title(self, parents_evening_service):
        """Updating the title persists the change."""
        result = parents_evening_service.create_event(
            title="Old Title", event_date="2026-04-22")
        updated = parents_evening_service.update_event(
            result["id"], title="New Title")
        assert updated["title"] == "New Title"

    def test_update_with_no_valid_fields(self, parents_evening_service):
        """Passing no recognised fields returns None."""
        result = parents_evening_service.create_event(
            title="T", event_date="2026-04-22")
        assert parents_evening_service.update_event(
            result["id"], bogus="value") is None


class TestDeleteEvent:
    """Tests for deleting parents evening events."""

    def test_delete_existing(self, parents_evening_service):
        """Deleting an existing event returns True and removes it."""
        result = parents_evening_service.create_event(
            title="Gone", event_date="2026-04-22")
        assert parents_evening_service.delete_event(result["id"]) is True
        assert parents_evening_service.get_event(result["id"]) is None

    def test_delete_nonexistent(self, parents_evening_service):
        """Deleting a non-existent event returns False."""
        assert parents_evening_service.delete_event(99999) is False


class TestSlots:
    """Tests for creating, booking, and cancelling appointment slots."""

    def test_create_slot_available(self, parents_evening_service, sample_staff):
        """Creating a slot without a pupil sets status to Available."""
        event = parents_evening_service.create_event(
            title="PE", event_date="2026-04-22")
        slot = parents_evening_service.create_slot(
            event_id=event["id"],
            teacher_staff_id=sample_staff["staff_id"],
            slot_time="15:30",
        )
        assert slot["status"] == "Available"

    def test_create_slot_pre_booked(self, parents_evening_service,
                                     sample_pupil, sample_staff):
        """Creating a slot with a pupil_id sets status to Booked."""
        event = parents_evening_service.create_event(
            title="PE", event_date="2026-04-22")
        slot = parents_evening_service.create_slot(
            event_id=event["id"],
            teacher_staff_id=sample_staff["staff_id"],
            slot_time="15:40",
            pupil_id=sample_pupil["pupil_id"],
            parent_name="Sarah Smith",
        )
        assert slot["status"] == "Booked"

    def test_get_slots_for_event(self, parents_evening_service, sample_staff):
        """get_slots returns all slots for a given event."""
        event = parents_evening_service.create_event(
            title="PE", event_date="2026-04-22")
        parents_evening_service.create_slot(
            event_id=event["id"], teacher_staff_id=sample_staff["staff_id"],
            slot_time="15:30")
        parents_evening_service.create_slot(
            event_id=event["id"], teacher_staff_id=sample_staff["staff_id"],
            slot_time="15:40")
        slots = parents_evening_service.get_slots(event["id"])
        assert len(slots) == 2

    def test_get_slots_filter_by_teacher(self, parents_evening_service,
                                          sample_staff, hr_service):
        """Filtering slots by teacher_staff_id narrows results."""
        staff2 = hr_service.create_staff(
            first_name="Bob", last_name="Teacher",
            email="bob.teacher@school.local", role="Teacher")
        event = parents_evening_service.create_event(
            title="PE", event_date="2026-04-22")
        parents_evening_service.create_slot(
            event_id=event["id"], teacher_staff_id=sample_staff["staff_id"],
            slot_time="15:30")
        parents_evening_service.create_slot(
            event_id=event["id"], teacher_staff_id=staff2["staff_id"],
            slot_time="15:30")
        slots = parents_evening_service.get_slots(
            event["id"], teacher_staff_id=sample_staff["staff_id"])
        assert len(slots) == 1

    def test_book_slot(self, parents_evening_service, sample_pupil,
                       sample_staff):
        """Booking an available slot sets it to Booked with pupil info."""
        event = parents_evening_service.create_event(
            title="PE", event_date="2026-04-22")
        slot = parents_evening_service.create_slot(
            event_id=event["id"], teacher_staff_id=sample_staff["staff_id"],
            slot_time="15:30")
        result = parents_evening_service.book_slot(
            slot["id"], pupil_id=sample_pupil["pupil_id"],
            parent_name="Sarah Smith")
        assert result is True
        slots = parents_evening_service.get_slots(
            event["id"], status="Booked")
        assert len(slots) == 1
        assert slots[0]["parent_name"] == "Sarah Smith"

    def test_book_already_booked_slot_raises(self, parents_evening_service,
                                              sample_pupil, sample_staff):
        """Booking an already-booked slot raises ParentsEveningError."""
        event = parents_evening_service.create_event(
            title="PE", event_date="2026-04-22")
        slot = parents_evening_service.create_slot(
            event_id=event["id"], teacher_staff_id=sample_staff["staff_id"],
            slot_time="15:30", pupil_id=sample_pupil["pupil_id"],
            parent_name="Sarah Smith")
        with pytest.raises(ParentsEveningError):
            parents_evening_service.book_slot(
                slot["id"], pupil_id=sample_pupil["pupil_id"],
                parent_name="Other Parent")

    def test_cancel_slot(self, parents_evening_service, sample_pupil,
                         sample_staff):
        """Cancelling a booked slot resets it to Available."""
        event = parents_evening_service.create_event(
            title="PE", event_date="2026-04-22")
        slot = parents_evening_service.create_slot(
            event_id=event["id"], teacher_staff_id=sample_staff["staff_id"],
            slot_time="15:30")
        parents_evening_service.book_slot(
            slot["id"], pupil_id=sample_pupil["pupil_id"],
            parent_name="Sarah Smith")
        result = parents_evening_service.cancel_slot(slot["id"])
        assert result is True
        slots = parents_evening_service.get_slots(
            event["id"], status="Available")
        assert len(slots) == 1
        assert slots[0]["pupil_id"] is None
