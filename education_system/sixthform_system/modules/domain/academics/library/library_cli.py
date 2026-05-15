"""CLI flows for Sixth Form Library."""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _td
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.academics.library import (
    library as data,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.sixthform_system.modules.domain.academics.library.library import (
    BOOK_STATUSES,
    Book,
    DEFAULT_BOOK_STATUS,
    DEFAULT_ITEM_TYPE,
    DEFAULT_LOAN_DAYS,
    ITEM_TYPES,
    Loan,
    LOAN_STATUSES,
    MAX_RENEWALS,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_book() -> Book:
    rows = data.list_books()
    if not rows:
        print("    No books yet.")
        raise _UserAbort
    print("\n  Books:")
    for i, b in enumerate(rows, 1):
        print(f"    {i:>3}) #{b.book_id}  "
              f"{b.title[:32]:<32}  by {(b.author or '—')[:20]:<20}  "
              f"avail={b.copies_available}/{b.copies_total}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((b for b in rows if b.book_id == n), None)
            if match:
                return match
        print("    No matching book.")


def _pick_loan() -> Loan:
    rows = data.list_loans()
    if not rows:
        print("    No loans yet.")
        raise _UserAbort
    print("\n  Loans:")
    for i, l in enumerate(rows, 1):
        marker = "!" if l.is_overdue else " "
        print(f"    {i:>3}){marker}#{l.loan_id}  book={l.book_id}  "
              f"student={l.student_id}  due={l.due_on}  "
              f"[{l.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((l for l in rows if l.loan_id == n), None)
            if match:
                return match
        print("    No matching loan.")


def _pick_student() -> str:
    rows = student_data.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or student id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
            continue
        match = next((s for s in rows
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_books(rows: list[Book]) -> None:
    if not rows:
        print("\n  (no books)")
        return
    print()
    print(f"  {'#':>4}  {'Title':<32}  {'Author':<20}  "
          f"{'Type':<14}  {'Avail':>8}  Status")
    print("  " + "-" * 100)
    for b in rows:
        avail = f"{b.copies_available}/{b.copies_total}"
        print(f"  {b.book_id:>4}  {b.title[:32]:<32}  "
              f"{(b.author or '—')[:20]:<20}  "
              f"{b.item_type[:14]:<14}  {avail:>8}  {b.status}")
    print(f"\n  {len(rows)} book(s).")


def _print_loans(rows: list[Loan]) -> None:
    if not rows:
        print("\n  (no loans)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    titles: dict[int, str] = {b.book_id: b.title
                                for b in data.list_books()}
    print()
    print(f"  {'#':>4}  {'Book':<26}  {'Student':<10}  "
          f"{'Name':<22}  {'Loaned':<10}  {'Due':<10}  Status")
    print("  " + "-" * 110)
    for l in rows:
        flag = " !" if l.is_overdue else "  "
        print(f"  {l.loan_id:>4}{flag}"
              f"{titles.get(l.book_id, f'#{l.book_id}')[:26]:<26}  "
              f"{l.student_id:<10}  "
              f"{names.get(l.student_id, '?')[:22]:<22}  "
              f"{l.loaned_on:<10}  {l.due_on:<10}  {l.status}"
              + (f"  ({l.days_overdue}d)" if l.is_overdue else ""))
    print(f"\n  {len(rows)} loan(s).")


# ── Book flows ────────────────────────────────────────────────────

def list_books_flow() -> None:
    print("\n═══ All Books ═══")
    _print_books(data.list_books())
    _pause()


def search_books_flow() -> None:
    print("\n═══ Search Books ═══")
    try:
        q = _input("Search (title/author/ISBN/keyword)") or None
        subject = _input("Subject area") or None
        itype = _input(f"Type ({'/'.join(ITEM_TYPES[:4])}…)") or None
        avail = _input("Available only? (y/n)",
                          default="n").lower() in ("y", "yes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_books(search=q, subject_area=subject,
                                 item_type=itype,
                                 available_only=avail)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_books(rows)
    _pause()


def view_book_flow() -> None:
    print("\n═══ View Book ═══")
    try:
        b = _pick_book()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print()
    print(f"    #{b.book_id}  {b.title}")
    print(f"    Author       : {b.author or '—'}")
    print(f"    ISBN         : {b.isbn or '—'}")
    print(f"    Publisher    : {b.publisher or '—'}"
          + (f" ({b.publication_year})"
             if b.publication_year else ""))
    print(f"    Edition      : {b.edition or '—'}")
    print(f"    Type         : {b.item_type}")
    print(f"    Subject area : {b.subject_area or '—'}")
    print(f"    Keywords     : {b.keywords or '—'}")
    print(f"    Location     : {b.location or '—'}")
    print(f"    Copies       : {b.copies_available}/{b.copies_total} "
          f"available")
    print(f"    Status       : {b.status}")
    if b.description:
        print()
        print("    Description:")
        for line in b.description.splitlines():
            print(f"      {line}")
    loans = data.list_loans(book_id=b.book_id, active_only=True)
    if loans:
        names = {s.student_id: s.full_name
                  for s in student_data.list_students()}
        print()
        print(f"    Currently on loan ({len(loans)}):")
        for l in loans:
            flag = " (OVERDUE)" if l.is_overdue else ""
            print(f"      #{l.loan_id}  {l.student_id}  "
                  f"{names.get(l.student_id, '?')[:20]}  "
                  f"due {l.due_on}{flag}")
    _pause()


def _collect_book_form(existing: Book | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["author"] = _input(
        "Author",
        default=(existing.author or "") if is_edit else "")
    payload["isbn"] = _input(
        "ISBN",
        default=(existing.isbn or "") if is_edit else "")
    payload["publisher"] = _input(
        "Publisher",
        default=(existing.publisher or "") if is_edit else "")
    payload["publication_year"] = _input(
        "Publication year",
        default=(str(existing.publication_year)
                  if is_edit and existing.publication_year
                  else ""))
    payload["edition"] = _input(
        "Edition",
        default=(existing.edition or "") if is_edit else "")
    payload["item_type"] = _pick_from(
        "Item type", list(ITEM_TYPES),
        default=(existing.item_type if is_edit
                  else DEFAULT_ITEM_TYPE))
    payload["subject_area"] = _input(
        "Subject area",
        default=(existing.subject_area or "") if is_edit else "")
    payload["keywords"] = _input(
        "Keywords",
        default=(existing.keywords or "") if is_edit else "")
    payload["location"] = _input(
        "Shelf location",
        default=(existing.location or "") if is_edit else "")
    payload["copies_total"] = _input(
        "Copies total",
        default=(str(existing.copies_total)
                  if is_edit else "1"))
    if not is_edit:
        payload["copies_available"] = payload["copies_total"]
    else:
        payload["copies_available"] = _input(
            "Copies available",
            default=str(existing.copies_available))
    payload["status"] = _pick_from(
        "Status", list(BOOK_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_BOOK_STATUS))
    payload["description"] = _input(
        "Description",
        default=(existing.description or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_book() -> None:
    print("\n═══ New Book ═══")
    try:
        payload = _collect_book_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        b = data.create_book(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created book #{b.book_id} {b.title!r}")
    _pause()


def edit_book() -> None:
    print("\n═══ Edit Book ═══")
    try:
        b = _pick_book()
        payload = _collect_book_form(b)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_book(b.book_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{b.book_id}")
    _pause()


def set_book_status_flow() -> None:
    print("\n═══ Change Book Status ═══")
    try:
        b = _pick_book()
        new_status = _pick_from(
            "New status", list(BOOK_STATUSES), default=b.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_book_status(b.book_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{b.book_id} → {new_status}")
    _pause()


def delete_book_flow() -> None:
    print("\n═══ Delete Book ═══")
    try:
        b = _pick_book()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete book #{b.book_id}? "
              "Cascade-deletes its loans. Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_book(b.book_id):
        print(f"\n  ✓ Deleted #{b.book_id}")
    _pause()


# ── Loan flows ────────────────────────────────────────────────────

def list_loans_flow() -> None:
    print("\n═══ All Loans ═══")
    _print_loans(data.list_loans())
    _pause()


def list_active_loans() -> None:
    print("\n═══ Active Loans ═══")
    _print_loans(data.list_loans(active_only=True))
    _pause()


def list_overdue_loans() -> None:
    print("\n═══ Overdue Loans ═══")
    _print_loans(data.list_loans(overdue_only=True))
    _pause()


def issue_flow() -> None:
    print("\n═══ Issue Loan ═══")
    try:
        b = _pick_book()
        sid = _pick_student()
        loaned = _input("Loaned on (YYYY-MM-DD)",
                          default=_date.today().isoformat())
        try:
            default_due = (_date.fromisoformat(loaned)
                            + _td(days=DEFAULT_LOAN_DAYS)).isoformat()
        except ValueError:
            default_due = ""
        due = _input("Due on (YYYY-MM-DD)", default=default_due)
        issued_by = _input("Issued by")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        l = data.issue(b.book_id, sid,
                          loaned_on=loaned, due_on=due,
                          issued_by=issued_by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Issued loan #{l.loan_id} (due {l.due_on})")
    _pause()


def return_flow() -> None:
    print("\n═══ Return Loan ═══")
    try:
        l = _pick_loan()
        returned_by = _input("Returned by")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.return_loan(l.loan_id,
                           returned_by=returned_by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Returned #{l.loan_id}")
    _pause()


def renew_flow() -> None:
    print("\n═══ Renew Loan ═══")
    try:
        l = _pick_loan()
        ext = int(_input("Extension (days)",
                            default=str(DEFAULT_LOAN_DAYS)))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        upd = data.renew(l.loan_id, extension_days=ext)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Renewed #{l.loan_id}: new due {upd.due_on} "
          f"(renewals {upd.renewals_count}/{MAX_RENEWALS})")
    _pause()


def mark_lost_flow() -> None:
    print("\n═══ Mark Lost ═══")
    try:
        l = _pick_loan()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Mark loan #{l.loan_id} as Lost? "
              "Drops copies_total. Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        data.mark_lost(l.loan_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{l.loan_id} → Lost")
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student Loans ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_loans(student_id=sid)
    print(f"\n  Loans for {sid}:")
    _print_loans(rows)
    _pause()


def delete_loan_flow() -> None:
    print("\n═══ Delete Loan ═══")
    try:
        l = _pick_loan()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete loan #{l.loan_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_loan(l.loan_id):
        print(f"\n  ✓ Deleted #{l.loan_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Library Summary ═══")
    summ = data.summary()
    print(f"\n  Total books        : {summ.total_books}")
    print(f"  Total copies       : {summ.total_copies}")
    print(f"  Copies on loan     : {summ.copies_on_loan}")
    print(f"  Active loans       : {summ.active_loans}")
    print(f"  Overdue loans      : {summ.overdue_loans}")
    print(f"  Returned loans     : {summ.returned_loans}")
    print(f"  Distinct borrowers : {summ.distinct_borrowers}")
    print("\n  Books by status:")
    for s in BOOK_STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  Books by type:")
    for t in ITEM_TYPES:
        n = summ.by_item_type.get(t, 0)
        if n:
            print(f"    {t:<22} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List books",          list_books_flow),
    ("Search books",        search_books_flow),
    ("View book",           view_book_flow),
    ("New book",            new_book),
    ("Edit book",           edit_book),
    ("Change book status",  set_book_status_flow),
    ("Delete book",         delete_book_flow),
    ("─" * 6,               lambda: None),
    ("Active loans",        list_active_loans),
    ("Overdue loans",       list_overdue_loans),
    ("All loans",           list_loans_flow),
    ("Issue loan",          issue_flow),
    ("Return loan",         return_flow),
    ("Renew loan",          renew_flow),
    ("Mark lost",           mark_lost_flow),
    ("Per-student loans",   per_student_flow),
    ("Delete loan",         delete_loan_flow),
    ("─" * 6,               lambda: None),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── Library ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Library CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Library":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Library CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
