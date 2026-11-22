"""Leave-of-absence requests (domain.pastoral.absence_requests.absence_requests)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.pastoral.absence_requests import (
    absence_requests as AR,
)

TODAY = dt.date.today().isoformat()


def _pupil(first="Ada", last="Lovelace", year="3"):
    return P.create_pupil({"first_name": first, "last_name": last,
                           "year_group": year, "date_of_birth": "2018-01-01"})


def _request(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "requested_by": "Mrs Lovelace",
            "start_date": "2026-03-02", "end_date": "2026-03-06",
            "reason": "Grandparent's wedding abroad"}
    data.update(extra)
    return AR.create(data)


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_values_and_defaults():
    p = _pupil()
    r = _request(p, relationship="Mother", destination="Spain",
                 contact_phone="07700 900000", notes="  ")
    assert r.request_id > 0
    assert r.pupil_id == p.pupil_id
    assert r.requested_by == "Mrs Lovelace"
    assert r.relationship == "Mother"
    assert r.destination == "Spain"
    assert r.contact_phone == "07700 900000"
    assert r.notes is None
    assert r.status == "Pending"
    assert r.category == "Family holiday"
    assert r.authorisation == "Not yet decided"
    assert r.submitted_date == TODAY
    assert r.decided_by is None and r.decided_date is None
    assert r.pupil_name == "Ada Lovelace"
    assert r.pupil_year == "3"


def test_get_reads_back_and_missing_is_none():
    r = _request(_pupil())
    assert AR.get(r.request_id) == r
    assert AR.get(9999) is None


def test_school_days_counted_mon_to_fri_inclusive():
    p = _pupil()
    # Mon 2 Mar 2026 → Fri 6 Mar 2026: 5 school days
    assert _request(p).school_days == 5
    # Fri 6 Mar → Mon 9 Mar: Fri + Mon = 2
    assert _request(p, start_date="2026-03-06", end_date="2026-03-09").school_days == 2
    # Saturday → Sunday: 0
    assert _request(p, start_date="2026-03-07", end_date="2026-03-08").school_days == 0
    # two full weeks Mon 2 → Fri 13 Mar: 10
    assert _request(p, start_date="2026-03-02", end_date="2026-03-13").school_days == 10


def test_explicit_school_days_kept():
    assert _request(_pupil(), school_days="3").school_days == 3
    assert _request(_pupil("Bo", "B"), school_days=0).school_days == 0


# ── validation ───────────────────────────────────────────────────────

def test_pupil_required_and_must_exist():
    p = _pupil()
    with pytest.raises(AR.ValidationError, match="Pupil ID is required"):
        _request(p, pupil_id="  ")
    with pytest.raises(AR.ValidationError, match="No pupil with id"):
        _request(p, pupil_id="NOPE123")


def test_requested_by_and_reason_required():
    p = _pupil()
    with pytest.raises(AR.ValidationError, match="Requested by is required"):
        _request(p, requested_by="")
    with pytest.raises(AR.ValidationError, match="Reason is required"):
        _request(p, reason="   ")
    with pytest.raises(AR.ValidationError, match="too long"):
        _request(p, reason="x" * 1001)
    assert len(_request(p, reason="x" * 1000).reason) == 1000


def test_dates_validated():
    p = _pupil()
    with pytest.raises(AR.ValidationError, match="Start date must be YYYY-MM-DD"):
        _request(p, start_date="02/03/2026")
    with pytest.raises(AR.ValidationError, match="End date is not a real date"):
        _request(p, end_date="2026-02-30")
    with pytest.raises(AR.ValidationError, match="Submitted date must be"):
        _request(p, submitted_date="yesterday")
    with pytest.raises(AR.ValidationError, match="End date cannot be before start date"):
        _request(p, start_date="2026-03-06", end_date="2026-03-02")


def test_blank_dates_default_to_today():
    r = _request(_pupil(), start_date="", end_date=None)
    assert r.start_date == TODAY and r.end_date == TODAY


def test_school_days_rules():
    p = _pupil()
    with pytest.raises(AR.ValidationError, match="whole number"):
        _request(p, school_days="two")
    with pytest.raises(AR.ValidationError, match="cannot be negative"):
        _request(p, school_days=-1)
    with pytest.raises(AR.ValidationError, match="unreasonable"):
        _request(p, school_days=61)
    assert _request(p, school_days=60).school_days == 60


def test_category_status_authorisation_lists():
    p = _pupil()
    with pytest.raises(AR.ValidationError, match="Category must be one of"):
        _request(p, category="Shopping")
    with pytest.raises(AR.ValidationError, match="Status must be one of"):
        _request(p, status="Maybe")
    with pytest.raises(AR.ValidationError, match="Authorisation must be one of"):
        _request(p, authorisation="Perhaps")
    assert _request(p, category="Bereavement").category == "Bereavement"


def test_decision_consistency_rules():
    p = _pupil()
    with pytest.raises(AR.ValidationError, match="Approved requests cannot be marked Unauthorised"):
        _request(p, status="Approved", authorisation="Unauthorised", decided_by="Head")
    with pytest.raises(AR.ValidationError, match="Declined requests cannot be marked Authorised"):
        _request(p, status="Declined", authorisation="Authorised", decided_by="Head")
    with pytest.raises(AR.ValidationError, match="Decided-by is required when status is Approved"):
        _request(p, status="Approved", authorisation="Authorised")


def test_decided_status_defaults_decided_date_to_today():
    r = _request(_pupil(), status="Declined", authorisation="Unauthorised",
                 decided_by="Head")
    assert r.decided_date == TODAY
    assert r.decided_by == "Head"


# ── list_requests ────────────────────────────────────────────────────

def test_list_empty_database():
    P.init_db()  # the pupils table always exists in a real install
    assert AR.list_requests() == []


def test_list_sorted_by_start_date_desc():
    p = _pupil()
    a = _request(p, start_date="2026-01-05", end_date="2026-01-06")
    b = _request(p, start_date="2026-05-04", end_date="2026-05-05")
    c = _request(p, start_date="2026-03-02", end_date="2026-03-03")
    assert [r.request_id for r in AR.list_requests()] == [b.request_id, c.request_id,
                                                          a.request_id]


def test_list_filters():
    p1 = _pupil("Ada", "A", "3")
    p2 = _pupil("Ben", "B", "5")
    a = _request(p1, category="Bereavement")
    b = _request(p2, status="Approved", authorisation="Authorised", decided_by="Head",
                 start_date="2026-06-01", end_date="2026-06-05")
    ids = lambda rows: [r.request_id for r in rows]  # noqa: E731
    assert ids(AR.list_requests(pupil_id=p1.pupil_id)) == [a.request_id]
    assert ids(AR.list_requests(status="Approved")) == [b.request_id]
    assert ids(AR.list_requests(pending_only=True)) == [a.request_id]
    assert ids(AR.list_requests(category="Bereavement")) == [a.request_id]
    assert ids(AR.list_requests(authorisation="Authorised")) == [b.request_id]
    assert ids(AR.list_requests(year_group="5")) == [b.request_id]
    # date window overlaps: end >= from and start <= to
    assert ids(AR.list_requests(from_date="2026-03-06")) == [b.request_id, a.request_id]
    assert ids(AR.list_requests(from_date="2026-03-07")) == [b.request_id]
    assert ids(AR.list_requests(to_date="2026-05-31")) == [a.request_id]


def test_list_filter_validation():
    with pytest.raises(AR.ValidationError, match="Status filter"):
        AR.list_requests(status="Nope")
    with pytest.raises(AR.ValidationError, match="Category filter"):
        AR.list_requests(category="Nope")
    with pytest.raises(AR.ValidationError, match="Authorisation filter"):
        AR.list_requests(authorisation="Nope")
    with pytest.raises(AR.ValidationError, match="From date"):
        AR.list_requests(from_date="1/1/2026")
    with pytest.raises(AR.ValidationError, match="To date"):
        AR.list_requests(to_date="soon")


# ── update / decide / cancel / delete ───────────────────────────────

def test_update_changes_only_given_fields():
    r = _request(_pupil(), destination="Spain")
    u = AR.update(r.request_id, {"reason": "Changed plans", "end_date": "2026-03-04"})
    assert u.reason == "Changed plans"
    assert u.end_date == "2026-03-04"
    assert u.destination == "Spain"
    assert u.school_days == 5  # stored figure carried over, not recomputed


def test_update_missing_and_invalid_refused():
    P.init_db()
    with pytest.raises(AR.ValidationError, match="No absence request #42"):
        AR.update(42, {"reason": "x"})
    r = _request(_pupil())
    with pytest.raises(AR.ValidationError, match="Status must be one of"):
        AR.update(r.request_id, {"status": "Bogus"})
    assert AR.get(r.request_id).status == "Pending"


def test_decide_approve_defaults():
    r = _request(_pupil())
    d = AR.decide(r.request_id, approve=True, decided_by=" Head ",
                  decision_notes="Exceptional", decided_date="2026-02-20")
    assert d.status == "Approved"
    assert d.authorisation == "Authorised"
    assert d.decided_by == "Head"
    assert d.decided_date == "2026-02-20"
    assert d.decision_notes == "Exceptional"


def test_decide_decline_defaults_unauthorised_today():
    r = _request(_pupil())
    d = AR.decide(r.request_id, approve=False, decided_by="Head")
    assert d.status == "Declined"
    assert d.authorisation == "Unauthorised"
    assert d.decided_date == TODAY


def test_decide_requires_decider_and_consistent_authorisation():
    r = _request(_pupil())
    with pytest.raises(AR.ValidationError, match="Decided-by is required"):
        AR.decide(r.request_id, approve=True, decided_by="  ")
    with pytest.raises(AR.ValidationError, match="Approved requests cannot"):
        AR.decide(r.request_id, approve=True, decided_by="Head",
                  authorisation="Unauthorised")


def test_back_to_pending_clears_decision():
    r = _request(_pupil())
    AR.decide(r.request_id, approve=True, decided_by="Head")
    back = AR.update(r.request_id, {"status": "Pending", "authorisation": "Not yet decided"})
    assert back.status == "Pending"
    assert back.decided_by is None and back.decided_date is None


def test_cancel_keeps_authorisation_and_notes():
    r = _request(_pupil())
    AR.decide(r.request_id, approve=True, decided_by="Head")
    c = AR.cancel(r.request_id, decision_notes="Trip called off")
    assert c.status == "Cancelled"
    assert c.decision_notes == "Trip called off"
    assert c.authorisation == "Authorised"
    assert c.decided_by == "Head"


def test_delete():
    r = _request(_pupil())
    assert AR.delete(r.request_id) is True
    assert AR.get(r.request_id) is None
    assert AR.delete(r.request_id) is False


# ── cohort_summary ───────────────────────────────────────────────────

def test_cohort_summary_empty():
    P.init_db()
    s = AR.cohort_summary()
    assert s["total"] == 0 and s["pupils"] == 0
    assert s["by_category"] == {} and s["total_school_days"] == 0


def test_cohort_summary_counts_and_days():
    p1, p2 = _pupil("Ada", "A"), _pupil("Ben", "B")
    _request(p1)                                                  # 5 days pending
    _request(p1, category="Bereavement", status="Approved", authorisation="Authorised",
             decided_by="Head", school_days=2)
    _request(p2, status="Declined", authorisation="Unauthorised", decided_by="Head",
             school_days=3)
    c = _request(p2, school_days=4)
    AR.cancel(c.request_id)
    s = AR.cohort_summary()
    assert s["total"] == 4
    assert (s["pending"], s["approved"], s["declined"], s["cancelled"]) == (1, 1, 1, 1)
    assert s["pupils"] == 2
    assert s["by_category"] == {"Family holiday": 3, "Bereavement": 1}
    assert s["by_auth"] == {"Not yet decided": 2, "Authorised": 1, "Unauthorised": 1}
    assert s["total_school_days"] == 5 + 2 + 3 + 4
    assert s["approved_school_days"] == 2


def test_cohort_summary_date_window():
    p = _pupil()
    _request(p, start_date="2026-01-05", end_date="2026-01-09")
    _request(p, start_date="2026-06-01", end_date="2026-06-02")
    s = AR.cohort_summary(from_date="2026-05-01", to_date="2026-07-01")
    assert s["total"] == 1 and s["total_school_days"] == 2
