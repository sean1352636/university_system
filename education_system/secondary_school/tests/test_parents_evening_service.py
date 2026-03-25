"""Tests for ParentsEveningService."""
import pytest


class TestParentsEvening:
    def test_create_event(self, parents_evening_service):
        event = parents_evening_service.create_event(
            title="Year 9 Parents Evening", date="2026-03-25",
            year_group="9",
        )
        assert event["title"] == "Year 9 Parents Evening"

    def test_list_events(self, parents_evening_service):
        parents_evening_service.create_event("PE 1", "2026-03-25")
        parents_evening_service.create_event("PE 2", "2026-04-10")
        events = parents_evening_service.list_events()
        assert len(events) >= 2

    def test_book_slot(self, parents_evening_service, sample_student):
        event = parents_evening_service.create_event("PE Booking", "2026-03-25")
        slot = parents_evening_service.book_slot(
            event_id=event["id"], teacher="Mr Smith",
            student_id=sample_student["id"], time_slot="16:00",
            parent_name="Mrs Doe",
        )
        assert slot["teacher"] == "Mr Smith"
        assert slot["time_slot"] == "16:00"

    def test_list_slots(self, parents_evening_service, sample_student):
        event = parents_evening_service.create_event("PE Slots", "2026-03-25")
        parents_evening_service.book_slot(event["id"], "Mr Smith", sample_student["id"], "16:00")
        parents_evening_service.book_slot(event["id"], "Mrs Jones", sample_student["id"], "16:05")
        slots = parents_evening_service.list_slots(event["id"])
        assert len(slots) >= 2

    def test_cancel_slot(self, parents_evening_service, sample_student):
        event = parents_evening_service.create_event("PE Cancel", "2026-03-25")
        slot = parents_evening_service.book_slot(event["id"], "Mr Smith", sample_student["id"], "16:00")
        parents_evening_service.cancel_slot(slot["id"])
        slots = parents_evening_service.list_slots(event["id"])
        assert all(s["id"] != slot["id"] for s in slots)

    def test_delete_event(self, parents_evening_service):
        event = parents_evening_service.create_event("PE Delete", "2026-03-25")
        parents_evening_service.delete_event(event["id"])
        events = parents_evening_service.list_events()
        assert all(e["id"] != event["id"] for e in events)
