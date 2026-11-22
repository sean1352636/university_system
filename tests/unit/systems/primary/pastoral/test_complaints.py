"""Complaints register (systems.primary.domain.pastoral.complaints.complaints)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.pastoral.complaints import complaints as CP

TODAY = dt.date.today()
PAST = (TODAY - dt.timedelta(days=10)).isoformat()
FUTURE = (TODAY + dt.timedelta(days=10)).isoformat()


def _new(**extra):
    data = {"complainant_name": "Mrs Jones", "subject": "Lunchtime supervision",
            "received_on": "2026-09-01"}
    data.update(extra)
    return CP.create_complaint(data)


# ── severity labels ──

def test_severity_label_names_each_level():
    assert [CP.severity_label(s) for s in CP.SEVERITIES] == [
        "Low", "Routine", "Standard", "Serious", "Major"]


def test_severity_label_none_and_unknown():
    assert CP.severity_label(None) == "—"
    assert CP.severity_label(9) == "Unknown"


# ── create / defaults ──

def test_create_applies_defaults():
    c = _new()
    assert c.complaint_id > 0
    assert c.complainant_role == "Parent / Carer"
    assert c.category == "Other"
    assert c.stage == "Informal"
    assert c.severity == 2
    assert c.status == "Received"
    assert c.complainant_satisfaction == "Not Recorded"
    assert c.outcome is None
    assert c.complainant_informed is False
    assert c.escalated_to_stage_2 is False
    assert c.is_open is True
    assert c.severity_label == "Routine"


def test_create_stores_all_given_fields():
    c = _new(complainant_role="Staff", category="Catering", stage="Formal Stage 1",
             severity="4", contact_email=" a@b.test ", contact_phone="0123",
             description="  Cold food ", assigned_to="Head", notes="",
             target_response_date="2026-09-15", governors_informed=1)
    got = CP.get_complaint(c.complaint_id)
    assert got.complainant_role == "Staff"
    assert got.category == "Catering"
    assert got.stage == "Formal Stage 1"
    assert got.severity == 4
    assert got.contact_email == "a@b.test"
    assert got.description == "Cold food"
    assert got.notes is None
    assert got.target_response_date == "2026-09-15"
    assert got.governors_informed is True


def test_blank_received_on_defaults_to_today():
    c = CP.create_complaint({"complainant_name": "X", "subject": "Y"})
    assert c.received_on == TODAY.isoformat()


# ── validation ──

@pytest.mark.parametrize("field, value, message", [
    ("complainant_name", "  ", "Complainant name is required"),
    ("subject", "", "Subject is required"),
    ("complainant_role", "Alien", "Complainant role must be one of"),
    ("category", "Weather", "Category must be one of"),
    ("stage", "Stage 9", "Stage must be one of"),
    ("severity", "6", "Severity must be 1-5"),
    ("severity", "high", "Severity must be 1-5"),
    ("status", "Lost", "Status must be one of"),
    ("outcome", "Maybe", "Outcome must be one of"),
    ("complainant_satisfaction", "Delighted", "Satisfaction must be one of"),
    ("received_on", "01/09/2026", "Received on must be YYYY-MM-DD"),
    ("acknowledged_on", "bad", "Acknowledged on must be YYYY-MM-DD"),
    ("target_response_date", "2026-13-01", "Target response date must be YYYY-MM-DD"),
    ("response_issued_on", "x", "Response issued on must be YYYY-MM-DD"),
    ("closed_on", "y", "Closed on must be YYYY-MM-DD"),
])
def test_create_refuses_bad_values(field, value, message):
    with pytest.raises(CP.ValidationError, match=message):
        _new(**{field: value})
    assert CP.list_complaints() == []


# ── get / update / delete ──

def test_get_missing_returns_none():
    assert CP.get_complaint(999) is None


def test_update_replaces_fields():
    c = _new()
    u = CP.update_complaint(c.complaint_id, {
        "complainant_name": "Mr Jones", "subject": "Changed", "received_on": "2026-09-02",
        "severity": 5, "category": "Transport"})
    assert u.complainant_name == "Mr Jones"
    assert u.subject == "Changed"
    assert u.severity == 5
    assert u.category == "Transport"
    assert u.created_on == c.created_on


def test_update_missing_refused():
    with pytest.raises(CP.ValidationError, match="No complaint with id 42"):
        CP.update_complaint(42, {"complainant_name": "a", "subject": "b"})


def test_update_validates():
    c = _new()
    with pytest.raises(CP.ValidationError, match="Subject is required"):
        CP.update_complaint(c.complaint_id, {"complainant_name": "a", "subject": ""})


def test_delete():
    c = _new()
    assert CP.delete_complaint(c.complaint_id) is True
    assert CP.get_complaint(c.complaint_id) is None
    assert CP.delete_complaint(c.complaint_id) is False


# ── listing ──

def test_list_empty():
    assert CP.list_complaints() == []


def test_list_sorted_newest_first():
    a = _new(received_on="2026-09-01")
    b = _new(received_on="2026-09-05")
    c = _new(received_on="2026-09-01")
    assert [x.complaint_id for x in CP.list_complaints()] == [
        b.complaint_id, c.complaint_id, a.complaint_id]


def test_list_filters():
    a = _new(category="Catering", stage="Formal Stage 2", severity=5, assigned_to="Mrs Head",
             complainant_name="Alice Smith", subject="Cold dinners", complainant_role="Staff",
             received_on="2026-09-10")
    b = _new(category="Transport", severity=1, status="Closed", outcome="Upheld",
             complainant_name="Bob Brown", subject="Late bus", received_on="2026-08-01")
    ids = lambda **kw: [c.complaint_id for c in CP.list_complaints(**kw)]  # noqa: E731
    assert ids(category="Catering") == [a.complaint_id]
    assert ids(stage="Formal Stage 2") == [a.complaint_id]
    assert ids(status="Closed") == [b.complaint_id]
    assert ids(outcome="Upheld") == [b.complaint_id]
    assert ids(complainant_role="Staff") == [a.complaint_id]
    assert ids(severity=1) == [b.complaint_id]
    assert ids(severity_min=4) == [a.complaint_id]
    assert ids(assigned_to_like="head") == [a.complaint_id]
    assert ids(complainant_like="brown") == [b.complaint_id]
    assert ids(subject_like="bus") == [b.complaint_id]
    assert ids(open_only=True) == [a.complaint_id]
    assert ids(stage2_or_higher=True) == [a.complaint_id]
    assert ids(date_from="2026-09-01") == [a.complaint_id]
    assert ids(date_to="2026-08-31") == [b.complaint_id]


def test_list_overdue_only():
    late = _new(target_response_date=PAST)
    _new(target_response_date=FUTURE)
    _new(target_response_date=PAST, response_issued_on=PAST)
    _new(target_response_date=PAST, status="Closed")
    assert [c.complaint_id for c in CP.list_complaints(overdue_only=True)] == [late.complaint_id]


def test_list_bad_date_filter_refused():
    with pytest.raises(CP.ValidationError, match="From must be YYYY-MM-DD"):
        CP.list_complaints(date_from="yesterday")
    with pytest.raises(CP.ValidationError, match="To must be YYYY-MM-DD"):
        CP.list_complaints(date_to="nope")


# ── derived properties ──

def test_response_overdue_property():
    assert _new(target_response_date=PAST).response_overdue is True
    assert _new(target_response_date=FUTURE).response_overdue is False
    assert _new().response_overdue is False
    assert _new(target_response_date=PAST, response_issued_on=PAST).response_overdue is False
    assert _new(target_response_date=PAST, status="Closed").response_overdue is False


def test_days_open_uses_closed_on_or_today():
    assert _new(received_on="2026-09-01", closed_on="2026-09-11").days_open == 10
    recv = (TODAY - dt.timedelta(days=3)).isoformat()
    assert _new(received_on=recv).days_open == 3


# ── workflow ──

def test_acknowledge_sets_status_and_fields():
    c = _new()
    a = CP.acknowledge(c.complaint_id, assigned_to="Deputy", acknowledged_on="2026-09-02",
                       target_response_date="2026-09-16")
    assert a.status == "Acknowledged"
    assert a.assigned_to == "Deputy"
    assert a.acknowledged_on == "2026-09-02"
    assert a.target_response_date == "2026-09-16"


def test_acknowledge_defaults_today_and_keeps_later_status():
    c = _new(status="Under Investigation", assigned_to="Head")
    a = CP.acknowledge(c.complaint_id)
    assert a.acknowledged_on == TODAY.isoformat()
    assert a.status == "Under Investigation"
    assert a.assigned_to == "Head"


def test_start_investigation():
    c = _new()
    assert CP.start_investigation(c.complaint_id).status == "Under Investigation"


def test_issue_response():
    c = _new()
    r = CP.issue_response(c.complaint_id, summary="Apologised", outcome="Partially Upheld",
                          issued_on="2026-09-10", actions_taken="Rota changed")
    assert r.status == "Response Issued"
    assert r.outcome == "Partially Upheld"
    assert r.response_summary == "Apologised"
    assert r.response_issued_on == "2026-09-10"
    assert r.actions_taken == "Rota changed"
    assert r.complainant_informed is True


def test_issue_response_default_date_today():
    c = _new()
    assert CP.issue_response(c.complaint_id, summary="s",
                             outcome="Not Upheld").response_issued_on == TODAY.isoformat()


def test_issue_response_refusals():
    c = _new()
    with pytest.raises(CP.ValidationError, match="Response summary is required"):
        CP.issue_response(c.complaint_id, summary="", outcome="Upheld")
    with pytest.raises(CP.ValidationError, match="Outcome must be one of"):
        CP.issue_response(c.complaint_id, summary="s", outcome="Meh")
    with pytest.raises(CP.ValidationError, match="No complaint with id 99"):
        CP.issue_response(99, summary="s", outcome="Upheld")


def test_escalate_to_stage_2_reopens_response_and_notes_reason():
    c = _new(notes="Phoned parent")
    CP.issue_response(c.complaint_id, summary="s", outcome="Not Upheld")
    e = CP.escalate(c.complaint_id, to_stage="Formal Stage 2", reason="Unhappy")
    assert e.stage == "Formal Stage 2"
    assert e.status == "Escalated"
    assert e.escalated_to_stage_2 is True
    assert e.escalated_to_appeal is False
    assert e.response_issued_on is None
    assert e.response_summary is None
    assert e.outcome is None
    assert e.notes == f"Phoned parent\n{TODAY.isoformat()} escalated to Formal Stage 2: Unhappy"


def test_escalate_to_appeal_informs_governors():
    c = _new()
    e = CP.escalate(c.complaint_id, to_stage="Appeal / Governors")
    assert e.escalated_to_appeal is True
    assert e.governors_informed is True
    assert e.notes is None


def test_escalate_refusals():
    c = _new(stage="Formal Stage 1")
    with pytest.raises(CP.ValidationError, match="Cannot escalate from Formal Stage 1 to Informal"):
        CP.escalate(c.complaint_id, to_stage="Informal")
    with pytest.raises(CP.ValidationError, match="Cannot escalate"):
        CP.escalate(c.complaint_id, to_stage="Formal Stage 1")
    with pytest.raises(CP.ValidationError, match="Stage must be one of"):
        CP.escalate(c.complaint_id, to_stage="Supreme Court")
    with pytest.raises(CP.ValidationError, match="No complaint"):
        CP.escalate(77, to_stage="Formal Stage 2")


def test_record_satisfaction():
    c = _new()
    assert CP.record_satisfaction(c.complaint_id,
                                  satisfaction="Satisfied").complainant_satisfaction == "Satisfied"
    with pytest.raises(CP.ValidationError, match="Satisfaction must be one of"):
        CP.record_satisfaction(c.complaint_id, satisfaction="Thrilled")
    with pytest.raises(CP.ValidationError, match="No complaint"):
        CP.record_satisfaction(77, satisfaction="Satisfied")


def test_close_complaint_sets_today_or_keeps_existing_date():
    a = CP.close_complaint(_new().complaint_id)
    assert a.status == "Closed"
    assert a.closed_on == TODAY.isoformat()
    assert a.is_open is False
    b = CP.close_complaint(_new(closed_on="2026-09-05").complaint_id)
    assert b.closed_on == "2026-09-05"
    with pytest.raises(CP.ValidationError, match="No complaint"):
        CP.close_complaint(5)


def test_set_status():
    c = _new()
    assert CP.set_status(c.complaint_id, "Response Drafted").status == "Response Drafted"
    with pytest.raises(CP.ValidationError, match="Status must be one of"):
        CP.set_status(c.complaint_id, "Done")
    with pytest.raises(CP.ValidationError, match="No complaint"):
        CP.set_status(5, "Closed")


def test_workflow_helpers_refuse_missing():
    with pytest.raises(CP.ValidationError, match="No complaint with id 3"):
        CP.acknowledge(3)
    with pytest.raises(CP.ValidationError, match="No complaint with id 3"):
        CP.start_investigation(3)


# ── summary ──

def test_summary_empty():
    s = CP.summary()
    assert s.total == 0
    assert s.average_days_to_close is None
    assert s.by_category == {}


def test_summary_counts():
    _new(category="Catering", severity=4, target_response_date=PAST)          # open, overdue
    _new(category="Catering", stage="Formal Stage 2", severity=5)              # open
    _new(category="Transport", stage="Appeal / Governors", governors_informed=True,
         status="Closed", outcome="Upheld", received_on="2026-09-01", closed_on="2026-09-11")
    _new(category="Other", status="Closed", outcome="Not Upheld",
         received_on="2026-09-01", closed_on="2026-09-06")
    s = CP.summary()
    assert s.total == 4
    assert s.open_count == 2
    assert s.closed_count == 2
    assert s.overdue == 1
    assert s.serious_or_major == 2
    assert s.at_stage_2_or_appeal == 2
    assert s.governors_informed == 1
    assert s.upheld_count == 1
    assert s.not_upheld_count == 1
    assert s.average_days_to_close == 7.5     # (10 + 5) / 2
    assert s.by_category == {"Catering": 2, "Transport": 1, "Other": 1}
    assert s.by_stage == {"Informal": 2, "Formal Stage 2": 1, "Appeal / Governors": 1}
    assert s.by_status == {"Received": 2, "Closed": 2}
    assert s.by_outcome == {"Upheld": 1, "Not Upheld": 1}
