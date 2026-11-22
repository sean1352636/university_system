"""Emergency events and drills (systems.primary.domain.pastoral.emergency.emergency)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.pastoral.emergency import emergency as EM


def _new(**extra):
    data = {"event_date": "2026-09-10"}
    data.update(extra)
    return EM.create(data)


# ── create / defaults ──

def test_create_defaults():
    e = _new()
    assert e.event_id > 0
    assert e.kind == "Drill"
    assert e.event_type == "Fire"
    assert e.outcome == "Successful"
    assert e.status == "Logged"
    assert e.missing_count == 0
    assert e.injuries_count == 0
    assert e.emergency_services is False
    assert e.duration_min is None
    assert e.pupils_evacuated is None


def test_blank_date_defaults_to_today():
    assert EM.create({}).event_date == dt.date.today().isoformat()


def test_create_stores_fields_and_trims():
    e = _new(kind="Real", event_type="Lockdown", start_time="10:00", end_time="10:20",
             location=" Hall ", trigger="Intruder seen", reported_by="Mr A",
             incident_commander="Head", pupils_evacuated="210", staff_evacuated=30,
             missing_count="1", injuries_count=2, lessons_learned=" Doors ",
             notes="  ")
    got = EM.get(e.event_id)
    assert got.kind == "Real"
    assert got.event_type == "Lockdown"
    assert got.duration_min == 20
    assert got.location == "Hall"
    assert got.pupils_evacuated == 210
    assert got.staff_evacuated == 30
    assert got.missing_count == 1
    assert got.injuries_count == 2
    assert got.lessons_learned == "Doors"
    assert got.notes is None
    assert got.incident_commander == "Head"


def test_explicit_duration_wins_over_times():
    assert _new(start_time="09:00", end_time="09:30", duration_min="12").duration_min == 12


def test_duration_needs_both_times():
    assert _new(start_time="09:00").duration_min is None


def test_services_attended_implies_emergency_services():
    e = _new(services_attended="Fire brigade")
    assert e.emergency_services is True
    assert e.services_attended == "Fire brigade"


def test_issues_identified_with_actions_ok():
    e = _new(outcome="Issues identified", follow_up_actions="Fix alarm in Y2")
    assert e.outcome == "Issues identified"
    assert e.follow_up_actions == "Fix alarm in Y2"


# ── validation ──

@pytest.mark.parametrize("field, value, message", [
    ("kind", "Rehearsal", "Kind must be one of"),
    ("event_type", "Zombies", "Event type must be one of"),
    ("event_date", "10/09/2026", "Event date must be YYYY-MM-DD"),
    ("event_date", "2026-02-30", "Event date is not a real date"),
    ("start_time", "9am", r"Start time must be HH:MM \(24-hour\)"),
    ("end_time", "24:00", r"End time must be HH:MM \(24-hour\)"),
    ("duration_min", "-1", "Duration \\(min\\) cannot be below 0"),
    ("duration_min", "1441", "Duration \\(min\\) cannot exceed 1440"),
    ("duration_min", "long", "Duration \\(min\\) must be a whole number"),
    ("pupils_evacuated", "-3", "Pupils evacuated cannot be below 0"),
    ("staff_evacuated", "lots", "Staff evacuated must be a whole number"),
    ("missing_count", "-1", "Missing count cannot be below 0"),
    ("injuries_count", "x", "Injuries count must be a whole number"),
    ("outcome", "Great", "Outcome must be one of"),
    ("status", "Done", "Status must be one of"),
])
def test_create_refuses_bad_values(field, value, message):
    with pytest.raises(EM.ValidationError, match=message):
        _new(**{field: value})
    assert EM.list_events() == []


def test_end_before_start_refused():
    with pytest.raises(EM.ValidationError, match="End time cannot be before start time"):
        _new(start_time="10:30", end_time="10:00")


def test_issues_identified_needs_follow_up():
    with pytest.raises(EM.ValidationError, match="Follow-up actions are required"):
        _new(outcome="Issues identified")


# ── get / update / delete ──

def test_get_missing_is_none():
    assert EM.get(123) is None


def test_update_merges_only_given_fields():
    e = _new(location="Field", pupils_evacuated=100)
    u = EM.update(e.event_id, {"status": "Under review", "notes": "Slow line-up"})
    assert u.status == "Under review"
    assert u.notes == "Slow line-up"
    assert u.location == "Field"
    assert u.pupils_evacuated == 100


def test_update_validates_merged_record():
    e = _new()
    with pytest.raises(EM.ValidationError, match="Follow-up actions are required"):
        EM.update(e.event_id, {"outcome": "Issues identified"})
    assert EM.get(e.event_id).outcome == "Successful"


def test_update_missing_refused():
    with pytest.raises(EM.ValidationError, match="No emergency event #9"):
        EM.update(9, {"status": "Closed"})


def test_set_status_and_close():
    e = _new()
    assert EM.set_status(e.event_id, "Actions outstanding").status == "Actions outstanding"
    assert EM.close_event(e.event_id).status == "Closed"
    with pytest.raises(EM.ValidationError, match="Status must be one of"):
        EM.set_status(e.event_id, "Archived")


def test_delete():
    e = _new()
    assert EM.delete(e.event_id) is True
    assert EM.get(e.event_id) is None
    assert EM.delete(e.event_id) is False


# ── listing ──

def test_list_empty():
    assert EM.list_events() == []


def test_list_order_newest_date_then_time():
    a = _new(event_date="2026-09-01", start_time="09:00")
    b = _new(event_date="2026-09-05", start_time="09:00")
    c = _new(event_date="2026-09-01", start_time="14:00")
    assert [e.event_id for e in EM.list_events()] == [b.event_id, c.event_id, a.event_id]


def test_list_filters():
    a = _new(kind="Real", event_type="Flood", status="Under review", event_date="2026-09-01")
    b = _new(kind="Drill", event_type="Lockdown", status="Actions outstanding",
             event_date="2026-10-01")
    c = _new(kind="Test", status="Closed", event_date="2026-11-01")
    ids = lambda **kw: [e.event_id for e in EM.list_events(**kw)]  # noqa: E731
    assert ids(kind="Real") == [a.event_id]
    assert ids(event_type="Lockdown") == [b.event_id]
    assert ids(status="Closed") == [c.event_id]
    assert ids(from_date="2026-10-01") == [c.event_id, b.event_id]
    assert ids(to_date="2026-09-30") == [a.event_id]
    assert ids(outstanding_only=True) == [b.event_id, a.event_id]


@pytest.mark.parametrize("kwargs, message", [
    ({"kind": "Party"}, "Kind filter must be one of"),
    ({"event_type": "Meteor"}, "Event type filter must be one of"),
    ({"status": "Gone"}, "Status filter must be one of"),
    ({"from_date": "1 Sept"}, "From date must be YYYY-MM-DD"),
    ({"to_date": "2026/09/01"}, "To date must be YYYY-MM-DD"),
])
def test_list_refuses_bad_filters(kwargs, message):
    with pytest.raises(EM.ValidationError, match=message):
        EM.list_events(**kwargs)


# ── summary ──

def test_cohort_summary_empty():
    s = EM.cohort_summary()
    assert s["total"] == 0
    assert s["avg_duration_min"] is None
    assert s["by_type"] == {}


def test_cohort_summary_figures():
    _new(kind="Drill", duration_min=10, event_date="2026-09-01")
    _new(kind="Drill", event_type="Lockdown", duration_min=15, status="Under review",
         event_date="2026-09-02")
    _new(kind="Real", event_type="Medical — pupil", missing_count=1, injuries_count=2,
         services_attended="Ambulance", outcome="Issues identified",
         follow_up_actions="Review", status="Actions outstanding", event_date="2026-09-03")
    _new(kind="False alarm", duration_min=4, event_date="2026-12-01")
    s = EM.cohort_summary()
    assert s["total"] == 4
    assert s["drills"] == 2
    assert s["real"] == 1
    assert s["outstanding"] == 2
    assert s["by_type"] == {"Fire": 2, "Lockdown": 1, "Medical — pupil": 1}
    assert s["by_outcome"] == {"Successful": 3, "Issues identified": 1}
    assert s["by_status"] == {"Logged": 2, "Under review": 1, "Actions outstanding": 1}
    assert s["total_missing"] == 1
    assert s["total_injuries"] == 2
    assert s["services_called"] == 1
    assert s["avg_duration_min"] == 9.7     # (10 + 15 + 4) / 3


def test_cohort_summary_date_window():
    _new(event_date="2026-09-01")
    _new(event_date="2026-12-01")
    assert EM.cohort_summary(from_date="2026-10-01")["total"] == 1
    assert EM.cohort_summary(to_date="2026-10-01")["total"] == 1
