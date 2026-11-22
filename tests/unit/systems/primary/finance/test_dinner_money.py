"""Dinner money ledger (systems.primary.domain.finance.dinner_money.dinner_money).

Amounts are stored in pence; credits/refunds are positive, charges negative.
"""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.finance.dinner_money import dinner_money as DM
from education_system.systems.primary.domain.learners.pupils import pupils as P

_n = 0


def _pupil(year="3"):
    global _n
    _n += 1
    return P.create_pupil({"first_name": f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2018-01-15"}).pupil_id


# ── recording and the sign rule ──────────────────────────────────────

def test_credit_in_pounds_is_stored_as_positive_pence():
    pid = _pupil()
    e = DM.credit(pid, amount_pounds="£10.50", entry_date="2026-09-01", recorded_by="office")
    assert (e.pupil_id, e.kind, e.amount_pence, e.entry_date) == (pid, "credit", 1050, "2026-09-01")
    assert e.description == "Top-up" and e.recorded_by == "office"
    assert e.amount_display == "£10.50"
    assert DM.get(e.entry_id) == e


def test_charge_meal_is_stored_negative_with_default_description():
    pid = _pupil()
    e = DM.charge_meal(pid, amount_pence=250, entry_date="2026-09-02")
    assert (e.kind, e.meal_type, e.amount_pence) == ("charge", "hot", -250)
    assert e.description == "Hot school meal"
    assert e.amount_display == "-£2.50"


def test_negative_credit_and_refund_are_flipped_positive():
    pid = _pupil()
    assert DM.credit(pid, amount_pence=-300).amount_pence == 300
    r = DM.record({"pupil_id": pid, "kind": "refund", "amount_pounds": -1.25})
    assert r.amount_pence == 125


def test_adjustment_keeps_the_callers_sign():
    pid = _pupil()
    assert DM.record({"pupil_id": pid, "kind": "adjustment", "amount_pence": -75}).amount_pence == -75
    assert DM.record({"pupil_id": pid, "kind": "adjustment", "amount_pence": 75}).amount_pence == 75


def test_zero_charge_allowed_for_free_meal_but_zero_credit_refused():
    pid = _pupil()
    fsm = DM.charge_meal(pid, meal_type="fsm", amount_pence=0)
    assert fsm.amount_pence == 0 and fsm.description == "Free school meal"
    with pytest.raises(DM.ValidationError, match="cannot be zero"):
        DM.credit(pid, amount_pence=0)
    with pytest.raises(DM.ValidationError, match="cannot be zero"):
        DM.record({"pupil_id": pid, "kind": "adjustment"})


def test_missing_entry_date_defaults_to_today():
    import datetime as dt
    pid = _pupil()
    e = DM.credit(pid, amount_pence=100)
    # SQLite date('now') is UTC; allow the boundary either side of midnight.
    today = dt.date.today()
    assert e.entry_date in {(today + dt.timedelta(days=d)).isoformat() for d in (-1, 0, 1)}


# ── validation ───────────────────────────────────────────────────────

def test_pupil_id_required():
    with pytest.raises(DM.ValidationError, match="Pupil ID is required"):
        DM.record({"kind": "credit", "amount_pence": 100})


def test_unknown_pupil_refused():
    DM.init_db()
    with pytest.raises(DM.ValidationError, match="No pupil with id P9999999"):
        DM.credit("P9999999", amount_pence=100)


def test_kind_required_and_must_be_known():
    pid = _pupil()
    with pytest.raises(DM.ValidationError, match="Kind is required"):
        DM.record({"pupil_id": pid, "amount_pence": 100})
    with pytest.raises(DM.ValidationError, match="Kind must be one of"):
        DM.record({"pupil_id": pid, "kind": "gift", "amount_pence": 100})


def test_kind_and_meal_type_are_case_insensitive():
    pid = _pupil()
    e = DM.record({"pupil_id": pid, "kind": "CHARGE", "meal_type": "Packed", "amount_pence": 0})
    assert (e.kind, e.meal_type) == ("charge", "packed")


def test_meal_type_must_be_known():
    pid = _pupil()
    with pytest.raises(DM.ValidationError, match="Meal type must be one of"):
        DM.charge_meal(pid, meal_type="banquet", amount_pence=100)


def test_entry_date_format():
    pid = _pupil()
    with pytest.raises(DM.ValidationError, match="YYYY-MM-DD"):
        DM.credit(pid, amount_pence=100, entry_date="01/09/2026")


def test_amount_must_be_numeric():
    pid = _pupil()
    with pytest.raises(DM.ValidationError, match="not a number"):
        DM.credit(pid, amount_pounds="ten")
    with pytest.raises(DM.ValidationError, match="must be an integer"):
        DM.record({"pupil_id": pid, "kind": "credit", "amount_pence": "abc"})


def test_amount_limited_to_1000_pounds_either_way():
    pid = _pupil()
    assert DM.credit(pid, amount_pence=100_000).amount_pence == 100_000
    with pytest.raises(DM.ValidationError, match="between"):
        DM.credit(pid, amount_pence=100_001)
    with pytest.raises(DM.ValidationError, match="between"):
        DM.record({"pupil_id": pid, "kind": "adjustment", "amount_pence": -100_001})


# ── get / update / delete ────────────────────────────────────────────

def test_get_missing_entry_is_none():
    assert DM.get(12345) is None


def test_update_changes_fields_and_reapplies_sign():
    pid = _pupil()
    e = DM.charge_meal(pid, amount_pence=250, entry_date="2026-09-02")
    u = DM.update(e.entry_id, {"amount_pounds": "3.10", "notes": "late"})
    assert (u.amount_pence, u.notes, u.entry_date) == (-310, "late", "2026-09-02")
    u2 = DM.update(e.entry_id, {"kind": "credit"})
    assert (u2.kind, u2.amount_pence) == ("credit", 310)


def test_update_refuses_missing_entry_and_unknown_pupil():
    pid = _pupil()
    e = DM.credit(pid, amount_pence=100)
    with pytest.raises(DM.ValidationError, match="No entry #999"):
        DM.update(999, {"notes": "x"})
    with pytest.raises(DM.ValidationError, match="No pupil"):
        DM.update(e.entry_id, {"pupil_id": "P0000000"})


def test_update_validates_like_record():
    pid = _pupil()
    e = DM.credit(pid, amount_pence=100)
    with pytest.raises(DM.ValidationError, match="Kind must be one of"):
        DM.update(e.entry_id, {"kind": "bonus"})
    assert DM.get(e.entry_id).kind == "credit"


def test_delete():
    pid = _pupil()
    e = DM.credit(pid, amount_pence=100)
    assert DM.delete(e.entry_id) is True
    assert DM.get(e.entry_id) is None
    assert DM.delete(e.entry_id) is False


def test_deleting_a_pupil_removes_their_ledger():
    pid = _pupil()
    e = DM.credit(pid, amount_pence=100)
    P.delete_pupil(pid)
    assert DM.get(e.entry_id) is None


# ── listing ──────────────────────────────────────────────────────────

def test_list_entries_newest_first_with_filters():
    a, b = _pupil(), _pupil()
    c1 = DM.credit(a, amount_pence=500, entry_date="2026-09-01")
    m1 = DM.charge_meal(a, amount_pence=250, entry_date="2026-09-02")
    m2 = DM.charge_meal(b, meal_type="fsm", amount_pence=0, entry_date="2026-09-03")
    m3 = DM.charge_meal(a, amount_pence=250, entry_date="2026-09-03")
    rows = DM.list_entries()
    assert [e.entry_id for e, _p in rows] == [m3.entry_id, m2.entry_id, m1.entry_id, c1.entry_id]
    assert rows[0][1].pupil_id == a
    assert [e.entry_id for e, _ in DM.list_entries(pupil_id=a)] == [m3.entry_id, m1.entry_id, c1.entry_id]
    assert [e.entry_id for e, _ in DM.list_entries(kind="credit")] == [c1.entry_id]
    assert [e.entry_id for e, _ in DM.list_entries(meal_type="fsm")] == [m2.entry_id]
    assert [e.entry_id for e, _ in DM.list_entries(from_date="2026-09-02", to_date="2026-09-02")] == [m1.entry_id]
    assert len(DM.list_entries(limit=2)) == 2


def test_list_entries_empty_and_bad_filters():
    assert DM.list_entries() == []
    with pytest.raises(DM.ValidationError, match="Kind filter"):
        DM.list_entries(kind="gift")
    with pytest.raises(DM.ValidationError, match="Meal-type filter"):
        DM.list_entries(meal_type="feast")
    with pytest.raises(DM.ValidationError, match="from_date"):
        DM.list_entries(from_date="2026/09/01")


# ── balances and statements ──────────────────────────────────────────

def test_pupil_balance_sums_the_ledger():
    pid = _pupil()
    assert DM.pupil_balance(pid) == 0
    DM.credit(pid, amount_pounds="5.00")
    DM.charge_meal(pid, amount_pence=230)
    DM.charge_meal(pid, amount_pence=230)
    DM.record({"pupil_id": pid, "kind": "adjustment", "amount_pence": -40})
    assert DM.pupil_balance(pid) == 500 - 230 - 230 - 40   # 0


def test_pupil_balance_and_statement_refuse_unknown_pupil():
    DM.init_db()
    with pytest.raises(DM.ValidationError, match="No pupil"):
        DM.pupil_balance("P1234567")
    with pytest.raises(DM.ValidationError, match="No pupil"):
        DM.pupil_statement("P1234567")


def test_statement_oldest_first_with_totals():
    pid = _pupil()
    m = DM.charge_meal(pid, amount_pence=250, entry_date="2026-09-03")
    c = DM.credit(pid, amount_pence=1000, entry_date="2026-09-01")
    f = DM.charge_meal(pid, meal_type="fsm", amount_pence=0, entry_date="2026-09-04")
    st = DM.pupil_statement(pid)
    assert [e.entry_id for e in st["entries"]] == [c.entry_id, m.entry_id, f.entry_id]
    assert st["total_credits_pence"] == 1000
    assert st["total_charges_pence"] == 250
    assert st["balance_pence"] == 750
    assert st["pupil_id"] == pid


def test_balances_most_owed_first_with_filters():
    a, b, c = _pupil("3"), _pupil("3"), _pupil("5")
    DM.charge_meal(a, amount_pence=500)
    DM.charge_meal(b, amount_pence=200)
    DM.credit(c, amount_pence=300)
    got = [(p.pupil_id, bal) for p, bal in DM.balances()]
    assert got == [(a, -500), (b, -200), (c, 300)]
    assert [p.pupil_id for p, _ in DM.balances(owing_only=True)] == [a, b]
    assert [p.pupil_id for p, _ in DM.balances(year_group="5")] == [c]
    assert [p.pupil_id for p, _ in DM.balances(limit=1)] == [a]


def test_balances_empty_and_bad_year():
    assert DM.balances() == []
    with pytest.raises(DM.ValidationError, match="Year filter"):
        DM.balances(year_group="7")


# ── summary ──────────────────────────────────────────────────────────

def test_summary_empty_database():
    s = DM.summary()
    assert s["entries"] == 0 and s["net_pence"] == 0
    assert s["by_meal_type"] == {m: 0 for m in DM.MEAL_TYPES}
    assert (s["pupils_with_balance"], s["pupils_owing"], s["pupils_in_credit"], s["total_owed_pence"]) == (0, 0, 0, 0)


def test_summary_totals():
    a, b, c = _pupil(), _pupil(), _pupil()
    DM.credit(a, amount_pence=1000, entry_date="2026-09-01")
    DM.charge_meal(a, amount_pence=250, entry_date="2026-09-02")
    DM.charge_meal(b, amount_pence=250, entry_date="2026-09-02")
    DM.charge_meal(b, amount_pence=250, entry_date="2026-09-03")
    DM.charge_meal(c, meal_type="uifsm", amount_pence=0, entry_date="2026-09-03")
    s = DM.summary()
    assert s["entries"] == 5
    assert s["total_credits_pence"] == 1000
    assert s["total_charges_pence"] == 750
    assert s["net_pence"] == 250
    assert s["by_meal_type"]["hot"] == 3 and s["by_meal_type"]["uifsm"] == 1
    assert s["by_meal_type"]["packed"] == 0
    # a +750, b -500, c 0
    assert (s["pupils_with_balance"], s["pupils_owing"], s["pupils_in_credit"]) == (3, 1, 1)
    assert s["total_owed_pence"] == 500


def test_summary_date_window():
    a = _pupil()
    DM.credit(a, amount_pence=1000, entry_date="2026-09-01")
    DM.charge_meal(a, amount_pence=250, entry_date="2026-09-02")
    DM.charge_meal(a, amount_pence=250, entry_date="2026-09-03")
    s = DM.summary(from_date="2026-09-02", to_date="2026-09-02")
    assert (s["entries"], s["total_credits_pence"], s["total_charges_pence"], s["net_pence"]) == (1, 0, 250, -250)
    with pytest.raises(DM.ValidationError, match="to_date"):
        DM.summary(to_date="tomorrow")


def test_format_pence():
    assert DM.format_pence(0) == "£0.00"
    assert DM.format_pence(1234) == "£12.34"
    assert DM.format_pence(-5) == "-£0.05"
