"""Expense claims (modules.finance.domain.expense_claims)."""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.finance.domain import budgets as B
from education_system.systems.secondary.modules.finance.domain import expense_claims as X
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")       # expense approver
FIN = Principal(username="fin", role="superadmin")       # another approver
ANN = Principal(username="ann", role="teacher")           # holds Maths
BOB = Principal(username="bob", role="teacher")           # Maths teacher, claims
CAT = Principal(username="cat", role="teacher")           # nobody special
PUPIL = Principal(username="kid", role="student")
LOGINS = [{"username": u, "display_name": n, "email": f"{u}@school.org", "role": "teacher"}
          for u, n in (("ann", "Ann Teacher"), ("bob", "Bob Teacher"), ("cat", "Cat Teacher"),
                       ("admin2", "Admin"), ("fin", "Finance Officer"))]
TODAY = dt.date.today()
YESTERDAY = (TODAY - dt.timedelta(days=1)).isoformat()


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


@pytest.fixture
def line():
    B.create_year(actor=ADMIN)
    maths = B.create_centre({"name": "Maths", "holder": "ann"}, actor=ADMIN)
    return B.create_line(maths.centre_id, {"code": "MAT-RES", "description": "Resources",
                                           "allocation": "100.00"}, actor=ADMIN)


def _claim(actor=BOB, line=None, **extra):
    data = {"title": "Trip to museum", "category": "Travel", **extra}
    if line is not None:
        data["budget_line_id"] = line.line_id
    return X.create_claim(data, actor=actor)


def _submitted(line, actor=BOB, amount="12.50"):
    c = _claim(actor, line)
    X.add_line(c.claim_id, {"incurred_on": YESTERDAY, "category": "Travel",
                            "description": "Train", "unit_amount": amount,
                            "receipt_ref": "R1"}, actor=actor)
    return X.submit(c.claim_id, actor=actor)


# ── Claims and lines ─────────────────────────────────────────────────

def test_staff_make_their_own_claims(line):
    c = _claim(line=line)
    assert c.status == "Draft" and c.claimant_id == "bob" and c.claimant_name == "Bob Teacher"
    assert c.claim_ref == f"EXP-{TODAY.year}-{c.claim_id:04d}"
    assert c.department == "Maths" and c.budget_code == "MAT-RES"
    with pytest.raises(X.PermissionDenied):
        X.create_claim({"title": "x", "claimant_id": "ann"}, actor=BOB)
    with pytest.raises(X.PermissionDenied):
        X.create_claim({"title": "x"}, actor=PUPIL)
    gov = X.create_claim({"title": "Governor travel", "claimant_type": "Governor",
                          "claimant_id": "GOV7", "claimant_name": "Mr Gov"}, actor=ADMIN)
    assert gov.claimant_type == "Governor" and gov.created_by == "admin2"
    assert [x.claim_id for x in X.my_claims(BOB)] == [c.claim_id]
    with pytest.raises(X.PermissionDenied):
        X.get_claim(c.claim_id, actor=CAT)
    assert X.get_claim(c.claim_id, actor=ANN).claim_id == c.claim_id   # the holder sees it
    assert [x.claim_id for x in X.list_claims(actor=CAT)] == []
    with pytest.raises(X.ValidationError, match="Title"):
        X.create_claim({"title": ""}, actor=BOB)
    with pytest.raises(X.ValidationError, match="budget code"):
        X.create_claim({"title": "x", "budget_code": "NOPE"}, actor=BOB)
    by_code = X.create_claim({"title": "y", "budget_code": "MAT-RES - Maths: Resources"},
                             actor=BOB)
    assert by_code.budget_line_id == line.line_id


def test_lines_are_pence_and_mileage_uses_the_rate(line):
    c = _claim(line=line)
    a = X.add_line(c.claim_id, {"incurred_on": YESTERDAY, "category": "Resources",
                                "description": "Pens", "quantity": "3", "unit_amount": "1.99",
                                "vat_amount": "1.19", "receipt_ref": "R1"}, actor=BOB)
    assert (a.net_pence, a.vat_pence, a.gross_pence) == (597, 119, 716)
    m = X.add_line(c.claim_id, {"incurred_on": YESTERDAY, "category": "Mileage",
                                "description": "Home to museum", "mileage_miles": "12.3"},
                   actor=BOB)
    assert (m.mileage_rate_pence, m.net_pence, m.gross_pence) == (45, 554, 554)
    X.set_settings({"mileage_rate_pence": 50}, actor=ADMIN)
    assert X.get_line(m.line_id).mileage_rate_pence == 45      # frozen on the line
    m2 = X.add_line(c.claim_id, {"incurred_on": YESTERDAY, "category": "Mileage",
                                 "description": "Back", "mileage_miles": 10}, actor=BOB)
    assert m2.gross_pence == 500
    with pytest.raises(X.PermissionDenied):
        X.set_settings({"mileage_rate_pence": 60}, actor=ANN)
    with pytest.raises(X.ValidationError) as e:
        X.add_line(c.claim_id, {"incurred_on": "2999-01-01", "category": "Mileage",
                                "description": "", "vat": "1"}, actor=BOB)
    text = " ".join(e.value.problems)
    for bit in ("future", "Description", "Miles are required", "no VAT"):
        assert bit in text
    with pytest.raises(X.ValidationError, match="VAT can't be more"):
        X.add_line(c.claim_id, {"incurred_on": YESTERDAY, "description": "x",
                                "unit_amount": "1", "vat_amount": "2"}, actor=BOB)
    X.update_line(a.line_id, {"quantity": 1}, actor=BOB)
    assert X.get_claim(c.claim_id).total_pence == 199 + 119 + 554 + 500
    with pytest.raises(X.PermissionDenied):
        X.add_line(c.claim_id, {"incurred_on": YESTERDAY, "description": "x",
                                "unit_amount": "1"}, actor=CAT)


def test_category_limits_and_receipts(line):
    X.set_limit("Subsistence", "10.00", actor=ADMIN)
    c = _claim(line=line)
    X.add_line(c.claim_id, {"incurred_on": YESTERDAY, "category": "Subsistence",
                            "description": "Lunch", "unit_amount": "8"}, actor=BOB)
    with pytest.raises(X.ValidationError, match="limit is £10.00"):
        X.add_line(c.claim_id, {"incurred_on": YESTERDAY, "category": "Subsistence",
                                "description": "Tea", "unit_amount": "3"}, actor=BOB)
    with pytest.raises(X.ValidationError, match="needs a receipt"):
        X.submit(c.claim_id, actor=BOB)
    X.set_settings({"receipt_over_pence": "10"}, actor=ADMIN)   # receipts only over £10
    assert X.submit(c.claim_id, actor=BOB).status == "Submitted"
    X.set_limit("Subsistence", "", actor=ADMIN)
    assert X.limits() == {}


def test_submit_needs_lines_and_a_budget_code(line):
    c = _claim()
    with pytest.raises(X.ValidationError) as e:
        X.submit(c.claim_id, actor=BOB)
    assert "no lines" in str(e.value) and "budget code" in str(e.value)


# ── Approval and separation of duties ────────────────────────────────

def test_holder_or_approver_decides_never_the_claimant(line):
    c = _submitted(line)
    assert X.approval_queue(ANN)[0].claim_id == c.claim_id
    assert X.approval_queue(BOB) == [] and X.approval_queue(CAT) == []
    assert X.awaiting_my_approval(ADMIN) == 1
    with pytest.raises(X.PermissionDenied):
        X.approve(c.claim_id, actor=BOB)
    with pytest.raises(X.PermissionDenied):
        X.approve(c.claim_id, actor=CAT)
    assert {"approve", "reject", "review"} <= X.allowed_actions(ANN, c)
    assert "approve" not in X.allowed_actions(BOB, c)
    X.begin_review(c.claim_id, actor=ANN)
    c = X.approve(c.claim_id, actor=ANN)
    assert c.status == "Approved" and c.approved_by == "ann"
    p = B.position(line.line_id)
    assert p.spent == 1250
    assert B.list_spend(line_id=line.line_id)[0].source == "expense_claim"
    # Ann's own claim on her own cost centre needs the finance office.
    own = _submitted(line, actor=ANN, amount="5")
    assert X.approval_queue(ANN) == []
    with pytest.raises(X.PermissionDenied):
        X.approve(own.claim_id, actor=ANN)
    X.approve(own.claim_id, actor=ADMIN)
    # An approver can't approve or pay their own claim either.
    mine = _submitted(line, actor=ADMIN, amount="1")
    with pytest.raises(X.PermissionDenied):
        X.approve(mine.claim_id, actor=ADMIN)
    X.approve(mine.claim_id, actor=FIN)
    with pytest.raises(X.PermissionDenied):
        X.pay(mine.claim_id, actor=ADMIN, payment_reference="P")
    assert X.pay(mine.claim_id, actor=FIN, payment_reference="BACS1").status == "Paid"


def test_reject_reopen_and_overspend_warning(line):
    c = _submitted(line, amount="150")
    assert X.approval_warnings(c.claim_id)[0].startswith("This takes MAT-RES over budget")
    with pytest.raises(X.ValidationError, match="reason"):
        X.reject(c.claim_id, actor=ANN)
    c = X.reject(c.claim_id, actor=ANN, reason="Use the school account")
    assert c.status == "Rejected" and c.rejection_reason == "Use the school account"
    assert B.position(line.line_id).spent == 0
    with pytest.raises(X.ValidationError):
        X.add_line(c.claim_id, {"incurred_on": YESTERDAY, "description": "x",
                                "unit_amount": "1"}, actor=BOB)
    c = X.reopen(c.claim_id, actor=BOB)
    assert c.status == "Draft" and c.rejection_reason
    c = X.submit(c.claim_id, actor=BOB)
    assert c.status == "Submitted" and c.rejection_reason is None


def test_cancel_an_approved_claim_reverses_the_spend(line):
    c = X.approve(_submitted(line).claim_id, actor=ANN)
    with pytest.raises(X.ValidationError):
        X.cancel(c.claim_id, actor=BOB)                 # too late for the claimant
    c = X.cancel(c.claim_id, actor=ADMIN, reason="Duplicate")
    assert c.status == "Cancelled" and B.position(line.line_id).spent == 0
    assert [s.amount_pence for s in B.list_spend(line_id=line.line_id)] == [-1250, 1250]
    with pytest.raises(X.ValidationError, match="posted"):
        X.delete_claim(c.claim_id, actor=ADMIN)
    d = _claim()
    assert X.delete_claim(d.claim_id, actor=BOB)


def test_old_change_status_keeps_the_rules(line):
    c = _submitted(line)
    with pytest.raises(X.PermissionDenied):
        X.set_status(c.claim_id, "Approved", actor=ANN)      # approvers only
    c = X.set_status(c.claim_id, "Approved", actor=ADMIN)
    assert c.status == "Approved" and B.position(line.line_id).spent == 1250
    with pytest.raises(X.ValidationError, match="reference"):
        X.set_status(c.claim_id, "Paid", actor=ADMIN)
    c = X.set_status(c.claim_id, "Paid", actor=ADMIN, payment_reference="CHQ 1")
    assert c.paid_by == "admin2"
    with pytest.raises(X.ValidationError):
        X.set_status(c.claim_id, "Draft", actor=ADMIN)


# ── Payment runs, summary, export, notices ───────────────────────────

def test_payment_run_pays_and_exports(line, tmp_path):
    a = X.approve(_submitted(line).claim_id, actor=ANN)
    b = X.approve(_submitted(line, actor=CAT, amount="3").claim_id, actor=ADMIN)
    mine = X.approve(_submitted(line, actor=ADMIN, amount="2").claim_id, actor=FIN)
    with pytest.raises(X.PermissionDenied):
        X.payment_run(tmp_path / "r.csv", actor=ANN)
    assert {c.claim_id for c in X.payable(ADMIN)} == {a.claim_id, b.claim_id}
    r = X.payment_run(tmp_path / "r.csv", actor=ADMIN)
    assert (r["claims"], r["total_pence"], r["reference"]) == (2, 1550, "PR-0001")
    rows = list(csv.DictReader((tmp_path / "r.csv").open()))
    assert {x["amount"] for x in rows} == {"12.50", "3.00"}
    assert X.get_claim(a.claim_id).payment_reference == "PR-0001"
    assert X.get_claim(mine.claim_id).status == "Approved"
    with pytest.raises(X.ValidationError, match="No approved"):
        X.payment_run(tmp_path / "r2.csv", actor=ADMIN)
    assert X.export_payment_run(r["run_id"], tmp_path / "again.csv", actor=ADMIN) == 2
    s = X.summary()
    assert (s.paid, s.approved, s.paid_value, s.awaiting_payment_value) == (2, 1, 1550, 200)
    assert X.export_csv(tmp_path / "c.csv", actor=ADMIN, scope="paid") == 2
    assert X.export_csv(tmp_path / "mine.csv", actor=CAT) == 1


def test_notice_to_the_claimant(line):
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    c = X.reject(_submitted(line).claim_id, actor=ANN, reason="Wrong code")
    with pytest.raises(X.PermissionDenied):
        X.notify_claimant(c.claim_id, actor=CAT)
    mid = X.notify_claimant(c.claim_id, actor=ADMIN)
    _msg, recips = E.get_message(mid, actor=ADMIN)
    assert recips[0]["address"] == "bob@school.org"
    with database.connect() as conn:
        r = conn.execute("SELECT subject, body FROM email_recipients WHERE message_id = ?",
                         (mid,)).fetchone()
    assert "Wrong code" in r["body"] and c.claim_ref in r["subject"]


def test_activity_log_has_ids_not_amounts(line, scratch):
    X.approve(_submitted(line, amount="77.77").claim_id, actor=ANN)
    text = (scratch / "activity.log").read_text()
    assert "expenses.approve" in text and "77" not in text.replace("7777", "")
    assert "Bob Teacher" not in text


def test_cli_menu_runs(line, monkeypatch, capsys):
    from education_system.systems.secondary.modules.finance.cli import expense_claims_cli
    c = _submitted(line)
    answers = iter(["25", "", "17", str(c.claim_id), "y", "", "", "26", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _m="": next(answers, "0"))
    expense_claims_cli.menu(BOB)
    out = capsys.readouterr().out
    assert c.claim_ref in out and "own claim" in out


def test_staff_self_service_menu(line, monkeypatch, capsys):
    from education_system.systems.secondary.modules.finance.cli import expense_claims_cli
    answers = iter(["2", "", "", "Taxi", "", "", "", "", "", "", "", "1", "", "1", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _m="": next(answers, "0"))
    expense_claims_cli.menu_mine(CAT)
    assert [c.title for c in X.my_claims(CAT)] == ["Taxi"]
    assert "Taxi" in capsys.readouterr().out
