"""Dinner Money (modules.finance.domain.dinner_money)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.finance.domain import dinner_money as DM
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")
KID = Principal(username="kid", role="student")
LOGINS = [{"username": "ann", "display_name": "Ann Teacher", "email": "ann@school.org",
           "role": "teacher"}]
TODAY = dt.date.today()
DAY = TODAY.isoformat()


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(accounts, "staff_logins", lambda: LOGINS)
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(**extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": "2011-01-15", "gender": "Female", "year_group": 10,
        "form_group": "10A", "admission_date": "2021-09-01", **extra}, actor=ADMIN)


def _lunch(price="2.50"):
    return DM.set_price("Lunch", price, actor=ADMIN)


def test_prices_set_by_the_office_lunch_covered_by_fsm():
    with pytest.raises(DM.PermissionDenied):
        DM.set_price("Lunch", "2.50", actor=ANN)
    pr = _lunch()
    assert (pr.price_pence, pr.fsm_covered) == (250, 1)
    br = DM.set_price("Breakfast", "1.20", actor=ADMIN)
    assert br.fsm_covered == 0
    assert [x.meal_type for x in DM.list_prices()] == ["Lunch", "Breakfast"]
    with pytest.raises(DM.ValidationError):
        DM.set_price("Lunch", "2.505", actor=ADMIN)


def test_top_ups_meals_balance_void_and_overdraft():
    _lunch()
    p = _pupil()
    with pytest.raises(DM.ValidationError) as e:
        DM.top_up(p.pupil_id, "10", method="Bank transfer", actor=ADMIN)
    assert "needs its reference" in " ".join(e.value.problems)
    t = DM.top_up(p.admission_no, "5.00", method="Cash", actor=ADMIN)
    assert t.amount_pence == 500 and DM.balance(p.pupil_id) == 500
    for i in range(3):
        DM.record_meal(p.pupil_id, actor=ADMIN, day=(TODAY - dt.timedelta(days=i)).isoformat())
    assert DM.balance(p.pupil_id) == -250            # never refused a meal
    with pytest.raises(DM.ValidationError):
        DM.record_meal(p.pupil_id, actor=ADMIN, day=DAY)    # twice the same day
    meal_line = next(x for x in DM.transactions(pupil_id=p.pupil_id) if x.kind == DM.MEAL)
    DM.void(meal_line.txn_id, actor=ADMIN, reason="Wrong pupil")
    assert DM.balance(p.pupil_id) == 0
    assert DM.get_txn(meal_line.txn_id).voided == 1
    with pytest.raises(DM.ValidationError):
        DM.void(meal_line.txn_id, actor=ADMIN, reason="again")
    DM.adjust(p.pupil_id, "-1.00", actor=ADMIN, reason="Snack at the till")
    assert DM.balance(p.pupil_id) == -100
    with pytest.raises(DM.ValidationError):
        DM.adjust(p.pupil_id, "1", actor=ADMIN, reason="")
    with pytest.raises(DM.PermissionDenied):
        DM.top_up(p.pupil_id, "1", actor=ANN)
    with pytest.raises(DM.PermissionDenied):
        DM.accounts() and DM.export_csv("x.csv", actor=KID)


def test_register_staff_tick_office_charges_fsm_free_and_needs_flagged():
    _lunch()
    paying, fsm = _pupil(), _pupil(fsm_eligible=True)
    DM.set_needs(fsm.pupil_id, actor=ADMIN, allergies="Peanuts", dietary="Halal")
    got = DM.save_register(DAY, "Lunch", [paying.pupil_id, fsm.pupil_id], actor=ANN)
    assert got == {"added": 2, "removed": 0}
    rows = {r.pupil_id: r for r in DM.register(DAY, "Lunch")}
    assert rows[fsm.pupil_id].needs == "ALLERGY: Peanuts; Halal"
    assert rows[fsm.pupil_id].price_pence == 0 and rows[paying.pupil_id].price_pence == 250
    with pytest.raises(DM.PermissionDenied):
        DM.charge_register(DAY, "Lunch", actor=ANN)
    res = DM.charge_register(DAY, "Lunch", actor=ADMIN)
    assert res == {"charged": 1, "fsm": 1, "total_pence": 250}
    assert DM.balance(paying.pupil_id) == -250 and DM.balance(fsm.pupil_id) == 0
    with pytest.raises(DM.ValidationError):
        DM.charge_register(DAY, "Lunch", actor=ADMIN)       # nothing left to charge
    # Unticking a charged meal: staff can't, the office can (the charge is voided).
    with pytest.raises(DM.ValidationError):
        DM.save_register(DAY, "Lunch", [fsm.pupil_id], actor=ANN)
    DM.save_register(DAY, "Lunch", [fsm.pupil_id], actor=ADMIN)
    assert DM.balance(paying.pupil_id) == 0
    with pytest.raises(DM.ValidationError) as e:
        DM.save_register(DAY, "Breakfast", [paying.pupil_id], actor=ANN)
    assert "Set the price" in " ".join(e.value.problems)


def test_arrears_low_balance_letters_and_weekly_gap():
    _lunch()
    owes, low, fine = _pupil(), _pupil(), _pupil()
    for p in (owes, low, fine):
        C.add_contact(p.pupil_id, {"full_name": "Parent", "relationship": "Mother",
                                   "email": f"p{p.pupil_id}@example.org"}, actor=ADMIN)
    DM.record_meal(owes.pupil_id, actor=ADMIN)
    DM.top_up(low.pupil_id, "3.00", actor=ADMIN)
    DM.top_up(fine.pupil_id, "20.00", actor=ADMIN)
    assert [a.pupil_id for a in DM.arrears()] == [owes.pupil_id]
    assert [a.pupil_id for a in DM.low_balance()] == [low.pupil_id]
    DM.set_low_balance_threshold("2.00", actor=ADMIN)
    assert DM.low_balance() == []
    DM.set_low_balance_threshold("5.00", actor=ADMIN)
    res = DM.send_debt_letters(actor=ADMIN)
    assert res["emails"] == 1 and [a.pupil_id for a in res["sent"]] == [owes.pupil_id]
    with pytest.raises(DM.ValidationError) as e:
        DM.send_debt_letters(actor=ADMIN)                  # a week hasn't passed
    assert "this week" in " ".join(e.value.problems)
    assert DM.send_debt_letters(actor=ADMIN, pupil_ids=[owes.pupil_id])["emails"] == 1
    assert DM.send_low_balance_alerts(actor=ADMIN)["emails"] == 1
    with database.connect() as conn:
        bodies = [r[0] for r in conn.execute("SELECT body FROM email_recipients")]
    assert any("overdrawn by £2.50" in b and "not be refused a meal" in b for b in bodies)
    assert any("below £5.00" in b for b in bodies)
    assert [x["kind"] for x in DM.last_letters(owes.pupil_id)] == ["debt", "debt"]


def test_statement_running_balance_and_email():
    _lunch()
    p = _pupil()
    C.add_contact(p.pupil_id, {"full_name": "Dad", "relationship": "Father",
                               "email": "dad@example.org"}, actor=ADMIN)
    yesterday = (TODAY - dt.timedelta(days=1)).isoformat()
    DM.top_up(p.pupil_id, "10", actor=ADMIN, day=yesterday)
    DM.record_meal(p.pupil_id, actor=ADMIN, day=DAY)
    s = DM.statement(p.pupil_id, date_from=DAY)
    assert s["opening_pence"] == 1000 and s["closing_pence"] == 750
    assert [run for _t, run in s["lines"]] == [750] and s["meals"] == 1
    assert "Closing balance" in DM.statement_text(s)
    assert DM.email_statement(p.pupil_id, actor=ADMIN)["emails"] == 1


def test_cash_up_and_takings():
    _lunch()
    a, b = _pupil(), _pupil(fsm_eligible=True)
    DM.top_up(a.pupil_id, "10", method="Cash", actor=ADMIN)
    DM.top_up(a.pupil_id, "5", method="Card", actor=ADMIN)
    DM.record_meal(a.pupil_id, actor=ADMIN)
    DM.record_meal(b.pupil_id, actor=ADMIN)
    DM.refund_balance(a.pupil_id, amount="2.00", actor=ADMIN)
    c = DM.cash_up(DAY)
    assert c["by_method"] == {"Cash": 800, "Card": 500}
    assert (c["top_ups_pence"], c["refunds_pence"], c["net_pence"]) == (1500, 200, 1300)
    assert c["meals"] == {"Lunch": 2} and c["fsm_meals"] == 1 and c["charges_pence"] == 250
    assert "Cash to bank" in DM.cash_up_text(c)
    days = DM.takings(DAY, DAY)
    assert days == [{"day": DAY, "by_method": {"Cash": 800, "Card": 500}, "net_pence": 1300,
                     "meals": 2}]


def test_leavers_refund_write_off_and_year_end():
    _lunch()
    credit, debt, stays = _pupil(), _pupil(), _pupil()
    prev = DM.current_year(TODAY.replace(year=TODAY.year - 1) if TODAY.month != 2
                           or TODAY.day != 29 else TODAY - dt.timedelta(days=366))
    old_day = f"{int(prev[:4]) + 1}-07-01"         # in the previous school year
    DM.top_up(credit.pupil_id, "8", actor=ADMIN, day=old_day)
    DM.record_meal(debt.pupil_id, actor=ADMIN, day=old_day)
    DM.top_up(stays.pupil_id, "4", actor=ADMIN, day=old_day)
    DM.top_up(stays.pupil_id, "1", actor=ADMIN)    # this year: not carried
    with pytest.raises(DM.ValidationError):
        DM.year_end(DM.current_year(), actor=ADMIN)    # not finished
    res = DM.year_end(prev, actor=ADMIN)
    assert res["pupils"] == 3 and res["credit_pence"] == 1200 and res["debt_pence"] == -250
    assert DM.balance(stays.pupil_id) == 500           # nets to zero
    s = DM.statement(stays.pupil_id, date_from=f"{int(prev[:4]) + 1}-09-01")
    assert s["opening_pence"] == 0 and s["lines"][0][0].kind == DM.CARRIED_IN
    with pytest.raises(DM.ValidationError):
        DM.year_end(prev, actor=ADMIN)                 # once only
    for p in (credit, debt):
        P.update_pupil(p.pupil_id, {"roll_status": "left", "leaving_date": DAY,
                                    "leaving_reason": "Moved away"}, actor=ADMIN)
    assert {a.pupil_id for a in DM.leavers_with_balance()} == {credit.pupil_id, debt.pupil_id}
    with pytest.raises(DM.ValidationError):
        DM.refund_balance(debt.pupil_id, actor=ADMIN)
    DM.refund_balance(credit.pupil_id, actor=ADMIN, method="Cash")
    DM.write_off(debt.pupil_id, actor=ADMIN, reason="Family left the area")
    assert DM.leavers_with_balance() == []


def test_family_view_export_and_history(tmp_path):
    _lunch()
    p = _pupil()
    DM.top_up(p.pupil_id, "3", actor=ADMIN)
    fam = DM.for_family(p.pupil_id)
    assert fam["balance"] == "£3.00" and fam["low"] and not fam["overdrawn"]
    out = tmp_path / "bal.csv"
    assert DM.export_csv(out, actor=ADMIN) == 1
    rows = list(csv.reader(out.open()))
    assert rows[0][0] == "admission_no" and rows[1][5] == "3.00"
    assert DM.export_csv(tmp_path / "t.csv", actor=ADMIN, kind="transactions") == 1
    assert DM.history(p.pupil_id)[0]["action"] == "top_up"
    s = DM.summary()
    assert s["pupils"] == 1 and s["credit_pence"] == 300 and s["low"] == 1


def test_never_used_account_is_not_running_low():
    _lunch()
    unused, spent = _pupil(), _pupil()
    DM.top_up(spent.pupil_id, "2.50", actor=ADMIN)
    DM.record_meal(spent.pupil_id, actor=ADMIN)               # back to £0.00, but used
    assert DM.for_family(unused.pupil_id)["balance"] == "£0.00"
    assert not DM.for_family(unused.pupil_id)["low"]
    assert DM.for_family(spent.pupil_id)["low"]
    assert [a.pupil_id for a in DM.low_balance()] == [spent.pupil_id]
