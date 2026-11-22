"""CLI: the reader's own account and the library operations screens — the
same rules as the GUI (``university/application/library/circulation`` and
``library_services``)."""

from __future__ import annotations

from contextlib import closing

from education_system.systems.university.application.library import circulation as circ
from education_system.systems.university.application.library import services
from education_system.systems.university.application.teaching import (
    occurrences as timetable_occurrences,
)
from education_system.systems.university.infrastructure.database.db import get_connection


def _run(fn, *args, write=False, **kwargs):
    try:
        with closing(get_connection(row_factory=False)) as conn:
            result = fn(conn, *args, **kwargs)
            if write:
                conn.commit()
    except ValueError as exc:
        print(f"Refused: {exc}")
        return None
    emails = result.get("emails") if isinstance(result, dict) else None
    if write and emails:
        timetable_occurrences.send_emails(emails)
    return True if result is None else result


def _me(auth):
    user = getattr(auth, "current_user", None) or {}
    if not isinstance(user, dict):
        user = {"username": getattr(user, "username", None)}
    return user.get("student_id") or user.get("username")


def my_library(auth, ref=None):
    ref = ref or _me(auth)
    data = _run(services.my_library, ref)
    if not isinstance(data, dict):
        return
    who, rules = data["borrower"], data["rules"]
    print(f"\n{who['name'] or who['ref']} — {who['category']}: up to {rules['max_loans']} items, "
          f"{rules['loan_days']} days, {rules['max_renewals']} renewals. Owed £{data['owed']:.2f}")
    for block in data["blocks"]:
        print(f"  ⚠ {block}")
    for loan in data["loans"]:
        print(f"  #{loan['loan_id']} {loan['title']} — due {str(loan['due_date'])[:16]}"
              + ("  RECALLED" if loan["recalled_at"] else "")
              + (f"  (can't renew: {loan['renewal_blocked']})" if loan["renewal_blocked"] else ""))
    for hold in data["holds"]:
        print(f"  request #{hold['reservation_id']} {hold['title']}: " + (
            f"READY — collect by {str(hold['collect_by'])[:16]}" if hold["status"] == "ready"
            else f"#{hold['position']} in queue"))
    choice = input("1. Renew a loan  2. Request a book  3. Cancel a request  0. Back: ").strip()
    if choice == "1":
        _run(circ.renew, input("Loan #: ").strip(), write=True) and print("Renewed.")
    elif choice == "2":
        rows = _run(services.search_titles, input("Title / author / ISBN: ").strip()) or []
        for r in rows if isinstance(rows, list) else []:
            print(f"  {r['book_id']}: {r['title']} — {r['on_shelf']} of {r['copies']} on shelf")
        book = input("Book ID to request: ").strip()
        result = book and _run(circ.place_hold, book, ref, write=True)
        if isinstance(result, dict):
            print("Ready on the holds shelf." if result["ready"] else
                  f"Requested: #{result['position']} in the queue.")
    elif choice == "3":
        rid = input("Request #: ").strip()
        if rid.isdigit():
            _run(circ.cancel_hold, int(rid), write=True) and print("Cancelled.")


def _copies():
    book = input("Book ID: ").strip()
    for c in _run(circ.copies, book) or []:
        print(f"  {c['barcode']:<22} {c['item_type']:<11} {c['status']:<11} "
              f"{c['location'] or '':<12} {c['borrower'] or ''}")
    choice = input("1. Add copies  2. Change a copy  3. Set classmark  4. Declare lost  "
                   "5. Found  0. Back: ").strip()
    if choice == "1":
        n, kind = input("How many: ").strip(), input("Type [standard]: ").strip() or "standard"
        made = _run(circ.add_copies, book, n, kind, input("Location: ").strip() or None,
                    input("Price £ (blank = unknown): ").strip() or None, write=True)
        if isinstance(made, list):
            print("New barcodes: " + ", ".join(made))
    elif choice == "2":
        barcode = input("Barcode: ").strip()
        copy = _run(circ.find_copy, barcode)
        if isinstance(copy, dict):
            _run(circ.update_copy, copy["copy_id"], item_type=input("Type (blank = same): ").strip()
                 or None, location=input("Location (blank = same): ").strip() or None,
                 status=input("available/damaged/missing/withdrawn (blank = same): ").strip()
                 or None, write=True) and print("Saved.")
    elif choice == "3":
        _run(circ.set_classmark, book, input("Classmark: ").strip(), write=True) and print("Saved.")
    elif choice == "4":
        result = _run(circ.declare_lost, input("Copy barcode: ").strip(), write=True)
        if isinstance(result, dict):
            print(f"Charged £{result['charged']:.2f}.")
    elif choice == "5":
        result = _run(circ.found, input("Copy barcode: ").strip(), write=True)
        if isinstance(result, dict):
            print(f"Back in stock; £{result['waived']:.2f} waived.")


def _holds():
    for h in _run(circ.holds_shelf) or []:
        print(f"  {h['user_id']:<12} {h['title'][:40]:<41} {h['barcode'] or '':<20} "
              f"collect by {str(h['collect_by'])[:16]}")
    if input("Release uncollected and lapsed requests? (y/N): ").strip().lower() == "y":
        result = _run(circ.expire_holds, write=True)
        if isinstance(result, dict):
            print(f"{len(result['expired'])} passed on, {result['lapsed']} lapsed.")


def _rules(auth):
    for category in circ.schema.BORROWER_CATEGORIES:
        r = _run(circ.borrower_rules, category)
        print(f"  {category:<14} {r['max_loans']} items, {r['loan_days']} days, "
              f"{r['max_renewals']} renewals")
    for name, label in circ.SETTING_LABELS.items():
        print(f"  {label}: {_run(circ.setting, name)}")
    choice = input("1. Change a category  2. Change a threshold  3. Put a reader in a category  "
                   "0. Back: ").strip()
    if choice == "1":
        cat = input("Category: ").strip()
        _run(circ.set_borrower_rule, cat, input("Max items: "), input("Loan days: "),
             input("Renewals: "), input("Short loans allowed (y/N): ").strip().lower() == "y",
             write=True) and print("Saved.")
    elif choice == "2":
        name = input(f"Setting ({', '.join(circ.SETTING_LABELS)}): ").strip()
        _run(circ.set_setting, name, input("Value: ").strip(), write=True) and print("Saved.")
    elif choice == "3":
        _run(circ.set_override, input("Reader: ").strip(), input("Category: ").strip(),
             input("Reason: ").strip(), input("Until (YYYY-MM-DD, blank = open): ").strip() or None,
             _me(auth), write=True) and print("Saved.")


def _reading_lists(auth):
    for lst in _run(services.module_lists) or []:
        print(f"  #{lst['list_id']} {lst['name']} — module {lst['module_code'] or '—'}, "
              f"{lst['items']} items")
    lid = input("List #: ").strip()
    if not lid.isdigit():
        return
    if input("Link to a module? (y/N): ").strip().lower() == "y":
        _run(services.link_list, int(lid), input("Module code: ").strip(), write=True)
    check = _run(services.holdings_check, int(lid))
    if isinstance(check, dict):
        print(f"{check['students']} students on the module.")
        for item in check["items"]:
            print(f"  item #{item['item_id']} {item['title']}: {item['importance']}, "
                  f"{item['lendable']} copies, need {item['needed']}"
                  + (f" — SHORT BY {item['shortfall']}" if item["shortfall"] else ""))
        if input("Raise purchase requests for shortfalls? (y/N): ").strip().lower() == "y":
            made = _run(services.request_shortfall, int(lid), _me(auth), write=True)
            print(f"{made if made is not True else 0} request(s) raised.")


def _acquisitions(auth):
    for f in _run(services.fund_position) or []:
        print(f"  {f['fund_code']}: £{f['allocation']:,.2f}, committed £{f['committed']:,.2f}, "
              f"spent £{f['spent']:,.2f}, remaining £{f['remaining']:,.2f}")
    for o in _run(services.orders) or []:
        print(f"  order #{o['order_id']} {o['title']} — {o['received_qty']}/{o['quantity']} "
              f"from {o['supplier']}")
    for r in _run(services.requests) or []:
        print(f"  request #{r['request_id']} {r['title']} ({r['priority']}): {r['reason'] or ''}")
    choice = input("1. Set a fund  2. Order a request  3. Receive  4. Cancel order  "
                   "0. Back: ").strip()
    if choice == "1":
        _run(services.set_fund, input("Code: "), input("Name: "), input("Year: "),
             input("Allocation £: "), write=True) and print("Saved.")
    elif choice == "2":
        rid = input("Request #: ").strip()
        _run(services.place_order, supplier=input("Supplier: "), fund_code=input("Fund: "),
             quantity=input("Quantity: "), unit_price=input("£ each: "),
             request_id=int(rid) if rid.isdigit() else None, actor=_me(auth),
             write=True) and print("Ordered.")
    elif choice == "3":
        made = _run(services.receive, int(input("Order #: ") or 0), input("How many arrived: "),
                    input("Shelve at: ").strip() or None, write=True)
        if isinstance(made, list):
            print("New barcodes: " + ", ".join(made))
    elif choice == "4":
        _run(services.cancel_order, int(input("Order #: ") or 0), input("Why: "),
             write=True) and print("Cancelled.")


def _stocktake(auth):
    locs = _run(services.locations) or []
    print("Locations: " + ", ".join(locs))
    sid = _run(services.start_stocktake, input("Location: ").strip(), _me(auth), write=True)
    if not isinstance(sid, int):
        return
    print("Scan barcodes; blank line to finish.")
    while True:
        code = input("> ").strip()
        if not code:
            break
        print("  " + str(_run(services.scan, sid, code, write=True)))
    progress = _run(services.stocktake_progress, sid)
    if isinstance(progress, dict) and input(
            f"Mark {len(progress['not_seen'])} unseen copies missing? (y/N): ").strip().lower() == "y":
        result = _run(services.finish_stocktake, sid, write=True)
        print(f"Missing: {', '.join(result['missing']) or 'none'}")


def _leavers():
    rows = _run(services.leavers) or []
    for r in rows:
        print(f"  {r['student_id']} {r['name']} ({r['status']}): {r['loans']} item(s), "
              f"£{r['owed']:.2f}")
    sid = input("Send a reminder to (student ID, blank = none): ").strip()
    if sid:
        _run(services.notify_leaver, sid, write=True) and print("Sent.")


def _eresources():
    for r in _run(services.eresources) or []:
        print(f"  #{r['resource_id']} {r['title']} — £{r['annual_cost'] or 0:,.0f}/yr, "
              f"{r['uses_12m']} uses, £/use {r['cost_per_use'] or '—'}, renews "
              f"{r['renewal_date'] or '—'}" + ("  RENEWAL DECISION DUE" if r["decision_due"] else ""))
    choice = input("1. Add  2. Record usage  0. Back: ").strip()
    if choice == "1":
        values = {k: input(f"{k.replace('_', ' ')}: ").strip() or None for k in (
            "title", "provider", "resource_type", "url", "concurrent_users", "annual_cost",
            "start_date", "renewal_date")}
        _run(services.save_eresource, values, write=True) and print("Saved.")
    elif choice == "2":
        _run(services.record_usage, int(input("Resource #: ") or 0), input("Month YYYY-MM: "),
             input("Uses: "), write=True) and print("Saved.")


def display_operations_menu(auth):
    actions = (("Copies & items", _copies), ("Holds shelf & recalls", _holds),
               ("Loan rules", lambda: _rules(auth)),
               ("Module reading lists", lambda: _reading_lists(auth)),
               ("Acquisitions", lambda: _acquisitions(auth)),
               ("Stocktake", lambda: _stocktake(auth)), ("Leavers", _leavers),
               ("E-resources", _eresources),
               ("A reader's account", lambda: my_library(auth, input("Reader: ").strip())))
    while True:
        print("\nLibrary operations")
        for i, (label, _fn) in enumerate(actions, 1):
            print(f"  {i}. {label}")
        print("  0. Back")
        choice = input("Choice: ").strip()
        if choice in ("0", ""):
            return
        if choice.isdigit() and 0 < int(choice) <= len(actions):
            actions[int(choice) - 1][1]()
