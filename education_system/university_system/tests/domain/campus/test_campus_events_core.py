"""Tests for the Campus Events Hub core service.

Uses the canonical campus_events schema for unified_events,
unified_event_registrations, event_series, event_announcements,
event_sponsors. Each test gets an isolated SQLite file via the
``campus_events_db`` fixture.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.university_system.infrastructure.database import db as db_module
from education_system.university_system.infrastructure.database.schemas.campus_events_schemas import (
    init_campus_events_system_db,
)
from education_system.university_system.modules.domain.campus.services.campus_events_core import (
    CampusEventManager,
    EventAnnouncementManager,
    EventRegistrationManager,
    EventSeriesManager,
    EventSponsorManager,
)


@pytest.fixture
def campus_events_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "campus_events_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    init_campus_events_system_db()
    yield db_path


def _create_event(**overrides) -> int:
    defaults = dict(
        event_name="Open Day",
        event_type="info",
        event_category="outreach",
        organizer_id="staff01",
        organizer_type="staff",
        event_date=(date.today() + timedelta(days=7)).isoformat(),
        start_time="10:00",
        end_time="12:00",
        location="Main Hall",
        capacity=2,
        registration_required=True,
        is_public=True,
        description="Spring open day",
    )
    defaults.update(overrides)
    return CampusEventManager.create_event(**defaults)


class TestCampusEventManager:
    def test_create_event_returns_id_and_persists_row(self, campus_events_db):
        eid = _create_event()
        assert isinstance(eid, int) and eid > 0

        from education_system.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT title, source_type, status, max_capacity, "
                "registration_required, is_public FROM unified_events "
                "WHERE event_id = ?", (eid,),
            ).fetchone()
        assert row["title"] == "Open Day"
        assert row["source_type"] == "campus"
        assert row["status"] == "scheduled"
        assert row["max_capacity"] == 2
        assert row["registration_required"] == 1
        assert row["is_public"] == 1

    def test_get_upcoming_events_returns_only_campus_scheduled_in_window(self, campus_events_db):
        soon = (date.today() + timedelta(days=3)).isoformat()
        far_future = (date.today() + timedelta(days=60)).isoformat()
        _create_event(event_name="Soon", event_date=soon)
        _create_event(event_name="Far", event_date=far_future)

        rows = CampusEventManager.get_upcoming_events(days_ahead=30)
        names = {r["event_name"] for r in rows}
        assert "Soon" in names and "Far" not in names

    def test_get_upcoming_events_filters_by_category(self, campus_events_db):
        soon = (date.today() + timedelta(days=2)).isoformat()
        _create_event(event_name="Outreach", event_date=soon, event_category="outreach")
        _create_event(event_name="Social", event_date=soon, event_category="social")

        rows = CampusEventManager.get_upcoming_events(days_ahead=30, event_category="social")
        names = {r["event_name"] for r in rows}
        assert names == {"Social"}


class TestEventRegistrationManager:
    def test_register_for_event(self, campus_events_db):
        eid = _create_event(capacity=5)
        rid = EventRegistrationManager.register_for_event(eid, "S12345", "student")
        assert isinstance(rid, int) and rid > 0

    def test_register_full_event_raises(self, campus_events_db):
        eid = _create_event(capacity=1)
        EventRegistrationManager.register_for_event(eid, "S1", "student")
        with pytest.raises(Exception, match="full capacity"):
            EventRegistrationManager.register_for_event(eid, "S2", "student")

    def test_register_zero_capacity_is_unbounded(self, campus_events_db):
        eid = _create_event(capacity=0)
        for i in range(5):
            EventRegistrationManager.register_for_event(eid, f"S{i}", "student")

        from education_system.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM unified_event_registrations WHERE event_id = ?",
                (eid,),
            ).fetchone()[0]
        assert n == 5

    def test_check_in_attendee_marks_attended_with_timestamp(self, campus_events_db):
        eid = _create_event()
        rid = EventRegistrationManager.register_for_event(eid, "S1", "student")
        assert EventRegistrationManager.check_in_attendee(rid) is True

        from education_system.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT attendance_status, checked_in_at "
                "FROM unified_event_registrations WHERE registration_id = ?", (rid,),
            ).fetchone()
        assert row["attendance_status"] == "attended"
        assert row["checked_in_at"]


class TestEventSeriesManager:
    def test_create_series_returns_id(self, campus_events_db):
        sid = EventSeriesManager.create_series(
            series_name="Friday Talks",
            organizer_id="staff01",
            recurrence_pattern="weekly",
            start_date="2026-09-01",
            end_date="2026-12-15",
            description="Term-time research talks",
        )
        assert isinstance(sid, int) and sid > 0

        from education_system.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT series_name, recurrence_pattern, is_active "
                "FROM event_series WHERE series_id = ?", (sid,),
            ).fetchone()
        assert row["series_name"] == "Friday Talks"
        assert row["recurrence_pattern"] == "weekly"
        assert row["is_active"] == 1


class TestEventAnnouncementManager:
    def test_send_announcement_persists_and_returns_id(self, campus_events_db, monkeypatch):
        # Stub the email side effect so the test is hermetic and stays focused on DB state.
        monkeypatch.setattr(
            EventAnnouncementManager, "_send_announcement_emails",
            staticmethod(lambda *a, **kw: None),
        )
        eid = _create_event()
        aid = EventAnnouncementManager.send_announcement(
            event_id=eid,
            announcement_text="Doors open at 09:45.",
            sent_to="all_registrants",
            sent_by="staff01",
        )
        assert isinstance(aid, int) and aid > 0

        from education_system.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT event_id, announcement_text, sent_to, sent_by "
                "FROM event_announcements WHERE announcement_id = ?", (aid,),
            ).fetchone()
        assert row["event_id"] == eid
        assert row["announcement_text"] == "Doors open at 09:45."
        assert row["sent_to"] == "all_registrants"

    def test_send_announcement_for_missing_event_raises(self, campus_events_db, monkeypatch):
        monkeypatch.setattr(
            EventAnnouncementManager, "_send_announcement_emails",
            staticmethod(lambda *a, **kw: None),
        )
        # Insert is FK-checked against unified_events, so the unknown event_id is
        # rejected before the in-method "not found" branch runs. Either error
        # form means the announcement was not persisted, which is what we care
        # about; assert on the persistence guarantee rather than the message.
        with pytest.raises(Exception):
            EventAnnouncementManager.send_announcement(
                event_id=999999, announcement_text="x", sent_to="all_registrants",
            )

        from education_system.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM event_announcements WHERE event_id = 999999"
            ).fetchone()[0]
        assert n == 0


class TestEventSponsorManager:
    def test_add_sponsor(self, campus_events_db):
        eid = _create_event()
        sid = EventSponsorManager.add_sponsor(
            event_id=eid, sponsor_name="Acme Corp",
            sponsor_type="gold", contribution_amount=2500.0,
            logo_url="https://example.com/logo.png",
            website_url="https://example.com",
        )
        assert isinstance(sid, int) and sid > 0

        from education_system.university_system.infrastructure.database.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT sponsor_name, sponsor_type, contribution_amount "
                "FROM event_sponsors WHERE sponsor_id = ?", (sid,),
            ).fetchone()
        assert row["sponsor_name"] == "Acme Corp"
        assert row["sponsor_type"] == "gold"
        assert row["contribution_amount"] == pytest.approx(2500.0)
