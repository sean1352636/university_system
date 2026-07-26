"""Tk views for absence requests."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.pastoral.absence_requests import (
    absence_requests as data,
)
from education_system.systems.secondary.domain.pastoral.absence_requests.absence_requests import (
    REQUEST_STATUSES, ABSENCE_CATEGORIES, AUTHORISATIONS,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
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
                messagebox.showerror("Absence Requests", str(e),
                                      parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\n"
                    f"See logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


def _request_dialog(host, title: str,
                      initial: dict[str, Any] | None = None
                      ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("560x720")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var   = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    reqby_var   = tk.StringVar(value=str(initial.get("requested_by") or ""))
    rel_var     = tk.StringVar(value=str(initial.get("relationship") or ""))
    sub_var     = tk.StringVar(value=str(initial.get("submitted_date") or ""))
    start_var   = tk.StringVar(value=str(initial.get("start_date") or ""))
    end_var     = tk.StringVar(value=str(initial.get("end_date") or ""))
    days_var    = tk.StringVar(value=str(initial.get("school_days") or ""))
    cat_var     = tk.StringVar(value=str(initial.get("category")
                                            or "Family holiday"))
    dest_var    = tk.StringVar(value=str(initial.get("destination") or ""))
    status_var  = tk.StringVar(value=str(initial.get("status") or "Pending"))
    auth_var    = tk.StringVar(value=str(initial.get("authorisation")
                                            or "Not yet decided"))
    decby_var   = tk.StringVar(value=str(initial.get("decided_by") or ""))
    decdate_var = tk.StringVar(value=str(initial.get("decided_date") or ""))
    phone_var   = tk.StringVar(value=str(initial.get("contact_phone") or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",       ttk.Entry(frm, textvariable=pupil_var, width=14)),
        ("Requested by:",   ttk.Entry(frm, textvariable=reqby_var, width=28)),
        ("Relationship:",   ttk.Entry(frm, textvariable=rel_var, width=18)),
        ("Submitted:",      ttk.Entry(frm, textvariable=sub_var, width=14)),
        ("Start date:",     ttk.Entry(frm, textvariable=start_var, width=14)),
        ("End date:",       ttk.Entry(frm, textvariable=end_var, width=14)),
        ("School days:",    ttk.Entry(frm, textvariable=days_var, width=6)),
        ("Category:",       ttk.Combobox(frm, textvariable=cat_var,
                                           values=list(ABSENCE_CATEGORIES),
                                           state="readonly", width=28)),
        ("Destination:",    ttk.Entry(frm, textvariable=dest_var, width=28)),
        ("Status:",         ttk.Combobox(frm, textvariable=status_var,
                                           values=list(REQUEST_STATUSES),
                                           state="readonly", width=14)),
        ("Authorisation:",  ttk.Combobox(frm, textvariable=auth_var,
                                           values=list(AUTHORISATIONS),
                                           state="readonly", width=18)),
        ("Decided by:",     ttk.Entry(frm, textvariable=decby_var, width=24)),
        ("Decided date:",   ttk.Entry(frm, textvariable=decdate_var, width=14)),
        ("Contact phone:",  ttk.Entry(frm, textvariable=phone_var, width=18)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                          pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Reason:",         "reason", 4),
                    ("Decision notes:", "decision_notes", 2),
                    ("Notes:",          "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for i, (label, key, lines) in enumerate(text_fields,
                                              start=len(rows)):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw",
                                          pady=2)
        t = tk.Text(frm, width=44, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.grid(row=i, column=1, sticky="ew", pady=2)
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":        pupil_var.get().strip(),
            "requested_by":    reqby_var.get().strip(),
            "relationship":    rel_var.get().strip(),
            "submitted_date":  sub_var.get().strip(),
            "start_date":      start_var.get().strip(),
            "end_date":        end_var.get().strip(),
            "school_days":     days_var.get().strip(),
            "category":        cat_var.get().strip(),
            "destination":     dest_var.get().strip(),
            "status":          status_var.get().strip(),
            "authorisation":   auth_var.get().strip(),
            "decided_by":      decby_var.get().strip(),
            "decided_date":    decdate_var.get().strip(),
            "contact_phone":   phone_var.get().strip(),
        }
        for k, w in text_widgets.items():
            result[k] = w.get("1.0", "end").strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + len(text_fields), column=0,
                columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel",
                 command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_absence_requests(host) -> None:
    logger.debug("GUI: open_absence_requests")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Absence Requests",
                font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var,
                foreground="#666").pack(anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                   values=["", *REQUEST_STATUSES], state="readonly",
                   width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Category:").pack(side="left", padx=(0, 4))
    cat_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=cat_var,
                   values=["", *ABSENCE_CATEGORIES], state="readonly",
                   width=22).pack(side="left", padx=(0, 6))
    pending_only_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Pending only",
                      variable=pending_only_var).pack(side="left", padx=4)
    ttk.Button(bar, text="Apply",
                 command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
                 command=lambda: _new(host, on_done=_refresh)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
                 command=lambda: _edit(host, tree, on_done=_refresh)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Approve",
                 command=lambda: _decide(host, tree, approve=True,
                                            on_done=_refresh)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Decline",
                 command=lambda: _decide(host, tree, approve=False,
                                            on_done=_refresh)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Cancel req",
                 command=lambda: _cancel(host, tree, on_done=_refresh)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
                 command=lambda: _delete(host, tree, on_done=_refresh)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
                 command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "pupil", "year", "start", "end", "days",
             "category", "status", "auth", "decided")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 200),
        ("year", "Yr", 50), ("start", "Start", 90),
        ("end", "End", 90), ("days", "Days", 50),
        ("category", "Category", 170), ("status", "Status", 90),
        ("auth", "Auth", 110), ("decided", "Decided", 90),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.tag_configure("pending",  background="#fff7d6")
    tree.tag_configure("approved", background="#e3f5e3")
    tree.tag_configure("declined", background="#fde7e7")
    tree.tag_configure("cancelled", foreground="#888")

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_requests(
                status=status_var.get().strip() or None,
                category=cat_var.get().strip() or None,
                pending_only=pending_only_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Absence Requests", str(e),
                                  parent=host.root)
            return
        except Exception as e:
            logger.exception("absence_requests refresh failed")
            messagebox.showerror("Absence Requests",
                                  f"Could not load:\n\n{e}",
                                  parent=host.root)
            return
        for r in rows:
            pupil = f"{r.pupil_id} ({r.pupil_name or '-'})"
            tag = r.status.lower()
            tree.insert("", "end", iid=str(r.request_id), values=(
                r.request_id, pupil, r.pupil_year or "-",
                r.start_date, r.end_date,
                r.school_days if r.school_days is not None else "-",
                r.category, r.status, r.authorisation,
                r.decided_date or "-",
            ), tags=(tag,))
        try:
            s = data.cohort_summary()
            summary_var.set(
                f"Requests: {s['total']}    "
                f"Pending: {s['pending']}    "
                f"Approved: {s['approved']}    "
                f"Declined: {s['declined']}    "
                f"Days approved: {s['approved_school_days']}")
        except Exception:
            summary_var.set(f"{len(rows)} request(s)")
        host.status_var.set(
            f"Absence Requests: {len(rows)} record(s)")

    tree.bind("<Double-1>",
                lambda _e: _edit(host, tree, on_done=_refresh))
    status_var.trace_add("write", lambda *_: _refresh())
    cat_var.trace_add("write", lambda *_: _refresh())
    pending_only_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Absence Requests",
                              "Select a request first.",
                              parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _request_dialog(host, "New absence request")
    if not fields:
        return
    r = data.create(fields)
    messagebox.showinfo(
        "Absence Requests",
        f"Created request #{r.request_id}: {r.pupil_id} "
        f"{r.start_date}→{r.end_date} ({r.school_days} days)",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    existing = data.get(rid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "requested_by", "relationship",
        "submitted_date", "start_date", "end_date",
        "school_days", "category", "reason", "destination",
        "status", "authorisation", "decided_by", "decided_date",
        "decision_notes", "contact_phone", "notes")}
    fields = _request_dialog(host, f"Edit request #{rid}",
                                initial=initial)
    if not fields:
        return
    data.update(rid, fields)
    if on_done:
        on_done()


@_safe_view
def _decide(host, tree: ttk.Treeview, *,
              approve: bool, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    label = "Approve" if approve else "Decline"
    decided_by = simpledialog.askstring(
        label, "Decided by (name):", parent=host.root)
    if not decided_by:
        return
    notes = simpledialog.askstring(
        label, "Decision notes (optional):", parent=host.root)
    data.decide(rid, approve=approve,
                  decided_by=decided_by.strip(),
                  decision_notes=(notes or "").strip() or None)
    if on_done:
        on_done()


@_safe_view
def _cancel(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    if not messagebox.askyesno(
            "Cancel request",
            f"Mark request #{rid} as Cancelled?",
            parent=host.root):
        return
    notes = simpledialog.askstring(
        "Cancel request", "Notes (optional):", parent=host.root)
    data.cancel(rid, decision_notes=(notes or "").strip() or None)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    existing = data.get(rid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete request",
            f"Delete request #{rid} ({existing.pupil_id}, "
            f"{existing.start_date}→{existing.end_date})?",
            parent=host.root):
        return
    data.delete(rid)
    if on_done:
        on_done()
