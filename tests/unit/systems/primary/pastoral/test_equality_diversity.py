"""Equality & diversity incidents (systems.primary.domain.pastoral.equality_diversity)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.pastoral.equality_diversity import (
    equality_diversity as ED,
)

TODAY = dt.date.today().isoformat()


def _new(**extra):
    data = {"incident_date": "2026-09-10", "reporter": "Miss Patel", "reporter_role": "Staff",
            "incident_type": "Bullying"}
    data.update(extra)
    return ED.create_incident(data)


# ── severity labels ──

def test_severity_labels():
    assert [ED.severity_label(s) for s in ED.SEVERITIES] == [
        "Low", "Moderate", "Serious", "Severe", "Critical"]
    assert ED.severity_label(None) == "—"
    assert ED.severity_label(0) == "Unknown"


# ── create ──

def test_create_defaults():
    i = _new()
    assert i.incident_id > 0
    assert i.subject_role == "Student"
    assert i.perpetrator_role == "Student"
    assert i.protected_characteristic == "Not Applicable"
    assert i.severity == 2
    assert i.severity_label == "Moderate"
    assert i.status == "Reported"
    assert i.reported_on == TODAY
    assert i.anonymous is False
    assert i.is_open is True
    assert i.closed_on is None


def test_create_stores_fields():
    i = _new(incident_time="12:15", reported_on="2026-09-11", anonymous=1,
             subject_name=" Ada ", subject_role="Group", alleged_perpetrator="Year 5 boy",
             perpetrator_role="Other", protected_characteristic="Race", severity="4",
             location="Playground", description="Name calling", witnesses="",
             escalated_to_dsl=True, governors_informed=True)
    got = ED.get_incident(i.incident_id)
    assert got.incident_time == "12:15"
    assert got.reported_on == "2026-09-11"
    assert got.anonymous is True
    assert got.subject_name == "Ada"
    assert got.subject_role == "Group"
    assert got.perpetrator_role == "Other"
    assert got.protected_characteristic == "Race"
    assert got.severity == 4
    assert got.witnesses is None
    assert got.escalated_to_dsl is True
    assert got.governors_informed is True
    assert got.escalated_to_head is False


# ── validation ──

@pytest.mark.parametrize("field, value, message", [
    ("incident_date", "", "Incident date is required"),
    ("incident_date", "10-09-2026", "Incident date must be YYYY-MM-DD"),
    ("incident_time", "noon", "Incident time must be HH:MM"),
    ("reported_on", "2026-02-31", "Reported on must be YYYY-MM-DD"),
    ("closed_on", "soon", "Closed on must be YYYY-MM-DD"),
    ("reporter", " ", "Reporter is required"),
    ("reporter_role", "", "Reporter role must be one of"),
    ("reporter_role", "Alien", "Reporter role must be one of"),
    ("subject_role", "Pet", "Subject role must be one of"),
    ("perpetrator_role", "Pet", "Perpetrator role must be one of"),
    ("incident_type", "", "Incident type must be one of"),
    ("incident_type", "Rudeness", "Incident type must be one of"),
    ("protected_characteristic", "Height", "Protected characteristic must be one of"),
    ("severity", "7", "Severity must be 1-5"),
    ("severity", "bad", "Severity must be 1-5"),
    ("status", "Pending", "Status must be one of"),
])
def test_create_refuses_bad_values(field, value, message):
    with pytest.raises(ED.ValidationError, match=message):
        _new(**{field: value})
    assert ED.list_incidents() == []


# ── get / update / delete ──

def test_get_missing_none():
    assert ED.get_incident(5) is None


def test_update_replaces_record():
    i = _new()
    u = ED.update_incident(i.incident_id, {
        "incident_date": "2026-09-12", "reporter": "Mr B", "reporter_role": "Parent / Visitor",
        "incident_type": "Harassment", "severity": 3})
    assert u.incident_date == "2026-09-12"
    assert u.reporter == "Mr B"
    assert u.reporter_role == "Parent / Visitor"
    assert u.incident_type == "Harassment"
    assert u.severity == 3
    assert u.created_on == i.created_on


def test_update_missing_and_invalid():
    with pytest.raises(ED.ValidationError, match="No incident with id 8"):
        ED.update_incident(8, {})
    i = _new()
    with pytest.raises(ED.ValidationError, match="Reporter is required"):
        ED.update_incident(i.incident_id, {"incident_date": "2026-09-12",
                                           "reporter_role": "Staff", "incident_type": "Other"})


def test_delete():
    i = _new()
    assert ED.delete_incident(i.incident_id) is True
    assert ED.get_incident(i.incident_id) is None
    assert ED.delete_incident(i.incident_id) is False


# ── listing ──

def test_list_empty():
    assert ED.list_incidents() == []


def test_list_order():
    a = _new(incident_date="2026-09-01")
    b = _new(incident_date="2026-09-05")
    c = _new(incident_date="2026-09-01")
    assert [i.incident_id for i in ED.list_incidents()] == [
        b.incident_id, c.incident_id, a.incident_id]


def test_list_filters():
    a = _new(incident_type="Hate Incident", protected_characteristic="Religion / Belief",
             severity=5, reporter="Mrs Green", subject_name="Sam", status="Substantiated",
             escalated_to_head=True, incident_date="2026-10-01")
    b = _new(incident_type="Microaggression", severity=1, reporter="Mr Black",
             alleged_perpetrator="Visitor Sam", status="Resolved", incident_date="2026-09-01")
    c = _new(severity=3, reporter="Mr White", status="Unsubstantiated",
             incident_date="2026-09-15")
    ids = lambda **kw: [i.incident_id for i in ED.list_incidents(**kw)]  # noqa: E731
    assert ids(incident_type="Hate Incident") == [a.incident_id]
    assert ids(characteristic="Religion / Belief") == [a.incident_id]
    assert ids(status="Resolved") == [b.incident_id]
    assert ids(severity=3) == [c.incident_id]
    assert ids(severity_min=3) == [a.incident_id, c.incident_id]
    assert ids(reporter_like="black") == [b.incident_id]
    assert ids(subject_like="sam") == [a.incident_id, b.incident_id]
    assert ids(open_only=True) == [a.incident_id]
    assert ids(substantiated_only=True) == [a.incident_id]
    assert ids(escalated_only=True) == [a.incident_id]
    assert ids(date_from="2026-09-10") == [a.incident_id, c.incident_id]
    assert ids(date_to="2026-09-10") == [b.incident_id]


def test_list_escalated_covers_dsl_and_governors():
    a = _new(escalated_to_dsl=True)
    b = _new(governors_informed=True)
    _new()
    assert {i.incident_id for i in ED.list_incidents(escalated_only=True)} == {
        a.incident_id, b.incident_id}


def test_list_bad_dates_refused():
    with pytest.raises(ED.ValidationError, match="From must be YYYY-MM-DD"):
        ED.list_incidents(date_from="x")
    with pytest.raises(ED.ValidationError, match="To must be YYYY-MM-DD"):
        ED.list_incidents(date_to="y")


# ── is_open ──

@pytest.mark.parametrize("status, expected", [
    ("Reported", True), ("Under Investigation", True), ("Substantiated", True),
    ("Actions Set", True), ("Resolved", False), ("Closed", False),
    ("Unsubstantiated", False),
])
def test_is_open_by_status(status, expected):
    assert _new(status=status).is_open is expected


# ── workflow ──

def test_start_investigation():
    i = _new()
    u = ED.start_investigation(i.incident_id, investigated_by="Deputy Head")
    assert u.status == "Under Investigation"
    assert u.investigated_by == "Deputy Head"
    with pytest.raises(ED.ValidationError, match="Investigator is required"):
        ED.start_investigation(i.incident_id, investigated_by="")
    with pytest.raises(ED.ValidationError, match="No incident with id 99"):
        ED.start_investigation(99, investigated_by="X")


def test_record_outcome_substantiated_stays_open():
    i = _new()
    u = ED.record_outcome(i.incident_id, substantiated=True, outcome="Apology",
                          investigation_notes="Spoke to both")
    assert u.status == "Substantiated"
    assert u.outcome == "Apology"
    assert u.investigation_notes == "Spoke to both"
    assert u.closed_on is None
    assert u.is_open is True


def test_record_outcome_unsubstantiated_closes():
    i = _new()
    u = ED.record_outcome(i.incident_id, substantiated=False, outcome="No evidence")
    assert u.status == "Unsubstantiated"
    assert u.closed_on == TODAY
    assert u.is_open is False


def test_record_outcome_refusals():
    i = _new()
    with pytest.raises(ED.ValidationError, match="Outcome is required"):
        ED.record_outcome(i.incident_id, substantiated=True, outcome="")
    with pytest.raises(ED.ValidationError, match="No incident"):
        ED.record_outcome(99, substantiated=True, outcome="x")


def test_set_actions():
    i = _new()
    u = ED.set_actions(i.incident_id, actions_taken="Restorative chat", training_required=True)
    assert u.status == "Actions Set"
    assert u.actions_taken == "Restorative chat"
    assert u.training_required is True
    with pytest.raises(ED.ValidationError, match="Actions taken is required"):
        ED.set_actions(i.incident_id, actions_taken="")
    with pytest.raises(ED.ValidationError, match="No incident"):
        ED.set_actions(99, actions_taken="x")


def test_resolve_and_close_set_closed_on():
    r = ED.resolve(_new().incident_id)
    assert r.status == "Resolved"
    assert r.closed_on == TODAY
    c = ED.close_incident(_new(closed_on="2026-09-20").incident_id)
    assert c.status == "Closed"
    assert c.closed_on == "2026-09-20"
    with pytest.raises(ED.ValidationError, match="No incident"):
        ED.resolve(99)
    with pytest.raises(ED.ValidationError, match="No incident"):
        ED.close_incident(99)


def test_set_status():
    i = _new()
    assert ED.set_status(i.incident_id, "Actions Set").status == "Actions Set"
    with pytest.raises(ED.ValidationError, match="Status must be one of"):
        ED.set_status(i.incident_id, "Done")
    with pytest.raises(ED.ValidationError, match="No incident"):
        ED.set_status(99, "Closed")


# ── summary ──

def test_summary_empty():
    s = ED.summary()
    assert s.total == 0
    assert s.by_type == {}


def test_summary_figures():
    _new(incident_type="Hate Incident", protected_characteristic="Race", severity=5,
         status="Substantiated", governors_informed=True)                    # awaiting action
    _new(incident_type="Hate Incident", protected_characteristic="Race", severity=4,
         status="Substantiated", actions_taken="Parents met")
    _new(severity=2, status="Resolved")
    _new(severity=2, status="Unsubstantiated", protected_characteristic="Disability")
    s = ED.summary()
    assert s.total == 4
    assert s.open_count == 2
    assert s.serious_or_critical == 2
    assert s.substantiated == 2
    assert s.awaiting_action == 1
    assert s.governors_informed == 1
    assert s.by_type == {"Hate Incident": 2, "Bullying": 2}
    assert s.by_characteristic == {"Race": 2, "Not Applicable": 1, "Disability": 1}
    assert s.by_severity == {5: 1, 4: 1, 2: 2}
    assert s.by_status == {"Substantiated": 2, "Resolved": 1, "Unsubstantiated": 1}
