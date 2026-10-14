"""Tk views for safeguarding."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.safeguarding import (
    safeguarding as data,
)
from education_system.systems.secondary.domain.safeguarding.safeguarding import (
    CONCERN_CATEGORIES, SEVERITIES, CONCERN_STATUSES,
    REFERRAL_BODIES, ACTION_TYPES,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
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
                messagebox.showerror("Safeguarding", str(e),
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


def _concern_dialog(host, title: str,
                     initial: dict[str, Any] | None = None
                     ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("580x720")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var  = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    cat_var    = tk.StringVar(value=str(initial.get("category")
                                          or "Disclosure"))
    sev_var    = tk.StringVar(value=str(initial.get("severity")
                                          or "Medium"))
    incdate_var = tk.StringVar(value=str(initial.get("incident_date")
                                             or ""))
    inctime_var = tk.StringVar(value=str(initial.get("incident_time")
                                             or ""))
    loc_var    = tk.StringVar(value=str(initial.get("location") or ""))
    raisedby_var = tk.StringVar(value=str(initial.get("raised_by")
                                              or ""))
    raiseddate_var = tk.StringVar(value=str(initial.get("raised_date")
                                                or ""))
    dsl_var    = tk.StringVar(value=str(initial.get("dsl_reviewer")
                                          or ""))
    review_var = tk.StringVar(value=str(initial.get("review_date")
                                          or ""))
    status_var = tk.StringVar(value=str(initial.get("status") or "Open"))
    body_var   = tk.StringVar(value=str(initial.get("referral_body")
                                          or ""))
    refdate_var = tk.StringVar(value=str(initial.get("referral_date")
                                             or ""))
    refref_var = tk.StringVar(value=str(initial.get("referral_reference")
                                          or ""))
    closed_var = tk.StringVar(value=str(initial.get("closed_date")
                                          or ""))
    conf_var   = tk.BooleanVar(value=(
        True if initial.get("confidential") is None
        else bool(initial.get("confidential"))))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",     ttk.Entry(frm, textvariable=pupil_var,
                                       width=14)),
        ("Category:",     ttk.Combobox(frm, textvariable=cat_var,
                                         values=list(CONCERN_CATEGORIES),
                                         state="readonly", width=36)),
        ("Severity:",     ttk.Combobox(frm, textvariable=sev_var,
                                         values=list(SEVERITIES),
                                         state="readonly", width=10)),
        ("Incident date:", ttk.Entry(frm, textvariable=incdate_var,
                                       width=14)),
        ("Incident time:", ttk.Entry(frm, textvariable=inctime_var,
                                       width=8)),
        ("Location:",     ttk.Entry(frm, textvariable=loc_var,
                                       width=24)),
        ("Raised by:",    ttk.Entry(frm, textvariable=raisedby_var,
                                       width=24)),
        ("Raised date:",  ttk.Entry(frm, textvariable=raiseddate_var,
                                       width=14)),
        ("DSL reviewer:", ttk.Entry(frm, textvariable=dsl_var,
                                       width=24)),
        ("DSL review date:", ttk.Entry(frm, textvariable=review_var,
                                         width=14)),
        ("Status:",       ttk.Combobox(frm, textvariable=status_var,
                                         values=list(CONCERN_STATUSES),
                                         state="readonly", width=14)),
        ("Referral body:", ttk.Combobox(frm, textvariable=body_var,
                                          values=["", *REFERRAL_BODIES],
                                          state="readonly", width=24)),
        ("Referral date:", ttk.Entry(frm, textvariable=refdate_var,
                                       width=14)),
        ("Referral ref:", ttk.Entry(frm, textvariable=refref_var,
                                       width=18)),
        ("Closed date:",  ttk.Entry(frm, textvariable=closed_var,
                                       width=14)),
        ("Confidential:", ttk.Checkbutton(frm, variable=conf_var)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Description (required):", "description", 4),
                   ("Outcome:", "outcome", 2),
                   ("Notes:", "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for i, (label, key, lines) in enumerate(text_fields,
                                              start=len(rows)):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw",
                                         pady=2)
        t = tk.Text(frm, width=52, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.grid(row=i, column=1, sticky="ew", pady=2)
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":           pupil_var.get().strip(),
            "category":           cat_var.get().strip(),
            "severity":           sev_var.get().strip(),
            "incident_date":      incdate_var.get().strip(),
            "incident_time":      inctime_var.get().strip(),
            "location":           loc_var.get().strip(),
            "raised_by":          raisedby_var.get().strip(),
            "raised_date":        raiseddate_var.get().strip(),
            "dsl_reviewer":       dsl_var.get().strip(),
            "review_date":        review_var.get().strip(),
            "status":             status_var.get().strip(),
            "referral_body":      body_var.get().strip(),
            "referral_date":      refdate_var.get().strip(),
            "referral_reference": refref_var.get().strip(),
            "closed_date":        closed_var.get().strip(),
            "confidential":       bool(conf_var.get()),
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


def _action_dialog(host, concern_id: int,
                    initial: dict[str, Any] | None = None
                    ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Action — concern #{concern_id}")
    dlg.transient(host.root)
    dlg.geometry("520x500")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    date_var = tk.StringVar(value=str(initial.get("action_date") or ""))
    type_var = tk.StringVar(value=str(initial.get("action_type")
                                         or "DSL meeting"))
    by_var   = tk.StringVar(value=str(initial.get("actioned_by") or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Date:", ttk.Entry(frm, textvariable=date_var, width=14)),
        ("Type:", ttk.Combobox(frm, textvariable=type_var,
                                 values=list(ACTION_TYPES),
                                 state="readonly", width=24)),
        ("Actioned by:", ttk.Entry(frm, textvariable=by_var,
                                      width=28)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=14).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    text_fields = [("Summary (required):", "summary", 4),
                   ("Outcome:", "outcome", 3),
                   ("Follow-up:", "follow_up", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for label, key, lines in text_fields:
        ttk.Label(frm, text=label).pack(anchor="w", pady=(8, 0))
        t = tk.Text(frm, width=54, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.pack(fill="x")
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "concern_id":   concern_id,
            "action_date":  date_var.get().strip(),
            "action_type":  type_var.get().strip(),
            "actioned_by":  by_var.get().strip(),
        }
        for k, w in text_widgets.items():
            result[k] = w.get("1.0", "end").strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
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
def open_safeguarding(host) -> None:
    logger.debug("GUI: open_safeguarding")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Safeguarding",
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
                 values=["", *CONCERN_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Category:").pack(side="left", padx=(0, 4))
    cat_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=cat_var,
                 values=["", *CONCERN_CATEGORIES],
                 state="readonly", width=22).pack(side="left",
                                                  padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="Raise",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Actions",
               command=lambda: _open_actions(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Status",
               command=lambda: _status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "raised", "pupil", "year", "category", "sev",
            "status", "dsl", "conf")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("raised", "Raised", 90),
        ("pupil", "Pupil", 90), ("year", "Yr", 50),
        ("category", "Category", 200), ("sev", "Severity", 90),
        ("status", "Status", 100), ("dsl", "DSL", 140),
        ("conf", "Conf", 50),
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
            rows = data.list_concerns(
                year_group=year_var.get().strip() or None,
                severity=sev_var.get().strip() or None,
                status=status_var.get().strip() or None,
                category=cat_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Safeguarding", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("safeguarding refresh failed")
            messagebox.showerror("Safeguarding",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for c in rows:
            tree.insert("", "end", iid=str(c.concern_id), values=(
                c.concern_id, c.raised_date, c.pupil_id,
                c.pupil_year or "-", c.category, c.severity,
                c.status, c.dsl_reviewer or "-",
                "Yes" if c.confidential else "No",
            ), tags=(f"sev_{c.severity}",))
        try:
            s = data.cohort_summary()
            summary_var.set(
                f"Concerns: {s['total']}    Open: {s['open']}    "
                f"Open Critical: {s['open_critical']}")
        except Exception:
            summary_var.set(f"{len(rows)} concern(s)")
        host.status_var.set(f"Safeguarding: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _open_actions(host, tree))
    year_var.trace_add("write", lambda *_: _refresh())
    sev_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    cat_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Safeguarding",
                            "Select a concern first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _concern_dialog(host, "Raise safeguarding concern")
    if not fields:
        return
    c = data.raise_concern(fields)
    messagebox.showinfo(
        "Safeguarding",
        f"Raised concern #{c.concern_id}: {c.category} ({c.severity})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "category", "severity",
        "incident_date", "incident_time", "location",
        "description", "raised_by", "raised_date",
        "dsl_reviewer", "review_date", "status",
        "referral_body", "referral_date", "referral_reference",
        "outcome", "closed_date", "confidential", "notes")}
    fields = _concern_dialog(host, f"Edit concern #{cid}",
                              initial=initial)
    if not fields:
        return
    data.update(cid, fields)
    if on_done:
        on_done()


@_safe_view
def _status(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    c = data.get(cid)
    if c is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — #{cid}")
    dlg.transient(host.root)
    dlg.geometry("380x220")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{c.pupil_id} — {c.category}").pack(
        anchor="w")
    ttk.Label(frm, text=f"Current: {c.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=c.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(CONCERN_STATUSES),
                 state="readonly").pack(fill="x")
    outcome_var = tk.StringVar(value=c.outcome or "")
    ttk.Label(frm,
              text="Outcome (required for Closed):").pack(
        anchor="w", pady=(8, 0))
    ttk.Entry(frm, textvariable=outcome_var).pack(fill="x")
    body_var = tk.StringVar(value=c.referral_body or "")
    ttk.Label(frm,
              text="Referral body (required for Referred):").pack(
        anchor="w", pady=(8, 0))
    ttk.Combobox(frm, textvariable=body_var,
                 values=["", *REFERRAL_BODIES],
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(cid, new_var.get(),
                             outcome=outcome_var.get().strip() or None,
                             referral_body=body_var.get().strip() or None)
        except ValidationError as ex:
            messagebox.showerror("Safeguarding", str(ex), parent=dlg)
            return
        dlg.destroy()
        if on_done:
            on_done()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    existing = data.get(cid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete concern",
            f"Delete concern #{cid} ({existing.pupil_id}, "
            f"{existing.category}) and ALL its actions?",
            parent=host.root):
        return
    data.delete(cid)
    if on_done:
        on_done()


@_safe_view
def _open_actions(host, tree: ttk.Treeview) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    rec = data.get(cid)
    if rec is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Actions — concern #{cid}")
    dlg.transient(host.root)
    dlg.geometry("820x520")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)
    header_var = tk.StringVar()
    ttk.Label(frm, textvariable=header_var,
              font=("", 10, "bold")).pack(anchor="w")
    ttk.Label(frm,
              text=("(Confidential — handle in line with DSL policy)"
                    if rec.confidential else ""),
              foreground="#aa0000").pack(anchor="w")

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 4))
    ttk.Button(bar, text="Add action",
               command=lambda: _do_add()).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete selected",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    t = ttk.Treeview(frm,
                       columns=("id", "date", "type", "by", "summary"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100),
        ("type", "Type", 160), ("by", "Actioned by", 160),
        ("summary", "Summary", 360),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in t.get_children():
            t.delete(i)
        try:
            s = data.concern_summary(cid)
        except Exception as e:
            logger.exception("concern_summary failed")
            messagebox.showerror("Safeguarding",
                                 f"Could not load:\n\n{e}",
                                 parent=dlg)
            return
        c_obj = s["concern"]
        header_var.set(
            f"#{c_obj.concern_id} {c_obj.pupil_id} ({c_obj.category}, "
            f"{c_obj.severity}, {c_obj.status})    "
            f"Actions: {s['action_count']}")
        for a in s["actions"]:
            t.insert("", "end", iid=str(a.action_id), values=(
                a.action_id, a.action_date, a.action_type,
                a.actioned_by or "-",
                a.summary[:120],
            ))

    def _do_add() -> None:
        fields = _action_dialog(host, cid)
        if not fields:
            return
        try:
            data.add_action(fields)
        except ValidationError as e:
            messagebox.showerror("Safeguarding", str(e), parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("Safeguarding",
                                "Select an action first.",
                                parent=dlg)
            return
        try:
            aid = int(sel)
        except ValueError:
            return
        if not messagebox.askyesno(
                "Delete action",
                f"Delete action #{aid}?", parent=dlg):
            return
        data.delete_action(aid)
        _refresh()

    _refresh()
