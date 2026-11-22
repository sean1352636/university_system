"""Budgets (modules.finance.domain.budgets)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.finance.domain import budgets as B
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
FIN = Principal(username="fin", role="superadmin")       # a second budget editor
ANN = Principal(username="ann", role="teacher")           # holds Maths
BOB = Principal(username="bob", role="teacher")           # holds nothing
PUPIL = Principal(username="kid", role="student")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("ann", "Ann Teacher"), ("bob", "Bob Teacher"), ("admin2", "Admin"),
                       ("fin", "Finance Officer"))]
TODAY = dt.date.today()


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


def _setup(allocation="1000.00"):
    y = B.create_year(actor=ADMIN)
    maths = B.create_centre({"name": "Maths", "kind": "Department", "holder": "ann"},
                            actor=ADMIN)
    res = B.create_line(maths.centre_id, {"code": "MAT-RES", "description": "Resources",
                                          "allocation": allocation}, actor=ADMIN)
    cpd = B.create_line(maths.centre_id, {"code": "MAT-CPD", "description": "Training",
                                          "allocation": 50000}, actor=ADMIN)
    return y, maths, res, cpd


# ── Money ────────────────────────────────────────────────────────────

def test_money_is_whole_pence():
    p: list[str] = []
    assert B.to_pence("12.50", "x", p) == 1250
    assert B.to_pence("£1,234", "x", p) == 123400
    assert B.to_pence(99, "x", p) == 99            # an int is already pence
    assert not p
    B.to_pence("1.005", "x", p)
    B.to_pence("abc", "x", p)
    B.to_pence("-1", "x", p)
    assert len(p) == 3
    assert B.money(123456) == "£1,234.56" and B.money(-500) == "-£5.00"
    assert B.pounds(1205) == "12.05"
    assert B._split(1000, [1] * 12) == [84, 84, 84, 84, 83, 83, 83, 83, 83, 83, 83, 83]
    assert sum(B._split(99999, [3, 0, 5, 1, 1, 1, 1, 1, 1, 1, 1, 7])) == 99999


# ── Years ────────────────────────────────────────────────────────────

def test_year_start_is_a_setting():
    assert B.settings()["year_start_month"] == 4
    y = B.create_year(2025, actor=ADMIN)
    assert (y.year_label, y.start_date, y.end_date) == ("2025-26", "2025-04-01", "2026-03-31")
    B.set_settings({"year_start_month": "Academy (September-August)"}, actor=ADMIN)
    with pytest.raises(B.ValidationError, match="already exists|overlap"):
        B.create_year(2025, actor=ADMIN)          # Sept 2025 is inside April 2025-March 2026
    y2 = B.create_year(2026, actor=ADMIN)
    assert (y2.start_date, y2.end_date) == ("2026-09-01", "2027-08-31")
    assert B.months(y2.year_label)[0] == "2026-09" and B.months(y2.year_label)[-1] == "2027-08"
    with pytest.raises(B.ValidationError):
        B.create_year(2026, actor=ADMIN)
    with pytest.raises(B.PermissionDenied):
        B.set_settings({"warn_percent": 80}, actor=ANN)
    with pytest.raises(B.ValidationError):
        B.set_settings({"year_start_month": 13}, actor=ADMIN)


# ── Centres and lines ────────────────────────────────────────────────

def test_centres_lines_and_who_sees_them():
    y, maths, res, cpd = _setup()
    assert res.allocation_pence == 100000 and res.code == "MAT-RES"
    with pytest.raises(B.ValidationError, match="already"):
        B.create_centre({"name": "maths", "holder": "ann"}, actor=ADMIN)
    with pytest.raises(B.ValidationError, match="holder"):
        B.create_centre({"name": "Science", "holder": "nobody"}, actor=ADMIN)
    with pytest.raises(B.ValidationError, match="already used"):
        B.create_line(maths.centre_id, {"code": "mat-res", "description": "x"}, actor=ADMIN)
    with pytest.raises(B.PermissionDenied):
        B.create_centre({"name": "Science"}, actor=ANN)
    sci = B.create_centre({"name": "Science", "holder": "Bob Teacher (bob)"}, actor=ADMIN)
    assert sci.holder == "bob"
    assert [c.name for c in B.list_centres(y.year_label, actor=ANN)] == ["Maths"]
    assert len(B.list_centres(y.year_label, actor=ADMIN)) == 2
    with pytest.raises(B.PermissionDenied):
        B.list_centres(y.year_label, actor=PUPIL)
    # Codes for claims carry no money and are open to all staff screens.
    codes = B.codes_for_claims()
    assert {c["code"] for c in codes} == {"MAT-RES", "MAT-CPD"}
    assert "allocation" not in codes[0]
    B.update_line(res.line_id, {"allocation": "1200"}, actor=ADMIN)
    assert B.position(res.line_id).budget == 120000
    assert B.history(line_id=res.line_id)[0]["detail"]["allocation_to"] == 120000
    assert B.delete_centre(sci.centre_id, actor=ADMIN)


def test_position_commitments_spend_and_warnings():
    y, maths, res, cpd = _setup()
    m = B.add_commitment(res.line_id, {"amount": "300", "description": "Textbooks",
                                       "supplier": "Books Ltd", "order_ref": "PO1"}, actor=ANN)
    with pytest.raises(B.PermissionDenied):
        B.add_commitment(res.line_id, {"amount": "1", "description": "x"}, actor=BOB)
    with pytest.raises(B.PermissionDenied):
        B.add_spend(res.line_id, {"amount": "1", "description": "x"}, actor=ANN)
    B.add_spend(res.line_id, {"amount": "500", "description": "Calculators"}, actor=ADMIN)
    p = B.position(res.line_id)
    assert (p.budget, p.committed, p.spent, p.remaining) == (100000, 30000, 50000, 20000)
    assert p.state(90) == "ok" and p.state(80) == "warn"
    assert B.check_spend(res.line_id, 25000)[0].startswith("This takes MAT-RES over budget")
    s = B.settle_commitment(m.commitment_id, amount="350", actor=ADMIN)
    assert s.amount_pence == 35000 and s.source == "commitment"
    p = B.position(res.line_id)
    assert (p.committed, p.spent, p.remaining) == (0, 85000, 15000)
    B.add_spend(res.line_id, {"amount": "200", "description": "Paper"}, actor=ADMIN)
    over = B.overspends(y.year_label)
    assert over[0][0].line_id == res.line_id and over[0][1] == "over"
    # A refund is negative spend; spend outside the year is refused.
    B.add_spend(res.line_id, {"amount": "-60", "description": "Refund"}, actor=ADMIN)
    assert B.position(res.line_id).remaining == -5000 + 6000
    with pytest.raises(B.ValidationError, match="financial year"):
        B.add_spend(res.line_id, {"amount": "1", "description": "x",
                                  "spend_date": "1999-01-01"}, actor=ADMIN)
    with pytest.raises(B.ValidationError, match="spend"):
        B.delete_line(res.line_id, actor=ADMIN)
    assert [c["name"] for c in B.centre_totals(y.year_label, actor=ANN)] == ["Maths"]


def test_virements_decided_by_the_holder_or_another_editor():
    y, maths, res, cpd = _setup()
    with pytest.raises(B.PermissionDenied):
        B.request_virement({"from_line_id": res.line_id, "to_line_id": cpd.line_id,
                            "amount": "10", "reason": "x"}, actor=BOB)
    with pytest.raises(B.ValidationError, match="reason"):
        B.request_virement({"from_line_id": res.line_id, "to_line_id": cpd.line_id,
                            "amount": "10"}, actor=ANN)
    with pytest.raises(B.ValidationError, match="left to move"):
        B.request_virement({"from_line_id": res.line_id, "to_line_id": cpd.line_id,
                            "amount": "5000", "reason": "x"}, actor=ANN)
    v = B.request_virement({"from_line_id": res.line_id, "to_line_id": cpd.line_id,
                            "amount": "250", "reason": "More CPD"}, actor=ANN)
    assert v.status == "Pending" and B.position(res.line_id).budget == 100000
    with pytest.raises(B.PermissionDenied):   # not the holder, not the finance office
        B.decide_virement(v.virement_id, "Approved", actor=BOB)
    own = B.request_virement({"from_line_id": cpd.line_id, "to_line_id": res.line_id,
                              "amount": "1", "reason": "Tidy"}, actor=ADMIN)
    with pytest.raises(B.ValidationError, match="Someone else"):
        B.decide_virement(own.virement_id, "Approved", actor=ADMIN)
    with pytest.raises(B.ValidationError, match="reason"):
        B.decide_virement(own.virement_id, "Rejected", actor=FIN)
    B.decide_virement(own.virement_id, "Rejected", actor=FIN, note="No need")
    # The holder of the "from" budget may approve their own request.
    v = B.decide_virement(v.virement_id, "Approved", actor=ANN)
    assert v.status == "Approved" and v.decided_by == ANN.username
    assert B.position(res.line_id).budget == 75000
    assert B.position(cpd.line_id).budget == 75000
    assert [x.virement_id for x in B.list_virements(y.year_label, actor=BOB)] == []
    assert len(B.list_virements(y.year_label, actor=ANN)) == 2


def test_profile_follows_the_budget_and_variance():
    y, maths, res, cpd = _setup("1200")
    assert B.profile(res.line_id) == [10000] * 12 and not B.has_profile(res.line_id)
    weights = ["0"] * 12
    weights[0], weights[5] = "600", "600"
    B.set_profile(res.line_id, weights, actor=ADMIN)
    assert B.profile(res.line_id)[0] == 60000 and sum(B.profile(res.line_id)) == 120000
    B.update_line(res.line_id, {"allocation": "600"}, actor=ADMIN)
    assert B.profile(res.line_id)[0] == 30000 and sum(B.profile(res.line_id)) == 60000
    with pytest.raises(B.ValidationError):
        B.set_profile(res.line_id, ["1"] * 11, actor=ADMIN)
    first = B.months(y.year_label)[0]
    B.add_spend(res.line_id, {"amount": "100", "description": "x",
                              "spend_date": f"{first}-15"}, actor=ADMIN)
    rows = B.variance(y.year_label, line_id=res.line_id)
    assert rows[0]["profiled"] == 30000 and rows[0]["actual"] == 10000
    assert rows[0]["variance"] == 20000 and rows[-1]["cum_profiled"] == 60000
    centre = B.variance(y.year_label, centre_id=maths.centre_id)
    assert centre[-1]["cum_profiled"] == 60000 + 50000


def test_holder_view_export_and_roll_forward(tmp_path):
    y, maths, res, cpd = _setup()
    B.set_profile(res.line_id, [str(i) for i in range(1, 13)], actor=ADMIN)
    mine = B.my_centres(ANN, y.year_label)
    assert len(mine) == 1 and mine[0]["budget"] == 150000
    assert B.my_centres(BOB, y.year_label) == []
    out = tmp_path / "b.csv"
    assert B.export_csv(out, actor=ANN, year=y.year_label) == 2
    rows = list(csv.DictReader(out.open()))
    assert rows[0]["code"] == "MAT-CPD" and rows[1]["budget"] == "1000.00"
    B.add_spend(res.line_id, {"amount": "1", "description": "=cmd()"}, actor=ADMIN)
    assert B.export_transactions_csv(tmp_path / "t.csv", actor=ADMIN, year=y.year_label) == 1
    assert "'=cmd()" in (tmp_path / "t.csv").read_text()
    with pytest.raises(B.PermissionDenied):
        B.roll_forward(y.year_label, actor=ANN)
    r = B.roll_forward(y.year_label, actor=ADMIN, uplift_percent="2.5")
    assert (r["centres"], r["lines"]) == (1, 2)
    nxt = B.get_year(r["year"])
    assert nxt.start_date > y.end_date
    new = {ln.code: ln for ln in B.list_lines(year=r["year"])}
    assert new["MAT-RES"].allocation_pence == 102500 and new["MAT-RES"].holder == "ann"
    assert B.has_profile(new["MAT-RES"].line_id)
    again = B.roll_forward(y.year_label, actor=ADMIN)
    assert again["centres"] == 0 and "Maths" in again["skipped"]


def test_closing_a_year_stops_changes():
    y, maths, res, cpd = _setup()
    m = B.add_commitment(res.line_id, {"amount": "10", "description": "x"}, actor=ANN)
    with pytest.raises(B.ValidationError, match="still open"):
        B.set_year_status(y.year_label, "Closed", actor=ADMIN)
    B.cancel_commitment(m.commitment_id, actor=ANN)
    B.set_year_status(y.year_label, "Closed", actor=ADMIN)
    with pytest.raises(B.ValidationError, match="closed"):
        B.add_spend(res.line_id, {"amount": "1", "description": "x"}, actor=ADMIN)
    assert B.codes_for_claims() == []
    B.set_year_status(y.year_label, "Open", actor=ADMIN)
    assert len(B.codes_for_claims()) == 2


def test_cli_menu_runs(monkeypatch, capsys):
    from education_system.systems.secondary.modules.finance.cli import budgets_cli
    _setup()
    answers = iter(["1", "", "23", "", "22", "1", "", "99", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _m="": next(answers, "0"))
    budgets_cli.menu(ADMIN)
    out = capsys.readouterr().out
    assert "Maths" in out and "Apr" in out and "Invalid selection" in out
