"""Bookings: eligibility, pricing, the waiting list, cancellation charges
and the register."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.modules import clients, sessions


def _day(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


def _book(learner: int, session: int, **extra) -> int:
    return r.save(sessions.BOOKINGS, {"learner_id": learner, "session_id": session, **extra})


def test_employer_billed_with_po_and_discount(world, make_learner):
    lid = make_learner(funding="Employer", client_id=world.client)
    with pytest.raises(r.ValidationError, match="purchase order"):
        _book(lid, world.session)
    bid = _book(lid, world.session, po_number="PO1")
    row = r.get(sessions.BOOKINGS, bid)
    assert row["client_id"] == world.client
    assert row["price"] == 270.0


def test_no_double_booking(world, make_learner):
    lid = make_learner()
    _book(lid, world.session)
    with pytest.raises(r.ValidationError, match="already booked"):
        _book(lid, world.session)


def test_minimum_age(world, make_learner):
    kid = make_learner("Kid", "Ray", dob=date(date.today().year - 15, 1, 1).isoformat())
    with pytest.raises(r.ValidationError, match="16 or over"):
        _book(kid, world.session)


def test_archived_learner_and_client_on_hold(world, make_learner):
    lid = make_learner(status="Archived")
    with pytest.raises(r.ValidationError, match="archived"):
        _book(lid, world.session)
    r.save(clients.CLIENTS, {"status": "On hold", "hold_reason": "Unpaid"},
           record_id=world.client)
    other = make_learner("Bob", "Ray")
    with pytest.raises(r.ValidationError, match="on hold"):
        _book(other, world.session, client_id=world.client, po_number="P")


def test_closed_session_only_takes_its_client(world, make_learner):
    sid = r.save(sessions.SESSIONS, {"course_id": world.cpd, "start_date": _day(30),
                                     "venue_id": world.online,
                                     "kind": sessions.SESSION_KINDS[1],
                                     "client_id": world.client})
    with pytest.raises(r.ValidationError, match="another client"):
        _book(make_learner(), sid)


def test_waiting_list_and_promotion(world, make_learner):
    ids = [make_learner(n, "X") for n in ("A", "B", "C", "D")]
    bookings = [_book(lid, world.session) for lid in ids]
    assert r.get(sessions.BOOKINGS, bookings[3])["status"] == "Waiting list"
    r.save(sessions.BOOKINGS, {"status": "Cancelled"}, record_id=bookings[0])
    assert r.get(sessions.BOOKINGS, bookings[3])["status"] == "Booked"


@pytest.mark.parametrize(("notice", "share"), [(10, 0.0), (5, 0.5), (1, 1.0)])
def test_cancellation_charges(notice, share):
    start = date.today() + timedelta(days=notice)
    assert sessions.cancellation_charge(200, start, date.today()) == 200 * share


def test_cancelled_session_cancels_bookings_free(world, make_learner):
    sid = r.save(sessions.SESSIONS, {"course_id": world.cpd, "start_date": _day(30),
                                     "venue_id": world.online})
    bid = _book(make_learner(), sid)
    with pytest.raises(r.ValidationError, match="reason"):
        r.save(sessions.SESSIONS, {"status": "Cancelled"}, record_id=sid)
    r.save(sessions.SESSIONS, {"status": "Cancelled", "cancel_reason": "Ill"}, record_id=sid)
    row = r.get(sessions.BOOKINGS, bid)
    assert row["status"] == "Cancelled by us" and sessions.chargeable(row) == 0


def test_capacity_cannot_drop_below_bookings(world, make_learner):
    _book(make_learner("A", "X"), world.session)
    _book(make_learner("B", "X"), world.session)
    with pytest.raises(r.ValidationError, match="already booked"):
        r.save(sessions.SESSIONS, {"capacity": 1}, record_id=world.session)


def test_attended_only_once_started(world, make_learner):
    sid = r.save(sessions.SESSIONS, {"course_id": world.cpd, "start_date": _day(30),
                                     "venue_id": world.online})
    bid = _book(make_learner(), sid)
    with pytest.raises(r.ValidationError, match="hasn't started"):
        r.save(sessions.BOOKINGS, {"status": "Attended"}, record_id=bid)


def test_register_last_day_settles_bookings(world, make_learner):
    a, b = make_learner("A", "X"), make_learner("B", "X")
    ba, bb = _book(a, world.session), _book(b, world.session)
    days = sessions.session_days(r.get(sessions.SESSIONS, world.session))
    for d in days:
        sessions.take_register(world.session, d, {a: "Present", b: "Absent"})
    assert r.get(sessions.BOOKINGS, ba)["status"] == "Attended"
    assert r.get(sessions.BOOKINGS, bb)["status"] == "Did not attend"
    assert sessions.full_attendance(a, world.session)
    assert not sessions.full_attendance(b, world.session)


def test_register_refuses_future_and_non_session_days(world, make_learner):
    a = make_learner()
    _book(a, world.session)
    with pytest.raises(r.ValidationError, match="session's days"):
        sessions.take_register(world.session, date.today() - timedelta(days=30),
                               {a: "Present"})
