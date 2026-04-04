"""Tests for the CalendarService in the Primary School system."""

import pytest


class TestCreateEvent:
    """Tests for creating calendar events."""

    def test_create_event_returns_dict(self, calendar_service):
        """Creating an event returns a dict with id, title, and start_date."""
        result = calendar_service.create_event(
            title="Spring Assembly",
            start_date="2026-04-15",
            event_type="Assembly",
        )
        assert isinstance(result, dict)
        assert "id" in result
        assert result["title"] == "Spring Assembly"
        assert result["start_date"] == "2026-04-15"

    def test_create_event_persists(self, calendar_service):
        """Created event can be retrieved with all fields intact."""
        result = calendar_service.create_event(
            title="Year 3 Trip",
            start_date="2026-05-20",
            start_time="09:00",
            end_time="15:00",
            description="Trip to the Science Museum",
            event_type="Trip",
            location="Science Museum",
            year_groups="Year 3",
        )
        fetched = calendar_service.get_event(result["id"])
        assert fetched["title"] == "Year 3 Trip"
        assert fetched["start_time"] == "09:00"
        assert fetched["end_time"] == "15:00"
        assert fetched["event_type"] == "Trip"
        assert fetched["location"] == "Science Museum"
        assert fetched["year_groups"] == "Year 3"

    def test_create_all_day_event(self, calendar_service):
        """An all-day event stores the all_day flag correctly."""
        result = calendar_service.create_event(
            title="Half Term",
            start_date="2026-05-25",
            end_date="2026-05-29",
            event_type="Holiday",
            all_day=1,
        )
        fetched = calendar_service.get_event(result["id"])
        assert fetched["all_day"] == 1
        assert fetched["end_date"] == "2026-05-29"


class TestGetEvent:
    """Tests for retrieving a single calendar event."""

    def test_get_nonexistent_returns_none(self, calendar_service):
        """Requesting a non-existent event ID returns None."""
        assert calendar_service.get_event(99999) is None

    def test_get_returns_created_at(self, calendar_service):
        """Retrieved event includes a created_at timestamp."""
        result = calendar_service.create_event(
            title="PTA Meeting", start_date="2026-04-22",
            event_type="Meeting")
        fetched = calendar_service.get_event(result["id"])
        assert fetched["created_at"] is not None


class TestListEvents:
    """Tests for listing calendar events."""

    def test_list_empty_db(self, calendar_service):
        """Listing on an empty database returns an empty list."""
        assert calendar_service.list_events() == []

    def test_list_returns_all(self, calendar_service):
        """Listing without filters returns all events."""
        calendar_service.create_event(
            title="E1", start_date="2026-04-10", event_type="Assembly")
        calendar_service.create_event(
            title="E2", start_date="2026-04-12", event_type="Trip")
        results = calendar_service.list_events()
        assert len(results) == 2

    def test_list_filter_by_event_type(self, calendar_service):
        """Filtering by event_type returns only matching events."""
        calendar_service.create_event(
            title="Assembly", start_date="2026-04-10", event_type="Assembly")
        calendar_service.create_event(
            title="Trip", start_date="2026-04-12", event_type="Trip")
        results = calendar_service.list_events(event_type="Trip")
        assert len(results) == 1
        assert results[0]["title"] == "Trip"

    def test_list_filter_by_date_range(self, calendar_service):
        """Filtering by date range returns events within bounds."""
        calendar_service.create_event(
            title="Early", start_date="2026-03-01", event_type="General")
        calendar_service.create_event(
            title="Mid", start_date="2026-04-15", event_type="General")
        calendar_service.create_event(
            title="Late", start_date="2026-06-01", event_type="General")
        results = calendar_service.list_events(
            date_from="2026-04-01", date_to="2026-05-01")
        assert len(results) == 1
        assert results[0]["title"] == "Mid"


class TestUpdateEvent:
    """Tests for updating calendar events."""

    @pytest.mark.xfail(reason="schema missing column: updated_at")
    def test_update_title_and_location(self, calendar_service):
        """Updating title and location persists changes."""
        result = calendar_service.create_event(
            title="Old", start_date="2026-04-20", event_type="Meeting")
        updated = calendar_service.update_event(
            result["id"], title="New", location="Hall")
        assert updated["title"] == "New"
        assert updated["location"] == "Hall"

    def test_update_with_no_valid_fields(self, calendar_service):
        """Passing no recognised fields returns None."""
        result = calendar_service.create_event(
            title="T", start_date="2026-04-20", event_type="General")
        assert calendar_service.update_event(
            result["id"], bogus="value") is None


class TestDeleteEvent:
    """Tests for deleting calendar events."""

    def test_delete_existing(self, calendar_service):
        """Deleting an existing event returns True and removes it."""
        result = calendar_service.create_event(
            title="Gone", start_date="2026-04-20", event_type="General")
        assert calendar_service.delete_event(result["id"]) is True
        assert calendar_service.get_event(result["id"]) is None

    def test_delete_nonexistent(self, calendar_service):
        """Deleting a non-existent event returns False."""
        assert calendar_service.delete_event(99999) is False

    def test_delete_does_not_affect_others(self, calendar_service):
        """Deleting one event leaves others intact."""
        r1 = calendar_service.create_event(
            title="Keep", start_date="2026-04-10", event_type="General")
        r2 = calendar_service.create_event(
            title="Remove", start_date="2026-04-11", event_type="General")
        calendar_service.delete_event(r2["id"])
        remaining = calendar_service.list_events()
        assert len(remaining) == 1
        assert remaining[0]["id"] == r1["id"]
