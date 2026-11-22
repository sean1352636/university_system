"""Library catalogue and loans (domain.academics.library.library)."""

from __future__ import annotations

import datetime as dt

import pytest

from education_system.systems.primary.domain.academics.library import library as L
from education_system.systems.primary.domain.learners.pupils import pupils as P

TODAY = dt.date.today()
PAST_LOAN = "2025-09-01"
PAST_DUE = "2025-09-15"
FUTURE = (TODAY + dt.timedelta(days=30)).isoformat()


def _book(title="The Gruffalo", **extra):
    return L.create_book({"title": title, **extra})


def _pupil(first="Ada"):
    return P.create_pupil({"first_name": first, "last_name": "Test", "year_group": "2",
                           "date_of_birth": "2019-01-01"}).pupil_id


def _lend(book, pid, **extra):
    extra.setdefault("loan_date", TODAY.isoformat())
    extra.setdefault("due_date", FUTURE)
    return L.lend(book.book_id, pid, **extra)


# ── empty database ──

def test_empty_db():
    assert L.list_books() == []
    assert L.list_loans() == []
    assert L.get_book(1) is None
    assert L.get_loan(1) is None
    assert L.delete_book(1) is False
    assert L.overview() == {"books_total": 0, "books_active": 0, "copies_total": 0,
                            "copies_avail": 0,
                            "loans": {"Out": 0, "Returned": 0, "Overdue": 0, "Lost": 0}}


# ── books ──

def test_create_book_stores_fields_and_copies():
    b = _book(isbn="978-0-333-71093-7", author=" Julia Donaldson ", category="Fiction",
              year_published="1999", copies_total="3", location=" Shelf A ", notes="")
    assert (b.isbn, b.title, b.author, b.category, b.year_published, b.copies_total,
            b.copies_available, b.location, b.is_active, b.notes) == (
        "978-0-333-71093-7", "The Gruffalo", "Julia Donaldson", "Fiction", 1999, 3, 3,
        "Shelf A", True, None)
    assert L.get_book(b.book_id) == b


def test_book_defaults():
    b = _book()
    assert (b.isbn, b.category, b.copies_total, b.copies_available, b.year_published) == (
        None, "Fiction", 1, 1, None)


def test_book_validation():
    with pytest.raises(L.ValidationError, match="Title is required"):
        _book(title=" ")
    with pytest.raises(L.ValidationError, match="200 characters"):
        _book(title="t" * 201)
    with pytest.raises(L.ValidationError, match="ISBN must be 10–17 chars"):
        _book(isbn="12345")
    with pytest.raises(L.ValidationError, match="Category must be one of"):
        _book(category="Comics")
    with pytest.raises(L.ValidationError, match="Year published must be a whole number"):
        _book(year_published="old")
    with pytest.raises(L.ValidationError, match="between 1000 and 2200"):
        _book(year_published=999)
    with pytest.raises(L.ValidationError, match="Copies total must be a whole number"):
        _book(copies_total="two")
    with pytest.raises(L.ValidationError, match="between 1 and 10000"):
        _book(copies_total=0)


def test_duplicate_isbn_refused_but_blank_isbns_allowed():
    _book(isbn="0123456789")
    with pytest.raises(L.ValidationError, match="already exists"):
        _book("Other", isbn="0123456789")
    _book("No ISBN 1")
    _book("No ISBN 2")
    assert len(L.list_books()) == 3


def test_list_books_filters():
    _book("zog", author="Julia Donaldson", category="Fiction")
    _book("Atlas", category="Reference", isbn="9780000000001")
    _book("Old book", is_active=False)
    out = _book("Popular")
    _lend(out, _pupil())
    titles = lambda bs: [b.title for b in bs]  # noqa: E731
    assert titles(L.list_books()) == ["Atlas", "Old book", "Popular", "zog"]
    assert titles(L.list_books(active_only=True)) == ["Atlas", "Popular", "zog"]
    assert titles(L.list_books(available_only=True)) == ["Atlas", "Old book", "zog"]
    assert titles(L.list_books(category="Reference")) == ["Atlas"]
    assert titles(L.list_books(query="donald")) == ["zog"]
    assert titles(L.list_books(query="97800000")) == ["Atlas"]
    with pytest.raises(L.ValidationError, match="Category filter"):
        L.list_books(category="Manga")


def test_update_book_adjusts_available_by_outstanding_loans():
    b = _book(copies_total=3)
    _lend(b, _pupil())
    out = L.update_book(b.book_id, {"copies_total": 5, "location": "Shelf B"})
    assert (out.copies_total, out.copies_available, out.location) == (5, 4, "Shelf B")
    out = L.update_book(b.book_id, {"copies_total": 1})
    assert (out.copies_total, out.copies_available) == (1, 0)


def test_update_book_duplicate_isbn_and_unknown():
    _book(isbn="0123456789")
    b = _book("Other", isbn="9999999999")
    with pytest.raises(L.ValidationError, match="already exists"):
        L.update_book(b.book_id, {"isbn": "0123456789"})
    assert L.update_book(b.book_id, {"isbn": "9999999999", "title": "Renamed"}).title == (
        "Renamed")
    with pytest.raises(L.ValidationError, match="No book #404"):
        L.update_book(404, {})


def test_toggle_active():
    b = _book()
    assert L.toggle_active(b.book_id).is_active is False
    assert L.toggle_active(b.book_id).is_active is True
    with pytest.raises(L.ValidationError, match="No book #8"):
        L.toggle_active(8)


def test_delete_book_with_history_but_no_active_loan():
    b = _book()
    loan = _lend(b, _pupil())
    L.return_loan(loan.loan_id)
    assert L.delete_book(b.book_id) is True
    assert L.get_book(b.book_id) is None
    assert L.get_loan(loan.loan_id) is None


def test_delete_book_refused_while_on_loan():
    b = _book()
    _lend(b, _pupil())
    with pytest.raises(L.ValidationError, match="1 active loan"):
        L.delete_book(b.book_id)
    assert L.get_book(b.book_id) is not None


# ── lending ──

def test_lend_records_loan_and_takes_a_copy():
    b = _book(author="Julia Donaldson", copies_total=2)
    pid = _pupil()
    loan = L.lend(b.book_id, f" {pid} ", loan_date="2025-09-01", due_date="2025-09-10",
                  notes=" careful ")
    assert (loan.book_id, loan.pupil_id, loan.loan_date, loan.due_date, loan.status,
            loan.notes, loan.returned_date) == (
        b.book_id, pid, "2025-09-01", "2025-09-10", "Out", "careful", None)
    assert (loan.book_title, loan.book_author) == ("The Gruffalo", "Julia Donaldson")
    assert L.get_book(b.book_id).copies_available == 1


def test_lend_defaults_to_today_and_fourteen_days():
    loan = L.lend(_book().book_id, _pupil())
    assert loan.loan_date == TODAY.isoformat()
    assert loan.due_date == (TODAY + dt.timedelta(days=14)).isoformat()
    assert loan.days_overdue == 0


def test_lend_due_date_defaults_from_given_loan_date():
    loan = L.lend(_book().book_id, _pupil(), loan_date="2025-09-01")
    assert loan.due_date == "2025-09-15"


def test_lend_refusals():
    pid = _pupil()
    with pytest.raises(L.ValidationError, match="No book #7"):
        L.lend(7, pid)
    inactive = _book("Gone", is_active=False)
    with pytest.raises(L.ValidationError, match="inactive"):
        L.lend(inactive.book_id, pid)
    one = _book()
    _lend(one, pid)
    with pytest.raises(L.ValidationError, match="no available copies"):
        L.lend(one.book_id, pid)
    b = _book("Spare", copies_total=5)
    with pytest.raises(L.ValidationError, match="Pupil ID is required"):
        L.lend(b.book_id, " ")
    with pytest.raises(L.ValidationError, match="No pupil with id GHOST"):
        L.lend(b.book_id, "GHOST")
    with pytest.raises(L.ValidationError, match="Loan date must be YYYY-MM-DD"):
        L.lend(b.book_id, pid, loan_date="today")
    with pytest.raises(L.ValidationError, match="Due date is not a real date"):
        L.lend(b.book_id, pid, due_date="2025-02-30")
    with pytest.raises(L.ValidationError, match="Due date cannot be before loan date"):
        L.lend(b.book_id, pid, loan_date="2025-09-10", due_date="2025-09-09")
    assert L.get_book(b.book_id).copies_available == 5


def test_return_loan_puts_copy_back():
    b = _book(copies_total=2)
    loan = _lend(b, _pupil(), notes="first")
    out = L.return_loan(loan.loan_id, returned_date="2025-09-12", notes=" fine ")
    assert (out.status, out.returned_date, out.notes) == ("Returned", "2025-09-12", "fine")
    assert out.days_overdue == 0
    assert L.get_book(b.book_id).copies_available == 2
    with pytest.raises(L.ValidationError, match="is Returned — cannot return"):
        L.return_loan(loan.loan_id)
    with pytest.raises(L.ValidationError, match="No loan #99"):
        L.return_loan(99)


def test_return_keeps_notes_when_none_given():
    loan = _lend(_book(), _pupil(), notes="torn cover")
    assert L.return_loan(loan.loan_id).notes == "torn cover"


def test_mark_lost_writes_off_the_copy():
    b = _book(copies_total=3)
    loan = _lend(b, _pupil())
    out = L.mark_lost(loan.loan_id, notes="left on bus")
    assert (out.status, out.notes) == ("Lost", "left on bus")
    book = L.get_book(b.book_id)
    assert (book.copies_total, book.copies_available) == (2, 2)
    with pytest.raises(L.ValidationError, match="is Lost — cannot mark lost"):
        L.mark_lost(loan.loan_id)
    with pytest.raises(L.ValidationError, match="is Lost — cannot return"):
        L.return_loan(loan.loan_id)
    with pytest.raises(L.ValidationError, match="No loan #50"):
        L.mark_lost(50)


# ── overdue + listing ──

def test_overdue_loans_flagged_on_list_and_counted():
    b = _book(copies_total=3)
    pid = _pupil()
    late = L.lend(b.book_id, pid, loan_date=PAST_LOAN, due_date=PAST_DUE)
    assert late.status == "Out"
    _lend(b, pid)
    loans = {x.loan_id: x for x in L.list_loans()}
    assert loans[late.loan_id].status == "Overdue"
    expected = (TODAY - dt.date(2025, 9, 15)).days
    assert loans[late.loan_id].days_overdue == expected
    assert [x.loan_id for x in L.list_loans(status="Overdue")] == [late.loan_id]
    returned = L.return_loan(late.loan_id)
    assert returned.status == "Returned"


def test_list_loans_without_refresh_leaves_status():
    b = _book()
    late = L.lend(b.book_id, _pupil(), loan_date=PAST_LOAN, due_date=PAST_DUE)
    assert L.list_loans(refresh_overdue=False)[0].status == "Out"
    assert L.get_loan(late.loan_id).days_overdue == (TODAY - dt.date(2025, 9, 15)).days


def test_list_loans_filters_and_order():
    a, b = _book("A", copies_total=5), _book("B", copies_total=5)
    p1, p2 = _pupil("Ada"), _pupil("Bea")
    l1 = _lend(a, p1, loan_date="2025-09-01")
    l2 = _lend(b, p2, loan_date="2025-09-03")
    l3 = _lend(a, p2, loan_date="2025-09-03")
    ids = lambda xs: [x.loan_id for x in xs]  # noqa: E731
    assert ids(L.list_loans()) == [l3.loan_id, l2.loan_id, l1.loan_id]
    assert ids(L.list_loans(pupil_id=f" {p2}")) == [l3.loan_id, l2.loan_id]
    assert ids(L.list_loans(book_id=a.book_id)) == [l3.loan_id, l1.loan_id]
    L.return_loan(l1.loan_id)
    assert ids(L.list_loans(status="Returned")) == [l1.loan_id]
    with pytest.raises(L.ValidationError, match="Status filter"):
        L.list_loans(status="Borrowed")


def test_overview_totals():
    a = _book("A", copies_total=3)
    b = _book("B", copies_total=2, is_active=False)
    pid = _pupil()
    L.lend(a.book_id, pid, loan_date=PAST_LOAN, due_date=PAST_DUE)    # overdue
    _lend(a, pid)                                                         # out
    lost = _lend(a, pid)
    L.mark_lost(lost.loan_id)                                             # A now 2 copies
    L.update_book(b.book_id, {"notes": "store room"})
    o = L.overview()
    assert (o["books_total"], o["books_active"]) == (2, 1)
    assert o["copies_total"] == 2 + 2
    assert o["copies_avail"] == 0 + 2
    assert o["loans"] == {"Out": 1, "Returned": 0, "Overdue": 1, "Lost": 1}
