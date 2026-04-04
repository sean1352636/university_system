"""Tests for CrossSystemCalendarService."""

import pytest
from datetime import datetime, timedelta


@pytest.fixture
def cal_db(tmp_path):
    return str(tmp_path / "calendar.db")


@pytest.fixture
def svc(cal_db):
    from education_system.shared.calendar.calendar_service import CrossSystemCalendarService
    return CrossSystemCalendarService(db_path=cal_db)


def _make_event(svc, title="Open Day", date=None, systems="all", event_type="open_day"):
    date = date or datetime.now().strftime("%Y-%m-%d")
    return svc.create_event(
        title=title, description="Test event", date=date, time="10:00",
        end_date="", systems=systems, event_type=event_type,
        created_by="admin", created_system="university",
    )


class TestCreateAndGet:
    def test_create_event_returns_dict(self, svc):
        event = _make_event(svc)
        assert isinstance(event, dict)
        assert event["title"] == "Open Day"
        assert event["id"] is not None

    def test_get_event_by_id(self, svc):
        event = _make_event(svc)
        fetched = svc.get_event(event["id"])
        assert fetched["title"] == "Open Day"
        assert fetched["event_type"] == "open_day"

    def test_get_event_missing_returns_none(self, svc):
        assert svc.get_event(9999) is None


class TestFiltering:
    def test_get_events_all(self, svc):
        _make_event(svc, title="Event A")
        _make_event(svc, title="Event B")
        events = svc.get_events()
        assert len(events) == 2

    def test_get_events_by_system(self, svc):
        _make_event(svc, title="Uni Only", systems="university")
        _make_event(svc, title="College Only", systems="college")
        _make_event(svc, title="All Systems", systems="all")
        uni_events = svc.get_events(system="university")
        assert len(uni_events) == 2  # "university" + "all"
        titles = {e["title"] for e in uni_events}
        assert "Uni Only" in titles
        assert "All Systems" in titles

    def test_get_events_by_month_year(self, svc):
        _make_event(svc, title="Jan Event", date="2026-01-15")
        _make_event(svc, title="Feb Event", date="2026-02-10")
        jan = svc.get_events(month=1, year=2026)
        assert len(jan) == 1
        assert jan[0]["title"] == "Jan Event"

    def test_get_upcoming_within_range(self, svc):
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        far = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
        _make_event(svc, title="Soon", date=today)
        _make_event(svc, title="Near", date=future)
        _make_event(svc, title="Far Away", date=far)
        upcoming = svc.get_upcoming(days=30)
        titles = {e["title"] for e in upcoming}
        assert "Soon" in titles
        assert "Near" in titles
        assert "Far Away" not in titles


class TestUpdateAndDelete:
    def test_update_event(self, svc):
        event = _make_event(svc, title="Original")
        svc.update_event(event["id"], title="Updated", event_type="holiday")
        updated = svc.get_event(event["id"])
        assert updated["title"] == "Updated"
        assert updated["event_type"] == "holiday"

    def test_update_ignores_invalid_fields(self, svc):
        event = _make_event(svc)
        result = svc.update_event(event["id"], bogus_field="nope")
        assert result is False

    def test_delete_event(self, svc):
        event = _make_event(svc)
        svc.delete_event(event["id"])
        assert svc.get_event(event["id"]) is None

    def test_delete_removes_from_listing(self, svc):
        e1 = _make_event(svc, title="Keep")
        e2 = _make_event(svc, title="Delete")
        svc.delete_event(e2["id"])
        events = svc.get_events()
        assert len(events) == 1
        assert events[0]["title"] == "Keep"
