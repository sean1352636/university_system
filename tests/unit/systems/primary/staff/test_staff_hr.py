"""Staff HR records + events (systems.primary.domain.staff.staff_hr.staff_hr)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.staff import staff as S
from education_system.systems.primary.domain.staff.staff_hr import staff_hr as HR

TODAY = dt.date.today()


def _d(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def _staff(first="Amy", last="Adams"):
    return S.create_staff({"first_name": first, "last_name": last})


def _record(staff_id, **extra):
    return HR.create_record({"staff_id": staff_id, "employment_status": "Permanent",
                             "start_date": "2020-09-01", **extra})


def _event(staff_id, **extra):
    return HR.create_event({"staff_id": staff_id, "event_type": "Annual Leave",
                            "start_date": "2026-10-26", **extra})


# ── HR records ───────────────────────────────────────────────────────

def test_create_record_defaults_and_read_back():
    s = _staff()
    r = _record(s.staff_id, spine_point=" M3 ", salary_amount="34502", fte_percent="80",
                holiday_entitlement_days=28)
    assert (r.employment_status, r.contract_type, r.salary_scale) == (
        "Permanent", "Full-time", "MPS")
    assert (r.fte_percent, r.spine_point, r.salary_amount, r.holiday_entitlement_days) == (
        80.0, "M3", 34502.0, 28.0)
    assert (r.pension_enrolled, r.right_to_work_checked) == (True, False)
    assert r.is_active is True
    assert HR.get_record(r.record_id) == r
    assert HR.get_record_for_staff(s.staff_id) == r
    assert HR.get_record(999) is None and HR.get_record_for_staff("T0000000") is None
    assert _record(_staff("Ben", "Brown").staff_id).fte_percent == 100.0


@pytest.mark.parametrize("bad, msg", [
    ({"staff_id": ""}, "Staff is required"),
    ({"staff_id": "T0000000"}, "No staff with id T0000000"),
    ({"employment_status": ""}, "Employment status must be one of"),
    ({"employment_status": "Retired"}, "Employment status must be one of"),
    ({"contract_type": "Gig"}, "Contract type must be one of"),
    ({"salary_scale": "Professorial"}, "Salary scale must be one of"),
    ({"start_date": ""}, "Start date is required"),
    ({"start_date": "1/9/2020"}, "Start date must be YYYY-MM-DD"),
    ({"probation_end": "x"}, "Probation end must be YYYY-MM-DD"),
    ({"contract_end": "x"}, "Contract end must be YYYY-MM-DD"),
    ({"end_date": "x"}, "End date must be YYYY-MM-DD"),
    ({"dbs_issued_on": "x"}, "DBS issued on must be YYYY-MM-DD"),
    ({"dbs_expires_on": "x"}, "DBS expires on must be YYYY-MM-DD"),
    ({"right_to_work_checked_on": "x"}, "Right-to-work checked on must be YYYY-MM-DD"),
    ({"safeguarding_training_on": "x"}, "Safeguarding training on must be YYYY-MM-DD"),
    ({"safeguarding_expires_on": "x"}, "Safeguarding expires on must be YYYY-MM-DD"),
    ({"last_review_on": "x"}, "Last review on must be YYYY-MM-DD"),
    ({"next_review_due": "x"}, "Next review due must be YYYY-MM-DD"),
    ({"fte_percent": "most"}, "FTE percent must be a number"),
    ({"fte_percent": 101}, "FTE percent must be between 0"),
    ({"salary_amount": "x"}, "salary amount must be a number"),
    ({"holiday_entitlement_days": -1}, "holiday entitlement days must be >= 0"),
])
def test_record_refusals(bad, msg):
    s = _staff()
    data = {"staff_id": s.staff_id, "employment_status": "Permanent",
            "start_date": "2020-09-01", **bad}
    with pytest.raises(HR.ValidationError, match=msg):
        HR.create_record(data)
    assert HR.list_records() == []


def test_zero_fte_is_refused():
    """The rule's own message says FTE is 0 (exclusive) to 100."""
    s = _staff()
    with pytest.raises(HR.ValidationError, match="between 0 \\(exclusive\\) and 100"):
        _record(s.staff_id, fte_percent=0)


def test_one_hr_record_per_staff():
    s = _staff()
    r = _record(s.staff_id)
    with pytest.raises(HR.ValidationError, match="already has an HR record"):
        _record(s.staff_id)
    up = HR.update_record(r.record_id, {"staff_id": s.staff_id,
                                        "employment_status": "Probation",
                                        "start_date": "2020-09-01"})
    assert up.employment_status == "Probation"
    other = _record(_staff("Ben", "Brown").staff_id)
    with pytest.raises(HR.ValidationError, match="already has an HR record"):
        HR.update_record(other.record_id, {"staff_id": s.staff_id,
                                           "employment_status": "Permanent",
                                           "start_date": "2020-09-01"})
    with pytest.raises(HR.ValidationError, match="No HR record with id 999"):
        HR.update_record(999, {"staff_id": s.staff_id})


def test_delete_record_and_staff_cascade():
    s = _staff()
    r = _record(s.staff_id)
    assert HR.delete_record(r.record_id) is True
    assert HR.delete_record(r.record_id) is False
    r2 = _record(s.staff_id)
    e = _event(s.staff_id)
    S.delete_staff(s.staff_id)
    assert HR.get_record(r2.record_id) is None and HR.get_event(e.event_id) is None


# ── Derived flags ────────────────────────────────────────────────────

def test_expiry_review_and_probation_flags():
    s = _staff()
    r = _record(s.staff_id, dbs_expires_on=_d(-1), safeguarding_expires_on=_d(-1),
                next_review_due=_d(-1))
    assert (r.dbs_expired, r.safeguarding_expired, r.review_overdue) == (True, True, True)
    ok = _record(_staff("Ben", "Brown").staff_id, dbs_expires_on=_d(0),
                 safeguarding_expires_on=_d(0), next_review_due=_d(0))
    assert (ok.dbs_expired, ok.safeguarding_expired, ok.review_overdue) == (False, False, False)
    left = _record(_staff("Cat", "Cole").staff_id, employment_status="Left",
                   next_review_due=_d(-10))
    assert left.is_active is False and left.review_overdue is False
    p30 = _record(_staff("Dan", "Dee").staff_id, employment_status="Probation",
                  probation_end=_d(30))
    p31 = _record(_staff("Eve", "Eno").staff_id, employment_status="Probation",
                  probation_end=_d(31))
    gone = _record(_staff("Fay", "Fox").staff_id, employment_status="Probation",
                   probation_end=_d(-1))
    perm = _record(_staff("Gus", "Gee").staff_id, probation_end=_d(5))
    assert (p30.probation_ending_soon, p31.probation_ending_soon) == (True, False)
    assert gone.probation_ending_soon is False and perm.probation_ending_soon is False


# ── Listing ──────────────────────────────────────────────────────────

def test_list_records_filters():
    rows = {}
    for key, extra in (
            ("perm", {"right_to_work_checked": True}),
            ("prob", {"employment_status": "Probation", "contract_type": "Term-time",
                      "right_to_work_checked": True, "dbs_expires_on": _d(-1)}),
            ("ups", {"salary_scale": "UPS", "safeguarding_expires_on": _d(-1),
                     "next_review_due": _d(-1), "right_to_work_checked": True}),
            ("left", {"employment_status": "Left", "dbs_expires_on": _d(-1),
                      "safeguarding_expires_on": _d(-1), "next_review_due": _d(-1)}),
            ("nortw", {})):
        rows[key] = _record(_staff(key, key).staff_id, **extra).record_id
    got = lambda **kw: {r.record_id for r in HR.list_records(**kw)}  # noqa: E731
    assert len(HR.list_records()) == 5
    assert [r.staff_id for r in HR.list_records()] == sorted(
        r.staff_id for r in HR.list_records())
    assert got(employment_status="Probation") == {rows["prob"]}
    assert got(contract_type="Term-time") == {rows["prob"]}
    assert got(salary_scale="UPS") == {rows["ups"]}
    assert got(active_only=True) == set(rows.values()) - {rows["left"]}
    assert got(probation_only=True) == {rows["prob"]}
    assert got(dbs_expired=True) == {rows["prob"]}
    assert got(safeguarding_expired=True) == {rows["ups"]}
    assert got(reviews_overdue=True) == {rows["ups"]}
    assert got(rtw_missing=True) == {rows["nortw"]}


# ── Record workflow ──────────────────────────────────────────────────

def test_review_dbs_safeguarding_status_and_leaving():
    s = _staff()
    r = _record(s.staff_id, next_review_due="2026-01-01")
    rev = HR.record_review(r.record_id, reviewed_on="2026-02-01", next_review_due="2027-02-01")
    assert (rev.last_review_on, rev.next_review_due) == ("2026-02-01", "2027-02-01")
    keep = HR.record_review(r.record_id)
    assert (keep.last_review_on, keep.next_review_due) == (_d(0), "2027-02-01")
    with pytest.raises(HR.ValidationError, match="DBS number is required"):
        HR.renew_dbs(r.record_id, number="")
    dbs = HR.renew_dbs(r.record_id, number="0099", issued_on="2026-03-01",
                       expires_on="2029-03-01")
    assert (dbs.dbs_number, dbs.dbs_issued_on, dbs.dbs_expires_on) == (
        "0099", "2026-03-01", "2029-03-01")
    assert HR.renew_dbs(r.record_id, number="0100").dbs_issued_on == _d(0)
    sg = HR.mark_safeguarding_completed(r.record_id, trained_on="2026-09-02",
                                        expires_on="2027-09-02")
    assert (sg.safeguarding_training_on, sg.safeguarding_expires_on) == (
        "2026-09-02", "2027-09-02")
    assert HR.mark_safeguarding_completed(r.record_id).safeguarding_training_on == _d(0)
    assert HR.set_employment_status(r.record_id, "Notice").employment_status == "Notice"
    with pytest.raises(HR.ValidationError, match="Employment status must be one of"):
        HR.set_employment_status(r.record_id, "Fired")
    left = HR.mark_left(r.record_id, end_date="2026-12-31")
    assert (left.employment_status, left.end_date, left.is_active) == (
        "Left", "2026-12-31", False)
    assert HR.mark_left(r.record_id).end_date == _d(0)


def test_record_workflow_refuses_missing():
    calls = (
        lambda: HR.record_review(404),
        lambda: HR.renew_dbs(404, number="1"),
        lambda: HR.mark_safeguarding_completed(404),
        lambda: HR.set_employment_status(404, "Left"),
        lambda: HR.mark_left(404),
    )
    for call in calls:
        with pytest.raises(HR.ValidationError, match="No HR record with id 404"):
            call()


# ── Events ───────────────────────────────────────────────────────────

def test_create_event_defaults_and_read_back():
    s = _staff()
    e = _event(s.staff_id, end_date="2026-10-30", days="5", reason=" half term trip ")
    assert (e.event_type, e.event_status, e.start_date, e.end_date) == (
        "Annual Leave", "Requested", "2026-10-26", "2026-10-30")
    assert (e.days, e.hours, e.reason) == (5.0, None, "half term trip")
    assert HR.get_event(e.event_id) == e
    assert HR.get_event(999) is None


@pytest.mark.parametrize("bad, msg", [
    ({"staff_id": ""}, "Staff is required"),
    ({"staff_id": "T0000000"}, "No staff with id T0000000"),
    ({"event_type": ""}, "Event type must be one of"),
    ({"event_type": "Holiday"}, "Event type must be one of"),
    ({"event_status": "Pending"}, "Event status must be one of"),
    ({"start_date": ""}, "Start date is required"),
    ({"start_date": "x"}, "Start date must be YYYY-MM-DD"),
    ({"end_date": "x"}, "End date must be YYYY-MM-DD"),
    ({"approved_on": "x"}, "Approved on must be YYYY-MM-DD"),
    ({"end_date": "2026-10-25"}, "End date must be on or after start date"),
    ({"days": "two"}, "days must be a number"),
    ({"hours": -1}, "hours must be >= 0"),
])
def test_event_refusals(bad, msg):
    s = _staff()
    data = {"staff_id": s.staff_id, "event_type": "Annual Leave", "start_date": "2026-10-26",
            **bad}
    with pytest.raises(HR.ValidationError, match=msg):
        HR.create_event(data)
    assert HR.list_events() == []


def test_event_workflow():
    s = _staff()
    e = _event(s.staff_id)
    with pytest.raises(HR.ValidationError, match="Approved by is required"):
        HR.approve_event(e.event_id, approved_by="")
    ok = HR.approve_event(e.event_id, approved_by="Head", approved_on="2026-10-01")
    assert (ok.event_status, ok.approved_by, ok.approved_on) == ("Approved", "Head",
                                                                 "2026-10-01")
    assert HR.mark_taken(e.event_id).event_status == "Taken"
    assert HR.decline_event(e.event_id).event_status == "Declined"
    assert HR.approve_event(e.event_id, approved_by="Head").approved_on == _d(0)
    for call in (lambda: HR.approve_event(404, approved_by="x"),
                 lambda: HR.decline_event(404), lambda: HR.mark_taken(404)):
        with pytest.raises(HR.ValidationError, match="No event with id 404"):
            call()
    with pytest.raises(HR.ValidationError, match="No event with id 404"):
        HR.update_event(404, {"staff_id": s.staff_id})


def test_update_delete_and_list_events():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    e1 = _event(a.staff_id, start_date="2026-09-10")
    e2 = _event(a.staff_id, start_date="2026-10-10", event_type="Sick Leave")
    e3 = _event(b.staff_id, start_date="2026-11-10", event_status="Approved")
    up = HR.update_event(e1.event_id, {"staff_id": a.staff_id, "event_type": "TOIL",
                                       "start_date": "2026-09-10", "hours": 3})
    assert (up.event_type, up.hours) == ("TOIL", 3.0)
    ids = lambda rows: [x.event_id for x in rows]  # noqa: E731
    assert ids(HR.list_events()) == [e3.event_id, e2.event_id, e1.event_id]
    assert ids(HR.list_events(staff_id=a.staff_id)) == [e2.event_id, e1.event_id]
    assert ids(HR.list_events(event_type="Sick Leave")) == [e2.event_id]
    assert ids(HR.list_events(event_status="Approved")) == [e3.event_id]
    assert ids(HR.list_events(date_from="2026-10-01", date_to="2026-10-31")) == [e2.event_id]
    with pytest.raises(HR.ValidationError, match="To must be YYYY-MM-DD"):
        HR.list_events(date_to="soon")
    assert HR.delete_event(e1.event_id) is True
    assert HR.delete_event(e1.event_id) is False


# ── Summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    sm = HR.summary()
    assert (sm.total_records, sm.total_events, sm.sick_taken_days) == (0, 0, 0.0)


def test_summary_figures():
    a = _staff("Amy", "Adams")
    b = _staff("Ben", "Brown")
    c = _staff("Cat", "Cole")
    _record(a.staff_id, right_to_work_checked=True, dbs_expires_on=_d(-1),
            next_review_due=_d(-1))
    _record(b.staff_id, employment_status="Probation", probation_end=_d(10),
            contract_type="Part-time", salary_scale="Support Staff")
    _record(c.staff_id, employment_status="Probation", probation_end=_d(90),
            right_to_work_checked=True, safeguarding_expires_on=_d(-5))
    _event(a.staff_id, event_status="Taken", days=3)
    _event(a.staff_id, event_status="Taken", days=1.5)
    _event(a.staff_id, event_status="Approved", days=10)            # not taken yet
    _event(b.staff_id, event_type="Sick Leave", event_status="Taken", days=2)
    _event(b.staff_id, event_type="Sick Leave", event_status="Requested", days=1)
    _event(b.staff_id, event_type="Sick Leave", event_status="Cancelled", days=4)
    sm = HR.summary()
    assert (sm.total_records, sm.active_records, sm.on_probation,
            sm.probation_ending_soon) == (3, 3, 2, 1)
    assert (sm.dbs_expired, sm.safeguarding_expired, sm.reviews_overdue,
            sm.right_to_work_missing) == (1, 1, 1, 1)
    assert (sm.total_events, sm.sick_events_open) == (6, 1)
    assert (sm.annual_leave_taken_days, sm.sick_taken_days) == (4.5, 3.0)
    assert sm.by_employment_status == {"Permanent": 1, "Probation": 2}
    assert sm.by_contract_type == {"Full-time": 2, "Part-time": 1}
    assert sm.by_scale == {"MPS": 2, "Support Staff": 1}
    assert sm.by_event_type == {"Annual Leave": 3, "Sick Leave": 3}


def test_summary_compliance_counts_ignore_leavers_like_the_filters_do():
    """A leaver's lapsed DBS / safeguarding training is not an open compliance
    issue: list_records(dbs_expired=…) leaves them out, so must summary()."""
    s = _staff()
    _record(s.staff_id, employment_status="Left", dbs_expires_on=_d(-1),
            safeguarding_expires_on=_d(-1))
    sm = HR.summary()
    assert sm.dbs_expired == len(HR.list_records(dbs_expired=True)) == 0
    assert sm.safeguarding_expired == len(HR.list_records(safeguarding_expired=True)) == 0
