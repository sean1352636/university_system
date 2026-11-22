"""Library rules (domain.library) on a scratch school DB.

auth.db and the activity log are redirected, so nothing touches live data.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.library.domain import library as LB
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="lib_teacher", role="teacher")
TODAY = dt.date(2026, 2, 12)
DOB = {y: f"{2026 - y - 4}-01-15" for y in P.YEAR_GROUPS}
ISBN = "9780747544593"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    monkeypatch.setattr(LB, "_today", lambda: TODAY)
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(year=8, **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": DOB[year], "gender": "Female", "year_group": year,
        "admission_date": "2024-09-01", **extra}, actor=ADMIN)


def _book(title="Holes", copies=1, **extra):
    return LB.create_book({"title": title, "copies_total": copies, **extra}, actor=ADMIN)


# ── Catalogue ────────────────────────────────────────────────────────

def test_create_makes_barcoded_copies():
    b = _book(copies=2, isbn="978-0-7475-4459-3", category="fiction", author="Louis Sachar")
    assert (b.isbn, b.category, b.copies_total, b.copies_available) == (ISBN, "Fiction", 2, 2)
    assert [c.barcode for c in LB.list_copies(b.book_id)] == ["L000001", "L000002"]
    assert _book("Atlas").copies_label == "1/1"
    assert [c.barcode for c in LB.list_copies(_book("Map", copies=1).book_id)] == ["L000004"]


def test_isbn_checked_and_unique():
    assert LB.isbn_ok(ISBN) and LB.isbn_ok("074754459X") and not LB.isbn_ok("9780747544594")
    with pytest.raises(LB.ValidationError, match="ISBN"):
        _book(isbn="123")
    _book(isbn=ISBN)
    with pytest.raises(LB.ValidationError, match="already book"):
        _book("Other", isbn=ISBN)


def test_create_reports_every_problem():
    with pytest.raises(LB.ValidationError) as e:
        LB.create_book({"title": "", "category": "zz", "year_published": "3000",
                        "copies_total": "-1"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("Title", "Category", "Year published"):
        assert bit in text


def test_only_the_librarian_changes_the_catalogue():
    with pytest.raises(LB.PermissionDenied):
        LB.create_book({"title": "X"}, actor=TEACHER)
    b = _book()
    for f in (lambda: LB.update_book(b.book_id, {"title": "Y"}, actor=TEACHER),
              lambda: LB.toggle_active(b.book_id, actor=TEACHER),
              lambda: LB.delete_book(b.book_id, actor=TEACHER),
              lambda: LB.add_copies(b.book_id, 1, actor=TEACHER),
              lambda: LB.set_settings({"loan_days": 7}, actor=TEACHER)):
        with pytest.raises(LB.PermissionDenied):
            f()


def test_search_by_title_author_isbn_and_barcode():
    _book("Holes", author="Louis Sachar", isbn=ISBN)
    _book("Atlas")
    assert [b.title for b in LB.list_books(query="sachar")] == ["Holes"]
    assert [b.title for b in LB.list_books(query="978-0747")] == ["Holes"]
    assert [b.title for b in LB.list_books(query="L000002")] == ["Atlas"]


def test_subject_link_and_filter():
    eng = S.create({"code": "ENG", "name": "English", "is_core": True}, actor=ADMIN)
    b = _book(subject_id=eng.subject_id)
    _book("Atlas")
    assert b.subject_code == "ENG"
    assert [x.title for x in LB.list_books(subject_id=eng.subject_id)] == ["Holes"]
    assert ("library book(s)", 1) in S.usage(eng.subject_id)


def test_changing_copies_adds_or_withdraws_shelf_copies():
    b = _book(copies=3)
    LB.lend(_pupil().pupil_id, book_id=b.book_id, actor=TEACHER)
    b, notes = LB.update_book(b.book_id, {"copies_total": 1}, actor=ADMIN)
    assert (b.copies_total, b.copies_available, notes) == (1, 0, ["Withdrew 2 cop(ies)"])
    with pytest.raises(LB.ValidationError, match="can't go below 1"):
        LB.update_book(b.book_id, {"copies_total": 0}, actor=ADMIN)
    b, notes = LB.update_book(b.book_id, {"copies_total": 3}, actor=ADMIN)
    assert (b.copies_total, b.copies_available) == (3, 2)


def test_delete_only_a_book_never_lent():
    b = _book()
    LB.lend(_pupil().pupil_id, book_id=b.book_id, actor=TEACHER)
    with pytest.raises(LB.ValidationError, match="inactive instead"):
        LB.delete_book(b.book_id, actor=ADMIN)
    spare = _book("Spare")
    LB.delete_book(spare.book_id, actor=ADMIN)
    with pytest.raises(LB.NotFound):
        LB.get_book(spare.book_id)


# ── Loans ────────────────────────────────────────────────────────────

def test_lend_and_return():
    b = _book()
    p = _pupil()
    loan = LB.lend(p.pupil_id, book_id=b.book_id, actor=TEACHER)
    assert (loan.barcode, loan.loan_date, loan.due_date, loan.status) == (
        "L000001", "2026-02-12", "2026-02-26", "Out")
    assert LB.get_book(b.book_id).copies_label == "0/1"
    with pytest.raises(LB.ValidationError, match="no copy on the shelf"):
        LB.lend(_pupil().pupil_id, book_id=b.book_id, actor=TEACHER)
    back, hold = LB.return_loan(loan.loan_id, actor=TEACHER)
    assert (back.status, back.returned_date, hold) == ("Returned", "2026-02-12", None)
    assert LB.get_book(b.book_id).copies_label == "1/1"
    with pytest.raises(LB.ValidationError, match="already returned"):
        LB.return_loan(loan.loan_id, actor=TEACHER)


def test_lend_by_barcode_and_dates():
    b = _book(copies=2)
    loan = LB.lend(_pupil().pupil_id, barcode="L000002", actor=TEACHER)
    assert loan.copy_id == LB.list_copies(b.book_id)[1].copy_id
    with pytest.raises(LB.ValidationError, match="on loan"):
        LB.lend(_pupil().pupil_id, barcode="L000002", actor=TEACHER)
    with pytest.raises(LB.ValidationError, match="future"):
        LB.lend(_pupil().pupil_id, book_id=b.book_id, actor=TEACHER, loan_date="2026-03-01")
    with pytest.raises(LB.ValidationError, match="before the loan date"):
        LB.lend(_pupil().pupil_id, book_id=b.book_id, actor=TEACHER, due_date="2026-01-01")


def test_inactive_book_and_off_roll_pupil_refused():
    b = _book()
    LB.toggle_active(b.book_id, actor=ADMIN)
    with pytest.raises(LB.ValidationError, match="inactive"):
        LB.lend(_pupil().pupil_id, book_id=b.book_id, actor=TEACHER)


def test_loan_limit_and_overdue_block_with_librarian_override():
    LB.set_settings({"max_loans": 1}, actor=ADMIN)
    a, c = _book("A"), _book("C")
    p = _pupil()
    LB.lend(p.pupil_id, book_id=a.book_id, actor=TEACHER)
    with pytest.raises(LB.ValidationError, match="limit is 1"):
        LB.lend(p.pupil_id, book_id=c.book_id, actor=TEACHER)
    with pytest.raises(LB.ValidationError, match="limit"):
        LB.lend(p.pupil_id, book_id=c.book_id, actor=TEACHER, override=True)
    assert LB.lend(p.pupil_id, book_id=c.book_id, actor=ADMIN, override=True).is_out


def test_overdue_is_worked_out_from_the_due_date():
    b, other = _book(), _book("Other")
    p = _pupil()
    loan = LB.lend(p.pupil_id, book_id=b.book_id, actor=TEACHER, loan_date="2026-01-01",
                   due_date="2026-01-15")
    assert (loan.status, loan.shown_status, loan.days_overdue) == ("Out", "Overdue", 28)
    assert [x.loan_id for x in LB.overdue()] == [loan.loan_id]
    assert [x.loan_id for x in LB.list_loans(status="Overdue")] == [loan.loan_id]
    assert LB.overview()["loans"]["Overdue"] == 1
    ok, why = LB.can_borrow(p.pupil_id)
    assert not ok and "overdue" in why[0]
    LB.set_settings({"block_overdue": 0}, actor=ADMIN)
    assert LB.lend(p.pupil_id, book_id=other.book_id, actor=TEACHER).is_out


def test_renewals():
    b = _book()
    loan = LB.lend(_pupil().pupil_id, book_id=b.book_id, actor=TEACHER)
    r = LB.renew(loan.loan_id, actor=TEACHER)
    assert (r.due_date, r.renewals) == ("2026-03-12", 1)
    LB.set_settings({"max_renewals": 1}, actor=ADMIN)
    with pytest.raises(LB.ValidationError, match="limit is 1"):
        LB.renew(loan.loan_id, actor=TEACHER)


def test_lost_then_found():
    b = _book()
    loan = LB.lend(_pupil().pupil_id, book_id=b.book_id, actor=TEACHER)
    with pytest.raises(LB.PermissionDenied):
        LB.mark_lost(loan.loan_id, actor=TEACHER)
    lost = LB.mark_lost(loan.loan_id, actor=ADMIN)
    assert lost.status == "Lost" and LB.get_book(b.book_id).copies_label == "0/0"
    found, _ = LB.return_by_barcode("L000001", actor=TEACHER)
    assert found.status == "Returned" and LB.get_book(b.book_id).copies_label == "1/1"
    assert LB.history(b.book_id)[0]["action"] == "found"


def test_delete_loan_puts_the_copy_back():
    b = _book()
    loan = LB.lend(_pupil().pupil_id, book_id=b.book_id, actor=TEACHER)
    LB.delete_loan(loan.loan_id, actor=ADMIN)
    assert LB.get_book(b.book_id).copies_available == 1
    with pytest.raises(LB.NotFound):
        LB.get_loan(loan.loan_id)


def test_withdrawn_copy_cannot_be_lent_and_comes_back():
    b = _book(copies=2)
    c1 = LB.list_copies(b.book_id)[0]
    LB.set_copy_status(c1.copy_id, "Withdrawn", actor=ADMIN, note="Damaged")
    assert LB.get_book(b.book_id).copies_label == "1/1"
    with pytest.raises(LB.ValidationError, match="withdrawn"):
        LB.lend(_pupil().pupil_id, barcode=c1.barcode, actor=TEACHER)
    LB.set_copy_status(c1.copy_id, "Available", actor=ADMIN)
    assert LB.get_book(b.book_id).copies_label == "2/2"


# ── Reservations ─────────────────────────────────────────────────────

def test_reservation_is_kept_for_the_first_pupil():
    b = _book()
    first, second, other = _pupil(), _pupil(), _pupil()
    loan = LB.lend(first.pupil_id, book_id=b.book_id, actor=TEACHER)
    with pytest.raises(LB.ValidationError, match="already has"):
        LB.reserve(b.book_id, first.pupil_id, actor=TEACHER)
    LB.reserve(b.book_id, second.pupil_id, actor=TEACHER)
    with pytest.raises(LB.ValidationError, match="already reserved"):
        LB.reserve(b.book_id, second.pupil_id, actor=TEACHER)
    with pytest.raises(LB.ValidationError, match="reserved"):
        LB.renew(loan.loan_id, actor=TEACHER)
    _back, hold = LB.return_loan(loan.loan_id, actor=TEACHER)
    assert (hold.pupil_id, hold.status, hold.barcode, hold.expires_on) == (
        second.pupil_id, "Ready", "L000001", "2026-02-17")
    with pytest.raises(LB.ValidationError, match="no copy on the shelf"):
        LB.lend(other.pupil_id, book_id=b.book_id, actor=TEACHER)
    with pytest.raises(LB.ValidationError, match="another pupil's reservation"):
        LB.lend(other.pupil_id, barcode="L000001", actor=TEACHER)
    LB.lend(second.pupil_id, book_id=b.book_id, actor=TEACHER)
    assert LB.list_holds() == []


def test_reserve_refused_when_on_the_shelf():
    b = _book()
    with pytest.raises(LB.ValidationError, match="lend it instead"):
        LB.reserve(b.book_id, _pupil().pupil_id, actor=TEACHER)


def test_uncollected_reservation_expires(monkeypatch):
    b = _book()
    loan = LB.lend(_pupil().pupil_id, book_id=b.book_id, actor=TEACHER)
    LB.reserve(b.book_id, _pupil().pupil_id, actor=TEACHER)
    LB.return_loan(loan.loan_id, actor=TEACHER)
    assert LB.expire_holds(actor=TEACHER) == 0
    monkeypatch.setattr(LB, "_today", lambda: dt.date(2026, 3, 1))
    assert LB.expire_holds(actor=TEACHER) == 1
    assert LB.get_book(b.book_id).copies_available == 1


def test_cancelling_a_ready_reservation_passes_the_copy_on():
    b = _book()
    loan = LB.lend(_pupil().pupil_id, book_id=b.book_id, actor=TEACHER)
    first, second = _pupil(), _pupil()
    h1 = LB.reserve(b.book_id, first.pupil_id, actor=TEACHER)
    LB.reserve(b.book_id, second.pupil_id, actor=TEACHER)
    LB.return_loan(loan.loan_id, actor=TEACHER)
    LB.cancel_hold(h1.hold_id, actor=TEACHER)
    [ready] = LB.list_holds()
    assert (ready.pupil_id, ready.status) == (second.pupil_id, "Ready")


# ── Settings and reports ─────────────────────────────────────────────

def test_settings_validated():
    with pytest.raises(LB.ValidationError) as e:
        LB.set_settings({"loan_days": 0, "zz": 1}, actor=ADMIN)
    assert len(e.value.problems) == 2
    assert LB.set_settings({"loan_days": 7}, actor=ADMIN)["loan_days"] == 7
    loan = LB.lend(_pupil().pupil_id, book_id=_book().book_id, actor=TEACHER)
    assert loan.due_date == "2026-02-19"


def test_reading_report_and_popular():
    a, b = _book("A", copies=2), _book("B")
    fsm, plain, idle = _pupil(fsm_eligible=True), _pupil(), _pupil(9)
    LB.lend(fsm.pupil_id, book_id=a.book_id, actor=TEACHER)
    LB.lend(plain.pupil_id, book_id=a.book_id, actor=TEACHER)
    LB.lend(plain.pupil_id, book_id=b.book_id, actor=TEACHER)
    r = LB.reading_report()
    assert (r["pupils"], r["borrowers"], r["loans"], r["fsm_pct"]) == (3, 2, 3, 100.0)
    assert r["by_year"] == {8: 100.0, 9: 0.0}
    assert [p.pupil_id for p in r["non_borrowers"]] == [idle.pupil_id]
    assert [(x.title, n) for x, n in LB.popular()] == [("A", 2), ("B", 1)]


def test_for_pupil_and_exports(tmp_path):
    b = _book("=SUM(A1)")
    p = _pupil()
    LB.lend(p.pupil_id, book_id=b.book_id, actor=TEACHER, loan_date="2026-01-01",
            due_date="2026-01-15")
    info = LB.for_pupil(p.pupil_id)
    assert len(info["out"]) == 1 and len(info["overdue"]) == 1
    path = tmp_path / "cat.csv"
    assert LB.export_catalogue(path, actor=TEACHER) == 1
    assert list(csv.reader(path.open(encoding="utf-8")))[1][2] == "'=SUM(A1)"
    assert LB.export_overdue(tmp_path / "od.csv", actor=TEACHER) == 1


def test_remind_overdue_needs_overdue_books():
    with pytest.raises(LB.ValidationError, match="No overdue"):
        LB.remind_overdue(actor=TEACHER)
