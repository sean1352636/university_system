"""Tkinter views for Sixth Form Library."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
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

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_library_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Library — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    BooksTab(nb)
    LoansTab(nb)
    SummaryTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


# ══ Books tab ═════════════════════════════════════════════════════

class BooksTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Books")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.f_search = ttk.Entry(bar, width=20)
        self.f_search.pack(side="left", padx=(2, 8))
        self.f_search.bind("<Return>", lambda _e: self.refresh())

        ttk.Label(bar, text="Subject:").pack(side="left")
        self.f_subject = ttk.Entry(bar, width=14)
        self.f_subject.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, values=("",) + ITEM_TYPES,
                                     state="readonly", width=14)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + BOOK_STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        self.available_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Available only",
                          variable=self.available_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "title", "author", "isbn", "type",
                "subject", "location", "avail", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "title": 240, "author": 160,
                  "isbn": 120, "type": 110, "subject": 130,
                  "location": 100, "avail": 80, "status": 90}
        headings = {"id": "ID", "title": "Title", "author": "Author",
                    "isbn": "ISBN", "type": "Type",
                    "subject": "Subject", "location": "Location",
                    "avail": "Avail", "status": "Status"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "avail" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Available", background="#d8f4d8")
        self.tree.tag_configure("Reserved",  background="#fff7d0")
        self.tree.tag_configure("Restricted", background="#eef7ff")
        self.tree.tag_configure("Withdrawn", background="#eeeeee")
        self.tree.tag_configure("Lost",      background="#ffd0d0")
        self.tree.tag_configure("NoneAvail", background="#fff7d0")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Issue…",
                    command=self._issue_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_search.delete(0, "end")
        self.f_subject.delete(0, "end")
        self.f_type.current(0)
        self.f_status.current(0)
        self.available_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_books(
                search=self.f_search.get().strip() or None,
                subject_area=self.f_subject.get().strip() or None,
                item_type=self.f_type.get() or None,
                status=self.f_status.get() or None,
                available_only=self.available_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for b in rows:
            avail = f"{b.copies_available}/{b.copies_total}"
            tags = []
            if b.status in BOOK_STATUSES:
                tags.append(b.status)
            if b.copies_available == 0 and b.status == "Available":
                tags.append("NoneAvail")
            self.tree.insert("", "end", iid=str(b.book_id), values=(
                b.book_id, b.title, b.author or "—",
                b.isbn or "—", b.item_type,
                b.subject_area or "—", b.location or "—",
                avail, b.status,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} book(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected(self) -> Book | None:
        bid = self._selected_id()
        if bid is None:
            return None
        return data.get_book(bid)

    def _view_selected(self) -> None:
        b = self._selected()
        if b is None:
            messagebox.showinfo("View", "Select a book first.")
            return
        loans = data.list_loans(book_id=b.book_id, active_only=True)
        lines = [
            f"#{b.book_id}  {b.title}",
            f"Author       : {b.author or '—'}",
            f"ISBN         : {b.isbn or '—'}",
            f"Publisher    : {b.publisher or '—'}"
            + (f"  ({b.publication_year})"
               if b.publication_year else ""),
            f"Edition      : {b.edition or '—'}",
            f"Type         : {b.item_type}",
            f"Subject area : {b.subject_area or '—'}",
            f"Keywords     : {b.keywords or '—'}",
            f"Location     : {b.location or '—'}",
            f"Copies       : {b.copies_available}/{b.copies_total}",
            f"Status       : {b.status}",
        ]
        if b.description:
            lines += ["", "Description:", b.description]
        if loans:
            lines += ["",
                       f"Currently on loan ({len(loans)}):"]
            names = {s.student_id: s.full_name
                      for s in student_data.list_students()}
            for l in loans:
                flag = " (OVERDUE)" if l.is_overdue else ""
                lines.append(
                    f"  #{l.loan_id}  {l.student_id}  "
                    f"{names.get(l.student_id, '?')[:20]}  "
                    f"due {l.due_on}{flag}")
        messagebox.showinfo(f"Book #{b.book_id}", "\n".join(lines))

    def _new(self) -> None:
        BookDialog(self.frame.winfo_toplevel(),
                     existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        b = self._selected()
        if b is None:
            messagebox.showinfo("Edit", "Select a book first.")
            return
        BookDialog(self.frame.winfo_toplevel(),
                     existing=b, on_save=self.refresh)

    def _issue_selected(self) -> None:
        b = self._selected()
        if b is None:
            messagebox.showinfo("Issue", "Select a book first.")
            return
        if not b.is_borrowable:
            messagebox.showerror(
                "Issue",
                f"Book is not borrowable "
                f"(status={b.status}, "
                f"available={b.copies_available})")
            return
        IssueDialog(self.frame.winfo_toplevel(), book=b,
                      on_save=self.refresh)

    def _status_selected(self) -> None:
        b = self._selected()
        if b is None:
            messagebox.showinfo("Status", "Select a book first.")
            return
        BookStatusDialog(self.frame.winfo_toplevel(),
                            b, on_save=self.refresh)

    def _delete_selected(self) -> None:
        b = self._selected()
        if b is None:
            messagebox.showinfo("Delete",
                                  "Select a book first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete book #{b.book_id} ({b.title})? "
                "Cascade-deletes loans."):
            return
        try:
            data.delete_book(b.book_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Loans tab ═════════════════════════════════════════════════════

class LoansTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Loans")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + LOAN_STATUSES,
                                       state="readonly", width=12)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))

        self.active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Active only",
                          variable=self.active_var,
                          command=self.refresh).pack(side="left", padx=4)
        self.overdue_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Overdue only",
                          variable=self.overdue_var,
                          command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "book", "title", "student", "name",
                "loaned", "due", "renewals", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "book": 60, "title": 240,
                  "student": 80, "name": 180,
                  "loaned": 100, "due": 100,
                  "renewals": 80, "status": 90}
        headings = {"id": "ID", "book": "Book",
                    "title": "Title", "student": "Student",
                    "name": "Name", "loaned": "Loaned",
                    "due": "Due", "renewals": "Renewals",
                    "status": "Status"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "renewals" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Active",   background="#d8f4d8")
        self.tree.tag_configure("Returned", background="#eeeeee")
        self.tree.tag_configure("Lost",     background="#ffd0d0")
        self.tree.tag_configure("Cancelled", background="#eeeeee")
        self.tree.tag_configure("Overdue",  background="#ffd0d0")
        self.tree.bind("<Double-1>",
                        lambda _e: self._return_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="Return",
                    command=self._return_selected).pack(side="left")
        ttk.Button(actions, text="Renew",
                    command=self._renew_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Mark lost",
                    command=self._mark_lost_selected).pack(side="left",
                                                             padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_status.current(0)
        self.active_var.set(False)
        self.overdue_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_loans_with_detail(
                student_id=self.f_student.get().strip() or None,
                status=self.f_status.get() or None,
                active_only=self.active_var.get(),
                overdue_only=self.overdue_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for r in rows:
            l = r.loan
            tags = []
            if l.status in LOAN_STATUSES:
                tags.append(l.status)
            if l.is_overdue:
                tags.append("Overdue")
            self.tree.insert("", "end", iid=str(l.loan_id), values=(
                l.loan_id, l.book_id, r.book_title,
                l.student_id, r.student_name,
                l.loaned_on, l.due_on, l.renewals_count,
                l.status,
            ), tags=tuple(tags))
        self.count_var.set(f"{len(rows)} loan(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _return_selected(self) -> None:
        lid = self._selected_id()
        if lid is None:
            messagebox.showinfo("Return", "Select a loan first.")
            return
        loan = data.get_loan(lid)
        if loan is None or not loan.is_active:
            messagebox.showinfo("Return",
                                  "Loan is not Active.")
            return
        try:
            data.return_loan(lid)
        except ValidationError as e:
            messagebox.showerror("Return", str(e))
            return
        self.refresh()

    def _renew_selected(self) -> None:
        lid = self._selected_id()
        if lid is None:
            messagebox.showinfo("Renew", "Select a loan first.")
            return
        try:
            new = data.renew(lid)
        except ValidationError as e:
            messagebox.showerror("Renew", str(e))
            return
        messagebox.showinfo(
            "Renew",
            f"New due {new.due_on}  "
            f"({new.renewals_count}/{MAX_RENEWALS} renewals)")
        self.refresh()

    def _mark_lost_selected(self) -> None:
        lid = self._selected_id()
        if lid is None:
            messagebox.showinfo("Lost", "Select a loan first.")
            return
        if not messagebox.askyesno(
                "Mark lost",
                f"Mark loan #{lid} as Lost?\n"
                "This drops the book's total copies."):
            return
        try:
            data.mark_lost(lid)
        except ValidationError as e:
            messagebox.showerror("Lost", str(e))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        lid = self._selected_id()
        if lid is None:
            messagebox.showinfo("Delete", "Select a loan first.")
            return
        if not messagebox.askyesno("Delete", f"Delete loan #{lid}?"):
            return
        try:
            data.delete_loan(lid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        ttk.Button(self.frame, text="Refresh",
                    command=self.refresh).pack(side="top", anchor="w",
                                                 padx=8, pady=(8, 4))
        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        summ = data.summary()
        lines = [
            f"Total books        : {summ.total_books}",
            f"Total copies       : {summ.total_copies}",
            f"Copies on loan     : {summ.copies_on_loan}",
            f"Active loans       : {summ.active_loans}",
            f"Overdue loans      : {summ.overdue_loans}",
            f"Returned loans     : {summ.returned_loans}",
            f"Distinct borrowers : {summ.distinct_borrowers}",
            "",
            "Books by status:",
        ]
        for s in BOOK_STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("Books by type:")
        for t in ITEM_TYPES:
            n = summ.by_item_type.get(t, 0)
            if n:
                lines.append(f"  {t:<22} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class BookStatusDialog:
    def __init__(self, parent: tk.Misc, existing: Book,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — book #{existing.book_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=BOOK_STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_book_status(
                self.existing.book_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class IssueDialog:
    def __init__(self, parent: tk.Misc, *, book: Book,
                 on_save: Callable[[], None]) -> None:
        self.book = book
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Issue — book #{book.book_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"{self.book.title}  "
                         f"({self.book.copies_available} "
                         f"of {self.book.copies_total} available)",
                   font=("", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        opts = _student_options()
        self._ids = [s for s, _ in opts]
        ttk.Label(form, text="Student:").grid(row=1, column=0,
                                                 sticky="e", pady=4)
        self.student_cb = ttk.Combobox(
            form, values=[l for _, l in opts],
            state="readonly", width=44)
        if opts:
            self.student_cb.current(0)
        self.student_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Loaned on:").grid(row=2, column=0,
                                                   sticky="e", pady=4)
        self.loaned_e = ttk.Entry(form, width=14)
        self.loaned_e.insert(0, _today())
        self.loaned_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Due on:").grid(row=3, column=0,
                                                sticky="e", pady=4)
        self.due_e = ttk.Entry(form, width=14)
        default_due = (
            _dt.date.today()
            + _dt.timedelta(days=DEFAULT_LOAN_DAYS)).isoformat()
        self.due_e.insert(0, default_due)
        self.due_e.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Issued by:").grid(row=4, column=0,
                                                   sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=24)
        self.by_e.grid(row=4, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Issue",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.student_cb.current()
        if idx < 0:
            messagebox.showerror("Issue", "Pick a student.")
            return
        try:
            data.issue(
                self.book.book_id,
                self._ids[idx],
                loaned_on=self.loaned_e.get().strip() or None,
                due_on=self.due_e.get().strip() or None,
                issued_by=self.by_e.get().strip() or None,
            )
        except (ValidationError, Exception) as e:
            messagebox.showerror("Issue failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class BookDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Book | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Book" if existing else "New Book")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="Title:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.title_e = ttk.Entry(form, width=44)
        if self.existing:
            self.title_e.insert(0, self.existing.title)
        self.title_e.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Author:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.author_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.author:
            self.author_e.insert(0, self.existing.author)
        self.author_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="ISBN:").grid(row=r, column=2,
                                              sticky="e", pady=3)
        self.isbn_e = ttk.Entry(form, width=20)
        if self.existing and self.existing.isbn:
            self.isbn_e.insert(0, self.existing.isbn)
        self.isbn_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Publisher:").grid(row=r, column=0,
                                                   sticky="e", pady=3)
        self.publisher_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.publisher:
            self.publisher_e.insert(0, self.existing.publisher)
        self.publisher_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Year:").grid(row=r, column=2,
                                              sticky="e", pady=3)
        self.year_e = ttk.Entry(form, width=8)
        if (self.existing
                and self.existing.publication_year is not None):
            self.year_e.insert(0, str(self.existing.publication_year))
        self.year_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Edition:").grid(row=r, column=0,
                                                 sticky="e", pady=3)
        self.edition_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.edition:
            self.edition_e.insert(0, self.existing.edition)
        self.edition_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Type:").grid(row=r, column=2,
                                              sticky="e", pady=3)
        self.type_cb = ttk.Combobox(form, values=ITEM_TYPES,
                                       state="readonly", width=14)
        self.type_cb.set(self.existing.item_type
                            if self.existing else DEFAULT_ITEM_TYPE)
        self.type_cb.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Subject area:").grid(row=r, column=0,
                                                      sticky="e", pady=3)
        self.subject_e = ttk.Entry(form, width=22)
        if self.existing and self.existing.subject_area:
            self.subject_e.insert(0, self.existing.subject_area)
        self.subject_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Location:").grid(row=r, column=2,
                                                  sticky="e", pady=3)
        self.location_e = ttk.Entry(form, width=18)
        if self.existing and self.existing.location:
            self.location_e.insert(0, self.existing.location)
        self.location_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Keywords:").grid(row=r, column=0,
                                                  sticky="e", pady=3)
        self.keywords_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.keywords:
            self.keywords_e.insert(0, self.existing.keywords)
        self.keywords_e.grid(row=r, column=1, columnspan=3,
                                sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Copies total:").grid(row=r, column=0,
                                                      sticky="e", pady=3)
        self.total_e = ttk.Entry(form, width=8)
        self.total_e.insert(0,
            str(self.existing.copies_total)
            if self.existing else "1")
        self.total_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Available:").grid(row=r, column=2,
                                                   sticky="e", pady=3)
        self.avail_e = ttk.Entry(form, width=8)
        if self.existing:
            self.avail_e.insert(0,
                                  str(self.existing.copies_available))
        self.avail_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=BOOK_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_BOOK_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                     sticky="ne", pady=3)
        self.desc_t = tk.Text(form, width=60, height=3)
        if self.existing and self.existing.description:
            self.desc_t.insert("1.0", self.existing.description)
        self.desc_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=60, height=2)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        return {
            "title":             self.title_e.get().strip(),
            "author":            self.author_e.get().strip(),
            "isbn":              self.isbn_e.get().strip() or None,
            "publisher":         self.publisher_e.get().strip(),
            "publication_year":  self.year_e.get().strip() or None,
            "edition":           self.edition_e.get().strip(),
            "item_type":         self.type_cb.get().strip(),
            "subject_area":      self.subject_e.get().strip(),
            "location":          self.location_e.get().strip(),
            "keywords":          self.keywords_e.get().strip(),
            "copies_total":      self.total_e.get().strip() or None,
            "copies_available":  self.avail_e.get().strip() or None,
            "status":            self.status_cb.get().strip(),
            "description":       self.desc_t.get("1.0", "end").strip(),
            "notes":             self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_book(self.existing.book_id, payload)
            else:
                data.create_book(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
