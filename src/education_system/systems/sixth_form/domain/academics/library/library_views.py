"""Tkinter views for Sixth Form Library."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable
from education_system.platform import branding
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

    DashboardTab(nb)
    BooksTab(nb)
    LoansTab(nb)
    ReservationsTab(nb)
    FinesTab(nb)
    CopiesTab(nb)
    ReadingListsTab(nb)
    AcquisitionsTab(nb)
    EResourcesTab(nb)
    StudyTab(nb)
    ReportsTab(nb)
    AdminTab(nb)
    KioskTab(nb)
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
        ttk.Button(actions, text="Return…",
                    command=self._return_selected).pack(side="left")
        ttk.Button(actions, text="Renew",
                    command=self._renew_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Recall",
                    command=self._recall_selected).pack(side="left", padx=4)
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
        ReturnDialog(self.frame.winfo_toplevel(), loan=loan,
                     on_save=self.refresh)

    def _recall_selected(self) -> None:
        lid = self._selected_id()
        if lid is None:
            messagebox.showinfo("Recall", "Select a loan first.")
            return
        try:
            out = holds.recall(lid)
        except ValidationError as e:
            messagebox.showerror("Recall", str(e))
            return
        messagebox.showinfo("Recall",
                            f"Loan #{out.loan_id} recalled — "
                            f"due now {out.due_on}.")
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
        ttk.Label(form, text="Classification:").grid(row=r, column=0,
                                                      sticky="e", pady=3)
        self.classification_e = ttk.Entry(form, width=22)
        if self.existing and self.existing.classification:
            self.classification_e.insert(0, self.existing.classification)
        self.classification_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Cover URL:").grid(row=r, column=2,
                                                  sticky="e", pady=3)
        self.cover_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.cover_image_url:
            self.cover_e.insert(0, self.existing.cover_image_url)
        self.cover_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Series:").grid(row=r, column=0,
                                                sticky="e", pady=3)
        self.series_e = ttk.Entry(form, width=22)
        if self.existing and self.existing.series:
            self.series_e.insert(0, self.existing.series)
        self.series_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Volume:").grid(row=r, column=2,
                                                sticky="e", pady=3)
        self.volume_e = ttk.Entry(form, width=10)
        if self.existing and self.existing.volume:
            self.volume_e.insert(0, self.existing.volume)
        self.volume_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Tags:").grid(row=r, column=0,
                                              sticky="e", pady=3)
        self.tags_e = ttk.Entry(form, width=44)
        if self.existing:
            self.tags_e.insert(
                0, ", ".join(catalog.tags_for_book(
                    self.existing.book_id)))
        self.tags_e.grid(row=r, column=1, columnspan=3,
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
            "classification":    self.classification_e.get().strip(),
            "series":            self.series_e.get().strip(),
            "volume":            self.volume_e.get().strip(),
            "cover_image_url":   self.cover_e.get().strip() or None,
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
                book = data.update_book(self.existing.book_id, payload)
            else:
                book = data.create_book(payload)
            tags = [t for t in self.tags_e.get().split(",") if t.strip()]
            catalog.set_tags(book.book_id, tags)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ReturnDialog:
    """Return a loan with an optional date and a damaged flag."""

    def __init__(self, parent: tk.Misc, *, loan: Loan,
                 on_save: Callable[[], None]) -> None:
        self.loan = loan
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Return — loan #{loan.loan_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Returned on:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Returned by:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=24)
        self.by_e.grid(row=1, column=1, sticky="w", padx=6)

        self.damaged_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Item returned damaged (raises a fee)",
                        variable=self.damaged_var).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Return",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        date = self.date_e.get().strip() or None
        by = self.by_e.get().strip() or None
        try:
            if self.damaged_var.get():
                data.return_damaged(self.loan.loan_id,
                                    returned_on=date, returned_by=by)
            else:
                data.return_loan(self.loan.loan_id,
                                 returned_on=date, returned_by=by)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Return failed", str(e))
            return
        bal = fines.student_balance(self.loan.student_id)
        self.win.destroy()
        self.on_save()
        if bal > 0:
            messagebox.showinfo(
                "Returned",
                f"Student {self.loan.student_id} now owes "
                f"{bal:.2f} in fines.")


# ══ Reservations tab ═══════════════════════════════════════════════

class ReservationsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Reservations")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Place reservation",
                    command=self._place).pack(side="left")
        ttk.Button(bar, text="Collect hold",
                    command=self._collect).pack(side="left", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self._cancel).pack(side="left", padx=4)
        ttk.Button(bar, text="Expire stale holds",
                    command=self._expire).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "book", "title", "student", "status",
                "queue", "expires")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "book": 60, "title": 260, "student": 90,
                  "status": 90, "queue": 60, "expires": 100}
        headings = {"id": "ID", "book": "Book", "title": "Title",
                    "student": "Student", "status": "Status",
                    "queue": "Queue", "expires": "Collect by"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c],
                             anchor="center" if c == "queue" else "w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Ready", background="#d8f4d8")

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        titles = {b.book_id: b.title for b in data.list_books()}
        for r in holds.list_reservations(open_only=True):
            pos = holds.waitlist_position(r.reservation_id)
            self.tree.insert("", "end", iid=str(r.reservation_id),
                             values=(r.reservation_id, r.book_id,
                                     titles.get(r.book_id, f"#{r.book_id}"),
                                     r.student_id, r.status,
                                     pos or "", r.expires_on or "—"),
                             tags=(r.status,))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _place(self) -> None:
        ReserveDialog(self.frame.winfo_toplevel(), on_save=self.refresh)

    def _collect(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Collect", "Select a reservation.")
            return
        try:
            _res, loan = holds.collect_reservation(rid)
        except ValidationError as e:
            messagebox.showerror("Collect", str(e))
            return
        messagebox.showinfo("Collect",
                            f"Collected as loan #{loan.loan_id} "
                            f"(due {loan.due_on}).")
        self.refresh()

    def _cancel(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Cancel", "Select a reservation.")
            return
        try:
            holds.cancel_reservation(rid)
        except ValidationError as e:
            messagebox.showerror("Cancel", str(e))
            return
        self.refresh()

    def _expire(self) -> None:
        n = holds.expire_holds()
        messagebox.showinfo("Expire",
                            f"Expired {n} hold(s) past collect-by date.")
        self.refresh()


class ReserveDialog:
    def __init__(self, parent: tk.Misc, *,
                 on_save: Callable[[], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Place reservation")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        books = data.list_books()
        self._book_ids = [b.book_id for b in books]
        ttk.Label(form, text="Book:").grid(row=0, column=0,
                                             sticky="e", pady=4)
        self.book_cb = ttk.Combobox(
            form, state="readonly", width=44,
            values=[f"#{b.book_id} — {b.title}" for b in books])
        if books:
            self.book_cb.current(0)
        self.book_cb.grid(row=0, column=1, sticky="w", padx=6)

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

        bar = ttk.Frame(form)
        bar.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Reserve",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        bi, si = self.book_cb.current(), self.student_cb.current()
        if bi < 0 or si < 0:
            messagebox.showerror("Reserve", "Pick a book and student.")
            return
        try:
            r = holds.reserve(self._book_ids[bi], self._ids[si])
        except ValidationError as e:
            messagebox.showerror("Reserve failed", str(e))
            return
        self.win.destroy()
        self.on_save()
        if r.status == "Ready":
            messagebox.showinfo("Reserved",
                                f"Ready to collect by {r.expires_on}.")
        else:
            pos = holds.waitlist_position(r.reservation_id)
            messagebox.showinfo("Reserved",
                                f"Placed — position {pos} in the queue.")


# ══ Fines tab ══════════════════════════════════════════════════════

class FinesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Fines")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        self.open_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only", variable=self.open_var,
                        command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Raise fine",
                    command=self._raise).pack(side="left", padx=(12, 4))
        ttk.Button(bar, text="Pay",
                    command=self._pay).pack(side="left", padx=4)
        ttk.Button(bar, text="Waive",
                    command=self._waive).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "reason", "amount", "owed", "status",
                "note")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "student": 90, "reason": 90, "amount": 80,
                  "owed": 80, "status": 100, "note": 280}
        headings = {"id": "ID", "student": "Student", "reason": "Reason",
                    "amount": "Amount", "owed": "Owed",
                    "status": "Status", "note": "Note"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "e" if c in ("amount", "owed") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Outstanding", background="#ffe8cc")
        self.tree.tag_configure("Paid", background="#eeeeee")
        self.tree.tag_configure("Waived", background="#eeeeee")

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for f in fines.list_fines(open_only=self.open_var.get()):
            self.tree.insert("", "end", iid=str(f.fine_id), values=(
                f.fine_id, f.student_id, f.reason,
                f"{f.amount:.2f}", f"{f.outstanding:.2f}",
                f.status, f.note or ""), tags=(f.status,))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _raise(self) -> None:
        RaiseFineDialog(self.frame.winfo_toplevel(),
                        on_save=self.refresh)

    def _pay(self) -> None:
        fid = self._selected_id()
        if fid is None:
            messagebox.showinfo("Pay", "Select a fine.")
            return
        fine = fines.get_fine(fid)
        amt = simpledialog.askfloat(
            "Pay fine", f"Amount to pay (owed {fine.outstanding:.2f}):",
            parent=self.frame.winfo_toplevel(),
            initialvalue=fine.outstanding, minvalue=0.01)
        if amt is None:
            return
        try:
            fines.pay_fine(fid, amt)
        except ValidationError as e:
            messagebox.showerror("Pay", str(e))
            return
        self.refresh()

    def _waive(self) -> None:
        fid = self._selected_id()
        if fid is None:
            messagebox.showinfo("Waive", "Select a fine.")
            return
        reason = simpledialog.askstring(
            "Waive fine", "Reason for waiver:",
            parent=self.frame.winfo_toplevel())
        if not reason:
            return
        try:
            fines.waive_fine(fid, reason=reason)
        except ValidationError as e:
            messagebox.showerror("Waive", str(e))
            return
        self.refresh()


class RaiseFineDialog:
    def __init__(self, parent: tk.Misc, *,
                 on_save: Callable[[], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Raise fine")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        opts = _student_options()
        self._ids = [s for s, _ in opts]
        ttk.Label(form, text="Student:").grid(row=0, column=0,
                                                sticky="e", pady=4)
        self.student_cb = ttk.Combobox(
            form, values=[l for _, l in opts],
            state="readonly", width=40)
        if opts:
            self.student_cb.current(0)
        self.student_cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Reason:").grid(row=1, column=0,
                                               sticky="e", pady=4)
        self.reason_cb = ttk.Combobox(form, values=fines.FINE_REASONS,
                                        state="readonly", width=14)
        self.reason_cb.set("Manual")
        self.reason_cb.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Amount:").grid(row=2, column=0,
                                               sticky="e", pady=4)
        self.amount_e = ttk.Entry(form, width=12)
        self.amount_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Note:").grid(row=3, column=0,
                                             sticky="e", pady=4)
        self.note_e = ttk.Entry(form, width=40)
        self.note_e.grid(row=3, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Raise",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        si = self.student_cb.current()
        if si < 0:
            messagebox.showerror("Raise fine", "Pick a student.")
            return
        try:
            amount = float(self.amount_e.get().strip())
            fines.create_fine(self._ids[si], self.reason_cb.get(),
                              amount,
                              note=self.note_e.get().strip() or None)
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Raise fine failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Admin tab (settings, policies, notifications) ══════════════════

class AdminTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Admin")
        self._build()
        self.refresh()

    def _build(self) -> None:
        left = ttk.LabelFrame(self.frame, text="Settings", padding=8)
        left.pack(side="left", fill="both", expand=True,
                  padx=(8, 4), pady=8)
        self.settings_tree = ttk.Treeview(
            left, columns=("key", "value"), show="headings", height=12)
        self.settings_tree.heading("key", text="Setting")
        self.settings_tree.heading("value", text="Value")
        self.settings_tree.column("key", width=220, anchor="w")
        self.settings_tree.column("value", width=120, anchor="w")
        self.settings_tree.pack(fill="both", expand=True)
        self.settings_tree.bind("<Double-1>",
                                lambda _e: self._edit_setting())
        ttk.Button(left, text="Edit selected",
                    command=self._edit_setting).pack(pady=(6, 0))

        mid = ttk.LabelFrame(self.frame, text="Loan policies",
                             padding=8)
        mid.pack(side="left", fill="both", expand=True, padx=4, pady=8)
        self.policy_tree = ttk.Treeview(
            mid, columns=("type", "days", "renewals", "borrow"),
            show="headings", height=12)
        for c, t, w in (("type", "Item type", 120), ("days", "Days", 50),
                        ("renewals", "Renew", 60),
                        ("borrow", "Borrow", 60)):
            self.policy_tree.heading(c, text=t)
            self.policy_tree.column(c, width=w, anchor="w")
        self.policy_tree.pack(fill="both", expand=True)
        self.policy_tree.bind("<Double-1>",
                              lambda _e: self._edit_policy())
        ttk.Button(mid, text="Edit selected",
                    command=self._edit_policy).pack(pady=(6, 0))

        right = ttk.LabelFrame(self.frame, text="Notifications",
                               padding=8)
        right.pack(side="left", fill="y", padx=(4, 8), pady=8)
        ttk.Button(right, text="Send due-soon reminders",
                    command=self._due_soon).pack(fill="x", pady=3)
        ttk.Button(right, text="Send overdue notices",
                    command=self._overdue).pack(fill="x", pady=3)
        ttk.Button(right, text="Send daily digest",
                    command=self._digest).pack(fill="x", pady=3)
        ttk.Button(right, text="Expire stale holds",
                    command=self._expire).pack(fill="x", pady=3)

    def refresh(self) -> None:
        for i in self.settings_tree.get_children():
            self.settings_tree.delete(i)
        for k, v in settings.all_settings().items():
            self.settings_tree.insert("", "end", iid=k,
                                      values=(k, v))
        for i in self.policy_tree.get_children():
            self.policy_tree.delete(i)
        for p in settings.list_policies():
            self.policy_tree.insert("", "end", iid=p.item_type, values=(
                p.item_type, p.loan_days, p.max_renewals,
                "yes" if p.borrowable else "no"))

    def _edit_setting(self) -> None:
        sel = self.settings_tree.selection()
        if not sel:
            messagebox.showinfo("Settings", "Select a setting.")
            return
        key = sel[0]
        val = simpledialog.askstring(
            "Edit setting", f"New value for {key}:",
            parent=self.frame.winfo_toplevel(),
            initialvalue=str(settings.get_setting(key)))
        if val is None:
            return
        try:
            settings.set_setting(key, val)
        except ValidationError as e:
            messagebox.showerror("Settings", str(e))
            return
        self.refresh()

    def _edit_policy(self) -> None:
        sel = self.policy_tree.selection()
        if not sel:
            messagebox.showinfo("Policies", "Select an item type.")
            return
        PolicyDialog(self.frame.winfo_toplevel(), item_type=sel[0],
                     on_save=self.refresh)

    def _due_soon(self) -> None:
        n = notifs.run_due_soon_sweep()
        messagebox.showinfo("Notifications",
                            f"Sent {n} due-soon reminder(s).")

    def _overdue(self) -> None:
        n = notifs.run_overdue_sweep()
        messagebox.showinfo("Notifications",
                            f"Sent {n} overdue notice(s).")

    def _digest(self) -> None:
        notifs.daily_digest()
        messagebox.showinfo("Notifications",
                            f"Digest sent to {notifs.DIGEST_INBOX}.")

    def _expire(self) -> None:
        n = holds.expire_holds()
        messagebox.showinfo("Holds",
                            f"Expired {n} stale hold(s).")
        self.refresh()


class PolicyDialog:
    def __init__(self, parent: tk.Misc, *, item_type: str,
                 on_save: Callable[[], None]) -> None:
        self.item_type = item_type
        self.on_save = on_save
        pol = settings.get_policy(item_type)
        self.win = tk.Toplevel(parent)
        self.win.title(f"Policy — {item_type}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Loan days:").grid(row=0, column=0,
                                                  sticky="e", pady=4)
        self.days_e = ttk.Entry(form, width=8)
        self.days_e.insert(0, str(pol.loan_days))
        self.days_e.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Max renewals:").grid(row=1, column=0,
                                                     sticky="e", pady=4)
        self.rens_e = ttk.Entry(form, width=8)
        self.rens_e.insert(0, str(pol.max_renewals))
        self.rens_e.grid(row=1, column=1, sticky="w", padx=6)

        self.borrow_var = tk.BooleanVar(value=pol.borrowable)
        ttk.Checkbutton(form, text="Borrowable",
                        variable=self.borrow_var).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            settings.set_policy(
                self.item_type,
                loan_days=int(self.days_e.get().strip()),
                max_renewals=int(self.rens_e.get().strip()),
                borrowable=self.borrow_var.get())
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Policy failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Helpers for the 26-50 tabs ═════════════════════════════════════

def _make_tree(parent, columns: list[tuple[str, str, int]]):
    """Build a headings-only Treeview. columns = [(key, heading, width)]."""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns],
                        show="headings")
    for key, heading, width in columns:
        tree.heading(key, text=heading)
        tree.column(key, width=width, anchor="w")
    vs = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")
    frame.pack(fill="both", expand=True, padx=8, pady=4)
    return tree


def _book_picker(parent) -> int | None:
    """Prompt for a book id (kept simple via a dialog list)."""
    books = data.list_books()
    if not books:
        messagebox.showinfo("Books", "No books yet.")
        return None
    labels = "\n".join(f"#{b.book_id}  {b.title}" for b in books[:40])
    bid = simpledialog.askinteger(
        "Pick book", f"Enter a book id:\n\n{labels}", parent=parent)
    return bid


# ══ Dashboard tab (item 47) ════════════════════════════════════════

class DashboardTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Dashboard")
        ttk.Button(self.frame, text="Refresh",
                    command=self.refresh).pack(anchor="w", padx=8,
                                                 pady=(8, 4))
        self.text = tk.Text(self.frame, height=16,
                             font=("TkFixedFont", 11))
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text.configure(state="disabled")
        self.refresh()

    def refresh(self) -> None:
        d = reports.dashboard()
        labels = {
            "active_loans": "Active loans",
            "overdue_loans": "Overdue loans",
            "due_soon": "Due soon",
            "holds_ready": "Holds ready to collect",
            "holds_expiring_today": "Holds expiring today",
            "holds_waiting": "Holds waiting",
            "open_fines": "Open fines",
            "outstanding_total": "Outstanding fines (total)",
            "total_books": "Total titles",
            "copies_on_loan": "Copies on loan",
        }
        lines = ["Library — today's working figures", "=" * 38, ""]
        for k, lbl in labels.items():
            lines.append(f"  {lbl:<28}: {d[k]}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Copies tab (items 28,37,40,41,43) ══════════════════════════════

class CopiesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Copies")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Book id:").pack(side="left")
        self.book_e = ttk.Entry(bar, width=8)
        self.book_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Show",
                    command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Add copy",
                    command=self._add).pack(side="left", padx=4)
        ttk.Button(bar, text="Set condition",
                    command=self._condition).pack(side="left", padx=4)
        ttk.Button(bar, text="Withdraw copy",
                    command=self._withdraw).pack(side="left", padx=4)
        ttk.Button(bar, text="Issue by barcode",
                    command=self._barcode_issue).pack(side="left", padx=4)
        ttk.Button(bar, text="Return by barcode",
                    command=self._barcode_return).pack(side="left", padx=4)
        ttk.Button(bar, text="Stock-take",
                    command=self._stocktake).pack(side="right")
        self.tree = _make_tree(self.frame, [
            ("id", "Copy", 60), ("barcode", "Barcode", 140),
            ("condition", "Condition", 110), ("status", "Status", 110),
            ("acquired", "Acquired", 110)])

    def _book_id(self) -> int | None:
        raw = self.book_e.get().strip()
        return int(raw) if raw.isdigit() else None

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        bid = self._book_id()
        for c in copies.list_copies(book_id=bid):
            self.tree.insert("", "end", iid=str(c.copy_id), values=(
                c.copy_id, c.barcode or "—", c.condition, c.status,
                c.acquired_on or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        bid = self._book_id()
        if bid is None:
            messagebox.showinfo("Add copy", "Enter a book id first.")
            return
        barcode = simpledialog.askstring(
            "Add copy", "Barcode (blank for none):",
            parent=self.frame.winfo_toplevel())
        try:
            copies.add_copy(bid, barcode=barcode or None)
        except ValidationError as e:
            messagebox.showerror("Add copy", str(e))
            return
        self.refresh()

    def _condition(self) -> None:
        cid = self._selected()
        if cid is None:
            messagebox.showinfo("Condition", "Select a copy.")
            return
        cond = simpledialog.askstring(
            "Condition",
            f"New condition {copies.COPY_CONDITIONS}:",
            parent=self.frame.winfo_toplevel())
        if not cond:
            return
        try:
            copies.set_condition(cid, cond)
        except ValidationError as e:
            messagebox.showerror("Condition", str(e))
            return
        self.refresh()

    def _withdraw(self) -> None:
        cid = self._selected()
        if cid is None:
            messagebox.showinfo("Withdraw", "Select a copy.")
            return
        reason = simpledialog.askstring(
            "Withdraw copy", "Reason:",
            parent=self.frame.winfo_toplevel())
        if not reason:
            return
        try:
            copies.withdraw_copy(cid, reason=reason)
        except ValidationError as e:
            messagebox.showerror("Withdraw", str(e))
            return
        self.refresh()

    def _barcode_issue(self) -> None:
        bc = simpledialog.askstring("Issue by barcode", "Scan barcode:",
                                    parent=self.frame.winfo_toplevel())
        if not bc:
            return
        sid = simpledialog.askstring("Issue by barcode", "Student id:",
                                     parent=self.frame.winfo_toplevel())
        if not sid:
            return
        try:
            l = copies.issue_by_barcode(bc, sid)
        except ValidationError as e:
            messagebox.showerror("Issue", str(e))
            return
        messagebox.showinfo("Issue", f"Issued loan #{l.loan_id}.")
        self.refresh()

    def _barcode_return(self) -> None:
        bc = simpledialog.askstring("Return by barcode", "Scan barcode:",
                                    parent=self.frame.winfo_toplevel())
        if not bc:
            return
        try:
            l = copies.return_by_barcode(bc)
        except ValidationError as e:
            messagebox.showerror("Return", str(e))
            return
        messagebox.showinfo("Return", f"Returned loan #{l.loan_id}.")
        self.refresh()

    def _stocktake(self) -> None:
        rows = copies.stock_take_report()
        flagged = [r for r in rows if r["discrepancy"]]
        msg = (f"{len(rows)} titles, {len(flagged)} with discrepancies.\n\n"
               + "\n".join(
                   f"#{r['book_id']} {r['title'][:30]}: "
                   f"counter={r['copies_total']} "
                   f"registered={r['registered']} missing={r['missing']}"
                   for r in flagged[:25]))
        messagebox.showinfo("Stock-take", msg or "No discrepancies.")


# ══ Reading lists tab (items 29,30,31,33) ══════════════════════════

class ReadingListsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Reading lists")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="New list",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Add item",
                    command=self._add_item).pack(side="left", padx=4)
        ttk.Button(bar, text="View items",
                    command=self._view).pack(side="left", padx=4)
        ttk.Button(bar, text="Request class set",
                    command=self._class_set).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        self.tree = _make_tree(self.frame, [
            ("id", "List", 60), ("title", "Title", 240),
            ("subject", "Subject", 140), ("owner", "Owner", 140)])
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for rl in reading.list_reading_lists():
            self.tree.insert("", "end", iid=str(rl.list_id), values=(
                rl.list_id, rl.title, rl.subject or "—",
                rl.owner or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _new(self) -> None:
        title = simpledialog.askstring("New list", "Title:",
                                       parent=self.frame.winfo_toplevel())
        if not title:
            return
        subject = simpledialog.askstring(
            "New list", "Subject (optional):",
            parent=self.frame.winfo_toplevel())
        reading.create_reading_list(title, subject=subject or None)
        self.refresh()

    def _add_item(self) -> None:
        lid = self._selected()
        if lid is None:
            messagebox.showinfo("Add item", "Select a list.")
            return
        bid = _book_picker(self.frame.winfo_toplevel())
        if bid is None:
            return
        req = simpledialog.askstring(
            "Add item", "Required or Recommended?",
            initialvalue="Recommended",
            parent=self.frame.winfo_toplevel())
        try:
            reading.add_item(lid, bid, requirement=req or "Recommended")
        except ValidationError as e:
            messagebox.showerror("Add item", str(e))
            return
        messagebox.showinfo("Add item", "Added.")

    def _view(self) -> None:
        lid = self._selected()
        if lid is None:
            messagebox.showinfo("View", "Select a list.")
            return
        items = reading.list_items(lid)
        msg = "\n".join(f"[{i.requirement}] {i.book_title}"
                        for i in items) or "(empty)"
        messagebox.showinfo("Reading list items", msg)

    def _class_set(self) -> None:
        bid = _book_picker(self.frame.winfo_toplevel())
        if bid is None:
            return
        n = simpledialog.askinteger("Class set", "Copies needed:",
                                    parent=self.frame.winfo_toplevel(),
                                    minvalue=1)
        if not n:
            return
        try:
            reading.request_class_set(bid, copies_needed=n)
        except ValidationError as e:
            messagebox.showerror("Class set", str(e))
            return
        messagebox.showinfo("Class set", "Request created.")


# ══ Acquisitions tab (items 34,35,36,39) ═══════════════════════════

class AcquisitionsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Acquisitions")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Suggest",
                    command=self._suggest).pack(side="left")
        ttk.Button(bar, text="Advance status",
                    command=self._advance).pack(side="left", padx=4)
        ttk.Button(bar, text="Add supplier",
                    command=self._supplier).pack(side="left", padx=4)
        ttk.Button(bar, text="Budgets",
                    command=self._budgets).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        self.tree = _make_tree(self.frame, [
            ("id", "ID", 50), ("title", "Title", 220),
            ("qty", "Qty", 50), ("cost", "Unit", 70),
            ("status", "Status", 110), ("subject", "Subject", 130)])
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for a in acq.list_acquisitions():
            self.tree.insert("", "end", iid=str(a.acq_id), values=(
                a.acq_id, a.title, a.quantity, f"{a.unit_cost:.2f}",
                a.status, a.subject_area or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _suggest(self) -> None:
        title = simpledialog.askstring("Suggest", "Title:",
                                       parent=self.frame.winfo_toplevel())
        if not title:
            return
        qty = simpledialog.askinteger("Suggest", "Quantity:",
                                      initialvalue=1, minvalue=1,
                                      parent=self.frame.winfo_toplevel())
        cost = simpledialog.askfloat("Suggest", "Unit cost:",
                                     initialvalue=0.0, minvalue=0.0,
                                     parent=self.frame.winfo_toplevel())
        subject = simpledialog.askstring(
            "Suggest", "Subject area (optional):",
            parent=self.frame.winfo_toplevel())
        try:
            acq.suggest(title, quantity=qty or 1, unit_cost=cost or 0.0,
                        subject_area=subject or None)
        except ValidationError as e:
            messagebox.showerror("Suggest", str(e))
            return
        self.refresh()

    def _advance(self) -> None:
        aid = self._selected()
        if aid is None:
            messagebox.showinfo("Advance", "Select an acquisition.")
            return
        status = simpledialog.askstring(
            "Advance", f"New status {acq.ACQ_STATUSES}:",
            parent=self.frame.winfo_toplevel())
        if not status:
            return
        try:
            if status == "Catalogued":
                book = acq.catalogue(aid)
                messagebox.showinfo("Catalogued",
                                    f"Created book #{book.book_id}.")
            else:
                acq.set_status(aid, status)
        except ValidationError as e:
            messagebox.showerror("Advance", str(e))
            return
        self.refresh()

    def _supplier(self) -> None:
        name = simpledialog.askstring("Supplier", "Name:",
                                      parent=self.frame.winfo_toplevel())
        if not name:
            return
        try:
            acq.add_supplier(name)
        except ValidationError as e:
            messagebox.showerror("Supplier", str(e))
            return
        messagebox.showinfo("Supplier", "Added.")

    def _budgets(self) -> None:
        year = simpledialog.askstring("Budgets", "Academic year:",
                                      parent=self.frame.winfo_toplevel())
        if not year:
            return
        rows = acq.budget_report(year)
        msg = "\n".join(
            f"{r['subject_area']}: alloc {r['allocated']:.2f} "
            f"spent {r['spent']:.2f} remain {r['remaining']:.2f}"
            for r in rows) or "No budget data."
        messagebox.showinfo(f"Budgets {year}", msg)


# ══ E-resources tab (item 49) ══════════════════════════════════════

class EResourcesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="E-resources")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Access (log)",
                    command=self._access).pack(side="left")
        ttk.Button(bar, text="Usage stats",
                    command=self._usage).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        self.tree = _make_tree(self.frame, [
            ("id", "ID", 50), ("title", "Title", 280),
            ("url", "Access URL", 320)])
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for b in eresources.list_eresources():
            self.tree.insert("", "end", iid=str(b.book_id), values=(
                b.book_id, b.title, b.location or "(no URL)"))

    def _access(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Access", "Select an e-resource.")
            return
        try:
            url = eresources.access(int(sel[0]))
        except ValidationError as e:
            messagebox.showerror("Access", str(e))
            return
        messagebox.showinfo("Access logged", f"URL: {url}")

    def _usage(self) -> None:
        rows = eresources.usage()
        msg = "\n".join(f"{r['title']}: {r['accesses']}"
                        for r in rows) or "No e-resources."
        messagebox.showinfo("E-resource usage", msg)


# ══ Study-space tab (item 48) ══════════════════════════════════════

class StudyTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Study rooms")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Date:").pack(side="left")
        self.date_e = ttk.Entry(bar, width=12)
        self.date_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Show",
                    command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Book",
                    command=self._book).pack(side="left", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self._cancel).pack(side="left", padx=4)
        self.tree = _make_tree(self.frame, [
            ("id", "ID", 50), ("space", "Space", 150),
            ("date", "Date", 100), ("time", "Time", 110),
            ("who", "Booked by", 120), ("status", "Status", 90)])
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        date = self.date_e.get().strip() or None
        for bk in study.list_bookings(date=date):
            who = bk.student_id or bk.staff or "—"
            self.tree.insert("", "end", iid=str(bk.booking_id), values=(
                bk.booking_id, bk.space, bk.date,
                f"{bk.start_time}-{bk.end_time}", who, bk.status))

    def _book(self) -> None:
        space = simpledialog.askstring("Book", "Space:",
                                       parent=self.frame.winfo_toplevel())
        if not space:
            return
        date = simpledialog.askstring("Book", "Date (YYYY-MM-DD):",
                                      initialvalue=_today(),
                                      parent=self.frame.winfo_toplevel())
        start = simpledialog.askstring("Book", "Start (HH:MM):",
                                       parent=self.frame.winfo_toplevel())
        end = simpledialog.askstring("Book", "End (HH:MM):",
                                     parent=self.frame.winfo_toplevel())
        try:
            study.book(space, date=date, start_time=start, end_time=end)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Book", str(e))
            return
        self.refresh()

    def _cancel(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Cancel", "Select a booking.")
            return
        try:
            study.cancel(int(sel[0]))
        except ValidationError as e:
            messagebox.showerror("Cancel", str(e))
            return
        self.refresh()


# ══ Reports tab (items 32,42,44,45,46) ═════════════════════════════

class ReportsTab:
    _REPORTS = {
        "Most borrowed": lambda: reports.most_borrowed(limit=20),
        "Least borrowed": lambda: reports.least_borrowed(limit=20),
        "Never borrowed": reports.never_borrowed,
        "Borrowers by year group": reports.borrowers_by_year_group,
        "Borrowers by tutor group": reports.borrowers_by_tutor_group,
        "Usage trends": lambda: reports.usage_trends(months=12),
        "Subject gap": reports.subject_gap_report,
        "New arrivals": lambda: [
            {"book_id": b.book_id, "title": b.title}
            for b in catalog.new_arrivals(limit=20)],
    }

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Reports")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Report:").pack(side="left")
        self.cb = ttk.Combobox(bar, state="readonly", width=28,
                                values=list(self._REPORTS))
        self.cb.current(0)
        self.cb.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Run",
                    command=self._run).pack(side="left")
        ttk.Button(bar, text="Export CSV",
                    command=self._export).pack(side="left", padx=4)
        self.text = tk.Text(self.frame, font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")
        self._rows: list[dict] = []

    def _run(self) -> None:
        self._rows = self._REPORTS[self.cb.get()]()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if not self._rows:
            self.text.insert("1.0", "(no data)")
        else:
            headers = list(self._rows[0].keys())
            self.text.insert("1.0", "  ".join(headers) + "\n")
            for r in self._rows:
                self.text.insert("end",
                                 "  ".join(str(r[h]) for h in headers)
                                 + "\n")
        self.text.configure(state="disabled")

    def _export(self) -> None:
        if not self._rows:
            messagebox.showinfo("Export", "Run a report first.")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        reports.export_csv(self._rows, path)
        messagebox.showinfo("Export", f"Saved to {path}")


# ══ Kiosk tab (item 50, read-only) ═════════════════════════════════

class KioskTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Kiosk")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search_e = ttk.Entry(bar, width=24)
        self.search_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Find books",
                    command=self._search).pack(side="left")
        ttk.Label(bar, text="   My id:").pack(side="left")
        self.sid_e = ttk.Entry(bar, width=12)
        self.sid_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="My loans & fines",
                    command=self._mine).pack(side="left")
        self.text = tk.Text(self.frame, font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def _show(self, content: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.configure(state="disabled")

    def _search(self) -> None:
        rows = kiosk.search(self.search_e.get().strip() or None)
        lines = [f"#{b.book_id}  {b.title}  "
                 f"({b.copies_available}/{b.copies_total} available)"
                 for b in rows] or ["(no matches)"]
        self._show("\n".join(lines))

    def _mine(self) -> None:
        sid = self.sid_e.get().strip()
        try:
            s = kiosk.student_summary(sid)
        except ValidationError as e:
            messagebox.showerror("Kiosk", str(e))
            return
        lines = [f"{s['name']} ({s['student_id']})", ""]
        lines.append(f"Loans ({len(s['loans'])}):")
        for l in s["loans"]:
            flag = " OVERDUE" if l["overdue"] else ""
            lines.append(f"  {l['title']}  due {l['due_on']}{flag}")
        lines.append(f"\nFines owed: {s['balance']:.2f}")
        lines.append(f"\nReservations ({len(s['reservations'])}):")
        for r in s["reservations"]:
            pos = (f" — #{r['queue_position']} in queue"
                   if r["queue_position"] else " — Ready")
            lines.append(f"  {r['title']}{pos}")
        self._show("\n".join(lines))
