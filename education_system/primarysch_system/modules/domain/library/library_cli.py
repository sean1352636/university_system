"""CLI handlers for the library catalogue + loans."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.library import (
    library as data,
)
from education_system.primarysch_system.modules.domain.library.library import (
    CATEGORIES, LOAN_STATUSES,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_books(rows: list[data.Book]) -> None:
    if not rows:
        print("  (no books)")
        return
    print(f"  {'ID':<4} {'Title':<32} {'Author':<22} {'Cat':<11} "
          f"{'Yr':<4} {'Avail/Tot':<10} {'ISBN':<14} {'Act':<3}")
    print(f"  {'-'*4} {'-'*32} {'-'*22} {'-'*11} {'-'*4} {'-'*10} "
          f"{'-'*14} {'-'*3}")
    for b in rows:
        copies = f"{b.copies_available}/{b.copies_total}"
        print(f"  {b.book_id:<4} {b.title[:32]:<32} "
              f"{(b.author or '-')[:22]:<22} {b.category[:11]:<11} "
              f"{(str(b.year_published) if b.year_published else '-'):<4} "
              f"{copies:<10} {(b.isbn or '-')[:14]:<14} "
              f"{('Y' if b.is_active else 'N'):<3}")


def _print_loans(rows: list[data.Loan]) -> None:
    if not rows:
        print("  (no loans)")
        return
    print(f"  {'ID':<4} {'Date':<10} {'Due':<10} {'Returned':<10} "
          f"{'Pupil':<10} {'Book':<28} {'Status':<9} {'Days OD':<7}")
    print(f"  {'-'*4} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*28} "
          f"{'-'*9} {'-'*7}")
    for l in rows:
        od = l.days_overdue
        print(f"  {l.loan_id:<4} {l.loan_date:<10} {l.due_date:<10} "
              f"{(l.returned_date or '-'):<10} {l.pupil_id:<10} "
              f"{(l.book_title or '?')[:28]:<28} {l.status:<9} "
              f"{(str(od) if od else '-'):<7}")


@_safe
def open_library() -> None:
    logger.debug("CLI: open_library")
    while True:
        o = data.overview()
        print("\n  ── Library ──")
        print(f"  Titles: {o['books_total']}  active: {o['books_active']}  "
              f"copies: {o['copies_avail']}/{o['copies_total']}")
        print("  Loans: "
              + "   ".join(f"{s}: {o['loans'][s]}" for s in LOAN_STATUSES))
        print("\n  Catalogue")
        print("    1) Add book")
        print("    2) List / search books")
        print("    3) Edit book")
        print("    4) Toggle book active")
        print("    5) Delete book")
        print("  Loans")
        print("    6) Lend book")
        print("    7) Return loan")
        print("    8) Mark loan lost")
        print("    9) List loans")
        print("   10) Pupil loan history")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_book, "2": _list_books, "3": _edit_book,
            "4": _toggle_book, "5": _delete_book,
            "6": _lend, "7": _return, "8": _lost,
            "9": _list_loans, "10": _pupil_loans,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_book(existing: data.Book | None = None) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {}
    f["title"] = ask("Title", existing.title if existing else None)
    f["author"] = ask("Author",
                       existing.author if existing else None)
    f["isbn"]  = ask("ISBN",
                      existing.isbn if existing else None)
    f["category"] = ask(f"Category ({'/'.join(CATEGORIES)})",
                         existing.category if existing else "Fiction")
    f["year_published"] = ask("Year published",
                                existing.year_published if existing
                                else None)
    f["copies_total"] = ask(
        "Total copies",
        existing.copies_total if existing else 1)
    f["location"] = ask("Shelf / location",
                         existing.location if existing else None)
    if existing:
        act = ask("Active? (y/n)",
                  "y" if existing.is_active else "n")
        f["is_active"] = act.lower().startswith("y")
    f["notes"] = ask("Notes", existing.notes if existing else None)
    return f


@_safe
def _new_book() -> None:
    print("\n  ── Add Book ──")
    fields = _collect_book()
    b = data.create_book(fields)
    print(f"  Added book #{b.book_id} {b.title} "
          f"({b.copies_total} copies)")


@_safe
def _list_books() -> None:
    only_active = _prompt("  Active only? (y/N): ").lower().startswith("y")
    only_avail = _prompt(
        "  Available copies only? (y/N): ").lower().startswith("y")
    cat = _prompt(
        f"  Category ({'/'.join(CATEGORIES)}, blank): ") or None
    q = _prompt("  Search (title/author/isbn, blank ok): ") or None
    rows = data.list_books(active_only=only_active,
                            available_only=only_avail,
                            category=cat, query=q)
    print(f"\n  {len(rows)} book(s):")
    _print_books(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_book_id() -> int | None:
    raw = _prompt("  Book ID: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("  Book ID must be a number.")
        return None


@_safe
def _edit_book() -> None:
    bid = _ask_book_id()
    if bid is None:
        return
    existing = data.get_book(bid)
    if existing is None:
        print("  No book with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_book(existing)
    b = data.update_book(bid, fields)
    print(f"  Updated book #{b.book_id} (copies "
          f"{b.copies_available}/{b.copies_total})")


@_safe
def _toggle_book() -> None:
    bid = _ask_book_id()
    if bid is None:
        return
    b = data.toggle_active(bid)
    print(f"  {b.title} is now "
          f"{'active' if b.is_active else 'inactive'}.")


@_safe
def _delete_book() -> None:
    bid = _ask_book_id()
    if bid is None:
        return
    b = data.get_book(bid)
    if b is None:
        print("  No book with that ID.")
        return
    confirm = _prompt(
        f"  Delete '{b.title}' and its loan history? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    if data.delete_book(bid):
        print(f"  Deleted book #{bid}.")


@_safe
def _lend() -> None:
    bid = _ask_book_id()
    if bid is None:
        return
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    ldate = _prompt("  Loan date (blank = today): ") or None
    ddate = _prompt("  Due date (blank = +14 days): ") or None
    notes = _prompt("  Notes (blank ok): ") or None
    loan = data.lend(bid, pid, loan_date=ldate, due_date=ddate,
                      notes=notes)
    print(f"  Loan #{loan.loan_id}: {loan.book_title} -> {loan.pupil_id}"
          f" (due {loan.due_date})")


def _ask_loan_id() -> int | None:
    raw = _prompt("  Loan ID: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("  Loan ID must be a number.")
        return None


@_safe
def _return() -> None:
    lid = _ask_loan_id()
    if lid is None:
        return
    rdate = _prompt("  Returned date (blank = today): ") or None
    notes = _prompt("  Notes (blank ok): ") or None
    rec = data.return_loan(lid, returned_date=rdate, notes=notes)
    print(f"  Returned loan #{rec.loan_id} (book: {rec.book_title})")


@_safe
def _lost() -> None:
    lid = _ask_loan_id()
    if lid is None:
        return
    confirm = _prompt(
        "  Marking as Lost will reduce the book's total copies. "
        "Continue? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    notes = _prompt("  Notes (blank ok): ") or None
    rec = data.mark_lost(lid, notes=notes)
    print(f"  Loan #{rec.loan_id} marked Lost.")


@_safe
def _list_loans() -> None:
    print(f"  Status ({'/'.join(LOAN_STATUSES)}) or blank.")
    status = _prompt("  Status: ") or None
    rows = data.list_loans(status=status)
    print(f"\n  {len(rows)} loan(s):")
    _print_loans(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _pupil_loans() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    rows = data.list_loans(pupil_id=pid)
    print(f"\n  {len(rows)} loan(s) for {pid}:")
    _print_loans(rows)
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Library": open_library}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching library CLI label: %s", label)
    handler()
    return True
