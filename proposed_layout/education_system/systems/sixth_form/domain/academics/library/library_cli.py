"""CLI flows for Sixth Form Library."""

from __future__ import annotations

import logging
from datetime import date as _date, timedelta as _td
from typing import Any, Callable
from education_system.systems.sixth_form.domain.academics.library import (
    library as data,
    library_settings as settings,
    library_fines as fines,
    library_reservations as holds,
    library_notifications as notifs,
    library_catalog as catalog,
    library_copies as copies,
    library_reading_lists as reading,
    library_acquisitions as acq,
    library_reports as reports,
    library_eresources as eresources,
    library_study as study,
    library_kiosk as kiosk,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.academics.library.library import (
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
    payload["classification"] = _input(
        "Classification (e.g. Dewey)",
        default=(existing.classification or "") if is_edit else "")
    payload["series"] = _input(
        "Series",
        default=(existing.series or "") if is_edit else "")
    payload["volume"] = _input(
        "Volume",
        default=(existing.volume or "") if is_edit else "")
    payload["cover_image_url"] = _input(
        "Cover image URL/path",
        default=(existing.cover_image_url or "") if is_edit else "")
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
        # Block reasons (overdue items / unpaid fines / loan limit) can
        # be overridden at librarian discretion; hard rules can't.
        if any(k in str(e) for k in ("overdue", "owes", "limit")):
            if _input("Override and issue anyway? (y/n)",
                      default="n").lower().startswith("y"):
                try:
                    l = data.issue(b.book_id, sid, loaned_on=loaned,
                                   due_on=due,
                                   issued_by=issued_by or None,
                                   override_blocks=True)
                    print(f"\n  ✓ Issued loan #{l.loan_id} "
                          f"(due {l.due_on}) [override]")
                    _pause()
                    return
                except ValidationError as e2:
                    print(f"\n  ✗ {e2}")
        _pause()
        return
    print(f"\n  ✓ Issued loan #{l.loan_id} (due {l.due_on})")
    _pause()


def return_flow() -> None:
    print("\n═══ Return Loan ═══")
    try:
        l = _pick_loan()
        returned_by = _input("Returned by")
        returned_on = _input(
            "Returned on (YYYY-MM-DD, blank = today)")
        damaged = _input("Item damaged? (y/n)",
                         default="n").lower().startswith("y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        if damaged:
            data.return_damaged(
                l.loan_id, returned_by=returned_by or None,
                returned_on=returned_on or None)
        else:
            data.return_loan(
                l.loan_id, returned_by=returned_by or None,
                returned_on=returned_on or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    verb = "Returned (damaged)" if damaged else "Returned"
    print(f"\n  ✓ {verb} #{l.loan_id}")
    bal = fines.student_balance(l.student_id)
    if bal > 0:
        print(f"  Student {l.student_id} now owes {bal:.2f} in fines.")
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


# ── Catalogue: ISBN + tags ────────────────────────────────────────

def new_book_from_isbn() -> None:
    print("\n═══ New Book from ISBN ═══")
    try:
        isbn = _input("ISBN", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        found = catalog.lookup_isbn(isbn)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not found:
        print("\n  No catalogue entry found for that ISBN. "
              "Add it manually via 'New book'.")
        _pause()
        return
    print("\n  Found:")
    for k, v in found.items():
        print(f"    {k:<18}: {v}")
    if _input("Add this book? (y/n)",
              default="y").lower().startswith("y"):
        try:
            b = catalog.create_book_from_isbn(isbn)
        except ValidationError as e:
            print(f"\n  ✗ {e}")
            _pause()
            return
        print(f"\n  ✓ Created book #{b.book_id} {b.title!r}")
    _pause()


def edit_tags_flow() -> None:
    print("\n═══ Edit Tags ═══")
    try:
        b = _pick_book()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    current = catalog.tags_for_book(b.book_id)
    print(f"\n  Current tags: {', '.join(current) or '(none)'}")
    try:
        raw = _input("New tags (comma-separated, blank to clear)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    names = [t for t in (raw.split(",") if raw else []) if t.strip()]
    stored = catalog.set_tags(b.book_id, names)
    print(f"\n  ✓ Tags: {', '.join(stored) or '(none)'}")
    _pause()


def browse_by_tag_flow() -> None:
    print("\n═══ Browse by Tag ═══")
    tags = catalog.all_tags()
    if not tags:
        print("\n  No tags yet.")
        _pause()
        return
    print("\n  Tags:")
    for name, n in tags:
        print(f"    {name:<24} ({n})")
    try:
        pick = _input("Tag to browse", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_books(catalog.find_books_by_tag(pick))
    _pause()


# ── Fines ──────────────────────────────────────────────────────────

def _pick_fine(*, student_id: str | None = None,
               open_only: bool = True) -> fines.Fine:
    rows = fines.list_fines(student_id=student_id, open_only=open_only)
    if not rows:
        print("    No matching fines.")
        raise _UserAbort
    print("\n  Fines:")
    for i, f in enumerate(rows, 1):
        print(f"    {i:>3}) #{f.fine_id}  {f.student_id}  "
              f"{f.reason:<8}  owed {f.outstanding:.2f}  [{f.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((f for f in rows if f.fine_id == n), None)
            if match:
                return match
        print("    No matching fine.")


def _print_fines(rows: list) -> None:
    if not rows:
        print("\n  (no fines)")
        return
    print(f"\n  {'ID':>4}  {'Student':<10} {'Reason':<8} "
          f"{'Amount':>8} {'Owed':>8}  Status")
    for f in rows:
        print(f"  {f.fine_id:>4}  {f.student_id:<10} {f.reason:<8} "
              f"{f.amount:>8.2f} {f.outstanding:>8.2f}  {f.status}")


def list_fines_flow() -> None:
    print("\n═══ Fines ═══")
    only_open = _input("Open fines only? (y/n)",
                       default="y").lower().startswith("y")
    _print_fines(fines.list_fines(open_only=only_open))
    _pause()


def raise_fine_flow() -> None:
    print("\n═══ Raise Manual Fine ═══")
    try:
        sid = _pick_student()
        reason = _pick_from("Reason", list(fines.FINE_REASONS),
                            default="Manual")
        amount = float(_input("Amount", allow_empty=False))
        note = _input("Note")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        f = fines.create_fine(sid, reason, amount, note=note or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Raised fine #{f.fine_id} for {amount:.2f}")
    _pause()


def pay_fine_flow() -> None:
    print("\n═══ Pay Fine ═══")
    try:
        sid = _pick_student()
        f = _pick_fine(student_id=sid)
        amount = float(_input("Amount to pay",
                              default=f"{f.outstanding:.2f}"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        out = fines.pay_fine(f.fine_id, amount)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Fine #{out.fine_id} now {out.status} "
          f"(owed {out.outstanding:.2f})")
    _pause()


def waive_fine_flow() -> None:
    print("\n═══ Waive Fine ═══")
    try:
        sid = _pick_student()
        f = _pick_fine(student_id=sid)
        reason = _input("Reason for waiver", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = fines.waive_fine(f.fine_id, reason=reason)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Fine #{out.fine_id} now {out.status}")
    _pause()


def student_balance_flow() -> None:
    print("\n═══ Student Fine Balance ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  {sid} owes {fines.student_balance(sid):.2f} in fines.")
    _print_fines(fines.list_fines(student_id=sid, open_only=True))
    _pause()


# ── Reservations / holds ───────────────────────────────────────────

def _pick_reservation(*, status: str | None = None) -> holds.Reservation:
    rows = holds.list_reservations(status=status, open_only=status is None)
    if not rows:
        print("    No matching reservations.")
        raise _UserAbort
    print("\n  Reservations:")
    for i, r in enumerate(rows, 1):
        pos = holds.waitlist_position(r.reservation_id)
        pos_s = f" #{pos} in queue" if pos else ""
        print(f"    {i:>3}) res#{r.reservation_id}  book={r.book_id}  "
              f"{r.student_id}  [{r.status}]{pos_s}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                          if r.reservation_id == n), None)
            if match:
                return match
        print("    No matching reservation.")


def list_reservations_flow() -> None:
    print("\n═══ Reservations ═══")
    rows = holds.list_reservations(open_only=True)
    if not rows:
        print("\n  (no open reservations)")
        _pause()
        return
    for r in rows:
        pos = holds.waitlist_position(r.reservation_id)
        pos_s = f"  queue #{pos}" if pos else ""
        print(f"  res#{r.reservation_id}  book={r.book_id}  "
              f"{r.student_id}  [{r.status}]"
              f"  expires {r.expires_on or '—'}{pos_s}")
    _pause()


def reserve_flow() -> None:
    print("\n═══ Place Reservation ═══")
    try:
        b = _pick_book()
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = holds.reserve(b.book_id, sid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if r.status == "Ready":
        print(f"\n  ✓ Reservation #{r.reservation_id} ready to collect "
              f"(by {r.expires_on}).")
    else:
        pos = holds.waitlist_position(r.reservation_id)
        print(f"\n  ✓ Reservation #{r.reservation_id} placed — "
              f"position {pos} in the queue.")
    _pause()


def cancel_reservation_flow() -> None:
    print("\n═══ Cancel Reservation ═══")
    try:
        r = _pick_reservation()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        holds.cancel_reservation(r.reservation_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Reservation #{r.reservation_id} cancelled")
    _pause()


def collect_reservation_flow() -> None:
    print("\n═══ Collect Hold ═══")
    try:
        r = _pick_reservation(status="Ready")
        issued_by = _input("Issued by")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        _res, loan = holds.collect_reservation(
            r.reservation_id, issued_by=issued_by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Collected as loan #{loan.loan_id} (due {loan.due_on})")
    _pause()


def expire_holds_flow() -> None:
    print("\n═══ Expire Stale Holds ═══")
    n = holds.expire_holds()
    print(f"\n  ✓ Expired {n} hold(s) past their collect-by date.")
    _pause()


def recall_flow() -> None:
    print("\n═══ Recall Loan ═══")
    try:
        l = _pick_loan()
        grace = int(_input("Grace days before due", default="0"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        out = holds.recall(l.loan_id, grace_days=grace)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Loan #{out.loan_id} recalled — due now {out.due_on}")
    _pause()


# ── Bulk operations ────────────────────────────────────────────────

def _collect_loan_ids() -> list[int]:
    raw = _input("Loan IDs (comma-separated)", allow_empty=False)
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def bulk_return_flow() -> None:
    print("\n═══ Bulk Return ═══")
    try:
        ids = _collect_loan_ids()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    results = data.bulk_return(ids)
    for lid, msg in results.items():
        mark = "✓" if msg == "ok" else "✗"
        print(f"    {mark} #{lid}: {msg}")
    _pause()


def bulk_renew_flow() -> None:
    print("\n═══ Bulk Renew ═══")
    try:
        ids = _collect_loan_ids()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    results = data.bulk_renew(ids)
    for lid, msg in results.items():
        mark = "✓" if msg == "ok" else "✗"
        print(f"    {mark} #{lid}: {msg}")
    _pause()


# ── Notifications ──────────────────────────────────────────────────

def due_soon_sweep_flow() -> None:
    print("\n═══ Send Due-Soon Reminders ═══")
    n = notifs.run_due_soon_sweep()
    print(f"\n  ✓ Sent {n} due-soon reminder(s).")
    _pause()


def overdue_sweep_flow() -> None:
    print("\n═══ Send Overdue Notices ═══")
    n = notifs.run_overdue_sweep()
    print(f"\n  ✓ Sent {n} overdue notice(s).")
    _pause()


def daily_digest_flow() -> None:
    print("\n═══ Send Daily Digest ═══")
    notifs.daily_digest()
    print(f"\n  ✓ Digest sent to {notifs.DIGEST_INBOX}.")
    _pause()


# ── Settings & policies ────────────────────────────────────────────

def settings_flow() -> None:
    print("\n═══ Library Settings ═══")
    current = settings.all_settings()
    keys = list(current)
    for i, k in enumerate(keys, 1):
        print(f"    {i:>2}) {k:<28} = {current[k]}")
    try:
        raw = _input("Edit which # (blank to exit)")
    except _UserAbort:
        return
    if not raw.isdigit() or not (1 <= int(raw) <= len(keys)):
        return
    key = keys[int(raw) - 1]
    try:
        val = _input(f"New value for {key}", allow_empty=False)
        settings.set_setting(key, val)
    except (ValidationError, _UserAbort) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {key} = {settings.get_setting(key)}")
    _pause()


def policies_flow() -> None:
    print("\n═══ Loan Policies ═══")
    pols = settings.list_policies()
    print(f"\n  {'Item type':<16} {'Days':>5} {'Renewals':>9} "
          f"{'Borrowable':>11}")
    for p in pols:
        print(f"  {p.item_type:<16} {p.loan_days:>5} "
              f"{p.max_renewals:>9} {str(p.borrowable):>11}")
    try:
        itype = _pick_from("Edit policy for", list(ITEM_TYPES))
        days = _input("Loan days",
                      default=str(settings.get_policy(itype).loan_days))
        rens = _input("Max renewals",
                      default=str(settings.get_policy(itype).max_renewals))
        borrow = _input("Borrowable? (y/n)",
                        default="y" if settings.get_policy(itype).borrowable
                        else "n")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        settings.set_policy(
            itype, loan_days=int(days), max_renewals=int(rens),
            borrowable=borrow.lower().startswith("y"))
    except (ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated policy for {itype}")
    _pause()


# ── Sub-menu helper ────────────────────────────────────────────────

def _run_submenu(title: str,
                 items: list[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(items, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("  Invalid selection.")
            continue
        try:
            items[int(choice) - 1][1]()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Library submenu handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


# ── Copies / barcodes / stock-take ─────────────────────────────────

def copies_list_flow() -> None:
    b = _pick_book()
    rows = copies.list_copies(book_id=b.book_id)
    if not rows:
        print("\n  (no registered copies)")
    else:
        print(f"\n  Copies of {b.title!r}:")
        for c in rows:
            print(f"    #{c.copy_id}  barcode={c.barcode or '—':<14} "
                  f"{c.condition:<9} [{c.status}]")
    _pause()


def copies_add_flow() -> None:
    b = _pick_book()
    barcode = _input("Barcode (blank for none)")
    condition = _pick_from("Condition", list(copies.COPY_CONDITIONS),
                           default="Good")
    acquired = _input("Acquired on (YYYY-MM-DD, blank=today)")
    try:
        c = copies.add_copy(b.book_id, barcode=barcode or None,
                            condition=condition,
                            acquired_on=acquired or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added copy #{c.copy_id}")
    _pause()


def copies_condition_flow() -> None:
    b = _pick_book()
    rows = copies.list_copies(book_id=b.book_id)
    if not rows:
        print("\n  No copies registered.")
        _pause()
        return
    for c in rows:
        print(f"    #{c.copy_id}  {c.condition:<9} [{c.status}]")
    cid = int(_input("Copy id", allow_empty=False))
    condition = _pick_from("New condition",
                           list(copies.COPY_CONDITIONS))
    note = _input("Note")
    try:
        copies.set_condition(cid, condition, note=note or None)
    except (ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Copy #{cid} → {condition}")
    _pause()


def copies_withdraw_flow() -> None:
    b = _pick_book()
    cid = int(_input("Copy id to withdraw", allow_empty=False))
    reason = _input("Reason", allow_empty=False)
    try:
        copies.withdraw_copy(cid, reason=reason)
    except (ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Withdrew copy #{cid}")
    _pause()


def withdraw_book_flow() -> None:
    b = _pick_book()
    reason = _input(f"Reason to withdraw {b.title!r}", allow_empty=False)
    try:
        copies.withdraw_book(b.book_id, reason=reason)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Withdrew book #{b.book_id}")
    _pause()


def barcode_issue_flow() -> None:
    barcode = _input("Scan/enter barcode", allow_empty=False)
    sid = _pick_student()
    try:
        l = copies.issue_by_barcode(barcode, sid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Issued loan #{l.loan_id} (due {l.due_on})")
    _pause()


def barcode_return_flow() -> None:
    barcode = _input("Scan/enter barcode", allow_empty=False)
    try:
        l = copies.return_by_barcode(barcode)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Returned loan #{l.loan_id}")
    _pause()


def stock_take_flow() -> None:
    print("\n═══ Stock-take ═══")
    rows = copies.stock_take_report()
    flagged = [r for r in rows if r["discrepancy"]]
    print(f"\n  {len(rows)} titles, {len(flagged)} with discrepancies:")
    for r in flagged:
        print(f"    #{r['book_id']} {r['title'][:30]:<30} "
              f"counter={r['copies_total']} registered={r['registered']} "
              f"missing={r['missing']}")
    _pause()


def copies_menu() -> None:
    _run_submenu("Copies & Stock", [
        ("List copies of a book", copies_list_flow),
        ("Add copy",              copies_add_flow),
        ("Set copy condition",    copies_condition_flow),
        ("Withdraw copy",         copies_withdraw_flow),
        ("Withdraw whole title",  withdraw_book_flow),
        ("Issue by barcode",      barcode_issue_flow),
        ("Return by barcode",     barcode_return_flow),
        ("Stock-take report",     stock_take_flow),
    ])


# ── Reading lists & class sets ─────────────────────────────────────

def reading_list_view_flow() -> None:
    lists = reading.list_reading_lists()
    if not lists:
        print("\n  No reading lists yet.")
        _pause()
        return
    for i, rl in enumerate(lists, 1):
        print(f"    {i:>2}) #{rl.list_id} {rl.title} "
              f"({rl.subject or '—'})")
    raw = _input("View list # (or id)", allow_empty=False)
    n = int(raw) if raw.isdigit() else 0
    chosen = (lists[n - 1] if 1 <= n <= len(lists)
              else next((x for x in lists if x.list_id == n), None))
    if not chosen:
        print("  No such list.")
        _pause()
        return
    items = reading.list_items(chosen.list_id)
    print(f"\n  {chosen.title} — {len(items)} item(s):")
    for it in items:
        print(f"    [{it.requirement:<11}] {it.book_title}"
              + (f"  (assignment {it.assignment_id})"
                 if it.assignment_id else ""))
    _pause()


def reading_list_create_flow() -> None:
    title = _input("List title", allow_empty=False)
    subject = _input("Subject")
    owner = _input("Owner (teacher)")
    year = _input("Academic year")
    rl = reading.create_reading_list(title, subject=subject or None,
                                     owner=owner or None,
                                     academic_year=year or None)
    print(f"\n  ✓ Created reading list #{rl.list_id}")
    _pause()


def reading_list_add_item_flow() -> None:
    lists = reading.list_reading_lists()
    if not lists:
        print("\n  Create a reading list first.")
        _pause()
        return
    for rl in lists:
        print(f"    #{rl.list_id} {rl.title}")
    lid = int(_input("List id", allow_empty=False))
    b = _pick_book()
    req = _pick_from("Requirement", list(reading.REQUIREMENTS),
                     default="Recommended")
    assignment = _input("Assignment id (optional)")
    try:
        reading.add_item(lid, b.book_id, requirement=req,
                         assignment_id=int(assignment) if assignment
                         else None)
    except (ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added {b.title!r} as {req}")
    _pause()


def class_sets_flow() -> None:
    rows = reading.list_class_sets()
    if not rows:
        print("\n  No class-set requests.")
    else:
        for cs in rows:
            print(f"    #{cs.set_id} {cs.book_title[:28]:<28} "
                  f"x{cs.copies_needed}  by {cs.needed_by or '—'} "
                  f"[{cs.status}]")
    _pause()


def request_class_set_flow() -> None:
    b = _pick_book()
    n = int(_input("Copies needed", allow_empty=False))
    subject = _input("Subject")
    needed_by = _input("Needed by (YYYY-MM-DD)")
    by = _input("Requested by")
    try:
        cs = reading.request_class_set(
            b.book_id, copies_needed=n, subject=subject or None,
            needed_by=needed_by or None, requested_by=by or None)
    except (ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Class-set request #{cs.set_id} created")
    _pause()


def reading_menu() -> None:
    _run_submenu("Reading Lists", [
        ("View reading lists",   reading_list_view_flow),
        ("Create reading list",  reading_list_create_flow),
        ("Add item to list",     reading_list_add_item_flow),
        ("Class-set requests",   class_sets_flow),
        ("Request class set",    request_class_set_flow),
    ])


# ── Acquisitions, suppliers, budgets ───────────────────────────────

def suppliers_flow() -> None:
    rows = acq.list_suppliers()
    if not rows:
        print("\n  No suppliers.")
    else:
        for s in rows:
            print(f"    #{s.supplier_id} {s.name} "
                  f"({s.email or '—'})")
    _pause()


def add_supplier_flow() -> None:
    name = _input("Supplier name", allow_empty=False)
    email = _input("Email")
    phone = _input("Phone")
    try:
        s = acq.add_supplier(name, email=email or None,
                             phone=phone or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added supplier #{s.supplier_id}")
    _pause()


def acquisitions_list_flow() -> None:
    rows = acq.list_acquisitions()
    if not rows:
        print("\n  No acquisitions.")
    else:
        for a in rows:
            print(f"    #{a.acq_id} {a.title[:30]:<30} x{a.quantity} "
                  f"@{a.unit_cost:.2f}  [{a.status}]")
    _pause()


def suggest_acquisition_flow() -> None:
    title = _input("Title", allow_empty=False)
    isbn = _input("ISBN")
    subject = _input("Subject area")
    qty = int(_input("Quantity", default="1"))
    cost = float(_input("Unit cost", default="0"))
    year = _input("Academic year")
    by = _input("Requested by")
    try:
        a = acq.suggest(title, isbn=isbn or None,
                        subject_area=subject or None, quantity=qty,
                        unit_cost=cost, academic_year=year or None,
                        requested_by=by or None)
    except (ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Suggestion #{a.acq_id} added")
    _pause()


def advance_acquisition_flow() -> None:
    rows = acq.list_acquisitions()
    if not rows:
        print("\n  No acquisitions.")
        _pause()
        return
    for a in rows:
        print(f"    #{a.acq_id} {a.title[:30]:<30} [{a.status}]")
    aid = int(_input("Acquisition id", allow_empty=False))
    status = _pick_from("New status", list(acq.ACQ_STATUSES))
    try:
        if status == "Catalogued":
            book = acq.catalogue(aid)
            print(f"\n  ✓ Catalogued as book #{book.book_id}")
        else:
            acq.set_status(aid, status)
            print(f"\n  ✓ Acquisition #{aid} → {status}")
    except (ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
    _pause()


def budgets_flow() -> None:
    year = _input("Academic year", allow_empty=False)
    rows = acq.budget_report(year)
    if not rows:
        print("\n  No budget data for that year.")
    else:
        print(f"\n  {'Subject':<22} {'Alloc':>9} {'Spent':>9} "
              f"{'Remain':>9}")
        for r in rows:
            print(f"  {r['subject_area'][:22]:<22} "
                  f"{r['allocated']:>9.2f} {r['spent']:>9.2f} "
                  f"{r['remaining']:>9.2f}")
    if _input("Set a budget? (y/n)", default="n").lower().startswith("y"):
        sa = _input("Subject area", allow_empty=False)
        amt = float(_input("Allocation", allow_empty=False))
        acq.set_budget(sa, year, amt)
        print(f"  ✓ Budget set for {sa}")
    _pause()


def acquisitions_menu() -> None:
    _run_submenu("Acquisitions", [
        ("List acquisitions",     acquisitions_list_flow),
        ("Suggest purchase",      suggest_acquisition_flow),
        ("Advance status",        advance_acquisition_flow),
        ("Suppliers",             suppliers_flow),
        ("Add supplier",          add_supplier_flow),
        ("Budgets",               budgets_flow),
    ])


# ── Reports & analytics ────────────────────────────────────────────

def _print_rows(rows: list[dict]) -> None:
    if not rows:
        print("\n  (no data)")
        return
    headers = list(rows[0].keys())
    print("\n  " + "  ".join(f"{h}" for h in headers))
    for r in rows:
        print("  " + "  ".join(str(r[h]) for h in headers))


def report_most_borrowed_flow() -> None:
    _print_rows(reports.most_borrowed(limit=15))
    _pause()


def report_least_borrowed_flow() -> None:
    _print_rows(reports.least_borrowed(limit=15))
    _pause()


def report_never_borrowed_flow() -> None:
    _print_rows(reports.never_borrowed())
    _pause()


def report_overdue_aging_flow() -> None:
    buckets = reports.overdue_aging()
    print("\n  Overdue aging:")
    for k, v in buckets.items():
        print(f"    {k:<6} days : {v['count']}")
    _pause()


def report_borrowers_flow() -> None:
    print("\n  By year group:")
    _print_rows(reports.borrowers_by_year_group())
    print("\n  By tutor group:")
    _print_rows(reports.borrowers_by_tutor_group())
    _pause()


def report_usage_flow() -> None:
    _print_rows(reports.usage_trends(months=12))
    print(f"\n  Fines: {reports.fines_collected()}")
    _pause()


def report_subject_gap_flow() -> None:
    _print_rows(reports.subject_gap_report())
    _pause()


def report_dashboard_flow() -> None:
    print("\n═══ Dashboard ═══")
    for k, v in reports.dashboard().items():
        print(f"  {k:<22}: {v}")
    _pause()


def report_export_flow() -> None:
    options = {
        "most_borrowed": lambda: reports.most_borrowed(limit=100),
        "never_borrowed": reports.never_borrowed,
        "subject_gap": reports.subject_gap_report,
        "usage_trends": lambda: reports.usage_trends(months=24),
    }
    name = _pick_from("Report", list(options))
    path = _input("Output CSV path", allow_empty=False)
    rows = options[name]()
    reports.export_csv(rows, path)
    print(f"\n  ✓ Exported {len(rows)} rows to {path}")
    _pause()


def reports_menu() -> None:
    _run_submenu("Reports & Analytics", [
        ("Dashboard",             report_dashboard_flow),
        ("Most borrowed",         report_most_borrowed_flow),
        ("Least borrowed",        report_least_borrowed_flow),
        ("Never borrowed",        report_never_borrowed_flow),
        ("Overdue aging",         report_overdue_aging_flow),
        ("Borrowers by cohort",   report_borrowers_flow),
        ("Usage & fines",         report_usage_flow),
        ("Subject gap",           report_subject_gap_flow),
        ("Export CSV",            report_export_flow),
    ])


# ── E-resources ────────────────────────────────────────────────────

def eresources_list_flow() -> None:
    rows = eresources.list_eresources()
    if not rows:
        print("\n  No e-resources. Add a book with type 'E-Resource' "
              "and put its URL in the Location field.")
    else:
        for b in rows:
            print(f"    #{b.book_id} {b.title[:34]:<34} "
                  f"{b.location or '(no URL)'}")
    _pause()


def eresource_access_flow() -> None:
    rows = eresources.list_eresources()
    if not rows:
        print("\n  No e-resources.")
        _pause()
        return
    for b in rows:
        print(f"    #{b.book_id} {b.title}")
    bid = int(_input("E-resource book id", allow_empty=False))
    try:
        url = eresources.access(bid)
    except (ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Access URL: {url}")
    _pause()


def eresource_usage_flow() -> None:
    _print_rows(eresources.usage())
    _pause()


def eresources_menu() -> None:
    _run_submenu("E-Resources", [
        ("List e-resources", eresources_list_flow),
        ("Access (log)",     eresource_access_flow),
        ("Usage stats",      eresource_usage_flow),
    ])


# ── Study-space bookings ───────────────────────────────────────────

def study_list_flow() -> None:
    date = _input("Date (YYYY-MM-DD, blank=all)")
    rows = study.list_bookings(date=date or None)
    if not rows:
        print("\n  No bookings.")
    else:
        for bk in rows:
            who = bk.student_id or bk.staff or "—"
            print(f"    #{bk.booking_id} {bk.space:<16} {bk.date} "
                  f"{bk.start_time}-{bk.end_time}  {who} [{bk.status}]")
    _pause()


def study_book_flow() -> None:
    space = _input("Space (e.g. Silent Desk 1)", allow_empty=False)
    date = _input("Date (YYYY-MM-DD)", allow_empty=False)
    start = _input("Start (HH:MM)", allow_empty=False)
    end = _input("End (HH:MM)", allow_empty=False)
    sid = _input("Student id (optional)")
    purpose = _input("Purpose")
    try:
        bk = study.book(space, date=date, start_time=start,
                        end_time=end, student_id=sid or None,
                        purpose=purpose or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Booked #{bk.booking_id}")
    _pause()


def study_cancel_flow() -> None:
    bid = int(_input("Booking id to cancel", allow_empty=False))
    try:
        study.cancel(bid)
    except (ValidationError, ValueError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Cancelled booking #{bid}")
    _pause()


def study_menu() -> None:
    _run_submenu("Study Rooms", [
        ("List bookings",  study_list_flow),
        ("Book a space",   study_book_flow),
        ("Cancel booking", study_cancel_flow),
    ])


# ── Self-service kiosk (read-only) ─────────────────────────────────

def kiosk_flow() -> None:
    print("\n═══ Library Kiosk ═══")
    while True:
        print("\n  1) Search catalogue   2) My loans & fines   0) Exit")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if choice == "1":
            try:
                q = _input("Search")
            except _UserAbort:
                continue
            _print_books(kiosk.search(q or None))
        elif choice == "2":
            try:
                sid = _input("Your student id", allow_empty=False)
                summ = kiosk.student_summary(sid)
            except (ValidationError, _UserAbort) as e:
                print(f"  ✗ {e}")
                continue
            print(f"\n  {summ['name']} ({summ['student_id']})")
            print(f"  Loans ({len(summ['loans'])}):")
            for l in summ["loans"]:
                flag = " OVERDUE" if l["overdue"] else ""
                print(f"    {l['title'][:34]:<34} due {l['due_on']}"
                      f"{flag}")
            print(f"  Fines: {summ['balance']:.2f} owed")
            print(f"  Reservations ({len(summ['reservations'])}):")
            for r in summ["reservations"]:
                pos = (f" — #{r['queue_position']} in queue"
                       if r["queue_position"] else " — Ready")
                print(f"    {r['title'][:34]:<34}{pos}")


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List books",          list_books_flow),
    ("Search books",        search_books_flow),
    ("View book",           view_book_flow),
    ("New book",            new_book),
    ("New book from ISBN",  new_book_from_isbn),
    ("Edit book",           edit_book),
    ("Edit tags",           edit_tags_flow),
    ("Browse by tag",       browse_by_tag_flow),
    ("Change book status",  set_book_status_flow),
    ("Delete book",         delete_book_flow),
    ("─" * 6,               lambda: None),
    ("Active loans",        list_active_loans),
    ("Overdue loans",       list_overdue_loans),
    ("All loans",           list_loans_flow),
    ("Issue loan",          issue_flow),
    ("Return loan",         return_flow),
    ("Renew loan",          renew_flow),
    ("Bulk return",         bulk_return_flow),
    ("Bulk renew",          bulk_renew_flow),
    ("Mark lost",           mark_lost_flow),
    ("Per-student loans",   per_student_flow),
    ("Delete loan",         delete_loan_flow),
    ("─" * 6,               lambda: None),
    ("Reservations",        list_reservations_flow),
    ("Place reservation",   reserve_flow),
    ("Collect hold",        collect_reservation_flow),
    ("Cancel reservation",  cancel_reservation_flow),
    ("Expire stale holds",  expire_holds_flow),
    ("Recall loan",         recall_flow),
    ("─" * 6,               lambda: None),
    ("List fines",          list_fines_flow),
    ("Raise fine",          raise_fine_flow),
    ("Pay fine",            pay_fine_flow),
    ("Waive fine",          waive_fine_flow),
    ("Student balance",     student_balance_flow),
    ("─" * 6,               lambda: None),
    ("Send due-soon reminders", due_soon_sweep_flow),
    ("Send overdue notices",    overdue_sweep_flow),
    ("Send daily digest",       daily_digest_flow),
    ("─" * 6,               lambda: None),
    ("Copies & stock…",     copies_menu),
    ("Reading lists…",      reading_menu),
    ("Acquisitions…",       acquisitions_menu),
    ("E-resources…",        eresources_menu),
    ("Study rooms…",        study_menu),
    ("Reports & analytics…", reports_menu),
    ("Kiosk mode",          kiosk_flow),
    ("─" * 6,               lambda: None),
    ("Settings",            settings_flow),
    ("Loan policies",       policies_flow),
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
