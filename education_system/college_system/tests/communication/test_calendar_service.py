"""Tests for CalendarService."""

import pytest


class TestCalendarService:
    @pytest.fixture
    def calendar_service(self, db_path):
        from education_system.college_system.modules.domain.calendar.services.calendar_service import CalendarService
        return CalendarService(db_path)

    def test_create_event(self, calendar_service):
        event = calendar_service.create_event(
            user_id=1, title="Staff Meeting",
            event_date="2026-04-15", start_time="09:00",
        )
        assert event["title"] == "Staff Meeting"
        assert event["event_date"] == "2026-04-15"

    def test_list_events(self, calendar_service):
        calendar_service.create_event(user_id=1, title="Event 1", event_date="2026-04-10")
        calendar_service.create_event(user_id=1, title="Event 2", event_date="2026-04-20")
        events = calendar_service.list_events(user_id=1)
        assert len(events) >= 2

    def test_list_events_date_range(self, calendar_service):
        calendar_service.create_event(user_id=1, title="In range", event_date="2026-05-15")
        calendar_service.create_event(user_id=1, title="Out of range", event_date="2026-06-15")
        events = calendar_service.list_events(
            user_id=1, month=5, year=2026,
        )
        assert all(e["event_date"].startswith("2026-05") for e in events)

    def test_get_events_for_date(self, calendar_service):
        calendar_service.create_event(user_id=1, title="Today event", event_date="2026-04-15")
        events = calendar_service.get_events_for_date(user_id=1, date_str="2026-04-15")
        assert len(events) >= 1

    def test_update_event(self, calendar_service):
        event = calendar_service.create_event(
            user_id=1, title="Original", event_date="2026-04-15",
        )
        updated = calendar_service.update_event(
            event["id"], user_id=1, title="Updated Title",
        )
        assert updated["title"] == "Updated Title"

    def test_delete_event(self, calendar_service):
        event = calendar_service.create_event(
            user_id=1, title="Delete me", event_date="2026-04-15",
        )
        result = calendar_service.delete_event(event["id"], user_id=1)
        assert result is True
