"""GDPR requests, RoPA, breaches and consents (domain.governance.gdpr.gdpr)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.governance.gdpr import gdpr as GD

TODAY = dt.date.today()


def _iso(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _req(name="Parent Smith", **extra):
    return GD.create_request({"subject_name": name, **extra})


def _proc(name="Pupil records", purpose="Education", **extra):
    return GD.create_processing({"name": name, "purpose": purpose, **extra})


def _breach(title="Email to wrong parent", summary="Report sent to wrong address", **extra):
    return GD.create_breach({"title": title, "summary": summary, **extra})


def _consent(name="Amy Pupil", purpose="Photography / Video", **extra):
    return GD.create_consent({"subject_name": name, "purpose": purpose, **extra})


# ── requests: create ──

def test_create_request_defaults_and_statutory_due_date():
    r = _req(received_date="2026-03-01")
    assert (r.subject_type, r.request_type, r.status) == \
        ("Student", "Subject Access (SAR)", "Received")
    assert r.due_date == "2026-03-31"            # +30 days
    assert r.identity_verified is False and r.responded_date is None
    assert r.is_open is True
    assert GD.get_request(r.request_id) == r


def test_create_request_received_defaults_to_today():
    r = _req()
    assert r.received_date == TODAY.isoformat()
    assert r.due_date == _iso(GD.DEFAULT_SAR_DUE_DAYS)
    assert r.days_remaining == 30 and r.is_overdue is False


def test_create_request_stores_fields():
    r = _req(subject_type="Parent / Guardian", subject_ref=" P1 ", request_type="Erasure (Right to be forgotten)",
             received_date="2026-01-01", due_date="2026-01-20", identity_verified=1,
             handler=" DPO ", description=" all ", contact_email=" a@b.c ",
             contact_phone=" 01 ", notes=" n ")
    assert (r.subject_type, r.subject_ref, r.request_type) == \
        ("Parent / Guardian", "P1", "Erasure (Right to be forgotten)")
    assert (r.due_date, r.identity_verified, r.handler) == ("2026-01-20", True, "DPO")
    assert (r.description, r.contact_email, r.contact_phone, r.notes) == ("all", "a@b.c", "01", "n")


def test_get_missing_request_is_none():
    assert GD.get_request(1) is None


# ── requests: validation ──

def test_request_subject_name_required():
    with pytest.raises(GD.ValidationError, match="Subject name is required"):
        GD.create_request({"subject_name": " "})


def test_request_vocabularies():
    with pytest.raises(GD.ValidationError, match="Subject type must be one of"):
        _req(subject_type="Cat")
    with pytest.raises(GD.ValidationError, match="Request type must be one of"):
        _req(request_type="FOI")
    with pytest.raises(GD.ValidationError, match="Status must be one of"):
        _req(status="Done")


def test_request_dates_validated():
    with pytest.raises(GD.ValidationError, match="Received date must be YYYY-MM-DD"):
        _req(received_date="1 March")
    with pytest.raises(GD.ValidationError, match="Due date must be YYYY-MM-DD"):
        _req(due_date="next month")
    with pytest.raises(GD.ValidationError, match="Responded date must be YYYY-MM-DD"):
        _req(responded_date="x")


def test_refused_request_needs_reason():
    with pytest.raises(GD.ValidationError, match="Refusal reason is required"):
        _req(status="Refused")
    r = _req(status="Refused", refusal_reason="Manifestly unfounded")
    assert r.refusal_reason == "Manifestly unfounded" and r.is_open is False


@pytest.mark.parametrize("status", ["Responded", "Fulfilled", "Partially Fulfilled", "Closed"])
def test_closing_statuses_stamp_responded_date(status):
    r = _req(status=status)
    assert r.responded_date == TODAY.isoformat()
    assert r.days_remaining is None and r.is_overdue is False


# ── requests: list / update / delete ──

def test_list_requests_order_and_filters():
    a = _req("Ann", received_date="2026-02-01", subject_type="Staff", description="payroll")
    b = _req("Bob", received_date="2026-01-01", request_type="Rectification")
    c = _req("Cat", received_date="2026-01-15", status="Closed")
    assert [r.request_id for r in GD.list_requests()] == [b.request_id, c.request_id, a.request_id]
    assert [r.request_id for r in GD.list_requests(status="Closed")] == [c.request_id]
    assert [r.request_id for r in GD.list_requests(request_type="Rectification")] == [b.request_id]
    assert [r.request_id for r in GD.list_requests(subject_type="Staff")] == [a.request_id]
    assert [r.request_id for r in GD.list_requests(open_only=True)] == [b.request_id, a.request_id]
    assert [r.request_id for r in GD.list_requests(search="payroll")] == [a.request_id]


def test_list_requests_overdue_only():
    late = _req("late", received_date=_iso(-40))
    _req("closed late", received_date=_iso(-40), status="Closed")
    _req("fresh")
    assert [r.request_id for r in GD.list_requests(overdue_only=True)] == [late.request_id]
    assert GD.get_request(late.request_id).days_remaining == -10


def test_update_request_merges():
    r = _req(handler="DPO", received_date="2026-03-01")
    out = GD.update_request(r.request_id, {"identity_verified": True, "status": "In Review"})
    assert out.identity_verified is True and out.status == "In Review"
    assert out.handler == "DPO" and out.due_date == "2026-03-31"


def test_update_request_validates_and_requires_request():
    r = _req()
    with pytest.raises(GD.ValidationError, match="Refusal reason"):
        GD.update_request(r.request_id, {"status": "Refused"})
    with pytest.raises(GD.ValidationError, match="No request #55"):
        GD.update_request(55, {"status": "Closed"})


def test_set_request_status():
    r = _req()
    out = GD.set_request_status(r.request_id, "Fulfilled", response_summary="Sent pack")
    assert out.status == "Fulfilled" and out.response_summary == "Sent pack"
    assert out.responded_date == TODAY.isoformat()
    ref = GD.set_request_status(_req("b").request_id, "Refused", refusal_reason="Repeat")
    assert ref.refusal_reason == "Repeat"


def test_delete_request():
    r = _req()
    assert GD.delete_request(r.request_id) is True
    assert GD.get_request(r.request_id) is None
    assert GD.delete_request(r.request_id) is False


# ── processing activities ──

def test_create_processing_defaults_and_fields():
    p = _proc(controller=" School ", data_categories=" names ", dpia_required=1,
              dpia_date="2026-01-01", next_review="2027-01-01")
    assert (p.lawful_basis, p.status) == ("Public Task", "Active")
    assert (p.controller, p.data_categories, p.dpia_required, p.dpia_completed) == \
        ("School", "names", True, False)
    assert (p.dpia_date, p.next_review) == ("2026-01-01", "2027-01-01")
    assert GD.get_processing(p.activity_id) == p


def test_processing_validation():
    with pytest.raises(GD.ValidationError, match="Name is required"):
        GD.create_processing({"purpose": "x"})
    with pytest.raises(GD.ValidationError, match="Purpose is required"):
        GD.create_processing({"name": "x"})
    with pytest.raises(GD.ValidationError, match="Lawful basis must be one of"):
        _proc(lawful_basis="Because")
    with pytest.raises(GD.ValidationError, match="Status must be one of"):
        _proc(status="Live")
    with pytest.raises(GD.ValidationError, match="DPIA date must be YYYY-MM-DD"):
        _proc(dpia_date="x")


def test_processing_name_unique():
    _proc()
    with pytest.raises(GD.ValidationError, match="already exists"):
        _proc()
    other = _proc("CCTV", "Security")
    with pytest.raises(GD.ValidationError, match="already exists"):
        GD.update_processing(other.activity_id, {"name": "Pupil records"})


def test_list_processing_sorted_and_filtered():
    _proc("b meals", "Catering", lawful_basis="Contract")
    _proc("Admissions", "Admit pupils", status="Retired", controller="LA")
    assert [p.name for p in GD.list_processing()] == ["Admissions", "b meals"]
    assert [p.name for p in GD.list_processing(status="Retired")] == ["Admissions"]
    assert [p.name for p in GD.list_processing(lawful_basis="Contract")] == ["b meals"]
    assert [p.name for p in GD.list_processing(search="LA")] == ["Admissions"]


def test_update_and_delete_processing():
    p = _proc(retention="7 years")
    out = GD.update_processing(p.activity_id, {"dpia_completed": True})
    assert out.dpia_completed is True and out.retention == "7 years"
    with pytest.raises(GD.ValidationError, match="No processing activity #9"):
        GD.update_processing(9, {})
    assert GD.delete_processing(p.activity_id) is True
    assert GD.get_processing(p.activity_id) is None
    assert GD.delete_processing(p.activity_id) is False


# ── breaches ──

def test_create_breach_defaults():
    b = _breach()
    assert (b.severity, b.status, b.affected_count) == ("Medium", "Reported", 0)
    assert b.discovered_date == TODAY.isoformat()
    assert b.closed_date is None and b.is_open is True
    assert GD.get_breach(b.breach_id) == b


def test_breach_validation():
    with pytest.raises(GD.ValidationError, match="Title is required"):
        GD.create_breach({"summary": "x"})
    with pytest.raises(GD.ValidationError, match="Summary is required"):
        GD.create_breach({"title": "x"})
    with pytest.raises(GD.ValidationError, match="Severity must be one of"):
        _breach(severity="Huge")
    with pytest.raises(GD.ValidationError, match="Status must be one of"):
        _breach(status="Fixed")
    with pytest.raises(GD.ValidationError, match="Affected count cannot be less than 0"):
        _breach(affected_count=-1)
    with pytest.raises(GD.ValidationError, match="Affected count must be a whole number"):
        _breach(affected_count="some")
    with pytest.raises(GD.ValidationError, match="Discovered date must be YYYY-MM-DD"):
        _breach(discovered_date="today")


def test_closed_breach_stamps_closed_date():
    b = _breach(status="Closed")
    assert b.closed_date == TODAY.isoformat() and b.is_open is False
    assert _breach("n", status="No Action").is_open is False


def test_ico_notified_status_stamps_date_only_when_notifiable():
    a = _breach(ico_notifiable=True, status="ICO Notified")
    assert a.ico_notified_date == TODAY.isoformat()
    b = _breach("b", status="ICO Notified")
    assert b.ico_notified_date is None


def test_list_breaches_order_and_filters():
    a = _breach("a", discovered_date="2026-01-01", severity="High", ico_notifiable=True)
    b = _breach("b", discovered_date="2026-03-01", status="Closed")
    c = _breach("c", discovered_date="2026-02-01", severity="Low")
    assert [x.breach_id for x in GD.list_breaches()] == [b.breach_id, c.breach_id, a.breach_id]
    assert [x.breach_id for x in GD.list_breaches(status="Closed")] == [b.breach_id]
    assert [x.breach_id for x in GD.list_breaches(severity="High")] == [a.breach_id]
    assert [x.breach_id for x in GD.list_breaches(ico_only=True)] == [a.breach_id]
    assert [x.breach_id for x in GD.list_breaches(open_only=True)] == [c.breach_id, a.breach_id]


def test_update_and_delete_breach():
    b = _breach(affected_count=3)
    out = GD.update_breach(b.breach_id, {"status": "Closed", "lessons_learned": "BCC"})
    assert out.status == "Closed" and out.closed_date == TODAY.isoformat()
    assert out.affected_count == 3 and out.lessons_learned == "BCC"
    with pytest.raises(GD.ValidationError, match="No breach #3"):
        GD.update_breach(3, {})
    assert GD.delete_breach(b.breach_id) is True
    assert GD.get_breach(b.breach_id) is None
    assert GD.delete_breach(b.breach_id) is False


# ── consents ──

def test_create_consent_defaults():
    c = _consent(subject_ref=" P001 ")
    assert c.granted is True and c.granted_date == TODAY.isoformat()
    assert c.subject_type == "Student" and c.subject_ref == "P001"
    assert c.is_active is True
    assert GD.get_consent(c.consent_id) == c


def test_consent_validation():
    with pytest.raises(GD.ValidationError, match="Subject name is required"):
        GD.create_consent({"purpose": "Marketing"})
    with pytest.raises(GD.ValidationError, match="Purpose is required"):
        GD.create_consent({"subject_name": "x"})
    with pytest.raises(GD.ValidationError, match="Expires date must be YYYY-MM-DD"):
        _consent(expires_date="never")


def test_consent_is_active_rules():
    assert _consent(granted=False).is_active is False
    assert _consent(withdrawn_date="2026-01-01").is_active is False
    assert _consent(expires_date=_iso(-1)).is_active is False
    assert _consent(expires_date=_iso(0)).is_active is True


def test_list_consents_filters():
    a = _consent("Amy", subject_ref="P1", granted_date="2026-01-01")
    b = _consent("Ben", purpose="Trips & Visits", subject_ref="P2", granted_date="2026-02-01",
                 detail="year 4 museum")
    c = _consent("Amy", purpose="Trips & Visits", subject_ref="P1", granted_date="2026-03-01",
                 withdrawn_date="2026-03-05")
    assert [x.consent_id for x in GD.list_consents()] == [c.consent_id, b.consent_id, a.consent_id]
    assert [x.consent_id for x in GD.list_consents(subject_ref=" P1 ")] == [c.consent_id, a.consent_id]
    assert [x.consent_id for x in GD.list_consents(purpose="Trips & Visits")] == \
        [c.consent_id, b.consent_id]
    assert [x.consent_id for x in GD.list_consents(active_only=True)] == [b.consent_id, a.consent_id]
    assert [x.consent_id for x in GD.list_consents(search="museum")] == [b.consent_id]


def test_withdraw_consent():
    c = _consent(notes="from form")
    out = GD.withdraw_consent(c.consent_id, withdrawn_date="2026-04-01")
    assert out.granted is False and out.withdrawn_date == "2026-04-01"
    assert out.notes == "from form" and out.is_active is False
    d = GD.withdraw_consent(_consent("b").consent_id, notes="parent call")
    assert d.withdrawn_date == TODAY.isoformat() and d.notes == "parent call"


def test_update_and_delete_consent():
    c = _consent(source="paper")
    out = GD.update_consent(c.consent_id, {"expires_date": "2030-01-01"})
    assert out.expires_date == "2030-01-01" and out.source == "paper"
    with pytest.raises(GD.ValidationError, match="No consent #8"):
        GD.update_consent(8, {})
    assert GD.delete_consent(c.consent_id) is True
    assert GD.get_consent(c.consent_id) is None
    assert GD.delete_consent(c.consent_id) is False


# ── overview ──

def test_overview_empty():
    o = GD.overview()
    assert (o.total_requests, o.open_requests, o.overdue_requests) == (0, 0, 0)
    assert o.requests_by_status == {} and o.requests_by_type == {}
    assert (o.total_processing, o.total_breaches, o.total_consents) == (0, 0, 0)


def test_overview_counts():
    _req("late", received_date=_iso(-31))
    _req("open")
    _req("done", status="Closed", request_type="Portability")
    _proc("a", "x", next_review=_iso(0))
    _proc("b", "y", status="Retired", next_review=_iso(-5))
    _proc("c", "z", next_review=_iso(1))
    _breach("hi", severity="Critical", ico_notifiable=True)
    _breach("closed hi", severity="High", status="Closed", ico_notifiable=True)
    _breach("low", severity="Low")
    _consent()
    _consent("b", withdrawn_date="2026-01-01")
    _consent("c", granted=False)
    o = GD.overview()
    assert (o.total_requests, o.open_requests, o.overdue_requests) == (3, 2, 1)
    assert o.requests_by_status == {"Received": 2, "Closed": 1}
    assert o.requests_by_type == {"Subject Access (SAR)": 2, "Portability": 1}
    assert (o.total_processing, o.processing_active, o.processing_due_review) == (3, 2, 2)
    assert (o.total_breaches, o.open_breaches, o.high_or_critical_breaches,
            o.ico_notifiable_open) == (3, 2, 2, 1)
    assert (o.total_consents, o.active_consents, o.withdrawn_consents) == (3, 1, 1)
