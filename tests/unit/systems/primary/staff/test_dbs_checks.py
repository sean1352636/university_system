"""DBS check register (systems.primary.domain.staff.dbs_checks.dbs_checks)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.staff import staff as S
from education_system.systems.primary.domain.staff.dbs_checks import dbs_checks as DB

TODAY = dt.date.today()


def _d(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _staff(first="Amy", last="Adams"):
    return S.create_staff({"first_name": first, "last_name": last})


def _check(staff_id, **extra):
    return DB.create_check({"staff_id": staff_id, **extra})


# ── Create ───────────────────────────────────────────────────────────

def test_create_defaults_and_read_back():
    s = _staff()
    c = _check(s.staff_id, dbs_number=" 001234567890 ", applied_on="2026-01-05")
    assert (c.level, c.certificate_type, c.status) == (
        "Enhanced with Barred List", "Original Seen", "Applied")
    assert (c.dbs_number, c.applied_on) == ("001234567890", "2026-01-05")
    assert (c.update_service_subscribed, c.portability_check,
            c.risk_assessment_required) == (False, False, False)
    assert c.is_active is False and c.is_expired is False and c.expiring_soon is False
    assert DB.get_check(c.check_id) == c
    assert DB.get_check(999) is None


@pytest.mark.parametrize("bad, msg", [
    ({"staff_id": ""}, "Staff is required"),
    ({"staff_id": "T0000000"}, "No staff with id T0000000"),
    ({"level": "Super"}, "Level must be one of"),
    ({"certificate_type": "Fax"}, "Certificate type must be one of"),
    ({"status": "Fine"}, "Status must be one of"),
    ({"applied_on": "05/01/2026"}, "Applied on must be YYYY-MM-DD"),
    ({"issued_on": "x"}, "Issued on must be YYYY-MM-DD"),
    ({"expires_on": "2026-13-01"}, "Expires on must be YYYY-MM-DD"),
    ({"certificate_seen_on": "x"}, "Certificate seen on must be YYYY-MM-DD"),
    ({"last_update_check_on": "x"}, "Last update check must be YYYY-MM-DD"),
    ({"next_update_check_due": "x"}, "Next update check must be YYYY-MM-DD"),
    ({"risk_assessment_completed_on": "x"}, "Risk assessment on must be YYYY-MM-DD"),
    ({"signed_off_on": "x"}, "Signed off on must be YYYY-MM-DD"),
    ({"issued_on": "2026-02-01", "expires_on": "2026-01-31"},
     "Expires on must be on or after issued on"),
])
def test_create_refusals(bad, msg):
    s = _staff()
    data = {"staff_id": s.staff_id, **bad}
    with pytest.raises(DB.ValidationError, match=msg):
        DB.create_check(data)
    assert DB.list_checks() == []


# ── Derived flags ────────────────────────────────────────────────────

def test_expiry_flags_only_for_active_checks():
    s = _staff()
    expired = _check(s.staff_id, status="Cleared", expires_on=_d(-1))
    soon = _check(s.staff_id, status="Cleared", expires_on=_d(90))
    today = _check(s.staff_id, status="Update Service Active", expires_on=_d(0))
    later = _check(s.staff_id, status="Cleared", expires_on=_d(91))
    lapsed = _check(s.staff_id, status="Lapsed", expires_on=_d(-10))
    assert (expired.is_expired, expired.expiring_soon) == (True, False)
    assert (soon.is_expired, soon.expiring_soon) == (False, True)
    assert (today.is_expired, today.expiring_soon) == (False, True)
    assert (later.is_expired, later.expiring_soon) == (False, False)
    assert (lapsed.is_active, lapsed.is_expired) == (False, False)


def test_update_check_overdue_flag():
    s = _staff()
    overdue = _check(s.staff_id, update_service_subscribed=True,
                     next_update_check_due=_d(-1))
    due_today = _check(s.staff_id, update_service_subscribed=True,
                       next_update_check_due=_d(0))
    not_sub = _check(s.staff_id, next_update_check_due=_d(-30))
    assert overdue.update_check_overdue is True
    assert due_today.update_check_overdue is False
    assert not_sub.update_check_overdue is False


# ── Update / delete / latest ─────────────────────────────────────────

def test_update_and_delete():
    s = _staff()
    c = _check(s.staff_id)
    up = DB.update_check(c.check_id, {"staff_id": s.staff_id, "level": "Basic",
                                      "notes": " ok "})
    assert (up.level, up.notes) == ("Basic", "ok")
    with pytest.raises(DB.ValidationError, match="No check with id 999"):
        DB.update_check(999, {"staff_id": s.staff_id})
    assert DB.delete_check(c.check_id) is True
    assert DB.delete_check(c.check_id) is False


def test_staff_delete_cascades():
    s = _staff()
    c = _check(s.staff_id)
    S.delete_staff(s.staff_id)
    assert DB.get_check(c.check_id) is None


def test_latest_for_staff_uses_issued_then_applied():
    s = _staff()
    assert DB.latest_for_staff(s.staff_id) is None
    _check(s.staff_id, issued_on="2020-01-01")
    newer = _check(s.staff_id, issued_on="2024-01-01")
    _check(s.staff_id, applied_on="2023-06-01")
    assert DB.latest_for_staff(s.staff_id).check_id == newer.check_id
    applied_later = _check(s.staff_id, applied_on="2025-03-01")
    assert DB.latest_for_staff(s.staff_id).check_id == applied_later.check_id


# ── Listing ──────────────────────────────────────────────────────────

def test_list_filters_and_order():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    expired = _check(a.staff_id, status="Cleared", expires_on=_d(-5), signed_off_by="DSL",
                     level="Enhanced")
    soon = _check(b.staff_id, status="Cleared", expires_on=_d(30),
                  certificate_type="DBS Portal", update_service_subscribed=True,
                  next_update_check_due=_d(-2))
    pending = _check(a.staff_id, status="Pending", risk_assessment_required=True)
    ids = lambda rows: [c.check_id for c in rows]  # noqa: E731
    # no expiry sorts first (''), then by expiry date ascending
    assert ids(DB.list_checks()) == [pending.check_id, expired.check_id, soon.check_id]
    assert ids(DB.list_checks(staff_id=a.staff_id)) == [pending.check_id, expired.check_id]
    assert ids(DB.checks_for_staff(b.staff_id)) == [soon.check_id]
    assert ids(DB.list_checks(level="Enhanced")) == [expired.check_id]
    assert ids(DB.list_checks(status="Pending")) == [pending.check_id]
    assert ids(DB.list_checks(certificate_type="DBS Portal")) == [soon.check_id]
    assert ids(DB.list_checks(active_only=True)) == [expired.check_id, soon.check_id]
    assert ids(DB.list_checks(expired=True)) == [expired.check_id]
    assert ids(DB.list_checks(expiring_soon=True)) == [soon.check_id]
    assert ids(DB.list_checks(update_check_overdue=True)) == [soon.check_id]
    assert ids(DB.list_checks(update_service_only=True)) == [soon.check_id]
    assert ids(DB.list_checks(unsigned=True)) == [pending.check_id, soon.check_id]
    assert ids(DB.list_checks(risk_assessment_pending=True)) == [pending.check_id]


# ── Workflow ─────────────────────────────────────────────────────────

def test_issue_certificate():
    s = _staff()
    c = _check(s.staff_id)
    out = DB.issue_certificate(c.check_id, dbs_number="0012", issued_on="2026-01-10",
                               expires_on="2029-01-10")
    assert (out.status, out.dbs_number, out.issued_on, out.expires_on) == (
        "Cleared", "0012", "2026-01-10", "2029-01-10")
    assert out.is_active is True
    default = DB.issue_certificate(_check(s.staff_id).check_id, dbs_number="9")
    assert default.issued_on == TODAY.isoformat() and default.expires_on is None
    with pytest.raises(DB.ValidationError, match="DBS number is required"):
        DB.issue_certificate(c.check_id, dbs_number="")
    with pytest.raises(DB.ValidationError, match="No check with id 999"):
        DB.issue_certificate(999, dbs_number="1")
    with pytest.raises(DB.ValidationError, match="Expires on must be on or after"):
        DB.issue_certificate(c.check_id, dbs_number="1", issued_on="2026-05-01",
                             expires_on="2026-04-01")


def test_see_certificate_and_sign_off():
    s = _staff()
    c = _check(s.staff_id)
    assert DB.see_certificate(c.check_id, seen_on="2026-02-02").certificate_seen_on == \
        "2026-02-02"
    assert DB.see_certificate(c.check_id).certificate_seen_on == TODAY.isoformat()
    signed = DB.sign_off(c.check_id, signed_off_by="Mrs Head", signed_off_on="2026-02-03")
    assert (signed.signed_off_by, signed.signed_off_on) == ("Mrs Head", "2026-02-03")
    assert DB.list_checks(unsigned=True) == []
    with pytest.raises(DB.ValidationError, match="Signed-off by is required"):
        DB.sign_off(c.check_id, signed_off_by="")
    assert DB.sign_off(c.check_id, signed_off_by="DSL").signed_off_on == TODAY.isoformat()


def test_update_service_subscription_and_checks():
    s = _staff()
    cleared = _check(s.staff_id, status="Cleared")
    sub = DB.subscribe_update_service(cleared.check_id, update_id="US-1",
                                      next_check_due="2027-01-01")
    assert (sub.update_service_subscribed, sub.update_service_id, sub.next_update_check_due,
            sub.status) == (True, "US-1", "2027-01-01", "Update Service Active")
    pending = _check(s.staff_id, status="Pending")
    assert DB.subscribe_update_service(pending.check_id).status == "Pending"
    rec = DB.record_update_check(cleared.check_id, checked_on="2026-03-01")
    assert (rec.last_update_check_on, rec.next_update_check_due) == ("2026-03-01", "2027-03-01")
    rec2 = DB.record_update_check(cleared.check_id, checked_on="2026-04-01",
                                  next_check_due="2026-10-01")
    assert rec2.next_update_check_due == "2026-10-01"
    rec3 = DB.record_update_check(cleared.check_id)
    assert rec3.last_update_check_on == TODAY.isoformat()
    assert rec3.next_update_check_due == (TODAY + dt.timedelta(days=365)).isoformat()


def test_risk_assessment():
    s = _staff()
    c = _check(s.staff_id, risk_assessment_required=True)
    with pytest.raises(DB.ValidationError, match="outcome is required"):
        DB.complete_risk_assessment(c.check_id, outcome="")
    out = DB.complete_risk_assessment(c.check_id, outcome="Approved", completed_on="2026-01-02")
    assert (out.risk_assessment_outcome, out.risk_assessment_completed_on) == \
        ("Approved", "2026-01-02")
    assert DB.list_checks(risk_assessment_pending=True) == []


def test_status_transitions():
    s = _staff()
    c = _check(s.staff_id, status="Cleared")
    assert DB.start_renewal(c.check_id).status == "Renewing"
    assert DB.mark_lapsed(c.check_id).status == "Lapsed"
    assert DB.set_status(c.check_id, "Refused").status == "Refused"
    with pytest.raises(DB.ValidationError, match="Status must be one of"):
        DB.set_status(c.check_id, "OK")


def test_workflow_helpers_refuse_missing_check():
    calls = (
        lambda: DB.see_certificate(404),
        lambda: DB.subscribe_update_service(404),
        lambda: DB.record_update_check(404),
        lambda: DB.complete_risk_assessment(404, outcome="x"),
        lambda: DB.sign_off(404, signed_off_by="x"),
        lambda: DB.mark_lapsed(404),
        lambda: DB.start_renewal(404),
        lambda: DB.set_status(404, "Cleared"),
    )
    for call in calls:
        with pytest.raises(DB.ValidationError, match="No check with id 404"):
            call()


# ── Summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    sm = DB.summary()
    assert sm.total == 0 and sm.distinct_staff == 0 and sm.by_level == {}


def test_summary_figures():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    _check(a.staff_id, status="Cleared", expires_on=_d(-1), signed_off_by="DSL")
    _check(a.staff_id, status="Cleared (with information)", expires_on=_d(10),
           risk_assessment_required=True, level="Enhanced")
    _check(b.staff_id, status="Update Service Active", update_service_subscribed=True,
           next_update_check_due=_d(-3), certificate_type="Update Service Check",
           signed_off_by="DSL")
    _check(b.staff_id, status="Awaiting Certificate")
    _check(b.staff_id, status="Renewing", expires_on=_d(-30))
    sm = DB.summary()
    assert (sm.total, sm.active, sm.cleared, sm.pending, sm.renewing) == (5, 3, 2, 1, 1)
    assert (sm.expired, sm.expiring_soon) == (1, 1)
    assert (sm.update_check_overdue, sm.update_service_subscribed) == (1, 1)
    assert (sm.risk_assessment_pending, sm.unsigned, sm.distinct_staff) == (1, 3, 2)
    assert sm.by_level == {"Enhanced with Barred List": 4, "Enhanced": 1}
    assert sm.by_status == {"Cleared": 1, "Cleared (with information)": 1,
                            "Update Service Active": 1, "Awaiting Certificate": 1,
                            "Renewing": 1}
    assert sm.by_certificate_type == {"Original Seen": 4, "Update Service Check": 1}
