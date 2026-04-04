"""Tests for CalendarService."""
import pytest


class TestCalendar:
    def test_add_event(self, calendar_service):
        event = calendar_service.add_event(
            title="Sports Day", date="2026-07-10",
            event_type="sports_day", location="Playing Fields",
        )
        assert event["title"] == "Sports Day"
        assert event["event_type"] == "sports_day"

    def test_list_events(self, calendar_service):
        calendar_service.add_event("Event A", "2026-06-01")
        calendar_service.add_event("Event B", "2026-06-15")
        events = calendar_service.list_events()
        assert len(events) >= 2

    def test_list_events_filters_by_type(self, calendar_service):
        calendar_service.add_event("Inset Day", "2026-09-01", event_type="inset_day")
        calendar_service.add_event("Open Day", "2026-10-01", event_type="open_day")
        events = calendar_service.list_events(event_type="inset_day")
        assert all(e["event_type"] == "inset_day" for e in events)

    def test_delete_event(self, calendar_service):
        event = calendar_service.add_event("Delete Me", "2026-12-01")
        calendar_service.delete_event(event["id"])
        events = calendar_service.list_events()
        assert all(e["id"] != event["id"] for e in events)
