"""Trips & payments (systems.primary.domain.finance.trips.trips).

Trip money is stored in pounds (REAL, rounded to 2 dp), not pence.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.finance.trips import trips as T
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.staff import staff as S

FUTURE = "2099-06-01"
PAST = "2000-06-01"
TODAY = dt.date.today().isoformat()

_n = 0


def _pupil(year: str = "4", **extra):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2017-03-01", **extra})


def _staff():
    return S.create_staff({"first_name": "Lead", "last_name": "Teacher"})


def _trip(**extra):
    data = {"name": "Zoo visit", "destination": "City Zoo", "start_date": FUTURE,
            "cost_per_place": "20.00", "deposit": "5.00", "capacity": 30}
    data.update(extra)
    return T.create_trip(data)


def _booked(trip=None, **extra):
    trip = trip or _trip()
    pupil = _pupil()
    return trip, pupil, T.create_booking(trip.trip_id, {"student_id": pupil.pupil_id, **extra})


def _pay(booking_id, amount, **extra):
    return T.add_payment(booking_id, {"amount": amount, "paid_on": "2099-01-10", **extra})


# ── trips: create / read ─────────────────────────────────────────────

def test_create_trip_stores_values_and_defaults():
    lead = _staff()
    t = T.create_trip({"name": "  Castle  ", "start_date": FUTURE, "end_date": "2099-06-02",
                       "cost_per_place": "12.5", "deposit": 3, "capacity": "25",
                       "payment_due": "2099-05-01", "lead_staff_id": lead.staff_id.lower(),
                       "description": " Day out ", "notes": ""})
    got = T.get_trip(t.trip_id)
    assert got == t
    assert (got.name, got.cost_per_place, got.deposit, got.capacity) == ("Castle", 12.5, 3.0, 25)
    assert got.year_group == T.DEFAULT_YEAR_GROUP == "Whole School"
    assert got.status == T.DEFAULT_TRIP_STATUS == "Planning"
    assert got.lead_staff_id == lead.staff_id            # upper-cased
    assert (got.description, got.notes, got.destination) == ("Day out", None, None)


def test_cost_and_deposit_default_to_zero_and_capacity_to_none():
    t = T.create_trip({"name": "Park", "start_date": FUTURE})
    assert (t.cost_per_place, t.deposit, t.capacity, t.end_date) == (0.0, 0.0, None, None)


def test_get_trip_missing_is_none():
    assert T.get_trip(999) is None


# ── trips: validation ────────────────────────────────────────────────

@pytest.mark.parametrize("bad, match", [
    ({"name": ""}, "Name is required"),
    ({"name": "   "}, "Name is required"),
    ({"start_date": ""}, "Start date is required"),
    ({"start_date": "01/06/2099"}, "Start date must be YYYY-MM-DD"),
    ({"end_date": "2099-5-1"}, "End date must be YYYY-MM-DD"),
    ({"end_date": "2099-05-31"}, "End date cannot be before start date"),
    ({"year_group": "Year 7"}, "Year group must be one of"),
    ({"cost_per_place": "abc"}, "Cost per place must be a number"),
    ({"cost_per_place": "1.234"}, "at most 2 decimal places"),
    ({"cost_per_place": "-1"}, "Cost per place cannot be negative"),
    ({"deposit": "-0.01"}, "Deposit cannot be negative"),
    ({"deposit": "25"}, "Deposit cannot exceed the cost per place"),
    ({"capacity": "ten"}, "Capacity must be a whole number"),
    ({"capacity": -1}, r"Capacity must be 0\.\.5000"),
    ({"capacity": 5001}, r"Capacity must be 0\.\.5000"),
    ({"payment_due": "soon"}, "Payment due must be YYYY-MM-DD"),
    ({"status": "Booked"}, "Status must be one of"),
    ({"lead_staff_id": "T0000000"}, "No staff with id T0000000"),
])
def test_create_trip_refusals(bad, match):
    with pytest.raises(T.ValidationError, match=match):
        _trip(**bad)
    assert T.list_trips() == []


def test_capacity_bounds_are_inclusive():
    assert _trip(capacity=0).capacity == 0
    assert _trip(capacity=5000).capacity == 5000


def test_deposit_may_equal_cost():
    assert _trip(cost_per_place="10", deposit="10").deposit == 10.0


# ── trips: listing ───────────────────────────────────────────────────

def test_list_trips_filters_and_sorts_newest_first():
    a = _trip(name="A", start_date="2099-01-01", year_group="Year 3", status="Open for Booking")
    b = _trip(name="B", start_date="2099-03-01", year_group="KS2", status="Completed")
    c = _trip(name="C", start_date="2099-02-01", year_group="Year 3", status="Cancelled")
    assert [t.name for t in T.list_trips()] == ["B", "C", "A"]
    assert [t.trip_id for t in T.list_trips(year_group="Year 3")] == [c.trip_id, a.trip_id]
    assert [t.trip_id for t in T.list_trips(status="Completed")] == [b.trip_id]
    assert [t.trip_id for t in T.list_trips(open_only=True)] == [a.trip_id]
    assert [t.name for t in T.list_trips(date_from="2099-02-01")] == ["B", "C"]
    assert [t.name for t in T.list_trips(date_to="2099-02-01")] == ["C", "A"]


def test_list_trips_refuses_unknown_filters():
    with pytest.raises(T.ValidationError, match="Year group"):
        T.list_trips(year_group="Year 9")
    with pytest.raises(T.ValidationError, match="Status"):
        T.list_trips(status="Nope")
    with pytest.raises(T.ValidationError, match="date_from must be YYYY-MM-DD"):
        T.list_trips(date_from="tomorrow")


def test_list_trips_empty_database():
    assert T.list_trips() == []
    assert T.list_trips(open_only=True) == []


# ── trips: update / status / delete ──────────────────────────────────

def test_update_trip_merges_only_given_fields():
    t = _trip()
    u = T.update_trip(t.trip_id, {"name": "Aquarium", "capacity": 10})
    assert (u.name, u.capacity, u.destination, u.cost_per_place) == ("Aquarium", 10, "City Zoo", 20.0)
    assert T.get_trip(t.trip_id).name == "Aquarium"


def test_update_trip_validates_and_refuses_unknown_id():
    t = _trip()
    with pytest.raises(T.ValidationError, match="End date cannot be before"):
        T.update_trip(t.trip_id, {"end_date": "2000-01-01"})
    with pytest.raises(T.ValidationError, match="No trip with id 999"):
        T.update_trip(999, {"name": "x"})


def test_cost_cannot_drop_below_what_a_pupil_has_already_paid():
    t, _p, b = _booked()
    _pay(b.booking_id, "15")
    with pytest.raises(T.ValidationError, match="less than the most a student has already paid"):
        T.update_trip(t.trip_id, {"cost_per_place": "14.99", "deposit": "0"})
    assert T.update_trip(t.trip_id, {"cost_per_place": "15"}).cost_per_place == 15.0


def test_lower_cost_ignores_pending_payments():
    t, _p, b = _booked()
    _pay(b.booking_id, "18", status="Pending")
    assert T.update_trip(t.trip_id, {"cost_per_place": "10"}).cost_per_place == 10.0


def test_set_trip_status():
    t = _trip()
    assert T.set_trip_status(t.trip_id, "Confirmed").status == "Confirmed"
    with pytest.raises(T.ValidationError, match="Status must be one of"):
        T.set_trip_status(t.trip_id, "Done")


def test_delete_trip_cascades_bookings_and_payments():
    t, _p, b = _booked()
    pay = _pay(b.booking_id, "5")
    assert T.delete_trip(t.trip_id) is True
    assert T.get_trip(t.trip_id) is None
    assert T.get_booking(b.booking_id) is None
    assert T.get_payment(pay.payment_id) is None
    assert T.delete_trip(t.trip_id) is False


def test_deleting_lead_staff_clears_lead():
    lead = _staff()
    t = _trip(lead_staff_id=lead.staff_id)
    assert S.delete_staff(lead.staff_id)
    assert T.get_trip(t.trip_id).lead_staff_id is None


# ── bookings ─────────────────────────────────────────────────────────

def test_create_booking_defaults_and_values():
    t = _trip()
    p = _pupil()
    b = T.create_booking(t.trip_id, {"student_id": f"  {p.pupil_id} ",
                                     "consent_received": 1, "medical_note": " Inhaler ",
                                     "dietary_note": "", "booking_date": "2099-01-02"})
    got = T.get_booking(b.booking_id)
    assert got == b
    assert (got.trip_id, got.student_id, got.booking_date) == (t.trip_id, p.pupil_id, "2099-01-02")
    assert got.status == T.DEFAULT_BOOKING_STATUS == "Interested"
    assert got.consent_received is True
    assert (got.medical_note, got.dietary_note, got.consent_note) == ("Inhaler", None, None)


def test_booking_date_defaults_to_today():
    _t, _p, b = _booked()
    assert b.booking_date == TODAY


def test_booking_refusals():
    t = _trip()
    p = _pupil()
    with pytest.raises(T.ValidationError, match="No trip with id 999"):
        T.create_booking(999, {"student_id": p.pupil_id})
    with pytest.raises(T.ValidationError, match="Student ID is required"):
        T.create_booking(t.trip_id, {"student_id": ""})
    with pytest.raises(T.ValidationError, match="No student with id P0000000"):
        T.create_booking(t.trip_id, {"student_id": "P0000000"})
    with pytest.raises(T.ValidationError, match="Status must be one of"):
        T.create_booking(t.trip_id, {"student_id": p.pupil_id, "status": "Maybe"})
    with pytest.raises(T.ValidationError, match="Booking date must be YYYY-MM-DD"):
        T.create_booking(t.trip_id, {"student_id": p.pupil_id, "booking_date": "1/1/2099"})
    assert T.list_bookings() == []


def test_same_pupil_cannot_be_booked_twice_on_one_trip():
    t, p, _b = _booked()
    with pytest.raises(T.ValidationError, match="already booked"):
        T.create_booking(t.trip_id, {"student_id": p.pupil_id})
    other = _trip(name="Other")
    assert T.create_booking(other.trip_id, {"student_id": p.pupil_id}).trip_id == other.trip_id


def test_over_capacity_booking_is_allowed():
    t = _trip(capacity=1)
    _booked(t)
    _booked(t)
    assert len(T.list_bookings(trip_id=t.trip_id)) == 2


def test_list_bookings_filters():
    t = _trip()
    _t, p1, b1 = _booked(t, status="Confirmed", consent_received=True)
    _t, p2, b2 = _booked(t, status="Cancelled")
    _t, _p3, b3 = _booked(_trip(name="Other"), status="Waitlist")
    assert {b.booking_id for b in T.list_bookings()} == {b1.booking_id, b2.booking_id, b3.booking_id}
    assert {b.booking_id for b in T.list_bookings(trip_id=t.trip_id)} == {b1.booking_id, b2.booking_id}
    assert [b.booking_id for b in T.list_bookings(student_id=p2.pupil_id)] == [b2.booking_id]
    assert [b.booking_id for b in T.list_bookings(status="Waitlist")] == [b3.booking_id]
    assert [b.booking_id for b in T.list_bookings(consent_received=True)] == [b1.booking_id]
    assert {b.booking_id for b in T.list_bookings(active_only=True)} == {b1.booking_id, b3.booking_id}
    with pytest.raises(T.ValidationError, match="Status must be one of"):
        T.list_bookings(status="Gone")


def test_list_bookings_sorted_by_booking_date_newest_first():
    t = _trip()
    _t, _p, old = _booked(t, booking_date="2099-01-01")
    _t, _p, new = _booked(t, booking_date="2099-02-01")
    assert [b.booking_id for b in T.list_bookings()] == [new.booking_id, old.booking_id]


def test_update_booking_keeps_pupil_and_merges():
    t, p, b = _booked()
    other = _pupil()
    u = T.update_booking(b.booking_id, {"status": "Confirmed", "consent_received": True,
                                        "student_id": other.pupil_id})
    assert (u.status, u.consent_received, u.student_id) == ("Confirmed", True, p.pupil_id)
    with pytest.raises(T.ValidationError, match="No booking with id 999"):
        T.update_booking(999, {"status": "Confirmed"})


def test_set_booking_status():
    _t, _p, b = _booked()
    assert T.set_booking_status(b.booking_id, "Attended").status == "Attended"
    with pytest.raises(T.ValidationError, match="Status must be one of"):
        T.set_booking_status(b.booking_id, "Gone")


def test_delete_booking_removes_payments():
    _t, _p, b = _booked()
    pay = _pay(b.booking_id, "5")
    assert T.delete_booking(b.booking_id) is True
    assert T.get_payment(pay.payment_id) is None
    assert T.delete_booking(b.booking_id) is False


def test_deleting_pupil_removes_their_bookings():
    _t, p, b = _booked()
    assert P.delete_pupil(p.pupil_id)
    assert T.get_booking(b.booking_id) is None


# ── payments ─────────────────────────────────────────────────────────

def test_add_payment_values_and_defaults():
    _t, _p, b = _booked()
    pay = T.add_payment(b.booking_id, {"amount": "7.5", "reference": " REF1 ", "recorded_by": "office"})
    got = T.get_payment(pay.payment_id)
    assert got == pay
    assert (got.amount, got.method, got.status) == (7.5, "Card", "Cleared")
    assert (got.paid_on, got.reference, got.recorded_by, got.notes) == (TODAY, "REF1", "office", None)


@pytest.mark.parametrize("bad, match", [
    ({"amount": ""}, "Amount is required"),
    ({"amount": "0"}, "Amount cannot be zero"),
    ({"amount": "-5"}, "Amount cannot be negative"),
    ({"amount": "5.001"}, "at most 2 decimal places"),
    ({"amount": "five"}, "Amount must be a number"),
    ({"amount": "5", "paid_on": "2099/01/01"}, "Paid on must be YYYY-MM-DD"),
    ({"amount": "5", "method": "Bitcoin"}, "Method must be one of"),
    ({"amount": "5", "status": "Bounced"}, "Status must be one of"),
])
def test_payment_refusals(bad, match):
    _t, _p, b = _booked()
    with pytest.raises(T.ValidationError, match=match):
        T.add_payment(b.booking_id, bad)
    assert T.list_payments() == []


def test_payment_needs_a_booking():
    with pytest.raises(T.ValidationError, match="No booking with id 42"):
        T.add_payment(42, {"amount": "5"})


def test_list_payments_filters_and_order():
    t, p1, b1 = _booked()
    _t, p2, b2 = _booked(_trip(name="Other"))
    a = _pay(b1.booking_id, "5", paid_on="2099-01-01", method="Cash")
    c = _pay(b1.booking_id, "6", paid_on="2099-03-01", status="Pending")
    d = _pay(b2.booking_id, "7", paid_on="2099-02-01", method="Cheque")
    assert [x.payment_id for x in T.list_payments()] == [c.payment_id, d.payment_id, a.payment_id]
    assert [x.payment_id for x in T.list_payments(booking_id=b1.booking_id)] == [c.payment_id, a.payment_id]
    assert [x.payment_id for x in T.list_payments(trip_id=t.trip_id)] == [c.payment_id, a.payment_id]
    assert [x.payment_id for x in T.list_payments(student_id=p2.pupil_id)] == [d.payment_id]
    assert [x.payment_id for x in T.list_payments(method="Cash")] == [a.payment_id]
    assert [x.payment_id for x in T.list_payments(status="Pending")] == [c.payment_id]
    assert [x.payment_id for x in T.list_payments(date_from="2099-02-01")] == [c.payment_id, d.payment_id]
    assert [x.payment_id for x in T.list_payments(date_to="2099-02-01")] == [d.payment_id, a.payment_id]
    with pytest.raises(T.ValidationError, match="Method"):
        T.list_payments(method="Gold")
    with pytest.raises(T.ValidationError, match="Status"):
        T.list_payments(status="Lost")


def test_update_and_delete_payment():
    _t, _p, b = _booked()
    pay = _pay(b.booking_id, "5")
    u = T.update_payment(pay.payment_id, {"amount": "6.25", "status": "Refunded"})
    assert (u.amount, u.status, u.paid_on) == (6.25, "Refunded", "2099-01-10")
    with pytest.raises(T.ValidationError, match="Amount cannot be zero"):
        T.update_payment(pay.payment_id, {"amount": 0})
    with pytest.raises(T.ValidationError, match="No payment with id 999"):
        T.update_payment(999, {"amount": "1"})
    assert T.delete_payment(pay.payment_id) is True
    assert T.delete_payment(pay.payment_id) is False
    assert T.get_payment(pay.payment_id) is None


# ── derived payment state ────────────────────────────────────────────

def _state(cost="20", deposit="5", status="Interested", payments=()):
    t = _trip(cost_per_place=cost, deposit=deposit)
    _t, _p, b = _booked(t, status=status)
    for amount, st in payments:
        _pay(b.booking_id, amount, status=st)
    return T.view_booking(b.booking_id)


def test_payment_state_unpaid_partial_deposit_paid():
    assert _state().payment_state == "Unpaid"
    assert _state(payments=[("4.99", "Cleared")]).payment_state == "Partial"
    assert _state(payments=[("5", "Cleared")]).payment_state == "Deposit"
    v = _state(payments=[("15", "Cleared"), ("5", "Cleared")])
    assert (v.payment_state, v.paid, v.balance, v.payment_count) == ("Paid", 20.0, 0.0, 2)


def test_no_deposit_means_partial_not_deposit():
    assert _state(deposit="0", payments=[("10", "Cleared")]).payment_state == "Partial"


def test_only_cleared_payments_count_toward_paid():
    v = _state(payments=[("20", "Pending"), ("3", "Failed"), ("2", "Cleared")])
    assert (v.paid, v.balance, v.payment_state, v.payment_count) == (2.0, 18.0, "Partial", 3)


def test_free_trip_is_paid():
    assert _state(cost="0", deposit="0").payment_state == "Paid"


def test_cancelled_booking_with_money_is_refunded():
    assert _state(status="Cancelled", payments=[("5", "Cleared")]).payment_state == "Refunded"
    assert _state(status="Withdrawn", payments=[("5", "Cleared")]).payment_state == "Refunded"
    assert _state(status="Cancelled").payment_state == "Unpaid"


def test_view_booking_names_pupil_and_missing_is_none():
    _t, p, b = _booked()
    v = T.view_booking(b.booking_id)
    assert v.student_name == p.full_name
    assert v.is_active is True
    assert T.view_booking(999) is None


def test_list_booking_views_empty_database():
    assert T.list_booking_views() == []


def test_list_booking_views_matches_view_booking():
    t = _trip()
    _t, p1, b1 = _booked(t)
    _t, _p2, b2 = _booked(t)
    _pay(b1.booking_id, "20")
    views = {v.booking.booking_id: v for v in T.list_booking_views(trip_id=t.trip_id)}
    assert set(views) == {b1.booking_id, b2.booking_id}
    assert views[b1.booking_id].student_name == p1.full_name
    assert (views[b1.booking_id].payment_state, views[b1.booking_id].paid) == ("Paid", 20.0)
    assert views[b2.booking_id].payment_state == "Unpaid"
    paid_only = T.list_booking_views(payment_state="Paid")
    assert [v.booking.booking_id for v in paid_only] == [b1.booking_id]


# ── trip view ────────────────────────────────────────────────────────

def test_view_trip_counts_and_money():
    t = _trip(cost_per_place="20", deposit="5", capacity=4)
    _t, _p, conf = _booked(t, status="Confirmed")
    _t, _p, _wait = _booked(t, status="Waitlist")
    _t, _p, _int = _booked(t, status="Interested")
    _t, _p, canc = _booked(t, status="Cancelled")
    _pay(conf.booking_id, "20")
    _pay(canc.booking_id, "5")                       # not counted: inactive
    v = T.view_trip(t.trip_id)
    assert (v.confirmed, v.interested, v.waitlist, v.cancelled, v.total_active) == (1, 1, 1, 1, 3)
    assert v.capacity_used_pct == 75.0
    assert (v.total_charged, v.total_paid, v.total_balance) == (60.0, 20.0, 40.0)


def test_view_trip_without_capacity_or_bookings():
    t = _trip(capacity=None)
    v = T.view_trip(t.trip_id)
    assert v.capacity_used_pct is None
    assert (v.total_active, v.total_charged, v.total_paid) == (0, 0.0, 0.0)
    assert T.view_trip(999) is None


# ── summary ──────────────────────────────────────────────────────────

def test_summary_empty_database():
    s = T.summary()
    assert (s.total_trips, s.total_bookings, s.total_charged, s.next_trip) == (0, 0, 0.0, None)
    assert s.by_trip_status == {st: 0 for st in T.TRIP_STATUSES}
    assert s.by_method == {m: 0.0 for m in T.PAYMENT_METHODS}
    assert s.top_trips_by_revenue == []


def test_summary_trip_counts_without_bookings():
    _trip(name="Past", start_date=PAST, status="Completed")
    soon = _trip(name="Soon", start_date="2098-01-01", status="Open for Booking")
    _trip(name="Later", start_date=FUTURE)
    _trip(name="Off", start_date="2097-01-01", status="Cancelled")
    s = T.summary()
    assert (s.total_trips, s.upcoming_trips, s.open_for_booking, s.completed, s.cancelled) == (4, 2, 1, 1, 1)
    assert s.next_trip.trip_id == soon.trip_id


def test_summary_money_with_bookings():
    due_passed = _trip(name="Museum", cost_per_place="20", deposit="0", payment_due=PAST)
    later = _trip(name="Farm", cost_per_place="10", deposit="0", payment_due=FUTURE)
    _t, _p, b1 = _booked(due_passed, consent_received=True)
    _t, _p, b2 = _booked(due_passed, status="Waitlist")
    _t, _p, b3 = _booked(later, status="Cancelled")
    _t, _p, b4 = _booked(later, status="Confirmed", consent_received=True)
    _pay(b1.booking_id, "15", method="Cash")
    _pay(b3.booking_id, "4", method="Card")
    _pay(b4.booking_id, "10", method="Card")
    _pay(b4.booking_id, "9", method="Cheque", status="Pending")
    s = T.summary()
    assert (s.total_bookings, s.active_bookings, s.waitlist_count, s.consent_missing) == (4, 3, 1, 1)
    # charged: 20 + 20 + 10 (active only); paid 15 + 0 + 10
    assert (s.total_charged, s.total_paid, s.total_outstanding) == (50.0, 25.0, 25.0)
    assert s.overdue_balance == 25.0                 # 5 + 20 on the Museum trip
    assert s.by_method["Cash"] == 15.0 and s.by_method["Card"] == 14.0
    assert s.by_method["Cheque"] == 0.0              # pending
    assert s.by_payment_state["Partial"] == 1 and s.by_payment_state["Refunded"] == 1
    assert s.top_trips_by_revenue == [(due_passed.trip_id, "Museum", 15.0),
                                      (later.trip_id, "Farm", 10.0)]
