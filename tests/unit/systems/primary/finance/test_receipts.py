"""Receipts (systems.primary.domain.finance.receipts.receipts).

Receipt money is stored in pounds (REAL, 2 dp); the dinner money import
converts the ledger's pence to pounds.
"""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.finance.dinner_money import dinner_money as DM
from education_system.systems.primary.domain.finance.receipts import receipts as R
from education_system.systems.primary.domain.finance.trips import trips as T
from education_system.systems.primary.domain.learners.pupils import pupils as P

TODAY = dt.date.today()
DAY = "2030-03-15"

_n = 0


def _pupil(**extra):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": "2", "date_of_birth": "2022-01-01", **extra})


def _line(amount="5.00", **extra):
    return {"description": "Item", "amount": amount, **extra}


def _receipt(lines=None, **header):
    h = {"issued_date": DAY, "payer_name": "Mrs Parent", **header}
    return R.create_receipt(h, lines if lines is not None else [_line()])


# ── create / read ────────────────────────────────────────────────────

def test_create_receipt_header_lines_and_total():
    p = _pupil()
    r = R.create_receipt(
        {"issued_date": DAY, "payer_name": "  Mrs Parent ", "student_id": p.pupil_id,
         "method": "Cash", "received_by": " office ", "reference": "", "notes": " n "},
        [_line("2.50", kind="Lunch", description=" Lunch week "),
         _line("10", kind="trip", source_id="7", notes="")])
    assert r == R.get_receipt(r.receipt_id)
    assert (r.receipt_number, r.issued_date, r.payer_name) == ("R-2030-00001", DAY, "Mrs Parent")
    assert (r.student_id, r.method, r.status, r.total_amount) == (p.pupil_id, "Cash", "Draft", 12.5)
    assert (r.received_by, r.reference, r.notes, r.voided_at) == ("office", None, "n", None)
    lines = R.list_lines(r.receipt_id)
    assert [(ln.description, ln.amount, ln.kind, ln.source_id) for ln in lines] == [
        ("Lunch week", 2.5, "lunch", None), ("Item", 10.0, "trip", 7)]


def test_defaults_today_card_draft_general():
    r = R.create_receipt({"payer_name": "Dad"}, [{"description": "x", "amount": 1}])
    assert (r.issued_date, r.method, r.status) == (TODAY.isoformat(), "Card", "Draft")
    assert R.list_lines(r.receipt_id)[0].kind == "general"
    assert not r.is_issued and not r.is_voided


def test_numbers_run_per_year_and_never_change():
    a = _receipt()
    b = _receipt()
    c = _receipt(issued_date="2031-01-02")
    assert [a.receipt_number, b.receipt_number, c.receipt_number] == [
        "R-2030-00001", "R-2030-00002", "R-2031-00001"]
    R.void_receipt(a.receipt_id, "mistake")
    assert R.get_receipt(a.receipt_id).receipt_number == "R-2030-00001"
    assert _receipt().receipt_number == "R-2030-00003"


def test_get_missing_and_by_number():
    r = _receipt()
    assert R.get_receipt(999) is None
    assert R.get_by_number(" r-2030-00001 ").receipt_id == r.receipt_id
    assert R.get_by_number("R-2030-99999") is None
    assert R.list_lines(999) == []


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("header, match", [
    ({"payer_name": ""}, "Payer name is required"),
    ({"issued_date": "15/03/2030"}, "Issued date must be YYYY-MM-DD"),
    ({"student_id": "P0000000"}, "No student with id P0000000"),
    ({"method": "Bitcoin"}, "Method must be one of"),
    ({"status": "Paid"}, "Status must be one of"),
])
def test_header_refusals(header, match):
    with pytest.raises(R.ValidationError, match=match):
        _receipt(**header)
    assert R.list_receipts() == []


@pytest.mark.parametrize("line, match", [
    ({"description": "", "amount": "1"}, "Description is required"),
    ({"description": "x", "amount": ""}, "Amount is required"),
    ({"description": "x", "amount": "0"}, "Amount cannot be zero"),
    ({"description": "x", "amount": "-1"}, "Amount cannot be negative"),
    ({"description": "x", "amount": "1.005"}, "at most 2 decimal places"),
    ({"description": "x", "amount": "lots"}, "Amount must be a number"),
    ({"description": "x", "amount": "1", "kind": "toys"}, "Line kind must be one of"),
    ({"description": "x", "amount": "1", "source_id": "abc"}, "source_id must be a whole number"),
])
def test_line_refusals(line, match):
    with pytest.raises(R.ValidationError, match=match):
        _receipt(lines=[line])
    assert R.list_receipts() == []


def test_receipt_needs_a_line():
    with pytest.raises(R.ValidationError, match="at least one line item"):
        _receipt(lines=[])


# ── listing / search ─────────────────────────────────────────────────

def test_list_receipts_filters_and_order():
    p = _pupil()
    a = _receipt(issued_date="2030-01-01", method="Cash", student_id=p.pupil_id)
    b = _receipt(issued_date="2030-03-01")
    c = _receipt(issued_date="2030-02-01")
    R.issue(b.receipt_id)
    R.void_receipt(c.receipt_id, "dup")
    ids = lambda rs: [r.receipt_id for r in rs]  # noqa: E731
    assert ids(R.list_receipts()) == [b.receipt_id, c.receipt_id, a.receipt_id]
    assert ids(R.list_receipts(student_id=p.pupil_id)) == [a.receipt_id]
    assert ids(R.receipts_for_student(p.pupil_id)) == [a.receipt_id]
    assert ids(R.list_receipts(status="Draft")) == [a.receipt_id]
    assert ids(R.list_receipts(method="Cash")) == [a.receipt_id]
    assert ids(R.list_receipts(date_from="2030-02-01")) == [b.receipt_id, c.receipt_id]
    assert ids(R.list_receipts(date_to="2030-02-01")) == [c.receipt_id, a.receipt_id]
    assert ids(R.list_receipts(issued_only=True)) == [b.receipt_id]
    assert ids(R.list_receipts(voided_only=True)) == [c.receipt_id]


def test_list_receipts_refuses_bad_filters_and_empty_db():
    assert R.list_receipts() == []
    with pytest.raises(R.ValidationError, match="Status"):
        R.list_receipts(status="Paid")
    with pytest.raises(R.ValidationError, match="Method"):
        R.list_receipts(method="Gold")
    with pytest.raises(R.ValidationError, match="date_from must be YYYY-MM-DD"):
        R.list_receipts(date_from="2030")


def test_search_receipts():
    a = _receipt(payer_name="Ann Smith", reference="BANK-77")
    b = _receipt(payer_name="Bob Jones")
    assert [r.receipt_id for r in R.search_receipts("smith")] == [a.receipt_id]
    assert [r.receipt_id for r in R.search_receipts("BANK-7")] == [a.receipt_id]
    assert [r.receipt_id for r in R.search_receipts("R-2030-00002")] == [b.receipt_id]
    assert len(R.search_receipts("  ")) == 2
    assert R.search_receipts("nobody") == []


def test_view_receipt():
    p = _pupil()
    r = _receipt(student_id=p.pupil_id, lines=[_line("1"), _line("2")])
    v = R.view_receipt(r.receipt_id)
    assert (v.receipt, v.student_name, len(v.lines)) == (r, p.full_name, 2)
    assert R.view_receipt(_receipt().receipt_id).student_name is None
    assert R.view_receipt(999) is None


# ── update ───────────────────────────────────────────────────────────

def test_update_draft_header_keeps_lines_and_total():
    r = _receipt(lines=[_line("3"), _line("4")])
    u = R.update_receipt(r.receipt_id, {"payer_name": "Mr Carer", "method": "Cheque"})
    assert (u.payer_name, u.method, u.total_amount) == ("Mr Carer", "Cheque", 7.0)
    assert len(R.list_lines(r.receipt_id)) == 2


def test_update_draft_replaces_lines_and_recomputes_total():
    r = _receipt()
    u = R.update_receipt(r.receipt_id, {}, [_line("1.25"), _line("2.50"), _line("0.25")])
    assert u.total_amount == 4.0
    assert [ln.amount for ln in R.list_lines(r.receipt_id)] == [1.25, 2.5, 0.25]
    with pytest.raises(R.ValidationError, match="at least one line"):
        R.update_receipt(r.receipt_id, {}, [])
    with pytest.raises(R.ValidationError, match="Payer name is required"):
        R.update_receipt(r.receipt_id, {"payer_name": ""})
    with pytest.raises(R.ValidationError, match="No receipt #999"):
        R.update_receipt(999, {})


def test_issued_receipt_only_notes_reference_received_by_change():
    r = _receipt(payer_name="Ann")
    R.issue(r.receipt_id)
    u = R.update_receipt(r.receipt_id, {"notes": "posted", "reference": "X1",
                                        "received_by": "bursar", "payer_name": "Ann"})
    assert (u.notes, u.reference, u.received_by, u.payer_name) == ("posted", "X1", "bursar", "Ann")
    with pytest.raises(R.ValidationError, match="Cannot change 'payer_name' on an Issued receipt"):
        R.update_receipt(r.receipt_id, {"payer_name": "Bob"})
    R.update_receipt(r.receipt_id, {}, [_line("99")])            # lines ignored once issued
    assert R.get_receipt(r.receipt_id).total_amount == 5.0


def test_voided_receipt_cannot_be_edited_or_issued():
    r = _receipt()
    R.void_receipt(r.receipt_id, "wrong payer")
    with pytest.raises(R.ValidationError, match="Cannot edit a voided receipt"):
        R.update_receipt(r.receipt_id, {"notes": "x"})
    with pytest.raises(R.ValidationError, match="Cannot issue a voided receipt"):
        R.issue(r.receipt_id)


# ── issue / void / delete ────────────────────────────────────────────

def test_issue_is_idempotent():
    r = _receipt()
    a = R.issue(r.receipt_id)
    assert a.status == "Issued" and a.is_issued
    assert R.issue(r.receipt_id).status == "Issued"
    with pytest.raises(R.ValidationError, match="No receipt #999"):
        R.issue(999)


def test_void_needs_reason_and_keeps_first_reason():
    r = _receipt()
    with pytest.raises(R.ValidationError, match="reason is required"):
        R.void_receipt(r.receipt_id, "  ")
    v = R.void_receipt(r.receipt_id, " cheque bounced ")
    assert (v.status, v.void_reason, v.is_voided) == ("Voided", "cheque bounced", True)
    assert v.voided_at
    assert R.void_receipt(r.receipt_id, "again").void_reason == "cheque bounced"
    with pytest.raises(R.ValidationError, match="No receipt #999"):
        R.void_receipt(999, "x")


def test_only_drafts_can_be_deleted():
    d = _receipt()
    i = _receipt()
    v = _receipt()
    R.issue(i.receipt_id)
    R.void_receipt(v.receipt_id, "x")
    assert R.delete_receipt(d.receipt_id) is True
    assert R.get_receipt(d.receipt_id) is None and R.list_lines(d.receipt_id) == []
    for rid, status in ((i.receipt_id, "Issued"), (v.receipt_id, "Voided")):
        with pytest.raises(R.ValidationError, match=f"this one is {status}"):
            R.delete_receipt(rid)
    assert R.delete_receipt(999) is False


def test_deleting_pupil_keeps_receipt_but_clears_link():
    p = _pupil()
    r = _receipt(student_id=p.pupil_id)
    R.issue(r.receipt_id)
    assert P.delete_pupil(p.pupil_id)
    assert R.get_receipt(r.receipt_id).student_id is None


# ── imports from dinner money and trips ──────────────────────────────

def test_receipt_from_dinner_money_topup_converts_pence():
    p = _pupil()
    e = DM.credit(p.pupil_id, amount_pence=1250, entry_date=DAY, recorded_by="office")
    r = R.receipt_from_dinner_money_topup(e.entry_id)
    assert (r.status, r.issued_date, r.payer_name, r.student_id) == ("Issued", DAY, p.full_name, p.pupil_id)
    assert (r.total_amount, r.reference, r.received_by) == (12.5, f"DM-{e.entry_id}", "office")
    [line] = R.list_lines(r.receipt_id)
    assert (line.amount, line.kind, line.source_id, line.description) == (12.5, "lunch", e.entry_id, "Top-up")
    draft = R.receipt_from_dinner_money_topup(e.entry_id, received_by="head", issued=False)
    assert (draft.status, draft.received_by) == ("Draft", "head")


def test_dinner_money_charge_cannot_be_receipted():
    p = _pupil()
    charge = DM.charge_meal(p.pupil_id, entry_date=DAY, amount_pence=240)
    with pytest.raises(R.ValidationError, match="Only dinner money top-ups"):
        R.receipt_from_dinner_money_topup(charge.entry_id)
    with pytest.raises(R.ValidationError, match="No dinner money entry #999"):
        R.receipt_from_dinner_money_topup(999)


def _trip_payment(status="Cleared", method="Cash"):
    p = _pupil()
    T.create_trip({"name": "Earlier trip", "start_date": "2030-05-01"})
    trip = T.create_trip({"name": "Farm", "start_date": "2030-06-01", "cost_per_place": "15"})
    b = T.create_booking(trip.trip_id, {"student_id": p.pupil_id})
    for _ in range(3):                    # payment ids run ahead of trip ids
        T.add_payment(b.booking_id, {"amount": "1", "paid_on": "2030-04-01"})
    pay = T.add_payment(b.booking_id, {"amount": "8.40", "paid_on": "2030-04-02",
                                       "method": method, "status": status,
                                       "reference": "TP9", "recorded_by": "clerk"})
    return p, trip, pay


def test_receipt_from_trip_payment_copies_payment():
    p, trip, pay = _trip_payment(method="Pupil Premium")   # not a receipt method
    r = R.receipt_from_trip_payment(pay.payment_id)
    assert (r.status, r.issued_date, r.payer_name, r.student_id) == ("Issued", "2030-04-02", p.full_name, p.pupil_id)
    assert (r.total_amount, r.method, r.reference, r.received_by) == (8.4, "Card", "TP9", "clerk")
    [line] = R.list_lines(r.receipt_id)
    assert (line.amount, line.kind, line.description) == (8.4, "trip", "Farm — trip payment")


def test_trip_payment_line_links_back_to_the_payment():
    """The line's source_id must identify the payment (as the dinner money
    import does with its ledger entry), so a re-import can be spotted."""
    _p, trip, pay = _trip_payment()
    assert pay.payment_id != trip.trip_id
    r = R.receipt_from_trip_payment(pay.payment_id)
    [line] = R.list_lines(r.receipt_id)
    assert line.source_id == pay.payment_id


def test_trip_payment_must_exist_and_be_cleared():
    _p, _trip, pay = _trip_payment(status="Pending")
    with pytest.raises(R.ValidationError, match="Only cleared trip payments"):
        R.receipt_from_trip_payment(pay.payment_id)
    with pytest.raises(R.ValidationError, match="No trip payment #999"):
        R.receipt_from_trip_payment(999)


# ── summary ──────────────────────────────────────────────────────────

def test_summary_empty_database():
    s = R.summary()
    assert (s.total_receipts, s.drafts, s.issued, s.voided) == (0, 0, 0, 0)
    assert (s.total_issued_amount, s.daily_today, s.top_payers) == (0.0, 0.0, [])
    assert s.by_method == {m: 0.0 for m in R.PAYMENT_METHODS}
    assert s.by_kind == {k: 0.0 for k in R.LINE_KINDS}


def test_summary_counts_and_totals():
    today = TODAY.isoformat()
    a = _receipt(issued_date=today, payer_name="Ann", method="Cash",
                 lines=[_line("3", kind="lunch"), _line("2", kind="club")])
    b = _receipt(issued_date="2001-01-01", payer_name="Bob",
                 lines=[_line("10", kind="trip")])
    c = _receipt(issued_date=today, payer_name="Ann", lines=[_line("1.50", kind="lunch")])
    v = _receipt(issued_date=today, payer_name="Cat", lines=[_line("7")])
    _receipt(issued_date=today, payer_name="Dee", lines=[_line("100")])   # draft
    for r in (a, b, c, v):
        R.issue(r.receipt_id)
    R.void_receipt(v.receipt_id, "error")
    s = R.summary()
    assert (s.total_receipts, s.drafts, s.issued, s.voided) == (5, 1, 3, 1)
    assert (s.total_issued_amount, s.total_voided_amount) == (16.5, 7.0)
    assert s.by_method["Cash"] == 5.0 and s.by_method["Card"] == 11.5
    assert (s.by_kind["lunch"], s.by_kind["club"], s.by_kind["trip"], s.by_kind["general"]) == (4.5, 2.0, 10.0, 0.0)
    assert (s.daily_today, s.daily_this_week, s.daily_this_month) == (6.5, 6.5, 6.5)
    assert s.top_payers == [("Bob", 10.0), ("Ann", 6.5)]
