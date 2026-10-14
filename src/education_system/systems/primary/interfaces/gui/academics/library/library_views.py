"""Tk views for the library catalogue + loans."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.academics.library import (
    library as data,
)
from education_system.systems.primary.domain.academics.library.library import (
    CATEGORIES, LOAN_STATUSES,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror("Library", str(e),
                                     parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


def _book_dialog(host, title: str, initial: dict[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("500x500")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    title_var  = tk.StringVar(value=str(initial.get("title") or ""))
    author_var = tk.StringVar(value=str(initial.get("author") or ""))
    isbn_var   = tk.StringVar(value=str(initial.get("isbn") or ""))
    cat_var    = tk.StringVar(value=str(initial.get("category")
                                         or "Fiction"))
    year_var   = tk.StringVar(value=str(initial.get("year_published")
                                         or ""))
    copies_var = tk.StringVar(value=str(initial.get("copies_total") or 1))
    loc_var    = tk.StringVar(value=str(initial.get("location") or ""))
    active_var = tk.BooleanVar(
        value=True if initial.get("is_active") is None
        else bool(initial.get("is_active")))

    rows: list[tuple[str, tk.Widget]] = [
        ("Title:",     ttk.Entry(frm, textvariable=title_var, width=44)),
        ("Author:",    ttk.Entry(frm, textvariable=author_var, width=30)),
        ("ISBN:",      ttk.Entry(frm, textvariable=isbn_var, width=20)),
        ("Category:",  ttk.Combobox(frm, textvariable=cat_var,
                                     values=list(CATEGORIES),
                                     state="readonly", width=14)),
        ("Year published:", ttk.Entry(frm, textvariable=year_var,
                                       width=8)),
        ("Total copies:",   ttk.Spinbox(frm, from_=1, to=10000,
                                         textvariable=copies_var,
                                         width=8)),
        ("Shelf / location:", ttk.Entry(frm, textvariable=loc_var,
                                          width=18)),
        ("Active:",    ttk.Checkbutton(frm, variable=active_var)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=40, height=4, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "title":          title_var.get().strip(),
            "author":         author_var.get().strip(),
            "isbn":           isbn_var.get().strip(),
            "category":       cat_var.get().strip(),
            "year_published": year_var.get().strip(),
            "copies_total":   copies_var.get().strip(),
            "location":       loc_var.get().strip(),
            "is_active":      bool(active_var.get()),
            "notes":          notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_library(host) -> None:
    logger.debug("GUI: open_library")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Library",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    # ── Catalogue tab ────────────────────────────────
    cat_tab = ttk.Frame(nb, padding=4)
    nb.add(cat_tab, text="Catalogue")

    c_bar = ttk.Frame(cat_tab)
    c_bar.pack(fill="x", pady=(0, 6))
    ttk.Label(c_bar, text="Search:").pack(side="left", padx=(0, 4))
    search_var = tk.StringVar(value="")
    ttk.Entry(c_bar, textvariable=search_var, width=22).pack(
        side="left", padx=(0, 6))
    ttk.Label(c_bar, text="Category:").pack(side="left", padx=(0, 4))
    cat_filter_var = tk.StringVar(value="")
    ttk.Combobox(c_bar, textvariable=cat_filter_var,
                 values=["", *CATEGORIES], state="readonly",
                 width=12).pack(side="left", padx=(0, 6))
    only_active_var = tk.BooleanVar(value=False)
    only_avail_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(c_bar, text="Active only", variable=only_active_var,
                    command=lambda: _refresh_books()).pack(
        side="left", padx=(0, 6))
    ttk.Checkbutton(c_bar, text="Available", variable=only_avail_var,
                    command=lambda: _refresh_books()).pack(
        side="left", padx=(0, 8))
    ttk.Button(c_bar, text="New",
               command=lambda: _new_book(host, on_done=_refresh_books)
               ).pack(side="left", padx=2)
    ttk.Button(c_bar, text="Edit",
               command=lambda: _edit_book(host, book_tree,
                                            on_done=_refresh_books)
               ).pack(side="left", padx=2)
    ttk.Button(c_bar, text="Toggle active",
               command=lambda: _toggle_book(host, book_tree,
                                              on_done=_refresh_books)
               ).pack(side="left", padx=2)
    ttk.Button(c_bar, text="Lend",
               command=lambda: _lend(host, book_tree,
                                       on_done=_refresh_all)
               ).pack(side="left", padx=2)
    ttk.Button(c_bar, text="Delete",
               command=lambda: _delete_book(host, book_tree,
                                              on_done=_refresh_books)
               ).pack(side="left", padx=2)
    ttk.Button(c_bar, text="Refresh",
               command=lambda: _refresh_books()).pack(side="left", padx=2)

    book_cols = ("id", "title", "author", "cat", "year", "copies",
                 "isbn", "location", "active")
    book_tree = ttk.Treeview(cat_tab, columns=book_cols,
                              show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("title", "Title", 250),
        ("author", "Author", 160), ("cat", "Cat", 90),
        ("year", "Yr", 50), ("copies", "Avail/Tot", 80),
        ("isbn", "ISBN", 130), ("location", "Loc", 90),
        ("active", "Act", 50),
    ]:
        book_tree.heading(c, text=label)
        book_tree.column(c, width=w, anchor="w")
    book_tree.pack(fill="both", expand=True)

    # ── Loans tab ───────────────────────────────────
    loan_tab = ttk.Frame(nb, padding=4)
    nb.add(loan_tab, text="Loans")

    l_bar = ttk.Frame(loan_tab)
    l_bar.pack(fill="x", pady=(0, 6))
    ttk.Label(l_bar, text="Status:").pack(side="left", padx=(0, 4))
    loan_status_var = tk.StringVar(value="")
    ttk.Combobox(l_bar, textvariable=loan_status_var,
                 values=["", *LOAN_STATUSES], state="readonly",
                 width=10).pack(side="left", padx=(0, 6))
    ttk.Label(l_bar, text="Pupil:").pack(side="left", padx=(0, 4))
    loan_pupil_var = tk.StringVar(value="")
    ttk.Entry(l_bar, textvariable=loan_pupil_var, width=14).pack(
        side="left", padx=(0, 8))
    ttk.Button(l_bar, text="Apply",
               command=lambda: _refresh_loans()).pack(side="left", padx=2)
    ttk.Button(l_bar, text="Return",
               command=lambda: _return(host, loan_tree,
                                          on_done=_refresh_all)
               ).pack(side="left", padx=2)
    ttk.Button(l_bar, text="Mark lost",
               command=lambda: _lost(host, loan_tree,
                                        on_done=_refresh_all)
               ).pack(side="left", padx=2)
    ttk.Button(l_bar, text="Refresh",
               command=lambda: _refresh_loans()).pack(side="left", padx=2)

    loan_cols = ("id", "date", "due", "ret", "pupil", "book", "status",
                 "od")
    loan_tree = ttk.Treeview(loan_tab, columns=loan_cols,
                              show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Loan", 90),
        ("due", "Due", 90), ("ret", "Returned", 90),
        ("pupil", "Pupil", 90),
        ("book", "Book", 240), ("status", "Status", 80),
        ("od", "Days OD", 70),
    ]:
        loan_tree.heading(c, text=label)
        loan_tree.column(c, width=w, anchor="w")
    loan_tree.pack(fill="both", expand=True)

    def _refresh_summary() -> None:
        try:
            o = data.overview()
            summary_var.set(
                f"Titles: {o['books_total']}    "
                f"Active: {o['books_active']}    "
                f"Copies: {o['copies_avail']}/{o['copies_total']}    "
                + "    ".join(f"{k}: {v}" for k, v in o["loans"].items()))
        except Exception:
            logger.exception("library overview failed")
            summary_var.set("(summary unavailable)")

    def _refresh_books() -> None:
        for i in book_tree.get_children():
            book_tree.delete(i)
        try:
            rows = data.list_books(
                active_only=bool(only_active_var.get()),
                available_only=bool(only_avail_var.get()),
                category=cat_filter_var.get().strip() or None,
                query=search_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Library", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("library books refresh failed")
            messagebox.showerror("Library",
                                 f"Could not load books:\n\n{e}",
                                 parent=host.root)
            return
        for b in rows:
            book_tree.insert("", "end", iid=str(b.book_id), values=(
                b.book_id, b.title, b.author or "-",
                b.category,
                b.year_published if b.year_published else "-",
                f"{b.copies_available}/{b.copies_total}",
                b.isbn or "-", b.location or "-",
                "Yes" if b.is_active else "No",
            ))
        _refresh_summary()
        host.status_var.set(f"Library: {len(rows)} title(s)")

    def _refresh_loans() -> None:
        for i in loan_tree.get_children():
            loan_tree.delete(i)
        try:
            rows = data.list_loans(
                status=loan_status_var.get().strip() or None,
                pupil_id=loan_pupil_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Library", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("library loans refresh failed")
            messagebox.showerror("Library",
                                 f"Could not load loans:\n\n{e}",
                                 parent=host.root)
            return
        for l in rows:
            od = l.days_overdue
            loan_tree.insert("", "end", iid=str(l.loan_id), values=(
                l.loan_id, l.loan_date, l.due_date,
                l.returned_date or "-", l.pupil_id,
                l.book_title or "?", l.status,
                od if od else "-",
            ))
        _refresh_summary()
        host.status_var.set(f"Library: {len(rows)} loan(s)")

    def _refresh_all() -> None:
        _refresh_books()
        _refresh_loans()

    book_tree.bind("<Double-1>",
                    lambda _e: _edit_book(host, book_tree,
                                            on_done=_refresh_books))
    loan_tree.bind("<Double-1>",
                    lambda _e: _return(host, loan_tree,
                                          on_done=_refresh_all))
    search_var.trace_add("write", lambda *_: _refresh_books())
    cat_filter_var.trace_add("write", lambda *_: _refresh_books())
    loan_status_var.trace_add("write", lambda *_: _refresh_loans())
    _refresh_books()
    _refresh_loans()


def _selected_id(tree: ttk.Treeview, host, label: str) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Library", f"Select a {label} first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new_book(host, *, on_done=None) -> None:
    fields = _book_dialog(host, "Add book")
    if not fields:
        return
    b = data.create_book(fields)
    messagebox.showinfo("Library",
                        f"Added {b.title} ({b.copies_total} copies)",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit_book(host, tree: ttk.Treeview, *, on_done=None) -> None:
    bid = _selected_id(tree, host, "book")
    if bid is None:
        return
    existing = data.get_book(bid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "isbn", "title", "author", "category", "year_published",
        "copies_total", "location", "is_active", "notes")}
    fields = _book_dialog(host, f"Edit {existing.title}",
                            initial=initial)
    if not fields:
        return
    data.update_book(bid, fields)
    if on_done:
        on_done()


@_safe_view
def _toggle_book(host, tree: ttk.Treeview, *, on_done=None) -> None:
    bid = _selected_id(tree, host, "book")
    if bid is None:
        return
    rec = data.toggle_active(bid)
    messagebox.showinfo(
        "Library",
        f"{rec.title} is now "
        f"{'active' if rec.is_active else 'inactive'}.",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _delete_book(host, tree: ttk.Treeview, *, on_done=None) -> None:
    bid = _selected_id(tree, host, "book")
    if bid is None:
        return
    existing = data.get_book(bid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete book",
            f"Delete '{existing.title}' and its loan history?",
            parent=host.root):
        return
    data.delete_book(bid)
    if on_done:
        on_done()


@_safe_view
def _lend(host, tree: ttk.Treeview, *, on_done=None) -> None:
    bid = _selected_id(tree, host, "book")
    if bid is None:
        return
    book = data.get_book(bid)
    if book is None:
        return
    if book.copies_available < 1:
        messagebox.showerror("Library",
                             f"No copies of '{book.title}' available.",
                             parent=host.root)
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Lend — {book.title}")
    dlg.transient(host.root)
    dlg.geometry("400x240")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pid_var = tk.StringVar(value="")
    ldate_var = tk.StringVar(value="")
    ddate_var = tk.StringVar(value="")
    notes_var = tk.StringVar(value="")
    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:", ttk.Entry(frm, textvariable=pid_var, width=14)),
        ("Loan date (blank = today):",
                       ttk.Entry(frm, textvariable=ldate_var, width=14)),
        ("Due date (blank = +14d):",
                       ttk.Entry(frm, textvariable=ddate_var, width=14)),
        ("Notes:", ttk.Entry(frm, textvariable=notes_var, width=24)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=22).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    def _save() -> None:
        try:
            rec = data.lend(bid, pid_var.get().strip(),
                              loan_date=ldate_var.get().strip() or None,
                              due_date=ddate_var.get().strip() or None,
                              notes=notes_var.get().strip() or None)
        except ValidationError as e:
            messagebox.showerror("Library", str(e), parent=dlg)
            return
        messagebox.showinfo("Library",
                            f"Lent to {rec.pupil_id} (due {rec.due_date})",
                            parent=dlg)
        dlg.destroy()
        if on_done:
            on_done()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Lend", command=_save).pack(side="right")


@_safe_view
def _return(host, tree: ttk.Treeview, *, on_done=None) -> None:
    lid = _selected_id(tree, host, "loan")
    if lid is None:
        return
    loan = data.get_loan(lid)
    if loan is None:
        return
    if loan.status in ("Returned", "Lost"):
        messagebox.showerror("Library",
                             f"Loan #{lid} is already {loan.status}.",
                             parent=host.root)
        return
    if not messagebox.askyesno(
            "Return loan",
            f"Return '{loan.book_title}' from {loan.pupil_id}?",
            parent=host.root):
        return
    data.return_loan(lid)
    if on_done:
        on_done()


@_safe_view
def _lost(host, tree: ttk.Treeview, *, on_done=None) -> None:
    lid = _selected_id(tree, host, "loan")
    if lid is None:
        return
    loan = data.get_loan(lid)
    if loan is None:
        return
    if loan.status in ("Returned", "Lost"):
        messagebox.showerror("Library",
                             f"Loan #{lid} is already {loan.status}.",
                             parent=host.root)
        return
    if not messagebox.askyesno(
            "Mark lost",
            f"Mark '{loan.book_title}' as lost? "
            f"This will reduce the title's total copies.",
            parent=host.root):
        return
    notes = simpledialog.askstring(
        "Notes", "Notes (optional):", parent=host.root)
    data.mark_lost(lid, notes=notes)
    if on_done:
        on_done()
