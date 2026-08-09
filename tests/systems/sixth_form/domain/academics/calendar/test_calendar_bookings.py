"""Tests for bookings: capacity, the waitlist queue, promotion and
check-in."""

from __future__ import annotations

import pytest

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
    calendar_bookings as bookings,
)


@pytest.fixture
def trip(caldb):
    """A two-place trip — small enough to fill in a test."""
    return core.create_event({
        "title": "Theatre Trip", "event_type": "Trip",
        "start_date": "2026-11-20", "capacity": 2,
        "rsvp_required": True,
    })


class TestCapacity:

    def test_the_full_event_waitlists(self, trip):
        assert bookings.book(trip.event_id, "S1").state == "Booked"
        assert bookings.book(trip.event_id, "S2").state == "Booked"
        assert bookings.book(trip.event_id,
                             "S3").state == "Waitlisted"

    def test_no_capacity_means_no_waitlist(self, caldb):
        open_evt = core.create_event({"title": "Open talk",
                                      "start_date": "2026-11-01"})
        for i in range(10):
            assert bookings.book(open_evt.event_id,
                                 f"P{i}").state == "Booked"

    def test_double_booking_is_rejected(self, trip):
        bookings.book(trip.event_id, "S1")
        with pytest.raises(bookings.ValidationError,
                           match="already has a booking"):
            bookings.book(trip.event_id, "S1")

    def test_attended_still_holds_the_place(self, trip):
        bookings.book(trip.event_id, "S1")
        bookings.book(trip.event_id, "S2")
        bookings.check_in(trip.event_id, "S1")
        assert bookings.booking_summary(trip.event_id).is_full


class TestPromotion:

    def test_cancel_promotes_the_longest_waiting(self, trip):
        for sid in ("S1", "S2", "S3", "S4"):
            bookings.book(trip.event_id, sid)
        bookings.cancel(trip.event_id, "S1")
        assert bookings.booking_for(trip.event_id,
                                    "S3").state == "Booked"
        assert bookings.booking_for(trip.event_id,
                                    "S4").state == "Waitlisted"

    def test_cancelling_a_waitlisted_row_promotes_nobody(self, trip):
        for sid in ("S1", "S2", "S3", "S4"):
            bookings.book(trip.event_id, sid)
        bookings.cancel(trip.event_id, "S4")
        assert bookings.booking_summary(trip.event_id).taken == 2

    def test_capacity_raise_fills_from_the_queue(self, trip):
        for sid in ("S1", "S2", "S3"):
            bookings.book(trip.event_id, sid)
        core.update_event(trip.event_id, {"capacity": 3})
        promoted = bookings.promote_waitlist(trip.event_id)
        assert [b.person for b in promoted] == ["S3"]

    def test_rebooking_after_cancel_rejoins_at_the_back(self, trip):
        for sid in ("S1", "S2"):
            bookings.book(trip.event_id, sid)
        bookings.cancel(trip.event_id, "S1")     # S2 + free place
        bookings.book(trip.event_id, "S3")       # takes the place
        again = bookings.book(trip.event_id, "S1")
        assert again.state == "Waitlisted"
        # And no duplicate row appeared.
        assert len(bookings.attendance_list(trip.event_id)) == 3


class TestCheckIn:

    def test_only_booked_can_check_in(self, trip):
        bookings.book(trip.event_id, "S1")
        assert bookings.check_in(trip.event_id,
                                 "S1").state == "Attended"
        with pytest.raises(bookings.ValidationError):
            bookings.check_in(trip.event_id, "S1")   # already in
        with pytest.raises(bookings.ValidationError):
            bookings.check_in(trip.event_id, "S9")   # never booked


class TestGuards:

    def test_cancelled_events_close_bookings(self, trip):
        core.cancel_event(trip.event_id)
        with pytest.raises(bookings.ValidationError,
                           match="bookings are closed"):
            bookings.book(trip.event_id, "S1")

    def test_archived_events_do_not_book(self, trip):
        core.delete_event(trip.event_id)
        with pytest.raises(bookings.ValidationError):
            bookings.book(trip.event_id, "S1")

    def test_per_person_view_skips_archived_events(self, trip):
        bookings.book(trip.event_id, "S1")
        core.delete_event(trip.event_id)
        assert bookings.bookings_for_person(
            "S1", upcoming_only=False) == []
