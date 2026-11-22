"""Library in the terminal. The old options 1-10 are kept (add, list / search,
edit, toggle active, delete; lend, return, mark lost, list loans, pupil loan
history); 11-20 are added. Rules live in :mod:`modules.library.domain.library`."""

from __future__ import annotations

from education_system.systems.secondary.modules.library.domain import library as LB
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (LB.ValidationError, LB.PermissionDenied, LB.NotFound)


_problem = prompts.problem


def _pct(v) -> str:
    return "-" if v is None else f"{v}%"


def _print_books(rows: list[LB.Book]) -> None:
    if not rows:
        print("  (no books)")
        return
    print(f"  {'ID':<4} {'Title':<32} {'Author':<20} {'Cat':<11} {'Yr':<4} {'Avail':<7} "
          f"{'ISBN':<13} {'Loc':<8} Act")
    for b in rows:
        print(f"  {b.book_id:<4} {b.title[:32]:<32} {(b.author or '')[:20]:<20} "
              f"{b.category:<11} {str(b.year_published or ''):<4} {b.copies_label:<7} "
              f"{(b.isbn or '')[:13]:<13} {(b.location or '')[:8]:<8} "
              f"{'Y' if b.is_active else 'N'}" + (f"  ({b.waiting} reserved)" if b.waiting
                                                  else ""))


def _print_loans(rows: list[LB.Loan]) -> None:
    if not rows:
        print("  (no loans)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Due':<10} {'Returned':<10} {'Pupil':<22} "
          f"{'Book':<28} {'Copy':<8} Status")
    for x in rows:
        print(f"  {x.loan_id:<5} {x.loan_date:<10} {x.due_date:<10} "
              f"{(x.returned_date or ''):<10} {x.pupil_name[:22]:<22} {x.book_title[:28]:<28} "
              f"{x.barcode[:8]:<8} {x.shown_status}"
              + (f" ({x.days_overdue}d)" if x.days_overdue else ""))


def _choose_book() -> LB.Book | None:
    raw = _prompt("  Book ID (or search): ")
    if not raw:
        return None
    if raw.isdigit():
        try:
            return LB.get_book(int(raw))
        except LB.NotFound:
            print("  No book with that ID.")
            return None
    hits = LB.list_books(query=raw)
    if len(hits) == 1:
        return hits[0]
    if hits:
        _print_books(hits)
        print("  More than one match - use the ID.")
    else:
        print("  No book matches.")
    return None


def _choose_pupil() -> P.Pupil | None:
    ref = _prompt("  Pupil (admission no or UPN): ")
    if not ref:
        return None
    p = P.find_by_reference(ref)
    if p is None:
        print("  No pupil with that admission number or UPN.")
    return p


def _choose_loan() -> LB.Loan | None:
    raw = _prompt("  Loan ID (or copy barcode): ")
    if not raw:
        return None
    if raw.isdigit():
        try:
            return LB.get_loan(int(raw))
        except LB.NotFound:
            print("  No such loan.")
            return None
    copy = LB.find_copy(raw)
    loans = [x for x in LB.list_loans() if copy and x.copy_id == copy.copy_id
             and x.status in ("Out", "Lost")]
    if not loans:
        print("  That copy isn't out on loan.")
        return None
    return loans[0]


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("library.view")
        o = LB.overview()
        print("\n── Library ──")
        print(f"  Titles: {o['books_total']}  active: {o['books_active']}  "
              f"copies: {o['copies_avail']}/{o['copies_total']}")
        print("  Loans: " + "   ".join(f"{s}: {o['loans'][s]}" for s in LB.LOAN_STATUSES)
              + f"   Reservations: {o['holds']}")
        print("\n  Catalogue\n    1) Add book\n    2) List / search books\n    3) Edit book"
              "\n    4) Toggle book active\n    5) Delete book"
              "\n  Loans\n    6) Lend book\n    7) Return loan\n    8) Mark loan lost"
              "\n    9) List loans\n   10) Pupil loan history"
              "\n  More\n   11) Renew a loan\n   12) Copies of a book"
              "\n   13) Reserve a book\n   14) Reservations\n   15) Overdue books"
              "\n   16) E-mail families about overdue books\n   17) Reading report"
              "\n   18) Most borrowed\n   19) Export catalogue / overdue (CSV)"
              "\n   20) Loan rules\n    0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        try:
            {"1": lambda: _new(principal), "2": _list, "3": lambda: _edit(principal),
             "4": lambda: _toggle(principal), "5": lambda: _delete(principal),
             "6": lambda: _lend(principal), "7": lambda: _return(principal),
             "8": lambda: _lost(principal), "9": _list_loans, "10": _pupil_loans,
             "11": lambda: _renew(principal), "12": lambda: _copies(principal),
             "13": lambda: _reserve(principal), "14": lambda: _holds(principal),
             "15": _overdue, "16": lambda: _remind(principal), "17": _report,
             "18": _popular, "19": lambda: _export(principal),
             "20": lambda: _rules(principal),
             }.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


def _collect(existing: LB.Book | None) -> dict:
    data: dict = {}

    def ask(key: str, label: str, current=None, **kw) -> None:
        v = _ask(label, None if current in (None, "") else str(current), **kw)
        if v is not None:
            data[key] = v
    g = (lambda k: getattr(existing, k)) if existing else (lambda _k: None)
    ask("title", "Title", g("title"), required=existing is None)
    ask("author", "Author", g("author"))
    ask("isbn", "ISBN", g("isbn"))
    ask("category", "Category", g("category") or "Fiction", hint="/".join(LB.CATEGORIES))
    ask("year_published", "Year published", g("year_published"))
    ask("copies_total", "Total copies", existing.copies_total if existing else 1)
    ask("location", "Shelf / location", g("location"))
    ask("publisher", "Publisher", g("publisher"))
    ask("reading_level", "Reading level", g("reading_level"))
    ask("notes", "Notes", g("notes"))
    return data


def _new(principal: Principal) -> None:
    print("\n  ── Add Book ──  (Enter keeps a value, '-' clears it)")
    b = LB.create_book(_collect(None), actor=principal)
    print(f"  ✓ Added book #{b.book_id} {b.title} - copies "
          + ", ".join(c.barcode for c in LB.list_copies(b.book_id)))


def _list() -> None:
    q = _prompt("  Search title / author / ISBN / barcode (blank = all): ") or None
    cat = _prompt("  Category (blank = all): ") or None
    match = next((c for c in LB.CATEGORIES if cat and c.lower() == cat.lower()), cat)
    rows = LB.list_books(query=q, category=match, active_only=_yes("  Active only?"),
                         available_only=_yes("  Available only?"))
    print(f"\n  {len(rows)} book(s):")
    _print_books(rows)
    _pause()


def _edit(principal: Principal) -> None:
    b = _choose_book()
    if not b:
        return
    print("  Enter keeps a value, '-' clears it.")
    data = _collect(b)
    active = _prompt(f"  Active? (y/n) [{'y' if b.is_active else 'n'}]: ").lower()
    b, notes = LB.update_book(b.book_id, data, actor=principal)
    if active and active.startswith("y") != b.is_active:
        b = LB.toggle_active(b.book_id, actor=principal)
    print(f"  ✓ Updated book #{b.book_id} (copies {b.copies_label})"
          + (" - " + "; ".join(notes) if notes else ""))


def _toggle(principal: Principal) -> None:
    b = _choose_book()
    if b:
        b = LB.toggle_active(b.book_id, actor=principal)
        print(f"  ✓ {b.title} is now {'active' if b.is_active else 'inactive'}")


def _delete(principal: Principal) -> None:
    b = _choose_book()
    if b and _yes(f"  Delete '{b.title}'?"):
        LB.delete_book(b.book_id, actor=principal)
        print(f"  ✓ Deleted book #{b.book_id}.")


def _lend(principal: Principal) -> None:
    code = _prompt("  Copy barcode (blank = choose a book): ")
    b = None if code else _choose_book()
    if not code and not b:
        return
    p = _choose_pupil()
    if not p:
        return
    ok, why = LB.can_borrow(p.pupil_id)
    override = False
    if not ok:
        for w in why:
            print(f"  ! {w}")
        if not (LB.is_editor(principal) and _yes("  Lend anyway?")):
            return
        override = True
    rules = LB.settings()
    loan = LB.lend(p.pupil_id, actor=principal, barcode=code or None,
                   book_id=b.book_id if b else None,
                   loan_date=_prompt("  Loan date (blank = today): ") or None,
                   due_date=_prompt(f"  Due date (blank = +{rules['loan_days']} days): ")
                   or None, notes=_prompt("  Notes (blank ok): ") or None, override=override)
    print(f"  ✓ Loan #{loan.loan_id}: {loan.book_title} ({loan.barcode}) -> {p.display_name}"
          f" (due {loan.due_date})")


def _return(principal: Principal) -> None:
    x = _choose_loan()
    if not x:
        return
    loan, hold = LB.return_loan(x.loan_id, actor=principal,
                                returned_date=_prompt("  Returned date (blank = today): ")
                                or None)
    print(f"  ✓ Returned loan #{loan.loan_id} (book: {loan.book_title})")
    if hold:
        print(f"  ! Keep copy {hold.barcode} for {hold.pupil_name} - reserved, collect by "
              f"{hold.expires_on}")


def _lost(principal: Principal) -> None:
    x = _choose_loan()
    if x and _yes(f"  Mark '{x.book_title}' ({x.barcode}) borrowed by {x.pupil_name} lost?"):
        LB.mark_lost(x.loan_id, actor=principal, notes=_prompt("  Note: ") or None)
        print(f"  ✓ Loan #{x.loan_id} marked Lost.")


def _list_loans() -> None:
    print(f"  Status ({'/'.join(LB.LOAN_STATUSES)}) or blank.")
    s = _prompt("  Status: ").title() or None
    rows = LB.list_loans(status=s)
    print(f"\n  {len(rows)} loan(s):")
    _print_loans(rows)
    _pause()


def _pupil_loans() -> None:
    p = _choose_pupil()
    if not p:
        return
    rows = LB.pupil_loans(p.pupil_id)
    print(f"\n  {len(rows)} loan(s) for {p.display_name}:")
    _print_loans(rows)
    holds = LB.list_holds(pupil_id=p.pupil_id)
    for h in holds:
        print(f"  Reserved: {h.book_title} ({h.status})")
    _pause()


def _renew(principal: Principal) -> None:
    x = _choose_loan()
    if x:
        r = LB.renew(x.loan_id, actor=principal)
        print(f"  ✓ {r.book_title} now due {r.due_date} (renewed {r.renewals}x)")


def _copies(principal: Principal) -> None:
    b = _choose_book()
    if not b:
        return
    for c in LB.list_copies(b.book_id):
        print(f"  {c.copy_id:<5} {c.barcode:<10} {c.status:<10} {(c.holder or '')[:22]:<22} "
              f"{c.due_date or ''}")
    if not LB.is_editor(principal):
        _pause()
        return
    act = _prompt("  a) Add copies  w) Withdraw a copy  r) Put a copy back  (Enter = done): ")
    if act == "a":
        n = _prompt("  How many: ")
        if n.isdigit():
            added = LB.add_copies(b.book_id, int(n), actor=principal)
            print("  ✓ Added " + ", ".join(c.barcode for c in added))
    elif act in ("w", "r"):
        c = LB.find_copy(_prompt("  Barcode: "))
        if c is None:
            print("  No such copy.")
            return
        LB.set_copy_status(c.copy_id, "Withdrawn" if act == "w" else "Available",
                           actor=principal, note=_prompt("  Note: ") or None if act == "w"
                           else None)
        print("  ✓ Done")


def _reserve(principal: Principal) -> None:
    b = _choose_book()
    p = b and _choose_pupil()
    if b and p:
        LB.reserve(b.book_id, p.pupil_id, actor=principal)
        print(f"  ✓ {p.display_name} is on the list for '{b.title}'")


def _holds(principal: Principal) -> None:
    n = LB.expire_holds(actor=principal)
    if n:
        print(f"  Released {n} uncollected reservation(s).")
    rows = LB.list_holds()
    if not rows:
        print("  (no reservations)")
        return
    for h in rows:
        print(f"  {h.hold_id:<5} {h.book_title[:30]:<30} {h.pupil_name[:22]:<22} {h.status:<8}"
              + (f" copy {h.barcode}, collect by {h.expires_on}" if h.status == "Ready"
                 else f" since {h.placed_at[:10]}"))
    raw = _prompt("  Cancel which reservation ID? (Enter = none): ")
    if raw.isdigit():
        LB.cancel_hold(int(raw), actor=principal)
        print("  ✓ Cancelled")


def _overdue() -> None:
    rows = LB.overdue()
    if not rows:
        print("  No overdue books.")
    for x in rows:
        print(f"  {x.days_overdue:>3}d  {x.pupil_name[:22]:<22} Y{x.year_group} "
              f"{(x.form_group or ''):<6} {x.book_title[:30]:<30} {x.barcode} due {x.due_date}")
    _pause()


def _remind(principal: Principal) -> None:
    rows = LB.overdue()
    if not rows:
        print("  No overdue books.")
        return
    pupils = {x.pupil_id for x in rows}
    if not _yes(f"  E-mail the families of {len(pupils)} pupil(s) with overdue books?"):
        return
    res = LB.remind_overdue(actor=principal)
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    for mid in res["sent"]:
        E.deliver(mid, principal=principal)
    print(f"  ✓ {len(res['sent'])} e-mail(s) sent ({E.delivery_mode()})")
    if res["no_email"]:
        print("  No e-mail address for: " + ", ".join(res["no_email"]))


def _report() -> None:
    year = _prompt("  Year (Enter = all): ")
    r = LB.reading_report(year_group=int(year) if year.isdigit() else None)
    print(f"\n  {r['borrowers']} of {r['pupils']} pupils borrowed in the last 12 months "
          f"({_pct(r['all_pct'])}), {r['loans']} loans")
    print(f"  FSM pupils {_pct(r['fsm_pct'])}")
    print("  By year: " + " · ".join(f"Y{y} {_pct(v)}" for y, v in r["by_year"].items()))
    if r["top_readers"]:
        print("  Top readers: " + ", ".join(f"{p.display_name} ({n})"
                                            for p, n in r["top_readers"][:10]))
    if r["non_borrowers"] and _yes(f"  List the {len(r['non_borrowers'])} pupil(s) who "
                                   "haven't borrowed?"):
        for p in r["non_borrowers"]:
            print(f"  {p.admission_no:<10} {p.display_name[:28]:<28} Y{p.year_group} "
                  f"{p.form_group or ''}")
    _pause()


def _popular() -> None:
    rows = LB.popular()
    if not rows:
        print("  Nothing borrowed in the last 12 months.")
    for b, n in rows:
        print(f"  {n:>4}  {b.title[:40]:<40} {b.author or ''}")
    _pause()


def _export(principal: Principal) -> None:
    which = _prompt("  c) Catalogue  o) Overdue books: ").lower()
    if which not in ("c", "o"):
        return
    default = "library-catalogue.csv" if which == "c" else "library-overdue.csv"
    path = _prompt(f"  Save to [{default}]: ") or default
    try:
        n = (LB.export_catalogue if which == "c" else LB.export_overdue)(path, actor=principal)
    except OSError as e:
        print(f"  Couldn't save: {e}")
        return
    print(f"  ✓ Saved {n} row(s) to {path}")


def _rules(principal: Principal) -> None:
    cur = LB.settings()
    for k, v in cur.items():
        print(f"  {LB._LIMITS[k][2]:<30} {('yes' if v else 'no') if k == 'block_overdue' else v}")
    if not LB.is_editor(principal) or not _yes("  Change them?"):
        return
    changes = {}
    for k in cur:
        raw = _prompt(f"  {LB._LIMITS[k][2]}"
                      + (" (1 = yes, 0 = no)" if k == "block_overdue" else "")
                      + f" [{cur[k]}]: ")
        if raw:
            changes[k] = raw
    if changes:
        LB.set_settings(changes, actor=principal)
        print("  ✓ Saved")
