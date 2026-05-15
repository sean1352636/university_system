"""Tk views for newsletters."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.primarysch_system.modules.domain.newsletters import (
    newsletters as data,
)
from education_system.primarysch_system.modules.domain.newsletters.newsletters import (
    AUDIENCE_CHOICES, AUDIENCE_LABELS, Newsletter, STATUSES, STATUS_LABELS,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
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
                messagebox.showerror("Newsletters", str(e),
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


def _set_text(text: tk.Text, value: str | None) -> None:
    text.delete("1.0", "end")
    if value:
        text.insert("1.0", value)


def _get_text(text: tk.Text) -> str:
    return text.get("1.0", "end").strip()


@_safe_view
def open_newsletters(host) -> None:
    logger.debug("GUI: open_newsletters")

    win = tk.Toplevel(host.root)
    win.title("Newsletters")
    win.transient(host.root)
    win.geometry("1180x640")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")
    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Year:").pack(side="left")
    year_var = tk.StringVar(value="All")
    year_box = ttk.Combobox(filt, textvariable=year_var,
                            values=["All"], state="readonly", width=10)
    year_box.pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Status:").pack(side="left")
    status_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["All"] + list(STATUSES),
                 state="readonly", width=10).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Audience:").pack(side="left")
    aud_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=aud_var,
                 values=["All"] + list(AUDIENCE_CHOICES),
                 state="readonly", width=14).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Year group:").pack(side="left")
    yg_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=yg_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Search:").pack(side="left", padx=(10, 0))
    search_var = tk.StringVar()
    ttk.Entry(filt, textvariable=search_var, width=24).pack(
        side="left", padx=(4, 0))

    cols = ("newsletter_id", "academic_year", "issue", "title",
            "audience", "status", "issue_date", "published_on", "author")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
    for col, label, width, anchor in [
        ("newsletter_id", "#", 50, "center"),
        ("academic_year", "AcYr", 80, "center"),
        ("issue", "Iss", 50, "center"),
        ("title", "Title", 280, "w"),
        ("audience", "Audience", 130, "w"),
        ("status", "Status", 90, "center"),
        ("issue_date", "Issue date", 100, "center"),
        ("published_on", "Published", 100, "center"),
        ("author", "Author", 160, "w"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.tag_configure("draft", foreground="#666")
    tree.tag_configure("archived", foreground="#888", background="#f4f4f4")
    tree.tag_configure("published", foreground="#1e7c1e")
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    btns = ttk.Frame(win, padding=10)
    btns.pack(fill="x")

    def _refresh() -> None:
        try:
            ay = None if year_var.get() == "All" else year_var.get()
            st = None if status_var.get() == "All" else status_var.get()
            aud = None if aud_var.get() == "All" else aud_var.get()
            yg = None if yg_var.get() == "All" else yg_var.get()
            rows = data.list_newsletters(
                academic_year=ay, status=st, audience=aud,
                target_year_group=yg,
                search=search_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Newsletters", str(e), parent=win)
            return
        except Exception:
            logger.exception("newsletters refresh failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for n in rows:
            aud_disp = n.audience
            if n.audience == "year_group" and n.target_year_group:
                aud_disp = f"year_group ({n.target_year_group})"
            tree.insert("", "end", iid=str(n.newsletter_id), values=(
                n.newsletter_id, n.academic_year,
                "" if n.issue_number is None else n.issue_number,
                n.title, aud_disp, n.status,
                n.issue_date or "", n.published_on or "",
                n.authored_by or "",
            ), tags=(n.status,))
        try:
            year_box["values"] = ["All"] + data.known_years()
            s = data.summary()
        except Exception:
            s = {"total": 0, "by_status": {st: 0 for st in STATUSES},
                 "academic_years": 0}
        parts = [f"Total: {s['total']}"]
        for st in STATUSES:
            parts.append(f"{st}: {s['by_status'].get(st, 0)}")
        parts.append(f"Years: {s['academic_years']}")
        parts.append(f"Showing: {len(rows)}")
        summary_var.set("   ".join(parts))

    def _selected_id() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Newsletters",
                                "Select a newsletter first.", parent=win)
            return None
        return int(sel[0])

    def _add() -> None:
        _open_form_dialog(win, newsletter_id=None, on_saved=_refresh)

    def _edit() -> None:
        nid = _selected_id()
        if nid is None:
            return
        _open_form_dialog(win, newsletter_id=nid, on_saved=_refresh)

    def _view() -> None:
        nid = _selected_id()
        if nid is None:
            return
        _open_view_dialog(win, nid, on_changed=_refresh)

    def _publish() -> None:
        nid = _selected_id()
        if nid is None:
            return
        try:
            data.publish(nid)
        except ValidationError as e:
            messagebox.showerror("Newsletters", str(e), parent=win)
            return
        except Exception:
            logger.exception("publish(%s) failed", nid)
            messagebox.showerror("Error", "Could not publish — see logs.",
                                 parent=win)
            return
        _refresh()

    def _revert() -> None:
        nid = _selected_id()
        if nid is None:
            return
        if not messagebox.askyesno("Revert to draft",
                                   f"Revert newsletter #{nid} to draft?",
                                   parent=win):
            return
        try:
            data.revert_to_draft(nid)
        except Exception:
            logger.exception("revert(%s) failed", nid)
            messagebox.showerror("Error", "Could not revert — see logs.",
                                 parent=win)
            return
        _refresh()

    def _archive() -> None:
        nid = _selected_id()
        if nid is None:
            return
        if not messagebox.askyesno("Archive",
                                   f"Archive newsletter #{nid}?", parent=win):
            return
        try:
            data.archive(nid)
        except Exception:
            logger.exception("archive(%s) failed", nid)
            messagebox.showerror("Error", "Could not archive — see logs.",
                                 parent=win)
            return
        _refresh()

    def _delete() -> None:
        nid = _selected_id()
        if nid is None:
            return
        if not messagebox.askyesno("Delete newsletter",
                                   f"Delete newsletter #{nid}? "
                                   f"Consider archiving instead.",
                                   parent=win):
            return
        try:
            data.delete(nid)
        except Exception:
            logger.exception("delete(%s) failed", nid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh()

    ttk.Button(btns, text="New draft", command=_add).pack(side="left")
    ttk.Button(btns, text="Edit draft", command=_edit).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="View...", command=_view).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Publish", command=_publish).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Revert to draft", command=_revert).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Archive", command=_archive).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _view())
    for v in (year_var, status_var, aud_var, yg_var, search_var):
        v.trace_add("write", lambda *_: _refresh())

    _refresh()


def _open_form_dialog(parent, *, newsletter_id: int | None,
                      on_saved: Callable[[], None]) -> None:
    existing: Newsletter | None = None
    if newsletter_id is not None:
        try:
            existing = data.get(newsletter_id)
        except Exception:
            logger.exception("get(%s) failed", newsletter_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Newsletters",
                                 f"No newsletter #{newsletter_id}",
                                 parent=parent)
            return
        if existing.is_published:
            messagebox.showinfo(
                "Newsletters",
                "This newsletter is published. Revert it to draft to edit.",
                parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Newsletter" if existing else "New newsletter")
    dlg.transient(parent)
    dlg.geometry("720x680")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Title *").grid(row=0, column=0, sticky="w", pady=3)
    title_var = tk.StringVar(value=existing.title if existing else "")
    ttk.Entry(frm, textvariable=title_var, width=48).grid(
        row=0, column=1, columnspan=3, sticky="ew", pady=3)

    ttk.Label(frm, text="Academic year *").grid(
        row=1, column=0, sticky="w", pady=3)
    ay_var = tk.StringVar(value=existing.academic_year if existing else "")
    ttk.Entry(frm, textvariable=ay_var, width=14).grid(
        row=1, column=1, sticky="w", pady=3)
    ttk.Label(frm, text="e.g. 2025-26", foreground="#888").grid(
        row=1, column=2, sticky="w", padx=(8, 0))

    ttk.Label(frm, text="Issue number").grid(
        row=2, column=0, sticky="w", pady=3)
    iss_var = tk.StringVar(
        value=str(existing.issue_number) if existing and existing.issue_number
        else "")
    ttk.Entry(frm, textvariable=iss_var, width=8).grid(
        row=2, column=1, sticky="w", pady=3)
    suggest_var = tk.StringVar()
    ttk.Label(frm, textvariable=suggest_var,
              foreground="#888").grid(row=2, column=2, sticky="w", padx=(8, 0))

    def _suggest_issue(*_a) -> None:
        ay = ay_var.get().strip()
        if not ay:
            suggest_var.set("")
            return
        try:
            n = data.next_issue_number(ay)
        except Exception:
            suggest_var.set("")
            return
        suggest_var.set(f"next free in {ay}: {n}")
    ay_var.trace_add("write", _suggest_issue)
    _suggest_issue()

    ttk.Label(frm, text="Issue date (YYYY-MM-DD)").grid(
        row=3, column=0, sticky="w", pady=3)
    date_var = tk.StringVar(
        value=existing.issue_date or "" if existing else "")
    ttk.Entry(frm, textvariable=date_var, width=14).grid(
        row=3, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Audience *").grid(row=4, column=0, sticky="w", pady=3)
    aud_var = tk.StringVar(
        value=existing.audience if existing else "whole_school")
    ttk.Combobox(frm, textvariable=aud_var, values=list(AUDIENCE_CHOICES),
                 state="readonly", width=18).grid(
        row=4, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Year group (if year_group)").grid(
        row=5, column=0, sticky="w", pady=3)
    yg_var = tk.StringVar(
        value=existing.target_year_group or "" if existing else "")
    ttk.Combobox(frm, textvariable=yg_var,
                 values=[""] + list(YEAR_GROUPS),
                 state="readonly", width=8).grid(
        row=5, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Authored by").grid(
        row=6, column=0, sticky="w", pady=3)
    author_var = tk.StringVar(
        value=existing.authored_by or "" if existing else "")
    ttk.Entry(frm, textvariable=author_var, width=30).grid(
        row=6, column=1, columnspan=2, sticky="ew", pady=3)

    ttk.Label(frm, text="Body").grid(row=7, column=0, sticky="nw", pady=(8, 0))
    body_text = tk.Text(frm, height=14, width=70, wrap="word")
    body_text.grid(row=7, column=1, columnspan=3, sticky="nsew", pady=(8, 0))
    _set_text(body_text, existing.body if existing else None)

    ttk.Label(frm, text="Notes").grid(row=8, column=0, sticky="w", pady=3)
    notes_var = tk.StringVar(value=existing.notes or "" if existing else "")
    ttk.Entry(frm, textvariable=notes_var, width=48).grid(
        row=8, column=1, columnspan=3, sticky="ew", pady=3)

    frm.columnconfigure(1, weight=1)
    frm.columnconfigure(2, weight=1)
    frm.columnconfigure(3, weight=1)
    frm.rowconfigure(7, weight=1)

    def _save(*, then_publish: bool = False) -> None:
        payload = {
            "title": title_var.get(),
            "issue_number": iss_var.get(),
            "academic_year": ay_var.get(),
            "issue_date": date_var.get(),
            "audience": aud_var.get(),
            "target_year_group": yg_var.get(),
            "authored_by": author_var.get(),
            "body": _get_text(body_text),
            "status": existing.status if existing else "draft",
            "notes": notes_var.get(),
        }
        try:
            if existing is None:
                rec = data.create(payload)
            else:
                rec = data.update(existing.newsletter_id, payload)
            if then_publish:
                rec = data.publish(rec.newsletter_id)
        except ValidationError as e:
            messagebox.showerror("Newsletters", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save newsletter failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=9, column=0, columnspan=4, sticky="ew", pady=(12, 0))
    ttk.Button(btn_row, text="Save draft", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Save & publish",
               command=lambda: _save(then_publish=True)).pack(
        side="right", padx=(0, 8))
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _open_view_dialog(parent, newsletter_id: int,
                      on_changed: Callable[[], None]) -> None:
    try:
        rec = data.get(newsletter_id)
    except Exception:
        logger.exception("get(%s) failed", newsletter_id)
        messagebox.showerror("Error", "Could not load — see logs.",
                             parent=parent)
        return
    if rec is None:
        messagebox.showerror("Newsletters",
                             f"No newsletter #{newsletter_id}", parent=parent)
        return

    dlg = tk.Toplevel(parent)
    dlg.title(f"Newsletter #{rec.newsletter_id}")
    dlg.transient(parent)
    dlg.geometry("720x620")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    iss = f"  issue {rec.issue_number}" if rec.issue_number else ""
    ttk.Label(frm,
              text=f"{rec.title}",
              font=("Segoe UI", 13, "bold"),
              wraplength=680).pack(anchor="w")
    aud = rec.audience
    if rec.audience == "year_group" and rec.target_year_group:
        aud = f"year_group ({rec.target_year_group})"
    ttk.Label(frm,
              text=f"{rec.academic_year}{iss}   •   {aud}   •   "
                   f"Status: {rec.status}",
              foreground="#444").pack(anchor="w", pady=(2, 4))
    ttk.Label(frm,
              text=f"Issue date: {rec.issue_date or '-'}   "
                   f"Published: {rec.published_on or '-'}   "
                   f"Author: {rec.authored_by or '-'}",
              foreground="#666").pack(anchor="w", pady=(0, 8))

    text = tk.Text(frm, wrap="word", height=20)
    text.pack(fill="both", expand=True)
    text.insert("1.0", rec.body or "(no body)")
    if rec.notes:
        text.insert("end", f"\n\n— Notes —\n{rec.notes}")
    text.config(state="disabled")

    btn_row = ttk.Frame(frm)
    btn_row.pack(fill="x", pady=(10, 0))

    def _do_publish() -> None:
        try:
            data.publish(rec.newsletter_id)
        except ValidationError as e:
            messagebox.showerror("Newsletters", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("publish failed for %s", rec.newsletter_id)
            messagebox.showerror("Error", "Could not publish — see logs.",
                                 parent=dlg)
            return
        on_changed()
        dlg.destroy()

    def _do_revert() -> None:
        try:
            data.revert_to_draft(rec.newsletter_id)
        except Exception:
            logger.exception("revert failed for %s", rec.newsletter_id)
            messagebox.showerror("Error", "Could not revert — see logs.",
                                 parent=dlg)
            return
        on_changed()
        dlg.destroy()

    def _do_archive() -> None:
        try:
            data.archive(rec.newsletter_id)
        except Exception:
            logger.exception("archive failed for %s", rec.newsletter_id)
            messagebox.showerror("Error", "Could not archive — see logs.",
                                 parent=dlg)
            return
        on_changed()
        dlg.destroy()

    if rec.is_draft:
        ttk.Button(btn_row, text="Publish",
                   command=_do_publish).pack(side="left")
    elif rec.is_published:
        ttk.Button(btn_row, text="Revert to draft",
                   command=_do_revert).pack(side="left")
        ttk.Button(btn_row, text="Archive",
                   command=_do_archive).pack(side="left", padx=(8, 0))
    elif rec.is_archived:
        ttk.Button(btn_row, text="Revert to draft",
                   command=_do_revert).pack(side="left")
    ttk.Button(btn_row, text="Close",
               command=dlg.destroy).pack(side="right")
