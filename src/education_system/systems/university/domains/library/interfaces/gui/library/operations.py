"""Library screens built on the shared rules (``university/application/
library_circulation`` and ``library_services``):

My library (any reader), Copies & items, Holds & recalls, Loan rules,
Module reading lists, Acquisitions, Stocktake, Leavers and E-resources.
Bound onto ``LibraryGUI`` in ``__init__``; each opens as a tab in the content
notebook like the existing screens.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from education_system.systems.university.application.library import circulation as circ
from education_system.systems.university.application.library import services

logger = logging.getLogger(__name__)
_PAD = {"padx": 6, "pady": 3}


# ── plumbing ────────────────────────────────────────────────────────────


def _call(fn, *args, write=False, **kwargs):
    """Run a rule in its own transaction; refusals become a dialog (None)."""
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    try:
        result = fn(conn, *args, **kwargs)
        if write:
            conn.commit()
    except ValueError as exc:
        conn.rollback()
        messagebox.showerror("Library", str(exc))
        return None
    except Exception as exc:
        conn.rollback()
        logger.exception("library action failed")
        messagebox.showerror("Library", f"That did not work: {exc}")
        return None
    finally:
        conn.close()
    emails = result.get("emails") if isinstance(result, dict) else (
        result if isinstance(result, list) and result and isinstance(result[0], tuple) else None)
    if write and emails:
        timetable_occurrences.send_emails(emails)
    return True if result is None else result


def _tree(parent, columns, widths, height=8):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, **_PAD)
    tree = ttk.Treeview(frame, columns=[c for c, _t in columns], show="headings", height=height)
    for (key, title), width in zip(columns, widths):
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    return tree


def _fill(tree, rows, values, iid=None):
    tree.delete(*tree.get_children())
    for i, row in enumerate(rows):
        tree.insert("", "end", iid=str(iid(row) if iid else i), values=values(row))


def _bar(parent):
    bar = ttk.Frame(parent)
    bar.pack(fill="x", **_PAD)
    return bar


def _entry(bar, label, width=10, value=""):
    ttk.Label(bar, text=label).pack(side="left")
    var = tk.StringVar(value=value)
    ttk.Entry(bar, textvariable=var, width=width).pack(side="left", padx=(2, 8))
    return var


def _tab(self, title, permission=None):
    if permission and not self.check_permission(permission):
        return None
    self.clear_content_area()
    frame = ttk.Frame(self.notebook)
    self.notebook.add(frame, text=title)
    self.notebook.select(frame)
    return frame


def _selected(tree):
    sel = tree.selection()
    return sel[0] if sel else None


def _me(self):
    user = getattr(getattr(self, "auth", None), "current_user", None) or {}
    if not isinstance(user, dict):
        user = {"username": getattr(user, "username", None)}
    return user.get("student_id") or user.get("username")


# ── my library ──────────────────────────────────────────────────────────


def show_my_library(self):
    tab = _tab(self, "My library")
    if tab is None:
        return
    head = _bar(tab)
    self._ml_ref = tk.StringVar(value=_me(self) or "")
    if self.is_admin() or self.is_staff():
        ttk.Label(head, text="Reader (student ID / username):").pack(side="left")
        ttk.Entry(head, textvariable=self._ml_ref, width=16).pack(side="left", padx=4)
        ttk.Button(head, text="Show", command=self._ml_load).pack(side="left")
    self._ml_summary = tk.StringVar()
    ttk.Label(tab, textvariable=self._ml_summary, wraplength=900, justify="left").pack(
        anchor="w", padx=8)
    ttk.Label(tab, text="On loan:", font=("Arial", 10, "bold")).pack(anchor="w", padx=8)
    ttk.Button(_bar(tab), text="Renew selected", command=self._ml_renew).pack(side="left")
    self._ml_loans = _tree(tab, [("title", "Title"), ("copy", "Copy"), ("due", "Due"),
                                 ("note", "")], [300, 160, 140, 300], height=5)
    ttk.Label(tab, text="Requests:", font=("Arial", 10, "bold")).pack(anchor="w", padx=8)
    hb = _bar(tab)
    ttk.Button(hb, text="Cancel selected request", command=self._ml_cancel).pack(side="left")
    self._ml_search = _entry(hb, "  Find a book to request:", 24)
    ttk.Button(hb, text="Search", command=self._ml_find).pack(side="left")
    ttk.Button(hb, text="Request selected result", command=self._ml_request).pack(
        side="left", padx=4)
    self._ml_holds = _tree(tab, [("title", "Title"), ("state", "Status"), ("detail", "")],
                           [300, 120, 380], height=3)
    self._ml_results = _tree(tab, [("title", "Search results"), ("author", "Author"),
                                   ("mark", "Classmark"), ("shelf", "On shelf")],
                             [300, 200, 140, 120], height=3)
    ttk.Label(tab, text="Charges and history:", font=("Arial", 10, "bold")).pack(anchor="w",
                                                                                 padx=8)
    self._ml_history = _tree(tab, [("when", "When"), ("what", "What"), ("amount", "Amount"),
                                   ("status", "Status")], [140, 460, 90, 100], height=4)
    if self._ml_ref.get():
        self._ml_load()


def _ml_load(self):
    data = _call(services.my_library, self._ml_ref.get().strip())
    if not data:
        return
    who, rules = data["borrower"], data["rules"]
    self._ml_summary.set(
        f"{who['name'] or who['ref']} — {who['category']} borrower: up to {rules['max_loans']} "
        f"items for {rules['loan_days']} days, {rules['max_renewals']} renewals. "
        f"Owed £{data['owed']:.2f}."
        + (f"  ⚠ Cannot borrow: {'; '.join(data['blocks'])}" if data["blocks"] else ""))
    _fill(self._ml_loans, data["loans"], lambda r: (
        r["title"], r["barcode"] or "", str(r["due_date"])[:16],
        ("OVERDUE. " if r["overdue"] else "") + ("RECALLED — return by the date shown. "
                                                 if r["recalled_at"] else "")
        + (f"Can't renew: {r['renewal_blocked']}" if r["renewal_blocked"] else "Renewable")),
        iid=lambda r: r["loan_id"])
    _fill(self._ml_holds, data["holds"], lambda r: (
        r["title"], "READY" if r["status"] == "ready" else f"#{r['position']} in queue",
        f"collect by {str(r['collect_by'])[:16]}" if r["status"] == "ready" else ""),
        iid=lambda r: r["reservation_id"])
    rows = [(c["created_at"], f"Charge — {c['kind']}: {c['note'] or ''}", c["amount"], c["status"])
            for c in data["charges"]]
    rows += [(h["checkout_date"], f"Borrowed {h['title']} (returned {str(h['return_date'] or '')[:10]})",
              h["fine_amount"] or 0, h["status"]) for h in data["history"]]
    _fill(self._ml_history, rows, lambda r: (str(r[0])[:16], r[1], f"£{float(r[2] or 0):.2f}",
                                              r[3]))


def _ml_renew(self):
    loan = _selected(self._ml_loans)
    if loan and _call(circ.renew, loan, write=True):
        self._ml_load()


def _ml_cancel(self):
    hold = _selected(self._ml_holds)
    if hold and messagebox.askyesno("Cancel request", "Cancel this request?"):
        if _call(circ.cancel_hold, int(hold), write=True) is not None:
            self._ml_load()


def _ml_find(self):
    rows = _call(services.search_titles, self._ml_search.get()) or []
    _fill(self._ml_results, rows, lambda r: (r["title"], r["author"] or "", r["classmark"] or "",
                                             f"{r['on_shelf']} of {r['copies']}"),
          iid=lambda r: r["book_id"])


def _ml_request(self):
    book = _selected(self._ml_results)
    result = book and _call(circ.place_hold, book, self._ml_ref.get().strip(), write=True)
    if result:
        messagebox.showinfo("Request", "A copy is waiting for you — collect it from the holds "
                            "shelf." if result["ready"] else
                            f"Requested: #{result['position']} in the queue.")
        self._ml_load()


# ── copies & items ──────────────────────────────────────────────────────


def show_copies(self):
    tab = _tab(self, "Copies & items", "manage_books")
    if tab is None:
        return
    top = _bar(tab)
    self._cp_search = _entry(top, "Title / author / ISBN:", 24)
    ttk.Button(top, text="Find", command=self._cp_find).pack(side="left")
    self._cp_titles = _tree(tab, [("title", "Title"), ("author", "Author"), ("mark", "Classmark"),
                                  ("shelf", "On shelf")], [320, 200, 140, 100], height=4)
    self._cp_titles.bind("<<TreeviewSelect>>", lambda _e: self._cp_load())
    act = _bar(tab)
    self._cp_mark = _entry(act, "Classmark:", 16)
    ttk.Button(act, text="Set", command=self._cp_set_mark).pack(side="left")
    self._cp_n = _entry(act, "   Add copies:", 3, "1")
    self._cp_type = ttk.Combobox(act, values=circ.schema.ITEM_TYPES, width=10, state="readonly")
    self._cp_type.set("standard")
    self._cp_type.pack(side="left", padx=2)
    self._cp_loc = _entry(act, "Location", 10)
    self._cp_price = _entry(act, "£", 6)
    ttk.Button(act, text="Add", command=self._cp_add).pack(side="left")
    act2 = _bar(tab)
    for label, command in (("Make short loan (24h)", lambda: self._cp_update(item_type="short_24h")),
                           ("Make short loan (3-day)", lambda: self._cp_update(item_type="short_3day")),
                           ("Make standard", lambda: self._cp_update(item_type="standard")),
                           ("Reference only", lambda: self._cp_update(item_type="reference")),
                           ("Withdraw", lambda: self._cp_update(status="withdrawn")),
                           ("Damaged", lambda: self._cp_update(status="damaged")),
                           ("Back on shelf", lambda: self._cp_update(status="available"))):
        ttk.Button(act2, text=label, command=command).pack(side="left", padx=1)
    act3 = _bar(tab)
    ttk.Button(act3, text="Declare lost (charge borrower)", command=self._cp_lost).pack(side="left")
    ttk.Button(act3, text="Found again", command=self._cp_found).pack(side="left", padx=4)
    ttk.Button(act3, text="Damage charge…", command=self._cp_damage).pack(side="left")
    self._cp_copies = _tree(tab, [("barcode", "Barcode"), ("type", "Type"), ("loc", "Location"),
                                  ("status", "Status"), ("who", "Borrower"), ("due", "Due"),
                                  ("seen", "Last seen")],
                            [170, 90, 100, 90, 100, 130, 110], height=8)


def _cp_find(self):
    rows = _call(services.search_titles, self._cp_search.get()) or []
    _fill(self._cp_titles, rows, lambda r: (r["title"], r["author"] or "", r["classmark"] or "",
                                            f"{r['on_shelf']} of {r['copies']}"),
          iid=lambda r: r["book_id"])


def _cp_book(self):
    book = _selected(self._cp_titles)
    if not book:
        messagebox.showinfo("Copies", "Select a title first.")
    return book


def _cp_load(self):
    book = _selected(self._cp_titles)
    if not book:
        return
    _fill(self._cp_copies, _call(circ.copies, book) or [], lambda c: (
        c["barcode"], c["item_type"], c["location"] or "", c["status"], c["borrower"] or "",
        str(c["due_date"] or "")[:16], str(c["last_seen"] or "")[:10]),
        iid=lambda c: c["copy_id"])
    vals = self._cp_titles.item(book, "values")
    self._cp_mark.set(vals[2] if len(vals) > 2 else "")


def _cp_set_mark(self):
    book = self._cp_book()
    if book and _call(circ.set_classmark, book, self._cp_mark.get(), write=True):
        self._cp_find()


def _cp_add(self):
    book = self._cp_book()
    made = book and _call(circ.add_copies, book, self._cp_n.get(), self._cp_type.get(),
                          self._cp_loc.get() or None, self._cp_price.get() or None, write=True)
    if made:
        messagebox.showinfo("Copies", "New barcodes:\n" + "\n".join(made))
        self._cp_load()


def _cp_copy(self):
    copy = _selected(self._cp_copies)
    if not copy:
        messagebox.showinfo("Copies", "Select a copy first.")
    return copy


def _cp_update(self, **changes):
    copy = self._cp_copy()
    if copy and _call(circ.update_copy, int(copy), write=True, **changes):
        self._cp_load()


def _cp_barcode(self):
    copy = self._cp_copy()
    return copy and self._cp_copies.item(copy, "values")[0]


def _cp_lost(self):
    barcode = self._cp_barcode()
    if barcode and messagebox.askyesno("Declare lost", f"Charge the borrower of {barcode} for a "
                                       "replacement plus the admin fee?"):
        result = _call(circ.declare_lost, barcode, staff=self._ext_user(), write=True)
        if result:
            messagebox.showinfo("Declared lost", f"Charged £{result['charged']:.2f}.")
            self._cp_load()


def _cp_found(self):
    barcode = self._cp_barcode()
    result = barcode and _call(circ.found, barcode, staff=self._ext_user(), write=True)
    if result:
        messagebox.showinfo("Found", f"Back in stock. Replacement charge waived: "
                            f"£{result['waived']:.2f}.")
        self._cp_load()


def _cp_damage(self):
    copy = self._cp_copy()
    if not copy:
        return
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    row = conn.execute("SELECT loan_id FROM book_loans WHERE copy_id = ? ORDER BY loan_id DESC "
                       "LIMIT 1", (int(copy),)).fetchone()
    conn.close()
    if not row:
        messagebox.showinfo("Damage charge", "That copy has never been lent.")
        return
    amount = simpledialog.askfloat("Damage charge", "Amount (£):", minvalue=0.01)
    note = amount and simpledialog.askstring("Damage charge", "What is the damage?")
    if note and _call(circ.charge_damage, row[0], amount, note, staff=self._ext_user(),
                      write=True) is not None:
        messagebox.showinfo("Damage charge", "Charged to the last borrower.")


def _ext_user(self):
    return _me(self) or "library"


# ── holds & recalls ─────────────────────────────────────────────────────


def show_holds_recalls(self):
    tab = _tab(self, "Holds & recalls", "manage_reservations")
    if tab is None:
        return
    bar = _bar(tab)
    ttk.Button(bar, text="Refresh", command=self._hr_load).pack(side="left")
    ttk.Button(bar, text="Release uncollected & lapsed requests", command=self._hr_expire).pack(
        side="left", padx=4)
    ttk.Label(tab, text="Holds shelf (waiting to be collected):",
              font=("Arial", 10, "bold")).pack(anchor="w", padx=8)
    self._hr_shelf = _tree(tab, [("who", "For"), ("title", "Title"), ("copy", "Copy"),
                                 ("by", "Collect by")], [140, 360, 170, 140], height=7)
    ttk.Label(tab, text="Recalled loans:", font=("Arial", 10, "bold")).pack(anchor="w", padx=8)
    self._hr_recalls = _tree(tab, [("who", "Borrower"), ("title", "Title"), ("due", "Now due"),
                                   ("was", "Was due")], [140, 360, 140, 140], height=7)
    self._hr_load()


def _hr_load(self):
    _fill(self._hr_shelf, _call(circ.holds_shelf) or [], lambda r: (
        r["user_id"], r["title"], r["barcode"] or "", str(r["collect_by"])[:16]))

    def recalled(conn):
        return circ._dicts(conn.execute(
            "SELECT l.user_id, b.title, l.due_date, l.original_due_date FROM book_loans l "
            "JOIN books b ON b.book_id = l.book_id WHERE l.recalled_at IS NOT NULL AND "
            "l.status IN ('active', 'overdue') ORDER BY l.due_date"))
    _fill(self._hr_recalls, _call(recalled) or [], lambda r: (
        r["user_id"], r["title"], str(r["due_date"])[:16], str(r["original_due_date"])[:16]))


def _hr_expire(self):
    result = _call(circ.expire_holds, write=True)
    if result:
        messagebox.showinfo("Holds", f"{len(result['expired'])} uncollected hold(s) passed on; "
                            f"{result['lapsed']} lapsed request(s) closed.")
        self._hr_load()


# ── loan rules ──────────────────────────────────────────────────────────


def show_loan_rules(self):
    tab = _tab(self, "Loan rules", "system_config")
    if tab is None:
        return
    ttk.Label(tab, text="By borrower category:", font=("Arial", 10, "bold")).pack(anchor="w",
                                                                                  padx=8)
    self._lr_borrowers = {}
    grid = ttk.Frame(tab)
    grid.pack(fill="x", **_PAD)
    for col, head in enumerate(("Category", "Max items", "Loan days", "Renewals", "Short loans")):
        ttk.Label(grid, text=head, foreground="#555").grid(row=0, column=col, padx=6, sticky="w")
    for row, category in enumerate(circ.schema.BORROWER_CATEGORIES, start=1):
        rules = _call(circ.borrower_rules, category) or {}
        ttk.Label(grid, text=category).grid(row=row, column=0, padx=6, sticky="w")
        vars_ = [tk.StringVar(value=str(rules.get(k, ""))) for k in
                 ("max_loans", "loan_days", "max_renewals")]
        for col, var in enumerate(vars_, start=1):
            ttk.Entry(grid, textvariable=var, width=6).grid(row=row, column=col, padx=6)
        short = tk.BooleanVar(value=bool(rules.get("short_loans_allowed")))
        ttk.Checkbutton(grid, variable=short).grid(row=row, column=4)
        self._lr_borrowers[category] = (vars_, short)
    ttk.Label(tab, text="By item type:", font=("Arial", 10, "bold")).pack(anchor="w", padx=8,
                                                                          pady=(8, 0))
    self._lr_items = {}
    grid2 = ttk.Frame(tab)
    grid2.pack(fill="x", **_PAD)
    for col, head in enumerate(("Item type", "Loan hours (blank = borrower's days)", "Lendable",
                                "Renewable", "Fine/day £", "Fine/hour £")):
        ttk.Label(grid2, text=head, foreground="#555").grid(row=0, column=col, padx=6, sticky="w")
    for row, item in enumerate(circ.schema.ITEM_TYPES, start=1):
        rules = _call(circ.item_rules, item) or {}
        ttk.Label(grid2, text=item).grid(row=row, column=0, padx=6, sticky="w")
        hours = tk.StringVar(value="" if rules.get("loan_hours") is None else str(rules["loan_hours"]))
        ttk.Entry(grid2, textvariable=hours, width=6).grid(row=row, column=1, padx=6)
        lend, renew = tk.BooleanVar(value=bool(rules.get("loanable"))), tk.BooleanVar(
            value=bool(rules.get("renewable")))
        ttk.Checkbutton(grid2, variable=lend).grid(row=row, column=2)
        ttk.Checkbutton(grid2, variable=renew).grid(row=row, column=3)
        day = tk.StringVar(value="" if rules.get("fine_per_day") is None else str(rules["fine_per_day"]))
        hour = tk.StringVar(value="" if rules.get("fine_per_hour") is None else str(rules["fine_per_hour"]))
        ttk.Entry(grid2, textvariable=day, width=6).grid(row=row, column=4, padx=6)
        ttk.Entry(grid2, textvariable=hour, width=6).grid(row=row, column=5, padx=6)
        self._lr_items[item] = (hours, lend, renew, day, hour)
    ttk.Label(tab, text="Thresholds:", font=("Arial", 10, "bold")).pack(anchor="w", padx=8,
                                                                        pady=(8, 0))
    grid3 = ttk.Frame(tab)
    grid3.pack(fill="x", **_PAD)
    self._lr_settings = {}
    for i, (name, label) in enumerate(circ.SETTING_LABELS.items()):
        ttk.Label(grid3, text=label).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=6)
        var = tk.StringVar(value=str(_call(circ.setting, name)))
        ttk.Entry(grid3, textvariable=var, width=8).grid(row=i // 2, column=(i % 2) * 2 + 1,
                                                         padx=6)
        self._lr_settings[name] = var
    ttk.Button(_bar(tab), text="Save all rules", command=self._lr_save).pack(side="left")
    ttk.Label(tab, text="Borrowers in a different category (external members, extended loans):",
              font=("Arial", 10, "bold")).pack(anchor="w", padx=8, pady=(8, 0))
    ob = _bar(tab)
    self._lr_ref = _entry(ob, "Reader", 12)
    self._lr_cat = ttk.Combobox(ob, values=circ.schema.BORROWER_CATEGORIES, width=13,
                                state="readonly")
    self._lr_cat.set("extended")
    self._lr_cat.pack(side="left", padx=2)
    self._lr_reason = _entry(ob, "Reason", 22)
    self._lr_until = _entry(ob, "Until (YYYY-MM-DD)", 10)
    ttk.Button(ob, text="Set", command=self._lr_override).pack(side="left")


def _lr_save(self):
    def save(conn):
        for category, (vars_, short) in self._lr_borrowers.items():
            circ.set_borrower_rule(conn, category, *[v.get() for v in vars_], short.get())
        for item, (hours, lend, renew, day, hour) in self._lr_items.items():
            circ.set_item_rule(conn, item, hours.get(), lend.get(), renew.get(), day.get(),
                               hour.get())
        for name, var in self._lr_settings.items():
            circ.set_setting(conn, name, var.get())
    if _call(save, write=True):
        messagebox.showinfo("Loan rules", "Saved. New loans and renewals use these rules.")


def _lr_override(self):
    if _call(circ.set_override, self._lr_ref.get(), self._lr_cat.get(), self._lr_reason.get(),
             self._lr_until.get() or None, _me(self), write=True):
        messagebox.showinfo("Loan rules", f"{self._lr_ref.get()} now borrows as "
                            f"{self._lr_cat.get()}.")


# ── module reading lists ────────────────────────────────────────────────


def show_module_reading_lists(self):
    tab = _tab(self, "Module reading lists", "manage_reading_lists")
    if tab is None:
        return
    bar = _bar(tab)
    self._mr_module = _entry(bar, "Link selected list to module:", 12)
    ttk.Button(bar, text="Link", command=self._mr_link).pack(side="left")
    self._mr_lists = _tree(tab, [("name", "Reading list"), ("module", "Module"),
                                 ("items", "Items")], [360, 140, 80], height=5)
    self._mr_lists.bind("<<TreeviewSelect>>", lambda _e: self._mr_check())
    self._mr_note = tk.StringVar()
    ttk.Label(tab, textvariable=self._mr_note).pack(anchor="w", padx=8)
    bar2 = _bar(tab)
    for importance in circ.schema.IMPORTANCE:
        ttk.Button(bar2, text=f"Mark {importance}",
                   command=lambda i=importance: self._mr_importance(i)).pack(side="left", padx=1)
    ttk.Button(bar2, text="Request purchases for every shortfall",
               command=self._mr_request).pack(side="left", padx=8)
    self._mr_items = _tree(tab, [("title", "Title"), ("importance", "Importance"),
                                 ("lendable", "Lendable copies"), ("needed", "Needed"),
                                 ("short", "Short by")], [360, 100, 110, 80, 80], height=8)
    self._mr_load()


def _mr_load(self):
    _fill(self._mr_lists, _call(services.module_lists) or [], lambda r: (
        r["name"], r["module_code"] or "—", r["items"]), iid=lambda r: r["list_id"])


def _mr_link(self):
    lst = _selected(self._mr_lists)
    if lst and _call(services.link_list, int(lst), self._mr_module.get(), write=True):
        self._mr_load()


def _mr_check(self):
    lst = _selected(self._mr_lists)
    check = lst and _call(services.holdings_check, int(lst))
    if not check:
        return
    self._mr_note.set(f"{check['students']} student(s) on {check['list']['module_code'] or 'no module'}"
                      f" — essential: 1 copy per {services.ESSENTIAL_RATIO}, recommended: 1 per "
                      f"{services.RECOMMENDED_RATIO}.")
    _fill(self._mr_items, check["items"], lambda r: (
        r["title"] or r["book_id"], r["importance"], r["lendable"], r["needed"],
        r["shortfall"] or ""), iid=lambda r: r["item_id"])


def _mr_importance(self, importance):
    item = _selected(self._mr_items)
    if item and _call(services.set_importance, int(item), importance, write=True):
        self._mr_check()


def _mr_request(self):
    lst = _selected(self._mr_lists)
    made = lst and _call(services.request_shortfall, int(lst), _me(self), write=True)
    if made is not None and lst:
        messagebox.showinfo("Reading list", f"{made} purchase request(s) raised for "
                            "Acquisitions.")


# ── acquisitions ────────────────────────────────────────────────────────


def show_acquisitions(self):
    tab = _tab(self, "Acquisitions", "manage_books")
    if tab is None:
        return
    fb = _bar(tab)
    self._aq_fund = {k: _entry(fb, label, w) for k, label, w in (
        ("code", "Fund code", 8), ("name", "Name", 16), ("year", "Year", 8),
        ("amount", "Allocation £", 8))}
    ttk.Button(fb, text="Save fund", command=self._aq_save_fund).pack(side="left")
    self._aq_funds = _tree(tab, [("code", "Fund"), ("name", "Name"), ("alloc", "Allocation"),
                                 ("committed", "Committed"), ("spent", "Spent"),
                                 ("left", "Remaining")], [90, 220, 100, 100, 100, 100], height=3)
    ttk.Label(tab, text="Purchase requests:", font=("Arial", 10, "bold")).pack(anchor="w", padx=8)
    self._aq_requests = _tree(tab, [("title", "Title"), ("isbn", "ISBN"), ("why", "Why"),
                                    ("priority", "Priority")], [260, 120, 380, 70], height=4)
    ob = _bar(tab)
    self._aq_order = {k: _entry(ob, label, w) for k, label, w in (
        ("supplier", "Supplier", 12), ("fund", "Fund", 7), ("qty", "Qty", 3),
        ("price", "£ each", 6))}
    ttk.Button(ob, text="Order selected request", command=self._aq_place).pack(side="left")
    ttk.Label(tab, text="Open orders:", font=("Arial", 10, "bold")).pack(anchor="w", padx=8)
    rb = _bar(tab)
    self._aq_recv = _entry(rb, "Arrived qty", 3, "1")
    self._aq_loc = _entry(rb, "Shelve at", 10)
    ttk.Button(rb, text="Receive", command=self._aq_receive).pack(side="left")
    ttk.Button(rb, text="Cancel order…", command=self._aq_cancel).pack(side="left", padx=4)
    self._aq_orders = _tree(tab, [("title", "Title"), ("supplier", "Supplier"), ("fund", "Fund"),
                                  ("qty", "Received / ordered"), ("cost", "£"),
                                  ("status", "Status")], [260, 130, 70, 130, 80, 100], height=4)
    self._aq_load()


def _aq_load(self):
    _fill(self._aq_funds, _call(services.fund_position) or [], lambda f: (
        f["fund_code"], f["name"], f"£{f['allocation']:,.2f}", f"£{f['committed']:,.2f}",
        f"£{f['spent']:,.2f}", f"£{f['remaining']:,.2f}"))
    _fill(self._aq_requests, _call(services.requests) or [], lambda r: (
        r["title"], r["isbn"] or "", r["reason"] or "", r["priority"] or ""),
        iid=lambda r: r["request_id"])
    _fill(self._aq_orders, _call(services.orders) or [], lambda o: (
        o["title"], o["supplier"], o["fund_code"], f"{o['received_qty']} / {o['quantity']}",
        f"{o['quantity'] * o['unit_price']:,.2f}", o["status"]), iid=lambda o: o["order_id"])


def _aq_save_fund(self):
    f = {k: v.get() for k, v in self._aq_fund.items()}
    if _call(services.set_fund, f["code"], f["name"], f["year"], f["amount"], write=True):
        self._aq_load()


def _aq_place(self, force=False):
    req = _selected(self._aq_requests)
    if not req:
        messagebox.showinfo("Acquisitions", "Select a purchase request.")
        return
    o = {k: v.get() for k, v in self._aq_order.items()}
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    try:
        services.place_order(conn, supplier=o["supplier"], fund_code=o["fund"],
                             quantity=o["qty"], unit_price=o["price"], request_id=int(req),
                             actor=_me(self), force=force)
        conn.commit()
    except ValueError as exc:
        conn.rollback()
        if str(exc).startswith("Over budget") and not force and messagebox.askyesno(
                "Over budget", f"{exc}\n\nOrder anyway?"):
            return self._aq_place(force=True)
        messagebox.showerror("Acquisitions", str(exc))
        return None
    finally:
        conn.close()
    self._aq_load()


def _aq_receive(self):
    order = _selected(self._aq_orders)
    made = order and _call(services.receive, int(order), self._aq_recv.get(),
                           self._aq_loc.get() or None, write=True)
    if made:
        messagebox.showinfo("Received", "New copies:\n" + "\n".join(made))
        self._aq_load()


def _aq_cancel(self):
    order = _selected(self._aq_orders)
    reason = order and simpledialog.askstring("Cancel order", "Why?")
    if reason and _call(services.cancel_order, int(order), reason, write=True):
        self._aq_load()


# ── stocktake ───────────────────────────────────────────────────────────


def show_stocktake(self):
    tab = _tab(self, "Stocktake", "manage_books")
    if tab is None:
        return
    bar = _bar(tab)
    ttk.Label(bar, text="Location:").pack(side="left")
    self._st_loc = ttk.Combobox(bar, values=_call(services.locations) or [], width=18,
                                state="readonly")
    self._st_loc.pack(side="left", padx=4)
    ttk.Button(bar, text="Start", command=self._st_start).pack(side="left")
    scan = _bar(tab)
    ttk.Label(scan, text="Scan barcode:").pack(side="left")
    self._st_code = tk.StringVar()
    entry = ttk.Entry(scan, textvariable=self._st_code, width=24)
    entry.pack(side="left", padx=4)
    entry.bind("<Return>", lambda _e: self._st_scan())
    ttk.Button(scan, text="Finish (mark unseen copies missing)", command=self._st_finish).pack(
        side="left", padx=8)
    self._st_progress = tk.StringVar(value="Choose a location and start.")
    ttk.Label(tab, textvariable=self._st_progress).pack(anchor="w", padx=8)
    self._st_log = tk.Listbox(tab, height=18)
    self._st_log.pack(fill="both", expand=True, **_PAD)
    self._st_id = None


def _st_start(self):
    sid = _call(services.start_stocktake, self._st_loc.get(), _me(self), write=True)
    if sid:
        self._st_id = sid
        self._st_log.delete(0, "end")
        self._st_update()


def _st_update(self):
    p = _call(services.stocktake_progress, self._st_id)
    if p:
        self._st_progress.set(f"{p['stocktake']['location']}: {p['scanned']} scanned, "
                              f"{len(p['not_seen'])} of {p['expected']} expected not yet seen.")


def _st_scan(self):
    code = self._st_code.get().strip()
    if not self._st_id or not code:
        return
    message = _call(services.scan, self._st_id, code, write=True)
    if message:
        self._st_log.insert(0, f"{code}: {message}")
        self._st_code.set("")
        self._st_update()


def _st_finish(self):
    if not self._st_id:
        return
    p = _call(services.stocktake_progress, self._st_id)
    if p and messagebox.askyesno("Finish stocktake", f"Mark {len(p['not_seen'])} unseen "
                                 "copies as missing?"):
        result = _call(services.finish_stocktake, self._st_id, write=True)
        if result:
            messagebox.showinfo("Stocktake", f"{result['scanned']} scanned; missing: "
                                + (", ".join(result["missing"]) or "none"))
            self._st_id = None


# ── leavers ─────────────────────────────────────────────────────────────


def show_leavers(self):
    tab = _tab(self, "Leavers", "manage_loans")
    if tab is None:
        return
    ttk.Label(tab, wraplength=900, justify="left", text=(
        "Students whose studies have ended but who still hold library items or owe charges. "
        "Withdrawn students are sent a notice automatically; send another from here.")).pack(
        anchor="w", padx=8, pady=4)
    ttk.Button(_bar(tab), text="Send reminder to selected", command=self._lv_notify).pack(
        side="left")
    self._lv_tree = _tree(tab, [("id", "Student"), ("name", "Name"), ("status", "Status"),
                                ("loans", "Items"), ("owed", "Owed")],
                          [100, 220, 110, 70, 90], height=16)
    _fill(self._lv_tree, _call(services.leavers) or [], lambda r: (
        r["student_id"], r["name"], r["status"], r["loans"], f"£{r['owed']:.2f}"),
        iid=lambda r: r["student_id"])


def _lv_notify(self):
    sid = _selected(self._lv_tree)
    if sid and _call(services.notify_leaver, sid, write=True) is not None:
        messagebox.showinfo("Leavers", f"Reminder sent to {sid}.")


# ── e-resources ─────────────────────────────────────────────────────────


def show_eresources(self):
    tab = _tab(self, "E-resources", "manage_books")
    if tab is None:
        return
    form = ttk.Frame(tab)
    form.pack(fill="x", **_PAD)
    self._er = {}
    fields = (("title", "Title", 22), ("provider", "Provider", 14), ("resource_type", "Type", 10),
              ("url", "URL", 22), ("concurrent_users", "Users", 4), ("annual_cost", "£/year", 7),
              ("start_date", "Start", 10), ("renewal_date", "Renews", 10),
              ("notice_days", "Notice days", 4), ("status", "Status", 8))
    for i, (key, label, width) in enumerate(fields):
        ttk.Label(form, text=label).grid(row=i // 5, column=(i % 5) * 2, sticky="w", padx=3)
        var = tk.StringVar(value="active" if key == "status" else "")
        ttk.Entry(form, textvariable=var, width=width).grid(row=i // 5, column=(i % 5) * 2 + 1,
                                                            padx=3, pady=2)
        self._er[key] = var
    bar = _bar(tab)
    ttk.Button(bar, text="Add new", command=lambda: self._er_save(None)).pack(side="left")
    ttk.Button(bar, text="Update selected", command=lambda: self._er_save(
        _selected(self._er_tree))).pack(side="left", padx=4)
    self._er_period = _entry(bar, "   Usage month (YYYY-MM)", 8)
    self._er_uses = _entry(bar, "uses", 6)
    ttk.Button(bar, text="Record usage", command=self._er_usage).pack(side="left")
    self._er_tree = _tree(tab, [("title", "Resource"), ("provider", "Provider"),
                                ("cost", "£/year"), ("uses", "Uses (12m)"),
                                ("cpu", "£ per use"), ("renews", "Renews"),
                                ("flag", "Decision")], [230, 130, 90, 90, 80, 100, 120],
                         height=10)
    self._er_tree.bind("<<TreeviewSelect>>", lambda _e: self._er_pick())
    self._er_load()


def _er_load(self):
    self._er_rows = {str(r["resource_id"]): r for r in _call(services.eresources) or []}
    _fill(self._er_tree, self._er_rows.values(), lambda r: (
        r["title"], r["provider"] or "", "" if r["annual_cost"] is None else f"{r['annual_cost']:,.0f}",
        r["uses_12m"], "" if r["cost_per_use"] is None else f"{r['cost_per_use']:.2f}",
        r["renewal_date"] or "", "RENEWAL DUE" if r["decision_due"] else r["status"]),
        iid=lambda r: r["resource_id"])


def _er_pick(self):
    row = self._er_rows.get(_selected(self._er_tree) or "")
    for key, var in (self._er.items() if row else ()):
        var.set("" if row.get(key) is None else str(row[key]))


def _er_save(self, resource_id):
    values = {k: v.get() for k, v in self._er.items()}
    if _call(services.save_eresource, values, int(resource_id) if resource_id else None,
             write=True):
        self._er_load()


def _er_usage(self):
    rid = _selected(self._er_tree)
    if rid and _call(services.record_usage, int(rid), self._er_period.get(), self._er_uses.get(),
                     write=True):
        self._er_load()


BINDINGS = {name: obj for name, obj in dict(globals()).items()
            if callable(obj) and (name.startswith("show_") or name[:4] in (
                "_ml_", "_cp_", "_hr_", "_lr_", "_mr_", "_aq_", "_st_", "_lv_", "_er_")
                or name == "_ext_user")}
