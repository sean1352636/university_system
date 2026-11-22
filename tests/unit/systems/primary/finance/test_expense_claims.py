"""Expense claims (systems.primary.domain.finance.expense_claims.expense_claims).

Amounts here are pounds (floats rounded to 2 dp), not pence.
Claims move Draft -> Submitted -> (Under Review) -> Approved -> Paid,
or Rejected / Cancelled.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.finance.expense_claims import expense_claims as EC

TODAY = dt.date.today().isoformat()
_n = 0


def _claim(**extra):
    global _n
    _n += 1
    data = {"claim_ref": f"EC-{_n:03d}", "claimant_id": "T001", "title": f"Claim {_n}"}
    data.update(extra)
    return EC.create_claim(data)


def _line(claim_id, **extra):
    data = {"incurred_on": "2026-09-10", "quantity": 1, "unit_amount": 10}
    data.update(extra)
    return EC.add_line(claim_id, data)


def _submitted(**extra):
    c = _claim(**extra)
    _line(c.claim_id)
    return EC.submit(c.claim_id)


# ── create / read ────────────────────────────────────────────────────

def test_create_claim_applies_defaults():
    c = _claim(claimant_name="  Ann Teacher ", notes="  ")
    assert (c.claimant_type, c.category, c.payment_method, c.status) == (
        "Staff", "Travel", "BACS", "Draft")
    assert (c.line_count, c.total_amount, c.receipts_attached) == (0, 0.0, False)
    assert c.claimant_name == "Ann Teacher" and c.notes is None
    assert c.is_open and not c.is_settled
    assert EC.get_claim(c.claim_id) == c
    assert EC.get_claim_by_ref(c.claim_ref) == c


def test_get_missing_is_none():
    assert EC.get_claim(999) is None
    assert EC.get_claim_by_ref("nope") is None
    assert EC.get_line(999) is None
    assert EC.lines_for_claim(999) == []


# ── claim validation ─────────────────────────────────────────────────

def test_claim_ref_required_and_unique():
    with pytest.raises(EC.ValidationError, match="Claim reference is required"):
        EC.create_claim({"claimant_id": "T1", "title": "x"})
    _claim(claim_ref="DUP")
    with pytest.raises(EC.ValidationError, match="already exists"):
        _claim(claim_ref="DUP")


def test_claimant_id_and_title_required():
    with pytest.raises(EC.ValidationError, match="Claimant id is required"):
        EC.create_claim({"claim_ref": "A", "title": "x"})
    with pytest.raises(EC.ValidationError, match="Title is required"):
        EC.create_claim({"claim_ref": "A", "claimant_id": "T1", "title": "  "})


@pytest.mark.parametrize("field,value,msg", [
    ("claimant_type", "Pupil", "Claimant type must be one of"),
    ("category", "Holiday", "Category must be one of"),
    ("payment_method", "Bitcoin", "Payment method must be one of"),
    ("status", "Lost", "Status must be one of"),
])
def test_allowed_value_lists(field, value, msg):
    with pytest.raises(EC.ValidationError, match=msg):
        _claim(**{field: value})


def test_dates_must_be_iso_and_in_order():
    with pytest.raises(EC.ValidationError, match="Incurred from must be YYYY-MM-DD"):
        _claim(incurred_from="10/09/2026")
    with pytest.raises(EC.ValidationError, match="Paid on must be YYYY-MM-DD"):
        _claim(paid_on="2026-13-01")
    with pytest.raises(EC.ValidationError, match="cannot be before"):
        _claim(incurred_from="2026-09-10", incurred_to="2026-09-09")
    ok = _claim(incurred_from="2026-09-10", incurred_to="2026-09-10")
    assert ok.incurred_to == "2026-09-10"


def test_total_and_line_count_must_be_non_negative_numbers():
    with pytest.raises(EC.ValidationError, match="Total amount must be a number"):
        _claim(total_amount="lots")
    with pytest.raises(EC.ValidationError, match="Total amount must be >= 0"):
        _claim(total_amount=-1)
    with pytest.raises(EC.ValidationError, match="Line count must be an integer"):
        _claim(line_count="x")
    with pytest.raises(EC.ValidationError, match="Line count must be >= 0"):
        _claim(line_count=-1)


# ── update / delete ──────────────────────────────────────────────────

def test_update_claim_keeps_own_ref_and_changes_fields():
    c = _claim(claim_ref="KEEP")
    u = EC.update_claim(c.claim_id, {"claim_ref": "KEEP", "claimant_id": "T001",
                                     "title": "New title", "category": "Mileage"})
    assert (u.claim_ref, u.title, u.category) == ("KEEP", "New title", "Mileage")


def test_update_claim_refuses_missing_and_taken_ref():
    a = _claim(claim_ref="A1")
    _claim(claim_ref="B1")
    with pytest.raises(EC.ValidationError, match="No claim with id 999"):
        EC.update_claim(999, {"claim_ref": "Z", "claimant_id": "T", "title": "t"})
    with pytest.raises(EC.ValidationError, match="already exists"):
        EC.update_claim(a.claim_id, {"claim_ref": "B1", "claimant_id": "T", "title": "t"})


def test_delete_claim_cascades_lines():
    c = _claim()
    ln = _line(c.claim_id)
    assert EC.delete_claim(c.claim_id) is True
    assert EC.get_claim(c.claim_id) is None
    assert EC.get_line(ln.line_id) is None
    assert EC.delete_claim(c.claim_id) is False


# ── lines and totals ─────────────────────────────────────────────────

def test_line_net_is_quantity_times_unit_plus_vat():
    c = _claim()
    ln = _line(c.claim_id, quantity=3, unit_amount=4.25, vat_amount=2.55,
               supplier=" Rymans ")
    assert (ln.net_amount, ln.gross_amount) == (12.75, 15.30)
    assert ln.supplier == "Rymans" and ln.category == "Travel"


def test_mileage_line_uses_miles_times_rate():
    c = _claim()
    ln = _line(c.claim_id, category="Mileage", mileage_miles=42, mileage_rate=0.45,
               unit_amount=99)
    assert (ln.net_amount, ln.gross_amount) == (18.90, 18.90)


def test_claim_totals_follow_line_add_update_delete():
    c = _claim()
    a = _line(c.claim_id, unit_amount=10)
    b = _line(c.claim_id, quantity=2, unit_amount=7.5, vat_amount=3)
    got = EC.get_claim(c.claim_id)
    assert (got.line_count, got.total_amount) == (2, 28.0)     # 10 + (15 + 3)
    EC.update_line(a.line_id, {"incurred_on": "2026-09-11", "unit_amount": 20})
    assert EC.get_claim(c.claim_id).total_amount == 38.0
    assert EC.delete_line(b.line_id) is True
    got = EC.get_claim(c.claim_id)
    assert (got.line_count, got.total_amount) == (1, 20.0)
    assert EC.delete_line(b.line_id) is False


def test_lines_listed_by_date():
    c = _claim()
    late = _line(c.claim_id, incurred_on="2026-09-20")
    early = _line(c.claim_id, incurred_on="2026-09-01")
    assert [ln.line_id for ln in EC.lines_for_claim(c.claim_id)] == [early.line_id, late.line_id]


def test_line_validation():
    c = _claim()
    with pytest.raises(EC.ValidationError, match="No claim with id 999"):
        _line(999)
    with pytest.raises(EC.ValidationError, match="Incurred on is required"):
        EC.add_line(c.claim_id, {"unit_amount": 1})
    with pytest.raises(EC.ValidationError, match="Incurred on must be YYYY-MM-DD"):
        _line(c.claim_id, incurred_on="tomorrow")
    with pytest.raises(EC.ValidationError, match="Category must be one of"):
        _line(c.claim_id, category="Holiday")
    with pytest.raises(EC.ValidationError, match="Unit amount must be >= 0"):
        _line(c.claim_id, unit_amount=-5)
    with pytest.raises(EC.ValidationError, match="Quantity must be a number"):
        _line(c.claim_id, quantity="two")
    with pytest.raises(EC.ValidationError, match="No line with id 999"):
        EC.update_line(999, {"incurred_on": "2026-09-01"})
    assert EC.get_claim(c.claim_id).line_count == 0


# ── workflow ─────────────────────────────────────────────────────────

def test_submit_needs_lines_and_stamps_today():
    c = _claim()
    with pytest.raises(EC.ValidationError, match="no lines"):
        EC.submit(c.claim_id)
    _line(c.claim_id)
    s = EC.submit(c.claim_id)
    assert (s.status, s.submitted_on) == ("Submitted", TODAY)


def test_full_happy_path_to_paid():
    s = _submitted()
    r = EC.begin_review(s.claim_id)
    assert r.status == "Under Review" and r.is_open
    a = EC.approve(s.claim_id, approved_by="head")
    assert (a.status, a.approved_on, a.approved_by) == ("Approved", TODAY, "head")
    assert not a.is_open and not a.is_settled
    p = EC.pay(s.claim_id, payment_reference="BACS-1", paid_on="2026-10-01")
    assert (p.status, p.paid_on, p.payment_reference) == ("Paid", "2026-10-01", "BACS-1")
    assert p.is_settled


def test_pay_defaults_to_today_and_needs_approval():
    s = _submitted()
    with pytest.raises(EC.ValidationError, match="Only Approved"):
        EC.pay(s.claim_id)
    EC.approve(s.claim_id)
    assert EC.pay(s.claim_id).paid_on == TODAY


def test_reject_records_reason():
    s = _submitted()
    r = EC.reject(s.claim_id, reason="No receipt")
    assert (r.status, r.rejected_on, r.rejection_reason) == ("Rejected", TODAY, "No receipt")
    assert r.is_settled


def test_cancel_and_set_status():
    c = _claim()
    assert EC.cancel(c.claim_id).status == "Cancelled"
    assert EC.set_status(c.claim_id, "Draft").status == "Draft"
    with pytest.raises(EC.ValidationError, match="Status must be one of"):
        EC.set_status(c.claim_id, "Gone")


def test_workflow_refuses_missing_claim():
    for fn in (EC.submit, EC.begin_review, EC.approve, EC.reject, EC.pay, EC.cancel):
        with pytest.raises(EC.ValidationError, match="No claim with id 404"):
            fn(404)
    with pytest.raises(EC.ValidationError, match="No claim with id 404"):
        EC.set_status(404, "Draft")


# Known bug: approve/reject do not check the current status.

def test_approve_refuses_a_draft_claim():
    c = _claim()
    _line(c.claim_id)
    with pytest.raises(EC.ValidationError):
        EC.approve(c.claim_id)
    assert EC.get_claim(c.claim_id).status == "Draft"


def test_approve_refuses_a_paid_claim():
    s = _submitted()
    EC.approve(s.claim_id, approved_by="head")
    EC.pay(s.claim_id, paid_on="2026-10-01")
    with pytest.raises(EC.ValidationError):
        EC.approve(s.claim_id, approved_by="someone else")
    assert EC.get_claim(s.claim_id).status == "Paid"


def test_reject_refuses_a_draft_claim():
    c = _claim()
    with pytest.raises(EC.ValidationError):
        EC.reject(c.claim_id, reason="x")
    assert EC.get_claim(c.claim_id).status == "Draft"


def test_reject_refuses_a_paid_claim():
    s = _submitted()
    EC.approve(s.claim_id)
    EC.pay(s.claim_id, paid_on="2026-10-01")
    with pytest.raises(EC.ValidationError):
        EC.reject(s.claim_id, reason="too late")
    assert EC.get_claim(s.claim_id).status == "Paid"


# ── listing ──────────────────────────────────────────────────────────

def test_list_claims_filters():
    d = _claim(title="Train to London", claimant_id="T1")
    s = _submitted(claimant_id="T2", category="Mileage", claimant_type="Governor")
    a = _submitted(payment_method="Cheque")
    EC.approve(a.claim_id)
    p = _submitted()
    EC.approve(p.claim_id)
    EC.pay(p.claim_id, paid_on="2026-10-01")
    ids = lambda rows: {c.claim_id for c in rows}  # noqa: E731
    assert ids(EC.list_claims()) == {d.claim_id, s.claim_id, a.claim_id, p.claim_id}
    assert ids(EC.list_claims(claimant_id="T1")) == {d.claim_id}
    assert ids(EC.list_claims(claimant_type="Governor")) == {s.claim_id}
    assert ids(EC.list_claims(status="Draft")) == {d.claim_id}
    assert ids(EC.list_claims(category="Mileage")) == {s.claim_id}
    assert ids(EC.list_claims(payment_method="Cheque")) == {a.claim_id}
    assert ids(EC.list_claims(open_only=True)) == {d.claim_id, s.claim_id}
    assert ids(EC.list_claims(awaiting_payment_only=True)) == {a.claim_id}
    assert ids(EC.list_claims(paid_only=True)) == {p.claim_id}
    assert ids(EC.list_claims(title_like="London")) == {d.claim_id}


def test_list_claims_date_window_and_bad_date():
    a = _claim(incurred_from="2026-09-01", incurred_to="2026-09-05")
    b = _claim(incurred_from="2026-10-01", incurred_to="2026-10-03")
    assert [c.claim_id for c in EC.list_claims(date_from="2026-09-15")] == [b.claim_id]
    assert [c.claim_id for c in EC.list_claims(date_to="2026-09-30")] == [a.claim_id]
    with pytest.raises(EC.ValidationError, match="From must be YYYY-MM-DD"):
        EC.list_claims(date_from="1 Sept")


def test_list_claims_newest_first():
    a, b = _claim(), _claim()
    assert [c.claim_id for c in EC.list_claims()] == [b.claim_id, a.claim_id]


# ── summary ──────────────────────────────────────────────────────────

def test_summary_empty():
    s = EC.summary()
    assert s.total_claims == 0 and s.total_value == 0.0 and s.by_status == {}


def test_summary_counts_and_values():
    d = _claim(claimant_id="T1")
    _line(d.claim_id, unit_amount=5)                 # Draft 5.00
    s = _submitted(claimant_id="T1")                 # Submitted 10.00
    a = _submitted(claimant_id="T2")
    _line(a.claim_id, unit_amount=2.5)
    EC.approve(a.claim_id)                           # Approved 12.50
    p = _submitted(claimant_id="T3", category="Mileage")
    EC.approve(p.claim_id)
    EC.pay(p.claim_id, paid_on="2026-10-01")         # Paid 10.00
    r = _submitted(claimant_id="T3")
    EC.reject(r.claim_id, reason="no")               # Rejected 10.00 (excluded)
    x = _submitted(claimant_id="T4", claimant_type="Volunteer")
    EC.cancel(x.claim_id)                            # Cancelled 10.00 (excluded)
    sm = EC.summary()
    assert sm.total_claims == 6
    assert (sm.drafts, sm.submitted, sm.under_review, sm.approved, sm.paid,
            sm.rejected, sm.cancelled) == (1, 1, 0, 1, 1, 1, 1)
    assert sm.total_value == 37.5                    # 5 + 10 + 12.5 + 10
    assert sm.awaiting_payment_value == 12.5
    assert sm.paid_value == 10.0
    assert sm.distinct_claimants == 4                # T1,T2,T3 Staff + T4 Volunteer
    assert sm.by_category == {"Travel": 5, "Mileage": 1}
    assert sm.by_claimant_type == {"Staff": 5, "Volunteer": 1}
    assert sm.by_status["Paid"] == 1 and sum(sm.by_status.values()) == 6
    assert sm.by_payment_method == {"BACS": 6}
    assert s.claim_id  # used
