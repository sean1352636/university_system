"""Tests for attendance notifications.

Everything is queued, never sent on the spot: a bug in a report should
not be an incident involving four hundred text messages.
"""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_notifications as notifications,
)


def recipient(name: str = "A Parent",
              address: str = "parent@example.test") -> notifications.Recipient:
    return notifications.Recipient(name=name, address=address,
                                   channel=notifications.EMAIL)


# ── 1. Queueing ────────────────────────────────────────────────────

class TestQueue:

    def test_a_message_queues_without_sending(self, attdb):
        note = notifications.queue(attdb.s1, notifications.ABSENCE_ALERT,
                                   "Ada was absent today.",
                                   recipient=recipient(),
                                   covers_date=attdb.prev_monday)
        assert note.state == notifications.QUEUED
        assert notifications.pending_count() == 1

    def test_a_body_is_required(self, attdb):
        with pytest.raises(core.ValidationError, match="needs a body"):
            notifications.queue(attdb.s1, notifications.ABSENCE_ALERT, "  ",
                                recipient=recipient())

    def test_an_unknown_kind_is_rejected(self, attdb):
        with pytest.raises(core.ValidationError, match="Kind must be"):
            notifications.queue(attdb.s1, "Carrier pigeon", "Hello",
                                recipient=recipient())

    def test_a_duplicate_inside_the_window_is_dropped(self, attdb):
        # A family should hear about Tuesday once.
        first = notifications.queue(attdb.s1, notifications.ABSENCE_ALERT,
                                    "Body", recipient=recipient(),
                                    covers_date=attdb.prev_monday)
        second = notifications.queue(attdb.s1, notifications.ABSENCE_ALERT,
                                     "Body", recipient=recipient(),
                                     covers_date=attdb.prev_monday)
        assert first is not None
        assert second is None
        assert notifications.pending_count() == 1

    def test_a_different_date_is_not_a_duplicate(self, attdb):
        notifications.queue(attdb.s1, notifications.ABSENCE_ALERT, "Body",
                            recipient=recipient(),
                            covers_date=attdb.prev_monday)
        second = notifications.queue(attdb.s1, notifications.ABSENCE_ALERT,
                                     "Body", recipient=recipient(),
                                     covers_date=attdb.monday)
        assert second is not None

    def test_a_recipient_with_no_address_is_skipped_not_queued(self, attdb):
        note = notifications.queue(
            attdb.s1, notifications.ABSENCE_ALERT, "Body",
            recipient=notifications.Recipient(name="Nobody", address=None,
                                              channel=notifications.SMS))
        assert note.state == notifications.SKIPPED


# ── 2. Absence alerts ──────────────────────────────────────────────

class TestAbsenceAlerts:

    def test_the_body_says_how_many_lessons(self, attdb):
        body = notifications.absence_alert_body(attdb.s1, attdb.prev_monday,
                                                sessions=2)
        assert "2 lessons" in body
        assert "Ada" in body

    def test_one_lesson_reads_singular(self, attdb):
        body = notifications.absence_alert_body(attdb.s1, attdb.prev_monday,
                                                sessions=1)
        assert "1 lesson " in body

    def test_a_learner_with_no_contacts_is_reported(self, attdb):
        # The fixture has no parent contacts, which is the case worth
        # surfacing rather than silently dropping.
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        result = notifications.queue_absence_alerts(date=attdb.prev_monday)
        assert attdb.s1 in result.no_recipient
        assert result.queued == 0

    def test_authorised_absence_raises_no_alert(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "I"}})
        result = notifications.queue_absence_alerts(date=attdb.prev_monday)
        assert result.no_recipient == []
        assert result.queued == 0

    def test_alerts_are_per_learner_not_per_lesson(self, attdb):
        # Five texts about one morning is how a family learns to ignore
        # the sixth.
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        core.save_register(attdb.pm_slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        result = notifications.queue_absence_alerts(date=attdb.prev_monday)
        assert len(result.no_recipient) == 1

    def test_a_late_alert_needs_significant_lateness(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"status": "Late",
                                       "minutes_late": 3}})
        result = notifications.queue_late_alerts(date=attdb.prev_monday,
                                                 min_minutes=15)
        assert result.queued == 0
        assert result.no_recipient == []


# ── 3. Weekly statements ───────────────────────────────────────────

class TestStatements:

    def test_the_statement_states_the_figure(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"status": "Present"}})
        core.save_register(attdb.pm_slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        body = notifications.statement_body(
            attdb.s1, date_from=attdb.prev_monday, date_to=attdb.prev_monday)
        assert "Attended 1 of 2 lessons" in body
        assert "50.0%" in body

    def test_a_week_with_no_lessons_says_so(self, attdb):
        body = notifications.statement_body(
            attdb.s1, date_from=attdb.tuesday, date_to=attdb.tuesday)
        assert "no timetabled lessons" in body

    def test_unexplained_absence_is_itemised(self, attdb):
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"code": "O"}})
        body = notifications.statement_body(
            attdb.s1, date_from=attdb.prev_monday, date_to=attdb.prev_monday)
        assert "Unexplained absence" in body

    def test_a_good_week_is_still_reported(self, attdb):
        # A message that only ever arrives with bad news gets ignored.
        core.save_register(attdb.slot, attdb.prev_monday,
                           {attdb.s1: {"status": "Present"}})
        body = notifications.statement_body(
            attdb.s1, date_from=attdb.prev_monday, date_to=attdb.prev_monday)
        assert "100.0%" in body

    def test_statements_skip_learners_with_no_sessions(self, attdb):
        result = notifications.queue_weekly_statements(date=attdb.tuesday)
        assert result.queued == 0
        assert result.skipped >= 1


# ── 4. Dispatch ────────────────────────────────────────────────────

class TestDispatch:

    def test_a_sender_is_used_when_given(self, attdb):
        sent: list[str] = []
        notifications.queue(attdb.s1, notifications.ABSENCE_ALERT, "Body",
                            recipient=recipient())
        result = notifications.dispatch_due(
            sender=lambda note: sent.append(note.recipient))
        assert result.sent == 1
        assert sent == ["parent@example.test"]
        assert notifications.pending_count() == 0

    def test_a_failing_sender_marks_it_failed(self, attdb):
        def explode(_note):
            raise RuntimeError("gateway down")

        notifications.queue(attdb.s1, notifications.ABSENCE_ALERT, "Body",
                            recipient=recipient())
        result = notifications.dispatch_due(sender=explode)
        assert result.failed == 1
        assert result.sent == 0
        assert notifications.list_notifications(
            state=notifications.FAILED)[0].detail == "gateway down"

    def test_sms_without_a_sender_fails_rather_than_pretending(self, attdb):
        notifications.queue(
            attdb.s1, notifications.ABSENCE_ALERT, "Body",
            recipient=notifications.Recipient(
                name="A Parent", address="07000000000",
                channel=notifications.SMS))
        assert notifications.dispatch_due().failed == 1

    def test_a_message_can_be_cancelled_before_it_goes(self, attdb):
        note = notifications.queue(attdb.s1, notifications.ABSENCE_ALERT,
                                   "Body", recipient=recipient())
        out = notifications.cancel(note.notification_id,
                                   reason="Wrong figure")
        assert out.state == notifications.CANCELLED

    def test_a_sent_message_cannot_be_cancelled(self, attdb):
        note = notifications.queue(attdb.s1, notifications.ABSENCE_ALERT,
                                   "Body", recipient=recipient())
        notifications.dispatch_due(sender=lambda _n: None)
        with pytest.raises(core.ValidationError, match="already gone"):
            notifications.cancel(note.notification_id)

    def test_the_whole_queue_can_be_emptied(self, attdb):
        notifications.queue(attdb.s1, notifications.ABSENCE_ALERT, "Body",
                            recipient=recipient())
        notifications.queue(attdb.s2, notifications.ABSENCE_ALERT, "Body",
                            recipient=recipient())
        assert notifications.cancel_queued() == 2
        assert notifications.pending_count() == 0

    def test_history_is_readable_before_ringing_a_family(self, attdb):
        notifications.queue(attdb.s1, notifications.ABSENCE_ALERT, "Body",
                            recipient=recipient())
        assert len(notifications.history_for(attdb.s1)) == 1

    def test_learners_with_no_contact_route_are_listed(self, attdb):
        assert set(notifications.unreachable_learners()) == set(attdb.students)
