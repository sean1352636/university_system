"""School events calendar (domain.academics.calendar.calendar)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.academics.calendar import calendar as CAL

MON = "2025-09-08"      # Monday
WED = "2025-09-10"
SUN = "2025-09-14"


def _event(title="Staff meeting", start=MON, **extra):
    return CAL.create_event({"title": title, "start_date": start, **extra})


# ── empty database ──

def test_empty_db():
    assert CAL.list_events() == []
    assert CAL.get_event(1) is None
    assert CAL.events_on(MON) == []
    assert CAL.events_in_week(MON) == []
    assert CAL.delete_event(1) is False
    s = CAL.summary()
    assert (s.total, s.upcoming, s.today_count, s.this_week_count) == (0, 0, 0, 0)
    assert set(s.by_type) == set(CAL.EVENT_TYPES) and sum(s.by_type.values()) == 0


# ── create ──

def test_create_defaults():
    e = _event()
    assert (e.title, e.event_type, e.audience, e.status, e.start_date, e.end_date) == (
        "Staff meeting", "Meeting", "All", "Scheduled", MON, MON)
    assert (e.all_day, e.rsvp_required, e.capacity, e.cost) == (False, False, None, None)
    assert CAL.get_event(e.event_id) == e


def test_create_full_record_and_time_normalised():
    e = _event("Year 4 trip", event_type="Trip", audience="KS2", start=MON, end_date=WED,
               start_time="09:00", end_time="15:30", location=" Museum ",
               organiser=" Mr Ash ", capacity="30", cost="12.50", rsvp_required=True,
               description=" coach ", notes=" packed lunch ")
    assert (e.start_time, e.end_time) == ("09:00:00", "15:30:00")
    assert (e.location, e.organiser, e.description, e.notes) == (
        "Museum", "Mr Ash", "coach", "packed lunch")
    assert (e.capacity, e.cost, e.rsvp_required) == (30, 12.5, True)
    assert e.is_multiday and e.day_count == 3
    assert e.time_label == "09:00–15:30"


def test_all_day_drops_times():
    e = _event(all_day=True, start_time="09:00", end_time="10:00")
    assert (e.start_time, e.end_time, e.time_label) == (None, None, "all day")


def test_time_label_variants():
    assert _event(start_time="13:15").time_label == "13:15"
    assert _event().time_label == "all day"


def test_occurs_on_is_inclusive():
    e = _event(start=MON, end_date=WED)
    assert e.occurs_on(MON) and e.occurs_on(WED)
    assert not e.occurs_on(SUN)


# ── validation ──

def test_title_required():
    with pytest.raises(CAL.ValidationError, match="Title is required"):
        _event(title=" ")


@pytest.mark.parametrize("field,value,msg", [
    ("event_type", "Party", "Event type must be one of"),
    ("audience", "Governors", "Audience must be one of"),
    ("status", "Maybe", "Status must be one of"),
])
def test_allowed_values(field, value, msg):
    with pytest.raises(CAL.ValidationError, match=msg):
        _event(**{field: value})


def test_dates():
    with pytest.raises(CAL.ValidationError, match="Start date is required"):
        _event(start="")
    with pytest.raises(CAL.ValidationError, match="Start date must be YYYY-MM-DD"):
        _event(start="8 Sept")
    with pytest.raises(CAL.ValidationError, match="End date is not a real date"):
        _event(end_date="2025-09-31")
    with pytest.raises(CAL.ValidationError, match="End date cannot be before start"):
        _event(start=WED, end_date=MON)


def test_times():
    with pytest.raises(CAL.ValidationError, match="Start time must be HH:MM"):
        _event(start_time="9am")
    with pytest.raises(CAL.ValidationError, match="End time is not a real time"):
        _event(end_time="25:00")
    with pytest.raises(CAL.ValidationError, match="End time must be after start time"):
        _event(start_time="10:00", end_time="10:00")


def test_end_time_before_start_ok_on_multiday_event():
    e = _event(start=MON, end_date=WED, start_time="18:00", end_time="09:00")
    assert e.end_time == "09:00:00"


def test_capacity_and_cost():
    with pytest.raises(CAL.ValidationError, match="Capacity must be a whole number"):
        _event(capacity="many")
    with pytest.raises(CAL.ValidationError, match="Capacity cannot be negative"):
        _event(capacity=-1)
    with pytest.raises(CAL.ValidationError, match="Cost must be a number"):
        _event(cost="free")
    with pytest.raises(CAL.ValidationError, match="Cost cannot be negative"):
        _event(cost=-0.01)
    e = _event(capacity=0, cost=0)
    assert (e.capacity, e.cost) == (0, 0.0)


# ── listing ──

def test_list_order_by_date_then_time_untimed_last():
    c = _event("C", start=WED)
    b = _event("B", start=MON)
    a = _event("A", start=MON, start_time="08:30")
    assert [e.event_id for e in CAL.list_events()] == [a.event_id, b.event_id, c.event_id]


def test_list_filters():
    _event("Football v St Mary's", event_type="Sports Fixture", audience="KS2",
           location="Field", organiser="Mr Kick", status="Scheduled")
    _event("Nativity", event_type="Performance / Nativity", audience="Parents",
           location="Hall", organiser="Mrs Song", status="Draft")
    assert [e.title for e in CAL.list_events(event_type="Sports Fixture")] == [
        "Football v St Mary's"]
    assert [e.title for e in CAL.list_events(audience="Parents")] == ["Nativity"]
    assert [e.title for e in CAL.list_events(status="Draft")] == ["Nativity"]
    assert [e.title for e in CAL.list_events(location_like=" hal ")] == ["Nativity"]
    assert [e.title for e in CAL.list_events(organiser_like="kick")] == [
        "Football v St Mary's"]
    assert [e.title for e in CAL.list_events(title_like="nativ")] == ["Nativity"]
    for kw, msg in (("event_type", "Event type"), ("audience", "Audience"),
                    ("status", "Status")):
        with pytest.raises(CAL.ValidationError, match=msg):
            CAL.list_events(**{kw: "nope"})


def test_list_date_window_overlap_and_strict():
    span = _event("Residential", start="2025-09-05", end_date="2025-09-09")
    inside = _event("Inside", start=WED)
    after = _event("After", start="2025-09-20")
    ids = lambda evs: [e.event_id for e in evs]  # noqa: E731
    assert ids(CAL.list_events(date_from=MON, date_to=SUN)) == [span.event_id,
                                                                 inside.event_id]
    assert ids(CAL.list_events(date_from=MON, date_to=SUN, overlapping=False)) == [
        inside.event_id]
    assert ids(CAL.list_events(date_from="2025-09-15")) == [after.event_id]
    assert ids(CAL.list_events(date_to="2025-09-06")) == [span.event_id]
    assert ids(CAL.list_events(date_from="2025-09-15", overlapping=False)) == [
        after.event_id]
    with pytest.raises(CAL.ValidationError, match="date_from must be YYYY-MM-DD"):
        CAL.list_events(date_from="soon")


def test_upcoming_only_hides_finished_events():
    today = dt.date.today()
    _event("Past", start=(today - dt.timedelta(days=10)).isoformat(),
           end_date=(today - dt.timedelta(days=1)).isoformat())
    _event("Running", start=(today - dt.timedelta(days=1)).isoformat(),
           end_date=today.isoformat())
    _event("Future", start=(today + dt.timedelta(days=5)).isoformat())
    assert [e.title for e in CAL.list_events(upcoming_only=True)] == ["Running", "Future"]


def test_events_on_and_in_week():
    span = _event("Book week", start="2025-09-05", end_date="2025-09-08")
    timed = _event("Assembly", start=MON, start_time="09:00", event_type="Assembly")
    _event("Next week", start="2025-09-15")
    assert [e.event_id for e in CAL.events_on(MON)] == [timed.event_id, span.event_id]
    assert [e.title for e in CAL.events_in_week(WED)] == ["Book week", "Assembly"]
    assert [e.title for e in CAL.events_in_week(SUN)] == ["Book week", "Assembly"]
    with pytest.raises(CAL.ValidationError, match="Date must be YYYY-MM-DD"):
        CAL.events_on("monday")


# ── update / status / delete ──

def test_update_merges_and_validates():
    e = _event(location="Hall", start_time="09:00", end_time="10:00")
    out = CAL.update_event(e.event_id, {"title": "Moved meeting", "location": "Library"})
    assert (out.title, out.location, out.start_time, out.end_time) == (
        "Moved meeting", "Library", "09:00:00", "10:00:00")
    with pytest.raises(CAL.ValidationError, match="End time must be after"):
        CAL.update_event(e.event_id, {"end_time": "08:00"})
    with pytest.raises(CAL.ValidationError, match="No event #404"):
        CAL.update_event(404, {})


def test_status_helpers():
    e = _event()
    assert CAL.cancel_event(e.event_id).status == "Cancelled"
    assert CAL.complete_event(e.event_id).status == "Completed"
    assert CAL.set_status(e.event_id, "Postponed").status == "Postponed"
    with pytest.raises(CAL.ValidationError, match="Status must be one of"):
        CAL.set_status(e.event_id, "Gone")
    with pytest.raises(CAL.ValidationError, match="No event #9"):
        CAL.cancel_event(9)


def test_delete_event():
    e = _event()
    assert CAL.delete_event(e.event_id) is True
    assert CAL.get_event(e.event_id) is None


# ── summary ──

def test_summary_counts():
    today = dt.date.today()
    iso = lambda d: d.isoformat()  # noqa: E731
    monday = today - dt.timedelta(days=today.weekday())
    _event("Today", start=iso(today), event_type="Assembly", audience="Pupils")
    _event("In window", start=iso(today + dt.timedelta(days=14)))
    _event("Beyond window", start=iso(today + dt.timedelta(days=15)))
    _event("Cancelled soon", start=iso(today + dt.timedelta(days=1)), status="Cancelled")
    _event("Last month", start=iso(today - dt.timedelta(days=30)), audience="Staff")
    _event("Week start", start=iso(monday), end_date=iso(monday))
    s = CAL.summary()
    assert s.total == 6
    assert s.by_type["Assembly"] == 1 and s.by_type["Meeting"] == 5
    assert s.by_audience == {**{a: 0 for a in CAL.AUDIENCES}, "All": 4, "Pupils": 1,
                             "Staff": 1}
    assert s.by_status["Cancelled"] == 1 and s.by_status["Scheduled"] == 5
    # Scheduled and starting today..today+14: Today, In window, (Week start if today)
    assert s.upcoming == 2 + (monday == today)
    assert s.today_count == 1 + (monday == today)
    # This Mon–Sun week: Today, Week start, plus any of the +1/+14 events inside it.
    sunday = monday + dt.timedelta(days=6)
    in_week = [today, monday, today + dt.timedelta(days=1)]
    assert s.this_week_count == sum(1 for d in in_week if monday <= d <= sunday)
    assert CAL.summary(upcoming_window_days=15).upcoming == s.upcoming + 1
