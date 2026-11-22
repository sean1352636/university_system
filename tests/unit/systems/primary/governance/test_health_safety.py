"""Health & safety incidents and actions (domain.governance.health_safety.health_safety)."""

from __future__ import annotations

import datetime as dt
import sqlite3

import pytest

from education_system.systems.primary.domain.governance.health_safety import health_safety as HS
from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.staff import staff as ST

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


_n = 0


def _pupil():
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pip{_n}", "last_name": "Hurt",
                           "year_group": "2", "date_of_birth": "2019-05-05"})


def _staff(first="Sam", last="Site"):
    return ST.create_staff({"first_name": first, "last_name": last})


def _inc(**extra):
    data = {"incident_date": "2026-10-01", "location": "Playground",
            "category": "Slip/Trip/Fall", "severity": "Minor",
            "incident_type": "Incident", "description": "Fell off climbing frame"}
    data.update(extra)
    return HS.create_incident(data)


# ── schema: pupils, not students ──

def test_incident_links_point_at_pupils_and_staff(primary_sandbox):
    HS.init_db()
    conn = sqlite3.connect(primary_sandbox.PRIMARY_HEALTH_SAFETY_DB)
    try:
        fks = {(r[3], r[2], r[4]) for r in conn.execute("PRAGMA foreign_key_list(hs_incidents)")}
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='hs_incidents'").fetchone()[0]
    finally:
        conn.close()
    assert ("affected_student_id", "pupils", "pupil_id") in fks
    assert ("reported_by", "staff", "staff_id") in fks
    assert "students" not in sql


def test_incident_for_real_pupil_saves():
    p = _pupil()
    i = _inc(affected_party="Student", affected_student_id=p.pupil_id)
    assert i.affected_student_id == p.pupil_id
    v = HS.view_incident(i.incident_id)
    assert v.affected_display == f"{p.pupil_id} — {p.first_name} {p.last_name}"


# ── create / read ──

def test_create_incident_minimal():
    i = _inc(incident_time="10:15", immediate_action=" ice pack ")
    assert (i.incident_date, i.incident_time, i.location) == ("2026-10-01", "10:15", "Playground")
    assert i.status == "Open" and i.is_open is True and i.is_high_severity is False
    assert i.immediate_action == "ice pack"
    assert i.riddor_reportable is False and i.parent_informed is False
    assert HS.get_incident(i.incident_id) == i


def test_create_incident_with_staff_links_and_flags():
    rep = _staff("Rita", "Reporter")
    ass = _staff("Alan", "Assessor")
    victim = _staff("Vic", "Tim")
    i = _inc(severity="Major", affected_party="Staff", affected_staff_id=victim.staff_id,
             reported_by=rep.staff_id, assessor_id=ass.staff_id, riddor_reportable=True,
             riddor_reported_on="2026-10-02", riddor_reference="R1", parent_informed=1,
             hse_notified=True, review_due="2026-11-01", root_cause=" wet floor ")
    assert i.is_high_severity is True
    assert (i.riddor_reportable, i.riddor_reported_on, i.riddor_reference) == \
        (True, "2026-10-02", "R1")
    assert (i.parent_informed, i.hse_notified, i.root_cause) == (True, True, "wet floor")
    v = HS.view_incident(i.incident_id)
    assert v.reporter_name == f"{rep.staff_id} — Rita Reporter"
    assert v.assessor_name == f"{ass.staff_id} — Alan Assessor"
    assert v.affected_display == f"{victim.staff_id} — Vic Tim"


def test_get_missing_incident_is_none():
    assert HS.get_incident(1) is None
    assert HS.view_incident(1) is None


# ── incident validation ──

@pytest.mark.parametrize("field, msg", [
    ("incident_date", "Incident date is required"),
    ("location", "Location is required"),
    ("category", "Category is required"),
    ("severity", "Severity is required"),
    ("incident_type", "Incident type is required"),
    ("description", "Description is required"),
])
def test_required_fields(field, msg):
    with pytest.raises(HS.ValidationError, match=msg):
        _inc(**{field: "  "})


@pytest.mark.parametrize("field, value, msg", [
    ("category", "Paper cut", "Category must be one of"),
    ("severity", "Fatal", "Severity must be one of"),
    ("incident_type", "Accident", "Incident type must be one of"),
    ("affected_party", "Pupil", "Affected party must be one of"),
    ("status", "Done", "Status must be one of"),
])
def test_vocabularies(field, value, msg):
    with pytest.raises(HS.ValidationError, match=msg):
        _inc(**{field: value})


def test_date_and_time_formats():
    with pytest.raises(HS.ValidationError, match="Incident date must be YYYY-MM-DD"):
        _inc(incident_date="2026-13-01")
    with pytest.raises(HS.ValidationError, match="Incident time must be HH:MM"):
        _inc(incident_time="9:00")
    with pytest.raises(HS.ValidationError, match="Incident time must be HH:MM"):
        _inc(incident_time="25:00")
    with pytest.raises(HS.ValidationError, match="Review due must be YYYY-MM-DD"):
        _inc(review_due="soon")


def test_unknown_pupil_and_staff_refused():
    with pytest.raises(HS.ValidationError, match="No student with id NOPE"):
        _inc(affected_student_id="NOPE")
    with pytest.raises(HS.ValidationError, match="No staff with id X1"):
        _inc(affected_staff_id="X1")
    with pytest.raises(HS.ValidationError, match="No staff with id X2"):
        _inc(reported_by="X2")
    with pytest.raises(HS.ValidationError, match="No staff with id X3"):
        _inc(assessor_id="X3")


def test_person_party_needs_someone_named():
    with pytest.raises(HS.ValidationError, match="requires a student id"):
        _inc(affected_party="Visitor")
    i = _inc(affected_party="Visitor", affected_name="Mr Plumber")
    assert HS.view_incident(i.incident_id).affected_display == "Mr Plumber (Visitor)"
    prop = _inc(affected_party="Property Only")
    assert HS.view_incident(prop.incident_id).affected_display == "Property Only"
    assert HS.view_incident(_inc().incident_id).affected_display == "—"


def test_riddor_needs_reported_on_date():
    with pytest.raises(HS.ValidationError, match="RIDDOR-reportable incidents require"):
        _inc(riddor_reportable=True)
    with pytest.raises(HS.ValidationError, match="RIDDOR reported on must be YYYY-MM-DD"):
        _inc(riddor_reportable=True, riddor_reported_on="today")


# ── list / filter ──

def test_list_incidents_empty():
    assert HS.list_incidents() == []


def test_list_incidents_order_and_filters():
    a = _inc(incident_date="2026-09-01", severity="Major", category="Burn/Scald",
             location="Kitchen")
    b = _inc(incident_date="2026-10-01", incident_time="09:00", incident_type="Near Miss",
             status="Closed", notes="mop sign")
    c = _inc(incident_date="2026-10-01", incident_time="14:00", affected_party="Visitor",
             affected_name="Delivery driver", riddor_reportable=True,
             riddor_reported_on="2026-10-02")
    ids = lambda xs: [x.incident_id for x in xs]  # noqa: E731
    assert ids(HS.list_incidents()) == [c.incident_id, b.incident_id, a.incident_id]
    assert ids(HS.list_incidents(status="Closed")) == [b.incident_id]
    assert ids(HS.list_incidents(severity="Major")) == [a.incident_id]
    assert ids(HS.list_incidents(category="Burn/Scald")) == [a.incident_id]
    assert ids(HS.list_incidents(incident_type="Near Miss")) == [b.incident_id]
    assert ids(HS.list_incidents(affected_party="Visitor")) == [c.incident_id]
    assert ids(HS.list_incidents(riddor_only=True)) == [c.incident_id]
    assert ids(HS.list_incidents(open_only=True)) == [c.incident_id, a.incident_id]
    assert ids(HS.list_incidents(date_from="2026-09-15")) == [c.incident_id, b.incident_id]
    assert ids(HS.list_incidents(date_to="2026-09-30")) == [a.incident_id]
    assert ids(HS.list_incidents(search="Kitchen")) == [a.incident_id]
    assert ids(HS.list_incidents(search="driver")) == [c.incident_id]
    assert ids(HS.list_incidents(search="mop")) == [b.incident_id]


def test_list_incidents_bad_date_filter():
    with pytest.raises(HS.ValidationError, match="From must be YYYY-MM-DD"):
        HS.list_incidents(date_from="Monday")


# ── update / status / delete ──

def test_update_incident_full_replace():
    i = _inc(notes="first")
    data = {"incident_date": "2026-10-03", "location": "Hall", "category": "Other",
            "severity": "Moderate", "incident_type": "Hazard", "description": "Loose tile",
            "status": "Investigating"}
    out = HS.update_incident(i.incident_id, data)
    assert (out.location, out.severity, out.status) == ("Hall", "Moderate", "Investigating")
    assert out.notes is None
    with pytest.raises(HS.ValidationError, match="No incident with id 99"):
        HS.update_incident(99, data)
    with pytest.raises(HS.ValidationError, match="Location is required"):
        HS.update_incident(i.incident_id, {**data, "location": ""})


def test_set_status():
    i = _inc()
    out = HS.set_status(i.incident_id, "Closed")
    assert out.status == "Closed" and out.is_open is False
    assert HS.set_status(i.incident_id, "Reopened").is_open is True
    with pytest.raises(HS.ValidationError, match="Status must be one of"):
        HS.set_status(i.incident_id, "Finished")
    with pytest.raises(HS.ValidationError, match="No incident with id 42"):
        HS.set_status(42, "Closed")


def test_delete_incident_cascades_actions():
    i = _inc()
    a = HS.add_action(i.incident_id, {"action": "Fix fence"})
    assert HS.delete_incident(i.incident_id) is True
    assert HS.get_incident(i.incident_id) is None
    assert HS.get_action(a.action_id) is None
    assert HS.delete_incident(i.incident_id) is False


# ── actions ──

def test_add_action_defaults_and_owner():
    owner = _staff()
    i = _inc()
    a = HS.add_action(i.incident_id, {"action": " Repair gate ", "owner_id": owner.staff_id,
                                      "due_date": "2026-10-10", "notes": " asap "})
    assert (a.incident_id, a.action, a.owner_id) == (i.incident_id, "Repair gate", owner.staff_id)
    assert (a.status, a.priority, a.due_date, a.notes) == ("Open", "Medium", "2026-10-10", "asap")
    assert a.completed_on is None
    assert HS.get_action(a.action_id) == a


def test_action_validation():
    i = _inc()
    with pytest.raises(HS.ValidationError, match="Action is required"):
        HS.add_action(i.incident_id, {"action": ""})
    with pytest.raises(HS.ValidationError, match="No staff with id GHOST"):
        HS.add_action(i.incident_id, {"action": "x", "owner_id": "GHOST"})
    with pytest.raises(HS.ValidationError, match="Action status must be one of"):
        HS.add_action(i.incident_id, {"action": "x", "status": "Doing"})
    with pytest.raises(HS.ValidationError, match="Priority must be one of"):
        HS.add_action(i.incident_id, {"action": "x", "priority": "Urgent"})
    with pytest.raises(HS.ValidationError, match="Due date must be YYYY-MM-DD"):
        HS.add_action(i.incident_id, {"action": "x", "due_date": "x"})
    with pytest.raises(HS.ValidationError, match="No incident with id 77"):
        HS.add_action(77, {"action": "x"})


def test_completed_action_gets_today():
    i = _inc()
    a = HS.add_action(i.incident_id, {"action": "x", "status": "Completed"})
    assert a.completed_on == TODAY.isoformat()


def test_action_is_overdue():
    i = _inc()
    late = HS.add_action(i.incident_id, {"action": "late", "due_date": _iso(-1)})
    today = HS.add_action(i.incident_id, {"action": "today", "due_date": _iso(0)})
    cancelled = HS.add_action(i.incident_id, {"action": "c", "due_date": _iso(-1),
                                              "status": "Cancelled"})
    assert late.is_overdue and not today.is_overdue and not cancelled.is_overdue


def test_list_actions_order_and_filters():
    i1 = _inc()
    i2 = _inc()
    undated = HS.add_action(i1.incident_id, {"action": "undated"})
    later = HS.add_action(i1.incident_id, {"action": "later", "due_date": "2026-12-01"})
    sooner = HS.add_action(i2.incident_id, {"action": "sooner", "due_date": _iso(-3)})
    done = HS.add_action(i2.incident_id, {"action": "done", "due_date": "2026-01-01",
                                          "status": "Completed"})
    ids = lambda xs: [x.action_id for x in xs]  # noqa: E731
    order = ids(HS.list_actions())
    assert order[-1] == done.action_id                       # completed last
    assert order.index(sooner.action_id) < order.index(undated.action_id)
    assert order.index(later.action_id) < order.index(undated.action_id)
    assert set(ids(HS.list_actions(incident_id=i1.incident_id))) == {undated.action_id,
                                                                     later.action_id}
    assert ids(HS.list_actions(status="Completed")) == [done.action_id]
    assert ids(HS.list_actions(overdue_only=True)) == [sooner.action_id]


def test_update_action_full_replace():
    i = _inc()
    a = HS.add_action(i.incident_id, {"action": "x", "notes": "n", "priority": "High"})
    out = HS.update_action(a.action_id, {"action": "y", "status": "In Progress"})
    assert (out.action, out.status, out.priority, out.notes) == ("y", "In Progress", "Medium", None)
    with pytest.raises(HS.ValidationError, match="No action with id 500"):
        HS.update_action(500, {"action": "y"})


def test_complete_action():
    i = _inc()
    a = HS.add_action(i.incident_id, {"action": "x"})
    out = HS.complete_action(a.action_id, completed_on="2026-10-05")
    assert out.status == "Completed" and out.completed_on == "2026-10-05"
    b = HS.add_action(i.incident_id, {"action": "y"})
    assert HS.complete_action(b.action_id).completed_on == TODAY.isoformat()
    with pytest.raises(HS.ValidationError, match="Completed on must be YYYY-MM-DD"):
        HS.complete_action(b.action_id, completed_on="5 Oct")
    with pytest.raises(HS.ValidationError, match="No action with id 600"):
        HS.complete_action(600)


def test_delete_action():
    i = _inc()
    a = HS.add_action(i.incident_id, {"action": "x"})
    assert HS.delete_action(a.action_id) is True
    assert HS.get_action(a.action_id) is None
    assert HS.delete_action(a.action_id) is False


# ── views / summary ──

def test_view_incident_splits_actions():
    i = _inc()
    HS.add_action(i.incident_id, {"action": "open"})
    HS.add_action(i.incident_id, {"action": "prog", "status": "In Progress"})
    HS.add_action(i.incident_id, {"action": "done", "status": "Completed"})
    HS.add_action(i.incident_id, {"action": "cancel", "status": "Cancelled"})
    v = HS.view_incident(i.incident_id)
    assert {a.action for a in v.open_actions} == {"open", "prog"}
    assert {a.action for a in v.completed_actions} == {"done", "cancel"}
    assert v.actions_count == 4
    assert v.reporter_name is None and v.assessor_name is None


def test_list_views_respects_filters():
    _inc(severity="Major")
    _inc()
    views = HS.list_views(severity="Major")
    assert [v.incident.severity for v in views] == ["Major"]


def test_summary_empty():
    s = HS.summary()
    assert s == HS.Summary()


def test_summary_counts():
    a = _inc(severity="Major", riddor_reportable=True, riddor_reported_on="2026-10-02")
    _inc(status="Closed", category="Electrical", incident_type="Hazard")
    _inc(status="Investigating", incident_type="Near Miss")
    HS.add_action(a.incident_id, {"action": "late", "due_date": _iso(-2)})
    HS.add_action(a.incident_id, {"action": "fine", "due_date": _iso(2)})
    HS.add_action(a.incident_id, {"action": "late but done", "due_date": _iso(-2),
                                  "status": "Completed"})
    s = HS.summary()
    assert (s.total, s.open_incidents, s.riddor_reportable) == (3, 2, 1)
    assert (s.open_actions, s.overdue_actions) == (2, 1)
    assert s.by_status == {"Open": 1, "Closed": 1, "Investigating": 1}
    assert s.by_severity == {"Major": 1, "Minor": 2}
    assert s.by_category == {"Slip/Trip/Fall": 2, "Electrical": 1}
    assert s.by_type == {"Incident": 1, "Hazard": 1, "Near Miss": 1}
