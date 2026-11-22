"""Tk views for absence requests."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.pastoral.absence_requests import (
    absence_requests as data,
)
from education_system.systems.primary.domain.pastoral.absence_requests.absence_requests import (
    REQUEST_STATUSES, ABSENCE_CATEGORIES, AUTHORISATIONS,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError,
)
from education_system.systems.primary.interfaces.gui import kit

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


def _owner(host, owner=None):
    """The window a pop-up belongs to: the page's own window when the page
    was popped out, else the main window."""
    return owner if owner is not None else host.root


def _request_dialog(host, title: str,
                      initial: dict[str, Any] | None = None, *,
                      owner=None) -> dict[str, Any] | None:
    master = _owner(host, owner)
    dlg = tk.Toplevel(master)
    dlg.title(title)
    dlg.transient(master)
    dlg.geometry("620x680")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    initial = initial or {}
    frm, footer = kit.scrolled_form(dlg)

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
        ("Pupil:",          kit.PupilPicker(frm, pupil_var)),
        ("Requested by:",   ttk.Entry(frm, textvariable=reqby_var, width=28)),
        ("Relationship:",   ttk.Entry(frm, textvariable=rel_var, width=18)),
        ("Submitted:",      kit.DateField(frm, sub_var)),
        ("Start date:",     kit.DateField(frm, start_var)),
        ("End date:",       kit.DateField(frm, end_var)),
        ("School days:",    kit.NumberField(frm, days_var, from_=0, to=60,
                                            width=6)),
        ("Category:",       kit.ChoiceField(frm, cat_var,
                                            choices=ABSENCE_CATEGORIES)),
        ("Destination:",    ttk.Entry(frm, textvariable=dest_var, width=28)),
        ("Status:",         kit.ChoiceField(frm, status_var,
                                            choices=REQUEST_STATUSES,
                                            width=14)),
        ("Authorisation:",  kit.ChoiceField(frm, auth_var,
                                            choices=AUTHORISATIONS,
                                            width=18)),
        ("Decided by:",     kit.StaffPicker(frm, decby_var, by="name")),
        ("Decided date:",   kit.DateField(frm, decdate_var)),
        ("Contact phone:",  ttk.Entry(frm, textvariable=phone_var, width=18)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                          pady=2)
        widget.grid(row=i, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="(leave School days blank to count them from the "
                        "dates)", foreground="#666").grid(
        row=len(rows), column=1, sticky="w")
    frm.columnconfigure(1, weight=1)

    text_fields = [("Reason:",         "reason", 4),
                    ("Decision notes:", "decision_notes", 2),
                    ("Notes:",          "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for i, (label, key, lines) in enumerate(text_fields,
                                              start=len(rows) + 1):
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

    ttk.Button(footer, text="Cancel",
                 command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(footer, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def _decision_dialog(owner, label: str) -> tuple[str, str] | None:
    """Who decided (a staff member) and optional notes; None if cancelled."""
    dlg = tk.Toplevel(owner)
    dlg.title(label)
    dlg.transient(owner)
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    by_var = tk.StringVar()
    notes_var = tk.StringVar()
    ttk.Label(frm, text="Decided by:").grid(row=0, column=0, sticky="w", pady=2)
    kit.StaffPicker(frm, by_var, by="name").grid(row=0, column=1, sticky="w",
                                                  pady=2)
    ttk.Label(frm, text="Decision notes (optional):").grid(
        row=1, column=0, sticky="w", pady=2)
    ttk.Entry(frm, textvariable=notes_var, width=44).grid(
        row=1, column=1, sticky="w", pady=2)
    result: tuple[str, str] | None = None

    def _ok() -> None:
        nonlocal result
        if not by_var.get().strip():
            messagebox.showerror(label, "Choose who decided.", parent=dlg)
            return
        result = (by_var.get().strip(), notes_var.get().strip())
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(btns, text=label, command=_ok).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_absence_requests(host) -> None:
    logger.debug("GUI: open_absence_requests")
    kit.show_page(host, "Absence Requests",
                  lambda parent: _draw_absence_requests(parent, host))


def _draw_absence_requests(parent, host) -> None:
    root = parent
    win = parent.winfo_toplevel()
    kit.page_heading(root, "Absence Requests",
                     "Term-time leave requests from parents: approve, "
                     "decline or cancel.")

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var,
                foreground="#666").pack(anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    kit.ChoiceField(bar, status_var, choices=REQUEST_STATUSES, blank=True,
                    width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Category:").pack(side="left", padx=(0, 4))
    cat_var = tk.StringVar(value="")
    kit.ChoiceField(bar, cat_var, choices=ABSENCE_CATEGORIES, blank=True,
                    width=22).pack(side="left", padx=(0, 6))
    pending_only_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Pending only",
                      variable=pending_only_var).pack(side="left", padx=4)
    ttk.Button(bar, text="Apply",
                 command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
                 command=lambda: _new(host, on_done=_refresh, owner=win)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
                 command=lambda: _edit(host, tree, on_done=_refresh,
                                       owner=win)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Approve",
                 command=lambda: _decide(host, tree, approve=True,
                                            on_done=_refresh, owner=win)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Decline",
                 command=lambda: _decide(host, tree, approve=False,
                                            on_done=_refresh, owner=win)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Cancel req",
                 command=lambda: _cancel(host, tree, on_done=_refresh,
                                         owner=win)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
                 command=lambda: _delete(host, tree, on_done=_refresh,
                                         owner=win)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
                 command=lambda: _refresh()).pack(side="left", padx=2)

    tree = kit.tree(root, [
        ("id", "ID", 50), ("pupil", "Pupil", 200),
        ("year", "Yr", 50), ("start", "Start", 90),
        ("end", "End", 90), ("days", "Days", 50),
        ("category", "Category", 170), ("status", "Status", 90),
        ("auth", "Auth", 110), ("decided", "Decided", 90),
    ], height=18, tags={
        "pending": "#fff7d6", "approved": "#e3f5e3", "declined": "#fde7e7",
        "cancelled": {"foreground": "#888"},
    })

    def _refresh() -> None:
        if not tree.winfo_exists():
            return
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
                                  parent=win)
            return
        except Exception as e:
            logger.exception("absence_requests refresh failed")
            messagebox.showerror("Absence Requests",
                                  f"Could not load:\n\n{e}",
                                  parent=win)
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
        status_bar = getattr(host, "status_var", None)
        if status_bar is not None:
            status_bar.set(f"Absence Requests: {len(rows)} record(s)")

    tree.bind("<Double-1>",
                lambda _e: _edit(host, tree, on_done=_refresh, owner=win))
    status_var.trace_add("write", lambda *_: _refresh())
    cat_var.trace_add("write", lambda *_: _refresh())
    pending_only_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host, owner=None) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Absence Requests",
                              "Select a request first.",
                              parent=_owner(host, owner))
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None, owner=None) -> None:
    fields = _request_dialog(host, "New absence request", owner=owner)
    if not fields:
        return
    r = data.create(fields)
    messagebox.showinfo(
        "Absence Requests",
        f"Created request #{r.request_id}: {r.pupil_id} "
        f"{r.start_date}→{r.end_date} ({r.school_days} days)",
        parent=_owner(host, owner),
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None, owner=None) -> None:
    rid = _selected_id(tree, host, owner)
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
                                initial=initial, owner=owner)
    if not fields:
        return
    data.update(rid, fields)
    if on_done:
        on_done()


@_safe_view
def _decide(host, tree: ttk.Treeview, *,
              approve: bool, on_done=None, owner=None) -> None:
    rid = _selected_id(tree, host, owner)
    if rid is None:
        return
    label = "Approve" if approve else "Decline"
    picked = _decision_dialog(_owner(host, owner), label)
    if not picked:
        return
    decided_by, notes = picked
    data.decide(rid, approve=approve,
                  decided_by=decided_by,
                  decision_notes=notes or None)
    if on_done:
        on_done()


@_safe_view
def _cancel(host, tree: ttk.Treeview, *, on_done=None, owner=None) -> None:
    rid = _selected_id(tree, host, owner)
    if rid is None:
        return
    if not messagebox.askyesno(
            "Cancel request",
            f"Mark request #{rid} as Cancelled?",
            parent=_owner(host, owner)):
        return
    notes = simpledialog.askstring(
        "Cancel request", "Notes (optional):", parent=_owner(host, owner))
    data.cancel(rid, decision_notes=(notes or "").strip() or None)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None, owner=None) -> None:
    rid = _selected_id(tree, host, owner)
    if rid is None:
        return
    existing = data.get(rid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete request",
            f"Delete request #{rid} ({existing.pupil_id}, "
            f"{existing.start_date}→{existing.end_date})?",
            parent=_owner(host, owner)):
        return
    data.delete(rid)
    if on_done:
        on_done()
