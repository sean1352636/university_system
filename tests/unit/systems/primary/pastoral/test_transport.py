"""Transport (primary domain.pastoral.transport.transport)."""

from __future__ import annotations

import datetime as dt
import sqlite3

import pytest

from education_system import paths
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.transport import transport as TR

TODAY = dt.date.today()
_n = 0


def _pupil(year="4"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Bus{_n:03d}",
                           "year_group": year, "date_of_birth": "2017-05-01"})


def _route(name="Route A", **extra):
    return TR.create_route({"route_name": name, "route_type": "School Bus",
                            "days": "Mon-Fri", **extra})


def _arr(pupil, **extra):
    return TR.create_arrangement({"student_id": pupil.pupil_id, "mode": "School Bus",
                                  "start_date": "2026-09-01", "days": "Mon-Fri", **extra})


# ── Pupil link ───────────────────────────────────────────────────────

def test_student_exists_reads_pupils_table():
    TR.init_db()
    ava = _pupil()
    assert TR._student_exists(ava.pupil_id) is True
    assert TR._student_exists("NOPE999") is False


def test_arrangement_table_references_pupils_and_routes():
    TR.init_db()
    conn = sqlite3.connect(paths.PRIMARY_TRANSPORT_DB)
    try:
        fks = conn.execute("PRAGMA foreign_key_list(transport_arrangements)").fetchall()
    finally:
        conn.close()
    assert sorted((f[2], f[3], f[4]) for f in fks) == [
        ("pupils", "student_id", "pupil_id"), ("transport_routes", "route_id", "route_id")]


def test_arrangement_for_real_pupil_saves_and_unknown_pupil_is_refused():
    ava = _pupil()
    a = _arr(ava, pickup_point=" Church ", notes="")
    got = TR.get_arrangement(a.arrangement_id)
    assert (got.student_id, got.mode, got.start_date, got.days) == (
        ava.pupil_id, "School Bus", "2026-09-01", "Mon-Fri")
    assert (got.status, got.fee_status, got.bursary_supported) == ("Active", "Not Applicable",
                                                                   False)
    assert got.pickup_point == "Church" and got.notes is None and got.route_id is None
    with pytest.raises(TR.ValidationError, match="No student with id GHOST1"):
        TR.create_arrangement({"student_id": "GHOST1", "mode": "Walking",
                               "start_date": "2026-09-01", "days": "Mon-Fri"})
    assert TR.list_arrangements() == [got]


def test_deleting_pupil_cascades_arrangements():
    ava = _pupil()
    a = _arr(ava)
    assert P.delete_pupil(ava.pupil_id)
    assert TR.get_arrangement(a.arrangement_id) is None


# ── Routes ───────────────────────────────────────────────────────────

def test_create_route_values_and_cleaning():
    r = _route(operator=" Blue Coaches ", am_pickup_time="07:45", pm_return_time="15:30",
               cost_per_term="120.50", cost_per_year=360, capacity="40", notes="")
    got = TR.get_route(r.route_id)
    assert (got.route_name, got.route_type, got.days, got.status) == (
        "Route A", "School Bus", "Mon-Fri", "Active")
    assert got.operator == "Blue Coaches" and got.notes is None
    assert (got.am_pickup_time, got.pm_return_time) == ("07:45", "15:30")
    assert (got.cost_per_term, got.cost_per_year, got.capacity) == (120.5, 360.0, 40)
    assert got.is_active


def test_route_validation_rules():
    for bad, msg in (({"route_name": " "}, "Route name is required"),
                     ({"route_type": "Rocket"}, "Route type must be one of"),
                     ({"days": ""}, "Days are required"),
                     ({"status": "Closed"}, "Status must be one of"),
                     ({"am_pickup_time": "7am"}, "AM pickup must be HH:MM"),
                     ({"pm_return_time": "25:00"}, "PM return must be HH:MM"),
                     ({"cost_per_term": "cheap"}, "cost per term must be a number"),
                     ({"cost_per_year": -1}, "cost per year must be >= 0"),
                     ({"capacity": "many"}, "Capacity must be an integer"),
                     ({"capacity": -5}, "Capacity must be >= 0")):
        with pytest.raises(TR.ValidationError, match=msg):
            _route(**bad)
    assert TR.list_routes() == []


def test_route_names_are_unique():
    r = _route()
    with pytest.raises(TR.ValidationError, match="already exists"):
        _route()
    # renaming itself to the same name is fine
    up = TR.update_route(r.route_id, {"route_name": "Route A", "route_type": "Coach",
                                      "days": "Mon-Wed"})
    assert (up.route_type, up.days) == ("Coach", "Mon-Wed")
    other = _route("Route B")
    with pytest.raises(TR.ValidationError, match="already exists"):
        TR.update_route(other.route_id, {"route_name": "Route A", "route_type": "Coach",
                                         "days": "Mon-Fri"})


def test_update_delete_and_status_of_routes():
    with pytest.raises(TR.ValidationError, match="No route with id 9"):
        TR.update_route(9, {"route_name": "X", "route_type": "Coach", "days": "Mon"})
    r = _route()
    assert TR.set_route_status(r.route_id, "Suspended").status == "Suspended"
    assert not TR.get_route(r.route_id).is_active
    with pytest.raises(TR.ValidationError, match="Status must be one of"):
        TR.set_route_status(r.route_id, "Gone")
    with pytest.raises(TR.ValidationError, match="No route with id 9"):
        TR.set_route_status(9, "Active")
    assert TR.delete_route(r.route_id) is True
    assert TR.delete_route(r.route_id) is False
    assert TR.get_route(r.route_id) is None


def test_list_routes_filters_and_order():
    b = _route("Bravo", operator="Blue Coaches", route_type="Coach")
    a = _route("Alpha", operator="Red Buses", status="Withdrawn")
    c = _route("Charlie")
    assert [r.route_name for r in TR.list_routes()] == ["Alpha", "Bravo", "Charlie"]
    assert [r.route_id for r in TR.list_routes(route_type="Coach")] == [b.route_id]
    assert [r.route_id for r in TR.list_routes(status="Withdrawn")] == [a.route_id]
    assert [r.route_id for r in TR.list_routes(active_only=True)] == [b.route_id, c.route_id]
    assert [r.route_id for r in TR.list_routes(operator_like="red")] == [a.route_id]
    assert [r.route_id for r in TR.list_routes(name_like="arl")] == [c.route_id]


def test_route_seats_used_counts_active_only():
    r = _route(capacity=2)
    ava, ben, cal = _pupil(), _pupil(), _pupil()
    _arr(ava, route_id=r.route_id)
    _arr(ben, route_id=str(r.route_id))
    _arr(cal, route_id=r.route_id, status="Suspended")
    assert TR.route_seats_used(r.route_id) == 2
    assert TR.route_seats_used(999) == 0


def test_deleting_route_unlinks_arrangements():
    r = _route()
    a = _arr(_pupil(), route_id=r.route_id)
    assert TR.get_arrangement(a.arrangement_id).route_name_cache == "Route A"
    TR.delete_route(r.route_id)
    got = TR.get_arrangement(a.arrangement_id)
    assert got.route_id is None and got.route_name_cache is None


# ── Arrangements: validation ─────────────────────────────────────────

def test_arrangement_validation_rules():
    ava = _pupil()
    for bad, msg in (({"student_id": ""}, "Student is required"),
                     ({"mode": "Pony"}, "Mode must be one of"),
                     ({"start_date": ""}, "Start date is required"),
                     ({"start_date": "1/9/2026"}, "Start date must be YYYY-MM-DD"),
                     ({"end_date": "2026-02-30"}, "End date must be YYYY-MM-DD"),
                     ({"end_date": "2026-08-31"}, "End date must be on or after start date"),
                     ({"pass_expires_on": "never"}, "Pass expires must be YYYY-MM-DD"),
                     ({"days": " "}, "Days are required"),
                     ({"fee_status": "Owed"}, "Fee status must be one of"),
                     ({"status": "Lost"}, "Status must be one of"),
                     ({"route_id": "abc"}, "Route id must be an integer"),
                     ({"route_id": 77}, "No route with id 77"),
                     ({"fee_amount": "lots"}, "Fee amount must be a number"),
                     ({"fee_amount": -2}, "Fee amount must be >= 0")):
        with pytest.raises(TR.ValidationError, match=msg):
            _arr(ava, **bad)
    assert TR.list_arrangements() == []


def test_arrangement_full_record_round_trip():
    r = _route()
    a = _arr(_pupil(), route_id=r.route_id, fee_status="Partial", fee_amount="45",
             bursary_supported=1, pass_number="P-1", pass_expires_on="2027-07-31",
             emergency_contact="Mum", emergency_phone="0123", medical_notes="Inhaler",
             end_date="2027-07-20")
    assert (a.route_id, a.route_name_cache, a.fee_status, a.fee_amount) == (
        r.route_id, "Route A", "Partial", 45.0)
    assert a.bursary_supported is True and a.pass_number == "P-1"
    assert (a.emergency_contact, a.emergency_phone, a.medical_notes) == ("Mum", "0123",
                                                                         "Inhaler")
    assert a.end_date == "2027-07-20" and a.is_overdue_unpaid


# ── Arrangements: derived flags ──────────────────────────────────────

def test_pass_expired_and_overdue_flags():
    ava = _pupil()
    yesterday = (TODAY - dt.timedelta(days=1)).isoformat()
    a = _arr(ava, pass_expires_on=yesterday, fee_status="Unpaid")
    assert a.pass_expired and a.is_overdue_unpaid
    b = _arr(ava, pass_expires_on=TODAY.isoformat(), fee_status="Paid")
    assert not b.pass_expired and not b.is_overdue_unpaid
    c = _arr(ava, fee_status="Unpaid", status="Suspended")
    assert not c.pass_expired and not c.is_overdue_unpaid


# ── Arrangements: update / delete / lifecycle ────────────────────────

def test_update_and_delete_arrangement():
    with pytest.raises(TR.ValidationError, match="No arrangement with id 3"):
        TR.update_arrangement(3, {})
    ava, ben = _pupil(), _pupil()
    a = _arr(ava)
    up = TR.update_arrangement(a.arrangement_id, {"student_id": ben.pupil_id, "mode": "Walking",
                                                  "start_date": "2026-09-02", "days": "Mon"})
    assert (up.student_id, up.mode, up.start_date, up.days) == (ben.pupil_id, "Walking",
                                                                "2026-09-02", "Mon")
    assert up.created_on == a.created_on
    assert TR.delete_arrangement(a.arrangement_id) is True
    assert TR.delete_arrangement(a.arrangement_id) is False
    assert TR.get_arrangement(a.arrangement_id) is None


def test_status_lifecycle():
    a = _arr(_pupil(), status="Pending")
    assert TR.activate(a.arrangement_id).status == "Active"
    assert TR.suspend(a.arrangement_id).status == "Suspended"
    ended = TR.end_arrangement(a.arrangement_id, end_date="2026-12-18")
    assert (ended.status, ended.end_date) == ("Ended", "2026-12-18")
    assert TR.set_arrangement_status(a.arrangement_id, "Active").status == "Active"
    with pytest.raises(TR.ValidationError, match="Status must be one of"):
        TR.set_arrangement_status(a.arrangement_id, "Paused")
    for fn in (TR.activate, TR.suspend, TR.end_arrangement, TR.cancel):
        with pytest.raises(TR.ValidationError, match="No arrangement with id 404"):
            fn(404)
    with pytest.raises(TR.ValidationError, match="No arrangement with id 404"):
        TR.set_arrangement_status(404, "Active")


def test_end_arrangement_defaults_to_today():
    a = _arr(_pupil(), start_date=(TODAY - dt.timedelta(days=5)).isoformat())
    assert TR.end_arrangement(a.arrangement_id).end_date == TODAY.isoformat()


def test_end_before_start_is_refused():
    a = _arr(_pupil())
    with pytest.raises(TR.ValidationError, match="End date must be on or after"):
        TR.end_arrangement(a.arrangement_id, end_date="2026-01-01")


def test_cancel_keeps_existing_end_date_or_uses_today():
    ava = _pupil()
    a = _arr(ava, end_date="2027-07-20")
    c = TR.cancel(a.arrangement_id)
    assert (c.status, c.end_date) == ("Cancelled", "2027-07-20")
    b = _arr(ava, start_date=(TODAY - dt.timedelta(days=5)).isoformat())
    assert TR.cancel(b.arrangement_id).end_date == TODAY.isoformat()


def test_cancel_a_future_arrangement():
    """A pending arrangement that has not started yet can still be cancelled."""
    start = (TODAY + dt.timedelta(days=60)).isoformat()
    a = _arr(_pupil(), start_date=start, status="Pending")
    c = TR.cancel(a.arrangement_id)
    assert c.status == "Cancelled"
    assert c.end_date is not None and c.end_date >= c.start_date


def test_set_fee_status():
    a = _arr(_pupil())
    assert TR.set_fee_status(a.arrangement_id, "LA Funded").fee_status == "LA Funded"
    with pytest.raises(TR.ValidationError, match="Fee status must be one of"):
        TR.set_fee_status(a.arrangement_id, "Owed")
    with pytest.raises(TR.ValidationError, match="No arrangement with id 8"):
        TR.set_fee_status(8, "Paid")


# ── Listing ──────────────────────────────────────────────────────────

def test_list_arrangements_filters_and_order():
    r = _route()
    ava, ben = _pupil(), _pupil()
    old = (TODAY - dt.timedelta(days=1)).isoformat()
    a1 = _arr(ava, start_date="2026-01-05", route_id=r.route_id, fee_status="Unpaid",
              pass_expires_on=old)
    a2 = _arr(ava, start_date="2026-09-01", mode="Walking", bursary_supported=True)
    b1 = _arr(ben, start_date="2026-09-01", fee_status="Partial", status="Suspended",
              pass_expires_on=old)
    ids = lambda rows: [x.arrangement_id for x in rows]  # noqa: E731
    assert ids(TR.list_arrangements()) == [b1.arrangement_id, a2.arrangement_id,
                                           a1.arrangement_id]
    assert ids(TR.list_arrangements(student_id=ava.pupil_id)) == [a2.arrangement_id,
                                                                  a1.arrangement_id]
    assert ids(TR.arrangements_for_student(ben.pupil_id)) == [b1.arrangement_id]
    assert ids(TR.list_arrangements(mode="Walking")) == [a2.arrangement_id]
    assert ids(TR.list_arrangements(route_id=r.route_id)) == [a1.arrangement_id]
    assert ids(TR.list_arrangements(status="Suspended")) == [b1.arrangement_id]
    assert ids(TR.list_arrangements(fee_status="Unpaid")) == [a1.arrangement_id]
    assert ids(TR.list_arrangements(active_only=True)) == [a2.arrangement_id, a1.arrangement_id]
    assert ids(TR.list_arrangements(unpaid_only=True)) == [a1.arrangement_id]
    assert ids(TR.list_arrangements(bursary_only=True)) == [a2.arrangement_id]
    assert ids(TR.list_arrangements(pass_expired=True)) == [a1.arrangement_id]
    assert TR.arrangements_for_student("NOPE") == []


# ── Summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    s = TR.summary()
    assert (s.total_routes, s.active_routes, s.total_arrangements, s.distinct_students) == (
        0, 0, 0, 0)
    assert s.by_mode == {} and s.by_route == {}


def test_summary_counts():
    r = _route()
    _route("Spare", status="Suspended")
    ava, ben = _pupil(), _pupil()
    old = (TODAY - dt.timedelta(days=3)).isoformat()
    _arr(ava, route_id=r.route_id, fee_status="Unpaid", pass_expires_on=old)
    _arr(ava, mode="Walking", fee_status="Partial", bursary_supported=True)
    _arr(ben, route_id=r.route_id, status="Suspended", fee_status="Unpaid",
         pass_expires_on=old)
    _arr(ben, mode="Taxi", status="Pending", fee_status="LA Funded", bursary_supported=True)
    s = TR.summary()
    assert (s.total_routes, s.active_routes) == (2, 1)
    assert (s.total_arrangements, s.active_arrangements) == (4, 2)
    assert (s.suspended, s.pending) == (1, 1)
    assert s.unpaid_or_partial == 2
    assert s.pass_expired == 1
    assert s.bursary_supported == 2
    assert s.distinct_students == 2
    assert s.by_mode == {"School Bus": 2, "Walking": 1, "Taxi": 1}
    assert s.by_fee_status == {"Unpaid": 2, "Partial": 1, "LA Funded": 1}
    assert s.by_status == {"Active": 2, "Suspended": 1, "Pending": 1}
    assert s.by_route == {"Route A": 2, "—": 2}
