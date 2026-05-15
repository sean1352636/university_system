"""Tk views for early-warning alerts."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.early_warning import (
    early_warning as data,
)
from education_system.primarysch_system.modules.domain.early_warning.early_warning import (
    ALERT_TYPES, SEVERITIES, ALERT_STATUSES, SOURCES,
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
                messagebox.showerror("Early Warning", str(e),
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


def _alert_dialog(host, title: str,
                   initial: dict[str, Any] | None = None
                   ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("520x620")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var   = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    type_var    = tk.StringVar(value=str(initial.get("alert_type")
                                           or "Academic"))
    sev_var     = tk.StringVar(value=str(initial.get("severity")
                                           or "Medium"))
    title_var   = tk.StringVar(value=str(initial.get("title") or ""))
    source_var  = tk.StringVar(value=str(initial.get("source")
                                           or "Teacher"))
    raisedby_var = tk.StringVar(value=str(initial.get("raised_by")
                                             or ""))
    raiseddate_var = tk.StringVar(value=str(initial.get("raised_date")
                                              or ""))
    status_var  = tk.StringVar(value=str(initial.get("status")
                                           or "Open"))
    assigned_var = tk.StringVar(value=str(initial.get("assigned_to")
                                             or ""))
    resolved_date_var = tk.StringVar(value=str(
        initial.get("resolved_date") or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",   ttk.Entry(frm, textvariable=pupil_var,
                                    width=14)),
        ("Type:",       ttk.Combobox(frm, textvariable=type_var,
                                      values=list(ALERT_TYPES),
                                      state="readonly", width=18)),
        ("Severity:",   ttk.Combobox(frm, textvariable=sev_var,
                                      values=list(SEVERITIES),
                                      state="readonly", width=10)),
        ("Title:",      ttk.Entry(frm, textvariable=title_var,
                                    width=40)),
        ("Source:",     ttk.Combobox(frm, textvariable=source_var,
                                      values=list(SOURCES),
                                      state="readonly", width=16)),
        ("Raised by:",  ttk.Entry(frm, textvariable=raisedby_var,
                                    width=24)),
        ("Raised date:", ttk.Entry(frm, textvariable=raiseddate_var,
                                     width=14)),
        ("Status:",     ttk.Combobox(frm, textvariable=status_var,
                                      values=list(ALERT_STATUSES),
                                      state="readonly", width=14)),
        ("Assigned to:", ttk.Entry(frm, textvariable=assigned_var,
                                     width=24)),
        ("Resolved date:", ttk.Entry(frm,
                                       textvariable=resolved_date_var,
                                       width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Details:").grid(row=len(rows), column=0,
                                          sticky="nw", pady=2)
    details_w = tk.Text(frm, width=44, height=4, wrap="word")
    details_w.insert("1.0", str(initial.get("details") or ""))
    details_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="Resolution:").grid(row=len(rows) + 1, column=0,
                                              sticky="nw", pady=2)
    res_w = tk.Text(frm, width=44, height=3, wrap="word")
    res_w.insert("1.0", str(initial.get("resolution") or ""))
    res_w.grid(row=len(rows) + 1, column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="Notes:").grid(row=len(rows) + 2, column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=44, height=2, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows) + 2, column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":      pupil_var.get().strip(),
            "alert_type":    type_var.get().strip(),
            "severity":      sev_var.get().strip(),
            "title":         title_var.get().strip(),
            "details":       details_w.get("1.0", "end").strip(),
            "source":        source_var.get().strip(),
            "raised_by":     raisedby_var.get().strip(),
            "raised_date":   raiseddate_var.get().strip(),
            "status":        status_var.get().strip(),
            "assigned_to":   assigned_var.get().strip(),
            "resolution":    res_w.get("1.0", "end").strip(),
            "resolved_date": resolved_date_var.get().strip(),
            "notes":         notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 3, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


_SEVERITY_COLOURS = {
    "Critical": "#ffcccc",
    "High":     "#ffe0b3",
    "Medium":   "#ffffb3",
    "Low":      "#e6f2ff",
}


@_safe_view
def open_early_warning(host) -> None:
    logger.debug("GUI: open_early_warning")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Early Warning",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    year_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=year_var,
                 values=["", *YEAR_GROUPS], state="readonly",
                 width=5).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Severity:").pack(side="left", padx=(0, 4))
    sev_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=sev_var,
                 values=["", *SEVERITIES], state="readonly",
                 width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *ALERT_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Type:").pack(side="left", padx=(0, 4))
    type_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=type_var,
                 values=["", *ALERT_TYPES], state="readonly",
                 width=16).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="Raise",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Resolve",
               command=lambda: _resolve(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Dismiss",
               command=lambda: _dismiss(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "raised", "pupil", "year", "type", "sev", "status",
            "source", "title")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("raised", "Raised", 90),
        ("pupil", "Pupil", 90), ("year", "Yr", 50),
        ("type", "Type", 140), ("sev", "Severity", 90),
        ("status", "Status", 100), ("source", "Source", 110),
        ("title", "Title", 280),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    for sev, colour in _SEVERITY_COLOURS.items():
        tree.tag_configure(f"sev_{sev}", background=colour)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_alerts(
                year_group=year_var.get().strip() or None,
                severity=sev_var.get().strip() or None,
                status=status_var.get().strip() or None,
                alert_type=type_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Early Warning", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("early_warning refresh failed")
            messagebox.showerror("Early Warning",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for a in rows:
            tree.insert("", "end", iid=str(a.alert_id), values=(
                a.alert_id, a.raised_date, a.pupil_id,
                a.pupil_year or "-", a.alert_type, a.severity,
                a.status, a.source, a.title,
            ), tags=(f"sev_{a.severity}",))
        try:
            s = data.cohort_summary(
                year_group=year_var.get().strip() or None)
            summary_var.set(
                f"Total: {s['total']}    Open: {s['open']}    "
                f"Open Critical: {s['open_critical']}    "
                f"Open High: {s['open_high']}")
        except Exception:
            summary_var.set(f"{len(rows)} alert(s) listed")
        host.status_var.set(f"Early Warning: {len(rows)} alert(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    sev_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    type_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Early Warning",
                            "Select an alert first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _alert_dialog(host, "Raise alert")
    if not fields:
        return
    a = data.create(fields)
    messagebox.showinfo(
        "Early Warning",
        f"Raised alert #{a.alert_id}: {a.title} ({a.severity})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    existing = data.get(aid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "alert_type", "severity", "title", "details",
        "source", "raised_by", "raised_date", "status",
        "assigned_to", "resolution", "resolved_date", "notes")}
    fields = _alert_dialog(host, f"Edit alert #{aid}", initial=initial)
    if not fields:
        return
    data.update(aid, fields)
    if on_done:
        on_done()


@_safe_view
def _resolve(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    res = simpledialog.askstring(
        "Resolve alert", "Resolution:", parent=host.root)
    if not res:
        return
    data.resolve(aid, resolution=res.strip())
    if on_done:
        on_done()


@_safe_view
def _dismiss(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    res = simpledialog.askstring(
        "Dismiss alert", "Reason for dismissal:", parent=host.root)
    if not res:
        return
    data.dismiss(aid, resolution=res.strip())
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    existing = data.get(aid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete alert",
            f"Delete alert #{aid} ({existing.title})?",
            parent=host.root):
        return
    data.delete(aid)
    if on_done:
        on_done()
