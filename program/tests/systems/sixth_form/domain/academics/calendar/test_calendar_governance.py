"""Tests for governance (trail, permissions, visibility), the
notification queue, taxonomy and the portal feeds."""

from __future__ import annotations

import datetime as _dt

import pytest

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
    calendar_bookings as bookings,
    calendar_governance as governance,
    calendar_notifications as notifications,
    calendar_portal as portal,
    calendar_taxonomy as taxonomy,
)


class TestPermissions:

    def test_the_ladder(self, caldb):
        assert governance.can("admin", "purge")
        assert governance.can("staff", "archive")
        assert not governance.can("staff", "purge")
        assert governance.can("teacher", "create")
        assert not governance.can("teacher", "archive")
        assert not governance.can("student", "create")

    def test_unknown_roles_fail_closed(self, caldb):
        assert not governance.can("hacker", "view")
        assert not governance.can(None, "view")

    def test_require_raises(self, caldb):
        with pytest.raises(governance.ValidationError,
                           match="may not purge"):
            governance.require("teacher", "purge")

    def test_no_role_means_no_gate(self, caldb):
        # Interfaces that don't know the role pass None and are not
        # blocked — gating is opt-in per call site.
        event = governance.audited_create(
            {"title": "x", "start_date": "2026-09-01"})
        assert event.event_id


class TestTrail:

    def test_update_diffs_per_field(self, one_event):
        governance.audited_update(one_event.event_id,
                                  {"location": "Gym"},
                                  actor="head", reason="rain")
        entries = governance.trail(one_event.event_id)
        loc = next(a for a in entries if a.field == "location")
        assert loc.old_value == "Main Hall"
        assert loc.new_value == "Gym"
        assert loc.amended_by == "head"
        assert loc.reason == "rain"

    def test_timestamp_churn_is_not_logged(self, one_event):
        governance.audited_update(one_event.event_id,
                                  {"location": "Gym"})
        assert not any(a.field in ("updated_at", "updated_by")
                       for a in governance.trail(one_event.event_id))

    def test_noop_status_writes_nothing(self, one_event):
        governance.audited_set_status(one_event.event_id,
                                      "Scheduled")
        assert not any(a.action == "status"
                       for a in governance.trail(one_event.event_id))

    def test_the_trail_survives_a_purge(self, one_event):
        governance.audited_purge(one_event.event_id, actor="admin",
                                 reason="test data")
        assert core.get_event(one_event.event_id) is None
        assert any(a.action == "purge"
                   for a in governance.trail(one_event.event_id))


class TestVisibility:

    @pytest.fixture
    def three(self, caldb):
        core.create_event({"title": "Open Evening",
                           "start_date": "2026-10-01",
                           "visibility": "Public"})
        core.create_event({"title": "Briefing",
                           "start_date": "2026-10-01"})
        core.create_event({"title": "Panel",
                           "start_date": "2026-10-01",
                           "visibility": "Confidential"})

    def test_staff_see_everything(self, three):
        assert len(governance.visible_events("teacher")) == 3

    def test_students_lose_confidential(self, three):
        titles = {e.title for e in governance.visible_events("student")}
        assert titles == {"Open Evening", "Briefing"}

    def test_parents_and_public_see_public_only(self, three):
        for viewer in ("parent", None, "anything-else"):
            titles = {e.title
                      for e in governance.visible_events(viewer)}
            assert titles == {"Open Evening"}


class TestNotifications:

    def test_reminder_sweep_is_idempotent(self, caldb):
        soon = (_dt.date.today()
                + _dt.timedelta(days=1)).isoformat()
        core.create_event({"title": "Meet", "start_date": soon})
        assert notifications.sweep_reminders() == 1
        assert notifications.sweep_reminders() == 0

    def test_change_notice_diffs_notifiable_fields_only(
            self, one_event):
        before = core.get_event(one_event.event_id)
        after = core.update_event(one_event.event_id,
                                  {"location": "Gym",
                                   "notes": "internal"})
        msg = notifications.notify_change(before, after)
        assert msg is not None
        assert "Location" in msg.body
        assert "internal" not in msg.body

    def test_a_pure_notes_edit_notifies_nobody(self, one_event):
        before = core.get_event(one_event.event_id)
        after = core.update_event(one_event.event_id,
                                  {"notes": "quiet"})
        assert notifications.notify_change(before, after) is None

    def test_cancellation_dedupes(self, one_event):
        after = core.cancel_event(one_event.event_id)
        assert notifications.notify_cancellation(after) is not None
        assert notifications.notify_cancellation(after) is None

    def test_drain_sends_direct_and_leaves_broadcasts(self, one_event):
        notifications.queue(one_event.event_id, "RSVP Confirmation",
                            "x@example.com", "s", "b")
        notifications.queue(one_event.event_id, "Reminder",
                            "audience:Parents", "s", "b")
        outbox: list[str] = []
        sent, failed = notifications.send_queued(
            sender=lambda to, subj, body: outbox.append(to))
        assert (sent, failed) == (1, 0)
        assert outbox == ["x@example.com"]
        still = notifications.list_notifications(state="Queued")
        assert len(still) == 1
        assert still[0].is_broadcast

    def test_a_failing_sender_marks_failed(self, one_event):
        row = notifications.queue(one_event.event_id,
                                  "RSVP Confirmation",
                                  "x@example.com", "s", "b")

        def boom(to, subj, body):
            raise RuntimeError("SMTP down")

        sent, failed = notifications.send_queued(sender=boom)
        assert (sent, failed) == (0, 1)
        got = notifications.get_notification(row.notification_id)
        assert got.state == "Failed"
        assert "SMTP down" in got.detail


class TestTaxonomy:

    def test_department_rename_cascades(self, caldb):
        core.create_event({"title": "x", "start_date": "2026-09-01",
                           "department": "Maths"})
        moved = taxonomy.rename_department("Maths", "Mathematics")
        assert moved == 1
        assert core.list_events()[0].department == "Mathematics"

    def test_tags_normalise_and_garbage_collect(self, one_event):
        assert taxonomy.tag_event(one_event.event_id,
                                  "Ofsted Week") == "ofsted-week"
        assert taxonomy.tags_for(one_event.event_id) == ["ofsted-week"]
        taxonomy.untag_event(one_event.event_id, "ofsted-week")
        assert taxonomy.list_tags() == []

    def test_every_event_type_has_a_colour(self, caldb):
        pal = taxonomy.palette()
        for etype in core.EVENT_TYPES:
            assert pal[etype].startswith("#")

    def test_colour_overrides_round_trip(self, caldb):
        taxonomy.set_colour("Exam", "#FF0000")
        assert taxonomy.colour_for("Exam") == "#ff0000"
        taxonomy.reset_colour("Exam")
        assert taxonomy.colour_for("Exam") == \
            taxonomy.DEFAULT_COLOURS["Exam"]


class TestPortal:

    def test_student_feed_pins_their_bookings_first(self, caldb):
        soon = (_dt.date.today()
                + _dt.timedelta(days=10)).isoformat()
        sooner = (_dt.date.today()
                  + _dt.timedelta(days=3)).isoformat()
        trip = core.create_event({"title": "Ski Trip",
                                  "event_type": "Trip",
                                  "start_date": soon,
                                  "visibility": "Public",
                                  "audience": "Students"})
        core.create_event({"title": "Workshop",
                           "start_date": sooner,
                           "audience": "Students"})
        bookings.book(trip.event_id, "S500")
        feed = portal.feed_for_student("S500")
        assert feed.events[0].title == "Ski Trip"
        assert feed.events[0].is_booked

    def test_parent_feed_is_public_only(self, caldb):
        soon = (_dt.date.today()
                + _dt.timedelta(days=5)).isoformat()
        core.create_event({"title": "Open Evening",
                           "start_date": soon,
                           "visibility": "Public"})
        core.create_event({"title": "Staff briefing",
                           "start_date": soon,
                           "audience": "Staff",
                           "visibility": "Internal"})
        titles = {e.title for e in portal.feed_for_parent().events}
        assert titles == {"Open Evening"}
