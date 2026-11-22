"""CPD activities and records (systems.primary.domain.staff.cpd.cpd)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.staff import staff as S
from education_system.systems.primary.domain.staff.cpd import cpd as CP

TODAY = dt.date.today()
FUTURE = (TODAY + dt.timedelta(days=30)).isoformat()
PAST = (TODAY - dt.timedelta(days=30)).isoformat()


def _staff(first="Amy", last="Adams"):
    return S.create_staff({"first_name": first, "last_name": last})


def _activity(title="Phonics refresher", date=FUTURE, **extra):
    return CP.create_activity({"title": title, "activity_date": date, **extra})


def _record(staff_id, activity_id=None, **extra):
    return CP.create_record({"staff_id": staff_id, "activity_id": activity_id, **extra})


def test_rating_labels():
    assert [CP.rating_label(r) for r in CP.RATINGS] == [
        "Poor", "Below Expectation", "Good", "Very Good", "Excellent"]
    assert CP.rating_label(None) == "—" and CP.rating_label(9) == "Unknown"


# ── Activities ───────────────────────────────────────────────────────

def test_create_activity_defaults_and_values():
    a = _activity(provider=" NCETM ", hours="3.5", cost="120", capacity="20",
                  certificated=1, end_date=FUTURE)
    assert (a.title, a.activity_type, a.status) == ("Phonics refresher",
                                                     "Internal Training", "Planned")
    assert (a.provider, a.hours, a.cost, a.capacity) == ("NCETM", 3.5, 120.0, 20)
    assert a.certificated is True and a.is_active is True and a.is_completed is False
    assert CP.get_activity(a.activity_id) == a
    assert CP.get_activity(999) is None


@pytest.mark.parametrize("bad, msg", [
    ({"title": " "}, "Title is required"),
    ({"activity_type": "Holiday"}, "Activity type must be one of"),
    ({"activity_date": ""}, "Activity date is required"),
    ({"activity_date": "next week"}, "Activity date must be YYYY-MM-DD"),
    ({"end_date": "31/12/2026"}, "End date must be YYYY-MM-DD"),
    ({"activity_date": "2026-05-02", "end_date": "2026-05-01"}, "End date must be on or after"),
    ({"status": "Running"}, "Status must be one of"),
    ({"hours": "two"}, "hours must be a number"),
    ({"hours": -1}, "hours must be >= 0"),
    ({"cost": -5}, "cost must be >= 0"),
    ({"capacity": "ten"}, "Capacity must be an integer"),
    ({"capacity": -1}, "Capacity must be >= 0"),
])
def test_activity_refusals(bad, msg):
    data = {"title": "T", "activity_date": FUTURE, **bad}
    with pytest.raises(CP.ValidationError, match=msg):
        CP.create_activity(data)
    assert CP.list_activities() == []


def test_update_and_status_helpers():
    a = _activity()
    up = CP.update_activity(a.activity_id, {"title": "Maths mastery", "activity_date": PAST,
                                            "activity_type": "INSET Day"})
    assert (up.title, up.activity_date, up.activity_type) == ("Maths mastery", PAST, "INSET Day")
    with pytest.raises(CP.ValidationError, match="No activity with id 999"):
        CP.update_activity(999, {"title": "x", "activity_date": PAST})
    done = CP.mark_activity_completed(a.activity_id)
    assert done.status == "Completed" and done.is_completed and done.title == "Maths mastery"
    cancelled = CP.set_activity_status(a.activity_id, "Cancelled")
    assert cancelled.is_active is False
    with pytest.raises(CP.ValidationError, match="Status must be one of"):
        CP.set_activity_status(a.activity_id, "Gone")
    with pytest.raises(CP.ValidationError, match="No activity with id 999"):
        CP.set_activity_status(999, "Completed")
    with pytest.raises(CP.ValidationError, match="No activity with id 999"):
        CP.mark_activity_completed(999)


def test_list_activities_filters():
    future = _activity("Future phonics", FUTURE, provider="NCETM")
    past = _activity("Past maths", PAST, activity_type="Webinar", status="Completed")
    cancelled = _activity("Future cancelled", FUTURE, status="Cancelled")
    ids = lambda rows: [x.activity_id for x in rows]  # noqa: E731
    assert ids(CP.list_activities()) == [cancelled.activity_id, future.activity_id,
                                         past.activity_id]
    assert ids(CP.list_activities(activity_type="Webinar")) == [past.activity_id]
    assert ids(CP.list_activities(status="Cancelled")) == [cancelled.activity_id]
    assert ids(CP.list_activities(provider_like="ncetm")) == [future.activity_id]
    assert ids(CP.list_activities(title_like="maths")) == [past.activity_id]
    assert ids(CP.list_activities(upcoming_only=True)) == [future.activity_id]
    assert ids(CP.list_activities(completed_only=True)) == [past.activity_id]
    assert ids(CP.list_activities(date_from=TODAY.isoformat())) == [
        cancelled.activity_id, future.activity_id]
    assert ids(CP.list_activities(date_to=TODAY.isoformat())) == [past.activity_id]
    with pytest.raises(CP.ValidationError, match="From must be YYYY-MM-DD"):
        CP.list_activities(date_from="soon")


def test_delete_activity_keeps_records_unlinked():
    s = _staff()
    a = _activity()
    r = _record(s.staff_id, a.activity_id)
    assert r.activity_title_cache == "Phonics refresher"
    assert CP.record_count(a.activity_id) == 1
    assert CP.delete_activity(a.activity_id) is True
    left = CP.get_record(r.record_id)
    assert left is not None and left.activity_id is None and left.activity_title_cache is None
    assert CP.delete_activity(a.activity_id) is False
    assert CP.record_count(a.activity_id) == 0


# ── Records ──────────────────────────────────────────────────────────

def test_create_record_defaults():
    s = _staff()
    a = _activity()
    r = _record(s.staff_id, str(a.activity_id), hours_completed="2", cost_to_staff="0",
                evaluation_rating="4", certificate_ref=" C1 ")
    assert (r.staff_id, r.activity_id, r.status) == (s.staff_id, a.activity_id, "Booked")
    assert r.booked_on == TODAY.isoformat()
    assert (r.hours_completed, r.cost_to_staff, r.evaluation_rating) == (2.0, 0.0, 4)
    assert (r.certificate_ref, r.certificate_received, r.certificate_filed) == \
        ("C1", False, False)
    assert r.is_active is True and r.is_completed is False
    assert CP.get_record(r.record_id) == r
    assert CP.get_record(999) is None


def test_record_without_activity_allowed():
    s = _staff()
    r = _record(s.staff_id, booked_on="2026-01-05", notes="self study")
    assert (r.activity_id, r.booked_on, r.notes) == (None, "2026-01-05", "self study")


@pytest.mark.parametrize("bad, msg", [
    ({"staff_id": ""}, "Staff is required"),
    ({"staff_id": "T0000000"}, "No staff with id T0000000"),
    ({"activity_id": "abc"}, "Activity id must be an integer"),
    ({"activity_id": 999}, "No activity with id 999"),
    ({"booked_on": "05/01/2026"}, "Booked on must be YYYY-MM-DD"),
    ({"attended_on": "yesterday"}, "Attended on must be YYYY-MM-DD"),
    ({"status": "Maybe"}, "Status must be one of"),
    ({"evaluation_rating": 6}, "Evaluation rating must be 1-5"),
    ({"evaluation_rating": "great"}, "Evaluation rating must be 1-5"),
    ({"hours_completed": "x"}, "hours completed must be a number"),
    ({"hours_completed": -1}, "hours completed must be >= 0"),
    ({"cost_to_staff": -2}, "cost to staff must be >= 0"),
])
def test_record_refusals(bad, msg):
    s = _staff()
    data = {"staff_id": s.staff_id, **bad}
    with pytest.raises(CP.ValidationError, match=msg):
        CP.create_record(data)
    assert CP.list_records() == []


def test_attend_evaluate_file_certificate():
    s = _staff()
    a = _activity()
    r = _record(s.staff_id, a.activity_id)
    att = CP.mark_attended(r.record_id, attended_on="2026-03-01", hours=3)
    assert (att.status, att.attended_on, att.hours_completed) == ("Attended", "2026-03-01", 3.0)
    assert att.is_active is True
    assert [x.record_id for x in CP.list_records(awaiting_certificate=True)] == [r.record_id]
    ev = CP.record_evaluation(r.record_id, rating=5, notes="useful", impact="new routines")
    assert (ev.status, ev.evaluation_rating, ev.evaluation_notes, ev.impact_on_practice) == \
        ("Completed", 5, "useful", "new routines")
    assert ev.is_completed and ev.hours_completed == 3.0
    filed = CP.file_certificate(r.record_id, ref="CERT-9")
    assert (filed.certificate_received, filed.certificate_filed, filed.certificate_ref) == \
        (True, True, "CERT-9")
    assert CP.list_records(awaiting_certificate=True) == []
    # filing without a ref keeps the existing one
    assert CP.file_certificate(r.record_id).certificate_ref == "CERT-9"


def test_mark_attended_defaults_today():
    s = _staff()
    r = _record(s.staff_id)
    att = CP.mark_attended(r.record_id)
    assert att.attended_on == TODAY.isoformat() and att.hours_completed is None


def test_record_helpers_refuse_missing_and_bad_status():
    for fn in (CP.mark_attended, CP.record_evaluation, CP.file_certificate):
        with pytest.raises(CP.ValidationError, match="No record with id 404"):
            fn(404)
    with pytest.raises(CP.ValidationError, match="No record with id 404"):
        CP.set_record_status(404, "Cancelled")
    with pytest.raises(CP.ValidationError, match="No record with id 404"):
        CP.update_record(404, {"staff_id": "x"})
    s = _staff()
    r = _record(s.staff_id)
    with pytest.raises(CP.ValidationError, match="Status must be one of"):
        CP.set_record_status(r.record_id, "Lost")
    with pytest.raises(CP.ValidationError, match="Evaluation rating must be 1-5"):
        CP.record_evaluation(r.record_id, rating=0)
    no_show = CP.set_record_status(r.record_id, "No-Show")
    assert no_show.status == "No-Show" and no_show.is_active is False


def test_delete_record_and_staff_cascade():
    s = _staff()
    r1 = _record(s.staff_id)
    r2 = _record(s.staff_id)
    assert CP.delete_record(r1.record_id) is True
    assert CP.delete_record(r1.record_id) is False
    S.delete_staff(s.staff_id)
    assert CP.get_record(r2.record_id) is None


def test_list_records_filters_and_order():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    act = _activity()
    r1 = _record(a.staff_id, act.activity_id, booked_on="2026-01-10")
    r2 = _record(b.staff_id, booked_on="2026-02-10", status="Completed")
    r3 = _record(a.staff_id, booked_on="2026-03-10", status="Attended",
                 certificate_received=True)
    ids = lambda rows: [x.record_id for x in rows]  # noqa: E731
    assert ids(CP.list_records()) == [r3.record_id, r2.record_id, r1.record_id]
    assert ids(CP.list_records(staff_id=a.staff_id)) == [r3.record_id, r1.record_id]
    assert ids(CP.records_for_staff(b.staff_id)) == [r2.record_id]
    assert ids(CP.list_records(activity_id=act.activity_id)) == [r1.record_id]
    assert ids(CP.list_records(status="Attended")) == [r3.record_id]
    assert ids(CP.list_records(awaiting_certificate=True)) == [r2.record_id]
    assert ids(CP.list_records(completed_only=True)) == [r2.record_id]
    assert ids(CP.list_records(date_from="2026-02-01", date_to="2026-02-28")) == [r2.record_id]
    with pytest.raises(CP.ValidationError, match="To must be YYYY-MM-DD"):
        CP.list_records(date_to="March")


# ── Summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    sm = CP.summary()
    assert (sm.total_activities, sm.total_records, sm.total_hours_logged) == (0, 0, 0.0)
    assert sm.average_rating is None and sm.distinct_staff == 0


def test_summary_figures():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    _activity("Up", FUTURE)
    _activity("Up but cancelled", FUTURE, status="Cancelled")
    _activity("Done", PAST, status="Completed", activity_type="Webinar")
    _record(a.staff_id, status="Completed", hours_completed=2.25, evaluation_rating=4)
    _record(a.staff_id, status="Attended", hours_completed=1.5, certificate_received=True,
            evaluation_rating=3)
    _record(b.staff_id, status="Booked")
    sm = CP.summary()
    assert (sm.total_activities, sm.upcoming_activities, sm.completed_activities) == (3, 1, 1)
    assert (sm.total_records, sm.completed_records, sm.distinct_staff) == (3, 1, 2)
    assert sm.total_hours_logged == 3.75
    assert sm.awaiting_certificate == 1
    assert sm.average_rating == 3.5
    assert sm.by_activity_type == {"Internal Training": 2, "Webinar": 1}
    assert sm.by_activity_status == {"Planned": 1, "Cancelled": 1, "Completed": 1}
    assert sm.by_record_status == {"Completed": 1, "Attended": 1, "Booked": 1}
