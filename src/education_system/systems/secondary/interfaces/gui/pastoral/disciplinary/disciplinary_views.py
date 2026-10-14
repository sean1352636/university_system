"""Tk views for disciplinary cases."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.pastoral.disciplinary import (
    disciplinary as data,
)
from education_system.systems.secondary.domain.pastoral.disciplinary.disciplinary import (
    CASE_TYPES, CASE_STATUSES, SEVERITIES, EVENT_TYPES,
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
                messagebox.showerror("Disciplinary", str(e),
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


def _case_dialog(host, title: str,
                  initial: dict[str, Any] | None = None
                  ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("560x620")
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
    type_var   = tk.StringVar(value=str(initial.get("case_type")
                                          or "Fixed-term suspension"))
    sev_var    = tk.StringVar(value=str(initial.get("severity")
                                          or "High"))
    inc_var    = tk.StringVar(value=str(initial.get("incident_date")
                                          or ""))
    start_var  = tk.StringVar(value=str(initial.get("start_date") or ""))
    end_var    = tk.StringVar(value=str(initial.get("end_date") or ""))
    days_var   = tk.StringVar(value=str(initial.get("days")
                                          if initial.get("days") is not None
                                          else ""))
    decision_var = tk.StringVar(value=str(initial.get("decision_maker")
                                             or ""))
    status_var = tk.StringVar(value=str(initial.get("status") or "Open"))
    appeal_var = tk.StringVar(value=str(initial.get("appeal_decision")
                                          or ""))
    return_var = tk.StringVar(value=str(initial.get("return_date")
                                          or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",    ttk.Entry(frm, textvariable=pupil_var,
                                      width=14)),
        ("Type:",        ttk.Combobox(frm, textvariable=type_var,
                                        values=list(CASE_TYPES),
                                        state="readonly", width=22)),
        ("Severity:",    ttk.Combobox(frm, textvariable=sev_var,
                                        values=list(SEVERITIES),
                                        state="readonly", width=10)),
        ("Incident date:", ttk.Entry(frm, textvariable=inc_var,
                                       width=14)),
        ("Start date:",  ttk.Entry(frm, textvariable=start_var,
                                      width=14)),
        ("End date:",    ttk.Entry(frm, textvariable=end_var,
                                      width=14)),
        ("Days (auto):", ttk.Entry(frm, textvariable=days_var,
                                      width=8)),
        ("Decision maker:", ttk.Entry(frm, textvariable=decision_var,
                                        width=28)),
        ("Status:",      ttk.Combobox(frm, textvariable=status_var,
                                        values=list(CASE_STATUSES),
                                        state="readonly", width=14)),
        ("Appeal decision:", ttk.Entry(frm, textvariable=appeal_var,
                                         width=30)),
        ("Return date:", ttk.Entry(frm, textvariable=return_var,
                                      width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Reason (required):").grid(
        row=len(rows), column=0, sticky="nw", pady=2)
    reason_w = tk.Text(frm, width=48, height=4, wrap="word")
    reason_w.insert("1.0", str(initial.get("reason") or ""))
    reason_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="Notes:").grid(row=len(rows) + 1, column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=48, height=3, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows) + 1, column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":        pupil_var.get().strip(),
            "case_type":       type_var.get().strip(),
            "severity":        sev_var.get().strip(),
            "incident_date":   inc_var.get().strip(),
            "start_date":      start_var.get().strip(),
            "end_date":        end_var.get().strip(),
            "days":            days_var.get().strip(),
            "decision_maker":  decision_var.get().strip(),
            "status":          status_var.get().strip(),
            "appeal_decision": appeal_var.get().strip(),
            "return_date":     return_var.get().strip(),
            "reason":          reason_w.get("1.0", "end").strip(),
            "notes":           notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 2, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def _event_dialog(host, case_id: int,
                   initial: dict[str, Any] | None = None
                   ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Event — case #{case_id}")
    dlg.transient(host.root)
    dlg.geometry("520x520")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    date_var = tk.StringVar(value=str(initial.get("event_date") or ""))
    type_var = tk.StringVar(value=str(initial.get("event_type")
                                         or "Meeting"))
    part_var = tk.StringVar(value=str(initial.get("participants")
                                         or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Date:", ttk.Entry(frm, textvariable=date_var, width=14)),
        ("Type:", ttk.Combobox(frm, textvariable=type_var,
                                 values=list(EVENT_TYPES),
                                 state="readonly", width=22)),
        ("Participants:", ttk.Entry(frm, textvariable=part_var,
                                       width=40)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=14).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    text_fields = [("Summary (required):", "summary", 4),
                   ("Outcome:", "outcome", 3),
                   ("Follow-up:", "follow_up", 2),
                   ("Notes:", "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for label, key, lines in text_fields:
        ttk.Label(frm, text=label).pack(anchor="w", pady=(8, 0))
        t = tk.Text(frm, width=52, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.pack(fill="x")
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "case_id":      case_id,
            "event_date":   date_var.get().strip(),
            "event_type":   type_var.get().strip(),
            "participants": part_var.get().strip(),
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
def open_disciplinary(host) -> None:
    logger.debug("GUI: open_disciplinary")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Disciplinary",
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
    ttk.Label(bar, text="Type:").pack(side="left", padx=(0, 4))
    type_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=type_var,
                 values=["", *CASE_TYPES], state="readonly",
                 width=20).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Severity:").pack(side="left", padx=(0, 4))
    sev_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=sev_var,
                 values=["", *SEVERITIES], state="readonly",
                 width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *CASE_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Events",
               command=lambda: _open_events(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Status",
               command=lambda: _status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "start", "pupil", "year", "type", "sev", "days",
            "status", "reason")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("start", "Start", 90),
        ("pupil", "Pupil", 90), ("year", "Yr", 50),
        ("type", "Type", 180), ("sev", "Severity", 90),
        ("days", "Days", 60), ("status", "Status", 100),
        ("reason", "Reason", 280),
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
            rows = data.list_cases(
                year_group=year_var.get().strip() or None,
                case_type=type_var.get().strip() or None,
                severity=sev_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Disciplinary", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("disciplinary refresh failed")
            messagebox.showerror("Disciplinary",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for c in rows:
            tree.insert("", "end", iid=str(c.case_id), values=(
                c.case_id, c.start_date, c.pupil_id,
                c.pupil_year or "-", c.case_type, c.severity,
                c.days if c.days is not None else "-",
                c.status, c.reason,
            ), tags=(f"sev_{c.severity}",))
        try:
            s = data.cohort_summary()
            summary_var.set(
                f"Cases: {s['total']}    Open: {s['open']}    "
                f"Total days: {s['total_days']}")
        except Exception:
            summary_var.set(f"{len(rows)} case(s)")
        host.status_var.set(f"Disciplinary: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _open_events(host, tree))
    year_var.trace_add("write", lambda *_: _refresh())
    type_var.trace_add("write", lambda *_: _refresh())
    sev_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Disciplinary",
                            "Select a case first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _case_dialog(host, "New disciplinary case")
    if not fields:
        return
    c = data.create_case(fields)
    messagebox.showinfo(
        "Disciplinary",
        f"Created case #{c.case_id}: {c.pupil_id} — {c.case_type}",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    existing = data.get_case(cid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "case_type", "severity", "incident_date",
        "start_date", "end_date", "days", "reason",
        "decision_maker", "status", "appeal_decision",
        "return_date", "notes")}
    fields = _case_dialog(host, f"Edit case #{cid}", initial=initial)
    if not fields:
        return
    data.update_case(cid, fields)
    if on_done:
        on_done()


@_safe_view
def _status(host, tree: ttk.Treeview, *, on_done=None) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    c = data.get_case(cid)
    if c is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — #{cid}")
    dlg.transient(host.root)
    dlg.geometry("360x200")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{c.pupil_id} — {c.case_type}").pack(
        anchor="w")
    ttk.Label(frm, text=f"Current: {c.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=c.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(CASE_STATUSES),
                 state="readonly").pack(fill="x")
    ttk.Label(frm, text="Appeal decision (if Appealed/Overturned):"
              ).pack(anchor="w", pady=(8, 0))
    appeal_var = tk.StringVar(value=c.appeal_decision or "")
    ttk.Entry(frm, textvariable=appeal_var).pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(cid, new_var.get(),
                             appeal_decision=appeal_var.get().strip()
                             or None)
        except ValidationError as ex:
            messagebox.showerror("Disciplinary", str(ex), parent=dlg)
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
    existing = data.get_case(cid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete case",
            f"Delete case #{cid} ({existing.pupil_id}, "
            f"{existing.case_type}) and ALL its events?",
            parent=host.root):
        return
    data.delete_case(cid)
    if on_done:
        on_done()


@_safe_view
def _open_events(host, tree: ttk.Treeview) -> None:
    cid = _selected_id(tree, host)
    if cid is None:
        return
    rec = data.get_case(cid)
    if rec is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Events — case #{cid}")
    dlg.transient(host.root)
    dlg.geometry("780x520")
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

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 4))
    ttk.Button(bar, text="Add event",
               command=lambda: _do_add()).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete selected",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    t = ttk.Treeview(frm,
                       columns=("id", "date", "type", "participants",
                                 "summary"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100),
        ("type", "Type", 160), ("participants", "Participants", 180),
        ("summary", "Summary", 320),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in t.get_children():
            t.delete(i)
        try:
            s = data.case_summary(cid)
        except Exception as e:
            logger.exception("case_summary failed")
            messagebox.showerror("Disciplinary",
                                 f"Could not load:\n\n{e}",
                                 parent=dlg)
            return
        c = s["case"]
        header_var.set(
            f"#{c.case_id}  {c.pupil_id}    {c.case_type}    "
            f"{c.severity}    {c.status}    "
            f"Events: {s['event_count']}")
        for e in s["events"]:
            t.insert("", "end", iid=str(e.event_id), values=(
                e.event_id, e.event_date, e.event_type,
                e.participants or "-",
                (e.summary or "-")[:100],
            ))

    def _do_add() -> None:
        fields = _event_dialog(host, cid)
        if not fields:
            return
        try:
            data.add_event(fields)
        except ValidationError as e:
            messagebox.showerror("Disciplinary", str(e), parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("Disciplinary",
                                "Select an event first.",
                                parent=dlg)
            return
        try:
            eid = int(sel)
        except ValueError:
            return
        if not messagebox.askyesno(
                "Delete event",
                f"Delete event #{eid}?", parent=dlg):
            return
        data.delete_event(eid)
        _refresh()

    _refresh()
