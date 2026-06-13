"""Tests for the library domain layer: catalogue enrichments, loan
rules, fines, reservations, tags and notifications."""

from __future__ import annotations

import datetime as _dt
import os

import pytest

_NO_DISPLAY = not os.environ.get("DISPLAY")

from education_system.sixthform_system.modules.domain.academics.library import (
    library as lib,
    library_settings as settings,
    library_fines as fines,
    library_reservations as holds,
    library_notifications as notifs,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as students_mod,
)
from education_system.sixthform_system.modules.domain.academics.subjects import (
    subjects as subjects_mod,
)
from education_system.sixthform_system.modules.domain.staff_comms.messages import (
    messages as messages_mod,
)
from education_system.sixthform_system.modules.domain.staff_comms.staff import (
    staff as staff_mod,
)
from education_system.sixthform_system.modules.domain.staff_comms.parent_contacts import (
    parent_contacts as parent_contacts_mod,
)
from education_system.sixthform_system.modules.domain.students.alumni import (
    alumni as alumni_mod,
)


def _today(offset: int = 0) -> str:
    return (_dt.date.today() + _dt.timedelta(days=offset)).isoformat()


@pytest.fixture
def lib_db(tmp_path, monkeypatch):
    """Point library + students at a fresh shared SQLite file and seed
    a couple of students. Returns a namespace with handy handles."""
    db_path = str(tmp_path / "sixthform.db")
    # Everything below shares the one sixthform.db file in production, so
    # point them all at the same tmp file for an isolated, FK-complete DB.
    shared = (lib, students_mod, subjects_mod, messages_mod, staff_mod,
              parent_contacts_mod, alumni_mod)
    for mod in shared:
        monkeypatch.setattr(mod, "DB_PATH", db_path)
        monkeypatch.setattr(mod, "_DB_READY", False)
    lib.init_db()
    subjects_mod.init_db()
    messages_mod.init_db()

    subs = {"subject_1": "Mathematics", "subject_2": "Physics",
            "subject_3": "Chemistry"}
    s1 = students_mod.create_student(
        {"first_name": "Ada", "last_name": "Lovelace", **subs})
    s2 = students_mod.create_student(
        {"first_name": "Alan", "last_name": "Turing", **subs})

    class NS:
        pass
    ns = NS()
    ns.s1 = s1.student_id
    ns.s2 = s2.student_id
    return ns


def _book(**over):
    payload = {"title": "Test Title", "item_type": "Book",
               "copies_total": 2, "copies_available": 2}
    payload.update(over)
    return lib.create_book(payload)


# ── Foundation: schema, columns, settings, policies ───────────────

def test_new_book_columns_roundtrip(lib_db):
    b = _book(classification="510 DEW", series="Maths Primers",
              volume="2", cover_image_url="https://x/cover.jpg")
    got = lib.get_book(b.book_id)
    assert got.classification == "510 DEW"
    assert got.series == "Maths Primers"
    assert got.volume == "2"
    assert got.cover_image_url == "https://x/cover.jpg"


def test_cover_url_validation(lib_db):
    with pytest.raises(lib.ValidationError):
        _book(cover_image_url="not a url")


def test_settings_defaults_and_override(lib_db):
    assert settings.get_setting("loan_limit_per_student") == 10
    settings.set_setting("loan_limit_per_student", 3)
    assert settings.get_setting("loan_limit_per_student") == 3
    assert settings.get_setting("block_issue_on_overdue") is True
    settings.set_setting("block_issue_on_overdue", False)
    assert settings.get_setting("block_issue_on_overdue") is False


def test_unknown_setting_rejected(lib_db):
    with pytest.raises(lib.ValidationError):
        settings.get_setting("nope")


def test_loan_policies_seeded(lib_db):
    pols = {p.item_type: p for p in settings.list_policies()}
    assert pols["Reference"].borrowable is False
    assert pols["Textbook"].loan_days == 28
    settings.set_policy("Book", loan_days=21)
    assert settings.get_policy("Book").loan_days == 21


# ── Loan rules (3,4,5,6) ──────────────────────────────────────────

def test_policy_sets_due_date(lib_db):
    b = _book(item_type="Textbook")
    loan = lib.issue(b.book_id, lib_db.s1, loaned_on=_today())
    assert loan.due_on == _today(28)  # Textbook policy = 28 days


def test_reference_not_borrowable(lib_db):
    b = _book(item_type="Reference")
    with pytest.raises(lib.ValidationError, match="not borrowable"):
        lib.issue(b.book_id, lib_db.s1)


def test_per_student_loan_limit(lib_db):
    settings.set_setting("loan_limit_per_student", 1)
    b1, b2 = _book(), _book(title="Second")
    lib.issue(b1.book_id, lib_db.s1)
    with pytest.raises(lib.ValidationError, match="limit"):
        lib.issue(b2.book_id, lib_db.s1)


def test_block_on_overdue(lib_db):
    b1, b2 = _book(), _book(title="Second")
    lib.issue(b1.book_id, lib_db.s1, loaned_on=_today(-30),
              due_on=_today(-16))
    with pytest.raises(lib.ValidationError, match="overdue"):
        lib.issue(b2.book_id, lib_db.s1)
    # Override lets the librarian force it through.
    lib.issue(b2.book_id, lib_db.s1, override_blocks=True)


def test_block_on_fines(lib_db):
    b = _book()
    fines.create_fine(lib_db.s1, "Manual", 6.00)
    with pytest.raises(lib.ValidationError, match="owes"):
        lib.issue(b.book_id, lib_db.s1)


def test_renew_respects_policy_cap(lib_db):
    settings.set_policy("Book", max_renewals=1)
    b = _book()
    loan = lib.issue(b.book_id, lib_db.s1)
    lib.renew(loan.loan_id)
    with pytest.raises(lib.ValidationError, match="renewals limit"):
        lib.renew(loan.loan_id)


def test_renew_blocked_by_reservation(lib_db):
    b = _book(copies_total=1, copies_available=1)
    loan = lib.issue(b.book_id, lib_db.s1)
    holds.reserve(b.book_id, lib_db.s2)
    with pytest.raises(lib.ValidationError, match="reserved"):
        lib.renew(loan.loan_id)


# ── Fines (1,2,10) ────────────────────────────────────────────────

def test_overdue_fine_on_late_return(lib_db):
    settings.set_setting("fine_daily_rate", 0.50)
    b = _book()
    loan = lib.issue(b.book_id, lib_db.s1, loaned_on=_today(-20),
                     due_on=_today(-10))
    lib.return_loan(loan.loan_id, returned_on=_today())
    bal = fines.student_balance(lib_db.s1)
    assert bal == 5.00  # 10 days * 0.50


def test_overdue_fine_capped(lib_db):
    settings.set_setting("fine_daily_rate", 1.00)
    settings.set_setting("fine_max_per_loan", 3.00)
    b = _book()
    loan = lib.issue(b.book_id, lib_db.s1, loaned_on=_today(-40),
                     due_on=_today(-30))
    lib.return_loan(loan.loan_id, returned_on=_today())
    assert fines.student_balance(lib_db.s1) == 3.00


def test_waive_and_pay(lib_db):
    f = fines.create_fine(lib_db.s1, "Manual", 10.00)
    fines.pay_fine(f.fine_id, 4.00)
    assert fines.student_balance(lib_db.s1) == 6.00
    fines.waive_fine(f.fine_id, reason="goodwill")
    assert fines.student_balance(lib_db.s1) == 0.00
    assert fines.get_fine(f.fine_id).status == "Paid"


def test_waive_requires_reason(lib_db):
    f = fines.create_fine(lib_db.s1, "Manual", 5.00)
    with pytest.raises(lib.ValidationError, match="reason"):
        fines.waive_fine(f.fine_id, reason="")


def test_return_damaged_raises_fee(lib_db):
    settings.set_setting("damaged_fee", 7.50)
    b = _book()
    loan = lib.issue(b.book_id, lib_db.s1)
    out = lib.return_damaged(loan.loan_id)
    assert out.status == "Returned Damaged"
    assert fines.student_balance(lib_db.s1) == 7.50
    assert lib.get_book(b.book_id).copies_available == 2


def test_mark_lost_raises_fee(lib_db):
    settings.set_setting("lost_fee", 12.00)
    b = _book(copies_total=1, copies_available=1)
    loan = lib.issue(b.book_id, lib_db.s1)
    lib.mark_lost(loan.loan_id)
    assert fines.student_balance(lib_db.s1) == 12.00


# ── Bulk ops (7) ──────────────────────────────────────────────────

def test_bulk_return(lib_db):
    b1, b2 = _book(), _book(title="Second")
    l1 = lib.issue(b1.book_id, lib_db.s1)
    l2 = lib.issue(b2.book_id, lib_db.s1)
    res = lib.bulk_return([l1.loan_id, l2.loan_id, 999])
    assert res[l1.loan_id] == "ok" and res[l2.loan_id] == "ok"
    assert "No loan" in res[999]


# ── Reservations (11-14) ──────────────────────────────────────────

def test_reserve_ready_when_copy_free(lib_db):
    b = _book(copies_total=1, copies_available=1)
    r = holds.reserve(b.book_id, lib_db.s1)
    # A copy was free, so the hold should be Ready immediately.
    assert holds.get_reservation(r.reservation_id).status == "Ready"
    assert lib.get_book(b.book_id).copies_available == 0


def test_waitlist_and_promotion(lib_db):
    b = _book(copies_total=1, copies_available=1)
    loan = lib.issue(b.book_id, lib_db.s1)  # only copy now out
    r1 = holds.reserve(b.book_id, lib_db.s2)
    assert holds.get_reservation(r1.reservation_id).status == "Waiting"
    assert holds.waitlist_position(r1.reservation_id) == 1
    lib.return_loan(loan.loan_id)
    # Returning promotes the waiting hold to Ready.
    assert holds.get_reservation(r1.reservation_id).status == "Ready"


def test_hold_expiry(lib_db):
    settings.set_setting("hold_shelf_days", 3)
    b = _book(copies_total=1, copies_available=1)
    r = holds.reserve(b.book_id, lib_db.s1)  # Ready, expires +3
    n = holds.expire_holds(as_of=_today(10))
    assert n == 1
    assert holds.get_reservation(r.reservation_id).status == "Expired"
    assert lib.get_book(b.book_id).copies_available == 1


def test_collect_reservation_creates_loan(lib_db):
    b = _book(copies_total=1, copies_available=1)
    r = holds.reserve(b.book_id, lib_db.s1)  # Ready
    res, loan = holds.collect_reservation(r.reservation_id)
    assert res.status == "Collected"
    assert loan.status == "Active"
    assert lib.get_book(b.book_id).copies_available == 0


def test_recall_shortens_due(lib_db):
    b = _book(copies_total=1, copies_available=1)
    loan = lib.issue(b.book_id, lib_db.s1, due_on=_today(14))
    out = holds.recall(loan.loan_id)
    assert out.due_on == _today()
    assert "Recalled" in (out.notes or "")


# ── Catalogue: ISBN + tags (21,24) ────────────────────────────────

def test_isbn_lookup_pluggable(lib_db):
    from education_system.sixthform_system.modules.domain.academics.library import (
        library_catalog as cat,
    )
    cat.set_isbn_resolver(lambda isbn: {
        "title": "Found Book", "author": "A. Author",
        "publisher": "Pub", "publication_year": 2020})
    found = cat.lookup_isbn("9780131103627")
    assert found["title"] == "Found Book"
    b = cat.create_book_from_isbn("9780131103627", item_type="Textbook")
    assert b.title == "Found Book" and b.item_type == "Textbook"


def test_tags_roundtrip(lib_db):
    from education_system.sixthform_system.modules.domain.academics.library import (
        library_catalog as cat,
    )
    b = _book()
    cat.set_tags(b.book_id, ["Revision", "  revision ", "A-Level"])
    assert cat.tags_for_book(b.book_id) == ["a-level", "revision"]
    assert cat.find_books_by_tag("A-Level")[0].book_id == b.book_id


# ── Notifications (15-20) ─────────────────────────────────────────

def test_due_soon_sweep_dedupes(lib_db):
    settings.set_setting("due_soon_days", 3)
    b = _book()
    lib.issue(b.book_id, lib_db.s1, due_on=_today(2))
    assert notifs.run_due_soon_sweep() == 1
    # Running again sends nothing (deduped).
    assert notifs.run_due_soon_sweep() == 0


def test_overdue_sweep_escalates(lib_db):
    b = _book()
    lib.issue(b.book_id, lib_db.s1, loaned_on=_today(-20),
              due_on=_today(-3))
    assert notifs.run_overdue_sweep() == 1
    # Same stage again -> deduped.
    assert notifs.run_overdue_sweep() == 0


def test_fine_issued_notification_logged(lib_db):
    fines.create_fine(lib_db.s1, "Manual", 5.00)
    with lib._connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM library_notifications "
            "WHERE kind = 'fine_issued'").fetchone()[0]
    assert n == 1
    assert notifs.run_due_soon_sweep is not None


# ── CLI glue ──────────────────────────────────────────────────────

def test_cli_raise_fine_flow(lib_db, monkeypatch):
    """Drive the raise-fine CLI flow through the input() layer."""
    from education_system.sixthform_system.modules.domain.academics.library import (
        library_cli as cli,
    )
    answers = iter([
        "1",        # _pick_student -> first student
        "Manual",   # reason (matches default)
        "7.50",     # amount
        "",         # note
        "",         # _pause
    ])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))
    cli.raise_fine_flow()
    # First student listed is whichever sorts first; just assert the
    # total raised across both students is 7.50.
    total = sum(fines.student_balance(s)
                for s in (lib_db.s1, lib_db.s2))
    assert total == 7.50


# ── GUI construction (requires a display) ─────────────────────────

@pytest.mark.skipif(_NO_DISPLAY, reason="no DISPLAY for Tk")
def test_gui_tabs_and_dialogs_build(lib_db):
    """Build every library tab and key dialog against a real Tk root."""
    import tkinter as tk
    from tkinter import ttk
    from education_system.sixthform_system.modules.domain.academics.library import (
        library_views as v,
    )
    # Seed a bit of data so refresh() has rows to render.
    b = _book()
    lib.issue(b.book_id, lib_db.s1)
    fines.create_fine(lib_db.s2, "Manual", 3.00)

    root = tk.Tk()
    root.withdraw()
    try:
        nb = ttk.Notebook(root)
        for tab_cls in (v.BooksTab, v.LoansTab, v.ReservationsTab,
                        v.FinesTab, v.AdminTab, v.SummaryTab):
            tab = tab_cls(nb)
            if hasattr(tab, "refresh"):
                tab.refresh()
        # Dialogs build without error.
        v.BookDialog(root, existing=None, on_save=lambda: None)
        v.ReserveDialog(root, on_save=lambda: None)
        v.RaiseFineDialog(root, on_save=lambda: None)
        v.PolicyDialog(root, item_type="Book", on_save=lambda: None)
        root.update_idletasks()
    finally:
        root.destroy()
