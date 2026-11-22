"""Library screen.

The old window's two tabs are kept: Catalogue (Search, Category, Active only,
Available; New, Edit, Toggle active, Lend, Delete, Refresh, with the old
columns) and Loans (Status, Pupil, Apply, Return, Mark lost, Refresh, with the
old columns). The old book and Lend dialogs keep their fields. Added: a Desk
tab to issue and return by barcode, each copy with its own barcode, renewals,
reservations, the overdue list with e-mails home, reading reports, exports and
the loan rules. Rules live in :mod:`modules.library.domain.library`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    make_toplevel,
    messagebox,
    simpledialog,
)
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.library.domain import library as LB
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = "All"
YEARS = ("7", "8", "9", "10", "11")
STATUS_BG = {"Out": "#ffffff", "Returned": "#e7f6ea", "Overdue": "#fde2e2", "Lost": "#eeeeee",
             "inactive": "#eeeeee", "none": "#fff6d5", "Available": "#ffffff",
             "On loan": "#e6f2ff", "On hold": "#fff6d5", "Withdrawn": "#eeeeee",
             "Waiting": "#ffffff", "Ready": "#fff6d5"}
_ERRORS = (LB.ValidationError, LB.PermissionDenied, LB.NotFound)


_problems = W.problems


def _tree(parent, columns, height: int = 10, *, multi: bool = False) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select="extended" if multi else "browse",
                  stretch={"title", "book", "pupil"}, tags=STATUS_BG)


_text_window = W.text_window


def _grid_rows(frm, rows, start: int = 0) -> None:
    for i, (text, w) in enumerate(rows, start):
        ttk.Label(frm, text=text).grid(row=i, column=0, sticky="nw", pady=2, padx=(0, 8))
        w.grid(row=i, column=1, sticky="w", pady=2)


def _buttons(frm, row: int, win, save, label: str = "Save") -> None:
    bar = ttk.Frame(frm)
    bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="right")
    ttk.Button(bar, text=label, command=save).pack(side="right", padx=(0, 6))


def _pct(v) -> str:
    return "-" if v is None else f"{v}%"


def _pupil_from(owner, text: str) -> P.Pupil | None:
    p = P.find_by_reference(text.strip()) if text.strip() else None
    if p is None:
        messagebox.showinfo("Library", "No pupil with that admission number or UPN.",
                            parent=owner)
    return p


def _save_csv(owner, name: str, fn) -> None:
    path = filedialog.asksaveasfilename(parent=owner, defaultextension=".csv",
                                        initialfile=name, filetypes=[("CSV", "*.csv")])
    if not path:
        return
    try:
        n = fn(path)
    except (*_ERRORS, OSError) as e:
        messagebox.showerror("Export", _problems(e), parent=owner)
        return
    messagebox.showinfo("Export", f"Saved {n} row(s) to {path}.", parent=owner)


_BOOK_COLS = (("id", "ID", 45), ("title", "Title", 240), ("author", "Author", 150),
              ("cat", "Cat", 85), ("year", "Yr", 45), ("copies", "Avail/Tot", 70),
              ("isbn", "ISBN", 115), ("location", "Loc", 80), ("active", "Act", 40),
              ("subj", "Subject", 60), ("res", "Reserved", 65))
_LOAN_COLS = (("id", "ID", 45), ("date", "Loan", 85), ("due", "Due", 85),
              ("ret", "Returned", 85), ("pupil", "Pupil", 160), ("book", "Book", 220),
              ("status", "Status", 70), ("od", "Days OD", 60), ("copy", "Copy", 75),
              ("ren", "Renewed", 60))


def _loan_row(x: LB.Loan) -> tuple:
    return (x.loan_id, x.loan_date, x.due_date, x.returned_date or "", x.pupil_name,
            x.book_title, x.shown_status, x.days_overdue or "", x.barcode, x.renewals or "")


class LibraryPage:
    TABS = ("Catalogue", "Loans", "Desk", "Reservations", "Overdue", "Reports", "Settings")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = LB.is_editor(principal)
        activity_log.record("library.view")
        ttk.Label(parent, text="Library", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(anchor="w",
                                                                                 pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_catalogue(self.tabs["Catalogue"])
        self._build_loans(self.tabs["Loans"])
        self.book.select(self.TABS.index(state.get("tab", "Catalogue")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _summary(self) -> None:
        o = LB.overview()
        lo = o["loans"]
        self.summary_var.set(f"Titles: {o['books_total']} (active {o['books_active']}) · copies "
                             f"{o['copies_avail']}/{o['copies_total']} on the shelf · out "
                             f"{lo['Out']} · overdue {lo['Overdue']} · lost {lo['Lost']} · "
                             f"reservations {o['holds']}")

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        self._summary()
        if name == "Catalogue":
            self.refresh_books()
            return
        if name == "Loans":
            self.refresh_loans()
            return
        tab = self.tabs[name]
        for w in tab.winfo_children():
            w.destroy()
        try:
            {"Desk": self._draw_desk, "Reservations": self._draw_holds,
             "Overdue": self._draw_overdue, "Reports": self._draw_reports,
             "Settings": self._draw_settings}[name](tab)
        except Exception:
            logger.exception("Library tab %s failed", name)
            ttk.Label(tab, text="Couldn't load this tab - see the log.",
                      foreground="#a00").pack(anchor="w")

    def _redraw(self) -> None:
        self._on_tab()

    # ── Catalogue (old tab) ──────────────────────────────────────────

    def _build_catalogue(self, tab: ttk.Frame) -> None:
        st = self.state
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Search:").pack(side="left", padx=(0, 4))
        self.search_var = tk.StringVar(value=st.get("search", ""))
        e = ttk.Entry(bar, textvariable=self.search_var, width=20)
        e.pack(side="left")
        e.bind("<Return>", lambda _e: self.refresh_books())
        ttk.Label(bar, text="Category:").pack(side="left", padx=(8, 4))
        self.cat_var = tk.StringVar(value=st.get("category", ALL))
        ttk.Combobox(bar, textvariable=self.cat_var, values=[ALL, *LB.CATEGORIES],
                     state="readonly", width=11).pack(side="left")
        self.active_var = tk.BooleanVar(value=st.get("active_only", False))
        ttk.Checkbutton(bar, text="Active only", variable=self.active_var,
                        command=self.refresh_books).pack(side="left", padx=(8, 0))
        self.avail_var = tk.BooleanVar(value=st.get("available", False))
        ttk.Checkbutton(bar, text="Available", variable=self.avail_var,
                        command=self.refresh_books).pack(side="left", padx=(4, 0))
        for text, cmd in (("New", self.new), ("Edit", self.edit),
                          ("Toggle active", self.toggle), ("Lend", self.lend),
                          ("Delete", self.delete), ("Refresh", self.refresh_books)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        ttk.Label(bar2, text="Subject:").pack(side="left", padx=(0, 4))
        self.subjects = {f"{s.code} - {s.name}": s.subject_id for s in S.list_subjects()}
        self.subj_var = tk.StringVar(value=st.get("subject", ALL))
        ttk.Combobox(bar2, textvariable=self.subj_var, values=[ALL, *self.subjects],
                     state="readonly", width=22).pack(side="left")
        for text, cmd in (("Copies…", self.copies), ("Reserve…", self.reserve),
                          ("Loan history", self.book_loans), ("History", self.history),
                          ("Export catalogue…", self.export)):
            ttk.Button(bar2, text=text, command=cmd).pack(side="left", padx=(8, 2))
        for var in (self.cat_var, self.subj_var):
            var.trace_add("write", lambda *_: self.refresh_books())
        self.book_tree = _tree(tab, _BOOK_COLS, height=15)
        self.book_tree.bind("<Double-1>", lambda _e: self.edit())
        self.books: dict[str, LB.Book] = {}

    def refresh_books(self) -> None:
        self.state.update(search=self.search_var.get(), category=self.cat_var.get(),
                          active_only=self.active_var.get(), available=self.avail_var.get(),
                          subject=self.subj_var.get())
        cat = self.cat_var.get()
        rows = LB.list_books(active_only=self.active_var.get(),
                             category=None if cat == ALL else cat,
                             available_only=self.avail_var.get(),
                             query=self.search_var.get().strip() or None,
                             subject_id=self.subjects.get(self.subj_var.get()))
        self.book_tree.delete(*self.book_tree.get_children())
        self.books = {}
        for b in rows:
            iid = str(b.book_id)
            self.books[iid] = b
            tag = "inactive" if not b.is_active else ("none" if not b.copies_available
                                                      else "Available")
            self.book_tree.insert("", "end", iid=iid, tags=(tag,), values=(
                b.book_id, b.title, b.author or "", b.category, b.year_published or "",
                b.copies_label, b.isbn or "", b.location or "", "Yes" if b.is_active else "No",
                b.subject_code or "", b.waiting or ""))
        self._summary()

    def _book(self) -> LB.Book | None:
        sel = self.book_tree.selection()
        if not sel:
            messagebox.showinfo("Library", "Select a book first.", parent=self.parent)
            return None
        return self.books.get(sel[0])

    def new(self) -> None:
        book_dialog(self.parent, self.principal, None, self.refresh_books)

    def edit(self) -> None:
        b = self._book()
        if b:
            book_dialog(self.parent, self.principal, b, self.refresh_books)

    def toggle(self) -> None:
        b = self._book()
        if not b:
            return
        try:
            LB.toggle_active(b.book_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Toggle active", _problems(e), parent=self.parent)
            return
        self.refresh_books()

    def lend(self) -> None:
        b = self._book()
        if b:
            lend_dialog(self.parent, self.principal, b, self.refresh_books)

    def delete(self) -> None:
        b = self._book()
        if not b or not messagebox.askyesno("Delete book", f"Delete '{b.title}' and its "
                                            f"{b.copies_total} cop(ies)?", parent=self.parent):
            return
        try:
            LB.delete_book(b.book_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Delete book", _problems(e), parent=self.parent)
            return
        self.refresh_books()

    def copies(self) -> None:
        b = self._book()
        if b:
            CopiesWindow(self.parent, self.principal, b, on_close=self.refresh_books)

    def reserve(self) -> None:
        b = self._book()
        if not b:
            return
        ref = simpledialog.askstring("Reserve", f"Reserve '{b.title}' for which pupil?\n"
                                     "Admission number or UPN:", parent=self.parent)
        p = _pupil_from(self.parent, ref or "") if ref else None
        if not p:
            return
        try:
            LB.reserve(b.book_id, p.pupil_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Reserve", _problems(e), parent=self.parent)
            return
        messagebox.showinfo("Reserve", f"{p.display_name} is on the list for '{b.title}'.",
                            parent=self.parent)
        self.refresh_books()

    def book_loans(self) -> None:
        b = self._book()
        if not b:
            return
        rows = LB.list_loans(book_id=b.book_id)
        _text_window(self.parent, f"{b.title} - loans", "\n".join(
            f"{x.loan_date}  {x.barcode:<9} {x.pupil_name[:26]:<26} due {x.due_date}  "
            f"{x.shown_status}" + (f" ({x.returned_date})" if x.returned_date else "")
            for x in rows) or "Never borrowed.")

    def history(self) -> None:
        b = self._book()
        if not b:
            return
        lines = [f"{h['at']}  {h['actor']:<14} {h['action']:<12} "
                 + ", ".join(f"{k}: {v}" for k, v in h["detail"].items())
                 for h in LB.history(b.book_id)]
        _text_window(self.parent, f"{b.title} - history", "\n".join(lines) or "No changes.")

    def export(self) -> None:
        _save_csv(self.parent, "library-catalogue.csv",
                  lambda path: LB.export_catalogue(path, actor=self.principal))

    # ── Loans (old tab) ──────────────────────────────────────────────

    def _build_loans(self, tab: ttk.Frame) -> None:
        st = self.state
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
        self.lstatus_var = tk.StringVar(value=st.get("loan_status", "Out"))
        ttk.Combobox(bar, textvariable=self.lstatus_var, values=[ALL, *LB.LOAN_STATUSES],
                     state="readonly", width=9).pack(side="left")
        ttk.Label(bar, text="Pupil:").pack(side="left", padx=(8, 4))
        self.lpupil_var = tk.StringVar(value=st.get("loan_pupil", ""))
        e = ttk.Entry(bar, textvariable=self.lpupil_var, width=12)
        e.pack(side="left")
        e.bind("<Return>", lambda _e: self.refresh_loans())
        ttk.Label(bar, text="Year:").pack(side="left", padx=(8, 4))
        self.lyear_var = tk.StringVar(value=st.get("loan_year", ALL))
        ttk.Combobox(bar, textvariable=self.lyear_var, values=[ALL, *YEARS],
                     state="readonly", width=5).pack(side="left")
        for text, cmd in (("Apply", self.refresh_loans), ("Return", self.return_loan),
                          ("Mark lost", self.mark_lost), ("Refresh", self.refresh_loans)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        for text, cmd in (("Renew", self.renew), ("Delete loan", self.delete_loan),
                          ("Open pupil", self.open_loan_pupil)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(8, 2))
        self.loan_tree = _tree(tab, _LOAN_COLS, height=16)
        self.loans: dict[str, LB.Loan] = {}

    def refresh_loans(self) -> None:
        st = self.state
        st.update(loan_status=self.lstatus_var.get(), loan_pupil=self.lpupil_var.get(),
                  loan_year=self.lyear_var.get())
        pid = None
        if self.lpupil_var.get().strip():
            p = _pupil_from(self.parent, self.lpupil_var.get())
            if p is None:
                return
            pid = p.pupil_id
        status, year = self.lstatus_var.get(), self.lyear_var.get()
        rows = LB.list_loans(status=None if status == ALL else status, pupil_id=pid,
                             year_group=None if year == ALL else int(year))
        self.loan_tree.delete(*self.loan_tree.get_children())
        self.loans = {}
        for x in rows:
            iid = str(x.loan_id)
            self.loans[iid] = x
            self.loan_tree.insert("", "end", iid=iid, values=_loan_row(x),
                                  tags=(x.shown_status,))
        self._summary()

    def _loan(self) -> LB.Loan | None:
        sel = self.loan_tree.selection()
        if not sel:
            messagebox.showinfo("Library", "Select a loan first.", parent=self.parent)
            return None
        return self.loans.get(sel[0])

    def return_loan(self) -> None:
        x = self._loan()
        if not x:
            return
        try:
            _loan, hold = LB.return_loan(x.loan_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Return", _problems(e), parent=self.parent)
            return
        _hold_notice(self.parent, hold)
        self.refresh_loans()

    def mark_lost(self) -> None:
        x = self._loan()
        if not x or not messagebox.askyesno("Mark lost", f"Mark '{x.book_title}' ({x.barcode}) "
                                            f"borrowed by {x.pupil_name} as lost?",
                                            parent=self.parent):
            return
        try:
            LB.mark_lost(x.loan_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Mark lost", _problems(e), parent=self.parent)
            return
        self.refresh_loans()

    def renew(self) -> None:
        x = self._loan()
        if not x:
            return
        try:
            r = LB.renew(x.loan_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Renew", _problems(e), parent=self.parent)
            return
        messagebox.showinfo("Renew", f"Now due {r.due_date}.", parent=self.parent)
        self.refresh_loans()

    def delete_loan(self) -> None:
        x = self._loan()
        if not x or not messagebox.askyesno("Delete loan", f"Delete loan #{x.loan_id} "
                                            "(entered by mistake)?", parent=self.parent):
            return
        try:
            LB.delete_loan(x.loan_id, actor=self.principal)
        except _ERRORS as e:
            messagebox.showerror("Delete loan", _problems(e), parent=self.parent)
            return
        self.refresh_loans()

    def open_loan_pupil(self) -> None:
        x = self._loan()
        if x and self.open_pupil:
            self.open_pupil(x.pupil_id)

    # ── Desk ─────────────────────────────────────────────────────────

    def _draw_desk(self, tab: ttk.Frame) -> None:
        ttk.Label(tab, text="Scan or type a pupil, then scan books to issue them. Scan a "
                            "book on its own to return it.", foreground="#666").pack(anchor="w")
        top = ttk.Frame(tab)
        top.pack(fill="x", pady=6)
        ttk.Label(top, text="Pupil:").pack(side="left")
        pupil_e = ttk.Entry(top, width=14)
        pupil_e.pack(side="left", padx=4)
        who = tk.StringVar(value="(no pupil)")
        ttk.Label(top, textvariable=who, font=("", 10, "bold")).pack(side="left", padx=8)
        mid = ttk.Frame(tab)
        mid.pack(fill="x", pady=6)
        ttk.Label(mid, text="Book barcode:").pack(side="left")
        code_e = ttk.Entry(mid, width=14)
        code_e.pack(side="left", padx=4)
        log = tk.Text(tab, height=8, wrap="word")
        ttk.Label(tab, text="Books out to this pupil:").pack(anchor="w")
        tree = _tree(tab, _LOAN_COLS, height=8)
        log.pack(fill="x", pady=(6, 0))
        current: dict[str, P.Pupil | None] = {"p": None}

        def say(msg: str) -> None:
            log.insert("1.0", msg + "\n")

        def show() -> None:
            tree.delete(*tree.get_children())
            p = current["p"]
            if p is None:
                return
            info = LB.for_pupil(p.pupil_id)
            for x in info["out"]:
                tree.insert("", "end", values=_loan_row(x), tags=(x.shown_status,))
            ok, why = LB.can_borrow(p.pupil_id)
            who.set(f"{p.display_name} ({p.admission_no}, Y{p.year_group}) · "
                    f"{len(info['out'])} out" + ("" if ok else " · " + "; ".join(why))
                    + (" · ready to collect: " + ", ".join(h.book_title for h in info["holds"]
                                                           if h.status == "Ready")
                       if any(h.status == "Ready" for h in info["holds"]) else ""))

        def pick(_e=None) -> None:
            current["p"] = _pupil_from(tab, pupil_e.get())
            show()
            code_e.focus_set()

        def scan(_e=None) -> None:
            code = code_e.get().strip()
            code_e.delete(0, "end")
            if not code:
                return
            p = current["p"]
            try:
                copy = LB.find_copy(code)
                if copy and copy.status in ("On loan", "Lost"):
                    loan, hold = LB.return_by_barcode(code, actor=self.principal)
                    say(f"Returned {loan.book_title} ({code}) from {loan.pupil_name}"
                        + (f" → keep it for {hold.pupil_name}, who reserved it"
                           if hold else ""))
                elif p is None:
                    say(f"{code}: choose a pupil first to issue it")
                else:
                    loan = LB.lend(p.pupil_id, barcode=code, actor=self.principal)
                    say(f"Issued {loan.book_title} ({code}) to {p.display_name}, due "
                        f"{loan.due_date}")
            except _ERRORS as e:
                say(f"{code}: " + _problems(e).replace("\n", " "))
            show()
            self._summary()
        pupil_e.bind("<Return>", pick)
        code_e.bind("<Return>", scan)
        ttk.Button(top, text="Find", command=pick).pack(side="left")
        ttk.Button(mid, text="Issue / return", command=scan).pack(side="left")
        pupil_e.focus_set()

    # ── Reservations ─────────────────────────────────────────────────

    def _draw_holds(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        tree = _tree(tab, (("id", "ID", 45), ("book", "Book", 240), ("pupil", "Pupil", 170),
                           ("status", "Status", 70), ("placed", "Placed", 130),
                           ("copy", "Kept copy", 80), ("until", "Collect by", 90)), height=16)
        rows: dict[str, LB.Hold] = {}

        def fill() -> None:
            tree.delete(*tree.get_children())
            rows.clear()
            for h in LB.list_holds():
                rows[str(h.hold_id)] = h
                tree.insert("", "end", iid=str(h.hold_id), tags=(h.status,), values=(
                    h.hold_id, h.book_title, h.pupil_name, h.status, h.placed_at,
                    h.barcode or "", h.expires_on or ""))

        def cancel() -> None:
            sel = tree.selection()
            if not sel:
                return
            try:
                LB.cancel_hold(int(sel[0]), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Cancel reservation", _problems(e), parent=tab)
            fill()

        def expire() -> None:
            try:
                n = LB.expire_holds(actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Reservations", _problems(e), parent=tab)
                return
            messagebox.showinfo("Reservations", f"Released {n} uncollected book(s) to the "
                                "next pupil (or the shelf).", parent=tab)
            fill()
        for text, cmd in (("Cancel reservation", cancel),
                          ("Release uncollected", expire), ("Refresh", fill)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        fill()

    # ── Overdue ──────────────────────────────────────────────────────

    def _draw_overdue(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        year = tk.StringVar(value=self.state.get("od_year", ALL))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=year, values=[ALL, *YEARS], state="readonly",
                     width=5).pack(side="left")
        tree = _tree(tab, (("pupil", "Pupil", 170), ("adm", "Adm no", 85), ("yr", "Yr", 35),
                           ("form", "Form", 60), ("book", "Book", 230), ("copy", "Copy", 75),
                           ("due", "Due", 85), ("od", "Days overdue", 85)), height=16,
                     multi=True)
        rows: dict[str, LB.Loan] = {}

        def fill(*_a) -> None:
            self.state["od_year"] = year.get()
            tree.delete(*tree.get_children())
            rows.clear()
            for x in LB.overdue(year_group=None if year.get() == ALL else int(year.get())):
                rows[str(x.loan_id)] = x
                tree.insert("", "end", iid=str(x.loan_id), tags=("Overdue",), values=(
                    x.pupil_name, x.admission_no, x.year_group, x.form_group or "",
                    x.book_title, x.barcode, x.due_date, x.days_overdue))

        def remind() -> None:
            chosen = [rows[i].pupil_id for i in tree.selection()] or None
            n = len({x.pupil_id for x in rows.values()}) if chosen is None else len(set(chosen))
            if not rows or not messagebox.askyesno(
                    "E-mail families", f"E-mail the families of {n} pupil(s) about their "
                    "overdue books?" + ("" if chosen else " (select rows to choose pupils)"),
                    parent=tab):
                return
            try:
                res = LB.remind_overdue(actor=self.principal, pupil_ids=chosen)
            except _ERRORS as e:
                messagebox.showerror("E-mail families", _problems(e), parent=tab)
                return
            from education_system.systems.secondary.modules.communication.gui import email_views
            for mid in res["sent"]:
                email_views.deliver_in_background(tab, mid, self.principal,
                                                  lambda _r, _e: None)
            messagebox.showinfo("E-mail families", f"{len(res['sent'])} e-mail(s) on their "
                                "way (see Email for delivery)."
                                + ("\n\nNo e-mail address for: " + ", ".join(res["no_email"])
                                   if res["no_email"] else ""), parent=tab)

        def open_row() -> None:
            sel = tree.selection()
            if sel and self.open_pupil:
                self.open_pupil(rows[sel[0]].pupil_id)
        for text, cmd in (("E-mail families…", remind), ("Open pupil", open_row),
                          ("Export…", lambda: _save_csv(tab, "library-overdue.csv", lambda p:
                                                        LB.export_overdue(
                                                            p, actor=self.principal))),
                          ("Refresh", fill)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(8, 2))
        year.trace_add("write", fill)
        fill()

    # ── Reports ──────────────────────────────────────────────────────

    def _draw_reports(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        year = tk.StringVar(value=self.state.get("rep_year", ALL))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        ttk.Combobox(bar, textvariable=year, values=[ALL, *YEARS], state="readonly",
                     width=5).pack(side="left")
        info = tk.StringVar()
        ttk.Label(tab, textvariable=info, justify="left").pack(anchor="w", pady=4)
        panes = ttk.Frame(tab)
        panes.pack(fill="both", expand=True)
        left, right = ttk.Frame(panes), ttk.Frame(panes)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Most borrowed (last 12 months)", font=("", 10, "bold")).pack(
            anchor="w")
        pop = _tree(left, (("title", "Title", 220), ("n", "Loans", 60)), height=14)
        ttk.Label(right, text="Pupils who haven't borrowed (double-click to open)",
                  font=("", 10, "bold")).pack(anchor="w")
        non = _tree(right, (("pupil", "Pupil", 200), ("yr", "Yr", 35), ("form", "Form", 60)),
                    height=14)
        ids: dict[str, int] = {}

        def fill(*_a) -> None:
            self.state["rep_year"] = year.get()
            r = LB.reading_report(year_group=None if year.get() == ALL else int(year.get()))
            info.set(f"{r['borrowers']} of {r['pupils']} pupils borrowed in the last 12 months "
                     f"({_pct(r['all_pct'])}), {r['loans']} loans · FSM pupils "
                     f"{_pct(r['fsm_pct'])}\nBy year: "
                     + " · ".join(f"Y{y} {_pct(v)}" for y, v in r["by_year"].items())
                     + ("\nTop readers: " + ", ".join(f"{p.display_name} ({n})"
                                                      for p, n in r["top_readers"][:5])
                        if r["top_readers"] else ""))
            pop.delete(*pop.get_children())
            for b, n in LB.popular():
                pop.insert("", "end", values=(b.title, n))
            non.delete(*non.get_children())
            ids.clear()
            for p in r["non_borrowers"]:
                iid = non.insert("", "end", values=(
                    f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name}",
                    p.year_group, p.form_group or ""))
                ids[iid] = p.pupil_id

        def open_row(_e=None) -> None:
            sel = non.selection()
            if sel and self.open_pupil:
                self.open_pupil(ids[sel[0]])
        non.bind("<Double-1>", open_row)
        year.trace_add("write", fill)
        fill()

    # ── Settings ─────────────────────────────────────────────────────

    def _draw_settings(self, tab: ttk.Frame) -> None:
        cur = LB.settings()
        frm = ttk.Frame(tab)
        frm.pack(anchor="w")
        v = {k: tk.StringVar(value=str(cur[k])) for k in LB.DEFAULTS if k != "block_overdue"}
        block = tk.BooleanVar(value=bool(cur["block_overdue"]))
        state = "normal" if self.editor else "disabled"
        rows = [(LB._LIMITS[k][2] + ":", ttk.Entry(frm, textvariable=var, width=6,
                                                   state=state)) for k, var in v.items()]
        rows.append(("", ttk.Checkbutton(frm, text="Pupils with an overdue book can't borrow "
                                         "more", variable=block, state=state)))
        _grid_rows(frm, rows)
        if not self.editor:
            ttk.Label(tab, text="Only the librarian can change these.",
                      foreground="#888").pack(anchor="w", pady=6)
            return

        def save() -> None:
            try:
                LB.set_settings({**{k: var.get() for k, var in v.items()},
                                 "block_overdue": int(block.get())}, actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Library settings", _problems(e), parent=tab)
                return
            messagebox.showinfo("Library settings", "Saved.", parent=tab)
        ttk.Button(tab, text="Save", command=save).pack(anchor="w", pady=8)


def draw_library(parent: ttk.Frame, *, principal: Principal, state: dict | None = None,
                 open_pupil: Callable[[int], None] | None = None) -> LibraryPage:
    return LibraryPage(parent, principal=principal, state=state if state is not None else {},
                       open_pupil=open_pupil)


def _hold_notice(owner, hold: LB.Hold | None) -> None:
    if hold:
        messagebox.showinfo("Reserved", f"Keep this copy ({hold.barcode}) for "
                            f"{hold.pupil_name} - they reserved '{hold.book_title}'. Collect by "
                            f"{hold.expires_on}.", parent=owner)


# ── Copies window ────────────────────────────────────────────────────

class CopiesWindow:
    def __init__(self, owner, principal: Principal, book: LB.Book, *,
                 on_close: Callable[[], None]) -> None:
        self.principal, self.book, self.on_close = principal, book, on_close
        self.win = win = make_toplevel(owner.winfo_toplevel())
        win.title(f"Copies - {book.title}")
        win.geometry("720x440")
        win.protocol("WM_DELETE_WINDOW", self.close)
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        for text, cmd in (("Add copies…", self.add), ("Withdraw", self.withdraw),
                          ("Put back on shelf", self.restore), ("Refresh", self.refresh)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.tree = _tree(frm, (("barcode", "Barcode", 90), ("status", "Status", 80),
                                ("pupil", "Borrowed by", 180), ("due", "Due", 85),
                                ("acq", "Acquired", 85), ("notes", "Notes", 160)), height=14)
        self.refresh()

    def close(self) -> None:
        self.win.destroy()
        self.on_close()

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for c in LB.list_copies(self.book.book_id):
            self.tree.insert("", "end", iid=str(c.copy_id), tags=(c.status,), values=(
                c.barcode, c.status, c.holder or "", c.due_date or "", c.acquired_on or "",
                c.notes or ""))

    def add(self) -> None:
        raw = simpledialog.askstring("Add copies", "How many copies? Or type their barcodes "
                                     "separated by commas:", parent=self.win)
        if not raw:
            return
        try:
            if raw.strip().isdigit():
                LB.add_copies(self.book.book_id, int(raw), actor=self.principal)
            else:
                LB.add_copies(self.book.book_id, 0, actor=self.principal,
                              barcodes=raw.split(","))
        except _ERRORS as e:
            messagebox.showerror("Add copies", _problems(e), parent=self.win)
        self.refresh()

    def _set(self, status: str) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Copies", "Select a copy first.", parent=self.win)
            return
        note = simpledialog.askstring("Copies", "Note (e.g. damaged):", parent=self.win) \
            if status == "Withdrawn" else None
        try:
            LB.set_copy_status(int(sel[0]), status, actor=self.principal, note=note)
        except _ERRORS as e:
            messagebox.showerror("Copies", _problems(e), parent=self.win)
        self.refresh()

    def withdraw(self) -> None:
        self._set("Withdrawn")

    def restore(self) -> None:
        self._set("Available")


# ── Dialogs ──────────────────────────────────────────────────────────

def book_dialog(owner, principal: Principal, book: LB.Book | None,
                after: Callable[[], None]) -> None:
    """The old Add / Edit book: title, author, ISBN, category, year, total
    copies, shelf, active and notes; plus publisher, subject and reading level."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title("Edit book" if book else "Add book")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    subjects = {f"{s.code} - {s.name}": s.subject_id for s in S.list_subjects()}
    g = (lambda k: getattr(book, k)) if book else (lambda _k: None)
    v = {k: tk.StringVar(value="" if g(k) is None else str(g(k)))
         for k in ("title", "author", "isbn", "year_published", "location", "publisher",
                   "reading_level")}
    cat = tk.StringVar(value=book.category if book else "Fiction")
    copies = tk.StringVar(value=str(book.copies_total if book else 1))
    active = tk.BooleanVar(value=book.is_active if book else True)
    subj = tk.StringVar(value=next((k for k, sid in subjects.items()
                                    if book and sid == book.subject_id), ""))
    notes = tk.Text(frm, width=44, height=3, wrap="word")
    notes.insert("1.0", (book.notes or "") if book else "")
    rows = [("Title:", ttk.Entry(frm, textvariable=v["title"], width=44)),
            ("Author:", ttk.Entry(frm, textvariable=v["author"], width=30)),
            ("ISBN:", ttk.Entry(frm, textvariable=v["isbn"], width=20)),
            ("Category:", ttk.Combobox(frm, textvariable=cat, values=LB.CATEGORIES,
                                       state="readonly", width=14)),
            ("Year published:", ttk.Entry(frm, textvariable=v["year_published"], width=8)),
            ("Total copies:", ttk.Spinbox(frm, from_=0, to=500, textvariable=copies,
                                          width=8)),
            ("Shelf / location:", ttk.Entry(frm, textvariable=v["location"], width=18)),
            ("Active:", ttk.Checkbutton(frm, variable=active)),
            ("Publisher:", ttk.Entry(frm, textvariable=v["publisher"], width=30)),
            ("Subject:", ttk.Combobox(frm, textvariable=subj, values=["", *subjects],
                                      state="readonly", width=28)),
            ("Reading level:", ttk.Entry(frm, textvariable=v["reading_level"], width=14)),
            ("Notes:", notes)]
    _grid_rows(frm, rows)

    def save() -> None:
        data = {k: var.get() for k, var in v.items()}
        data.update(category=cat.get(), copies_total=copies.get(),
                    subject_id=subjects.get(subj.get(), ""), notes=notes.get("1.0", "end"))
        try:
            if book:
                b, msgs = LB.update_book(book.book_id, data, actor=principal)
            else:
                b, msgs = LB.create_book(data, actor=principal), []
            if b.is_active != active.get():
                LB.toggle_active(b.book_id, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Book", _problems(e), parent=win)
            return
        win.destroy()
        after()
        if msgs:
            messagebox.showinfo("Book", "Saved. " + "; ".join(msgs) + ".", parent=owner)
    _buttons(frm, len(rows), win, save)


def lend_dialog(owner, principal: Principal, book: LB.Book,
                after: Callable[[], None]) -> None:
    """The old Lend dialog: pupil, loan date, due date, notes. Added: which copy,
    and (for the librarian) going over the loan limits."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(f"Lend - {book.title}")
    win.resizable(False, False)
    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)
    rules = LB.settings()
    pupil = tk.StringVar()
    ldate, ddate, note, code = (tk.StringVar() for _ in range(4))
    override = tk.BooleanVar(value=False)
    rows = [("Pupil (admission no / UPN):", ttk.Entry(frm, textvariable=pupil, width=14)),
            ("Loan date (blank = today):", ttk.Entry(frm, textvariable=ldate, width=14)),
            (f"Due date (blank = +{rules['loan_days']}d):", ttk.Entry(frm, textvariable=ddate,
                                                                      width=14)),
            ("Notes:", ttk.Entry(frm, textvariable=note, width=24)),
            ("Copy barcode (blank = any):", ttk.Entry(frm, textvariable=code, width=14))]
    if LB.is_editor(principal):
        rows.append(("", ttk.Checkbutton(frm, text="Allow over the loan limits",
                                         variable=override)))
    _grid_rows(frm, rows)

    def save() -> None:
        p = _pupil_from(win, pupil.get())
        if p is None:
            return
        try:
            rec = LB.lend(p.pupil_id, actor=principal,
                          barcode=code.get().strip() or None,
                          book_id=None if code.get().strip() else book.book_id,
                          loan_date=ldate.get().strip() or None,
                          due_date=ddate.get().strip() or None,
                          notes=note.get().strip() or None, override=override.get())
        except _ERRORS as e:
            messagebox.showerror("Library", _problems(e), parent=win)
            return
        messagebox.showinfo("Library", f"Lent {rec.barcode} to {p.display_name} (due "
                            f"{rec.due_date})", parent=win)
        win.destroy()
        after()
    _buttons(frm, len(rows), win, save, label="Lend")
