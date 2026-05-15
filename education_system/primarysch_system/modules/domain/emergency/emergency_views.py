"""Tk views for emergency events and drills."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.emergency import (
    emergency as data,
)
from education_system.primarysch_system.modules.domain.emergency.emergency import (
    EVENT_KINDS, EMERGENCY_TYPES, OUTCOMES, STATUSES,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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
                messagebox.showerror("Emergency", str(e),
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


def _event_dialog(host, title: str,
                    initial: dict[str, Any] | None = None
                    ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("580x780")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    kind_var    = tk.StringVar(value=str(initial.get("kind") or "Drill"))
    type_var    = tk.StringVar(value=str(initial.get("event_type") or "Fire"))
    date_var    = tk.StringVar(value=str(initial.get("event_date") or ""))
    start_var   = tk.StringVar(value=str(initial.get("start_time") or ""))
    end_var     = tk.StringVar(value=str(initial.get("end_time") or ""))
    dur_var     = tk.StringVar(value=str(initial.get("duration_min") or ""))
    loc_var     = tk.StringVar(value=str(initial.get("location") or ""))
    trigger_var = tk.StringVar(value=str(initial.get("trigger") or ""))
    reported_var = tk.StringVar(value=str(initial.get("reported_by") or ""))
    cmdr_var    = tk.StringVar(value=str(initial.get("incident_commander")
                                            or ""))
    pe_var      = tk.StringVar(value=str(initial.get("pupils_evacuated")
                                            or ""))
    se_var      = tk.StringVar(value=str(initial.get("staff_evacuated")
                                            or ""))
    miss_var    = tk.StringVar(value=str(initial.get("missing_count") or 0))
    inj_var     = tk.StringVar(value=str(initial.get("injuries_count") or 0))
    es_var      = tk.BooleanVar(value=bool(initial.get("emergency_services")))
    svc_var     = tk.StringVar(value=str(initial.get("services_attended")
                                            or ""))
    outcome_var = tk.StringVar(value=str(initial.get("outcome")
                                            or "Successful"))
    status_var  = tk.StringVar(value=str(initial.get("status") or "Logged"))

    rows: list[tuple[str, tk.Widget]] = [
        ("Kind:",        ttk.Combobox(frm, textvariable=kind_var,
                                         values=list(EVENT_KINDS),
                                         state="readonly", width=14)),
        ("Type:",        ttk.Combobox(frm, textvariable=type_var,
                                         values=list(EMERGENCY_TYPES),
                                         state="readonly", width=18)),
        ("Date:",        ttk.Entry(frm, textvariable=date_var, width=14)),
        ("Start time:",  ttk.Entry(frm, textvariable=start_var, width=8)),
        ("End time:",    ttk.Entry(frm, textvariable=end_var, width=8)),
        ("Duration (min):", ttk.Entry(frm, textvariable=dur_var, width=6)),
        ("Location:",    ttk.Entry(frm, textvariable=loc_var, width=28)),
        ("Trigger:",     ttk.Entry(frm, textvariable=trigger_var, width=28)),
        ("Reported by:", ttk.Entry(frm, textvariable=reported_var, width=22)),
        ("Commander:",   ttk.Entry(frm, textvariable=cmdr_var, width=22)),
        ("Pupils evac:", ttk.Entry(frm, textvariable=pe_var, width=6)),
        ("Staff evac:",  ttk.Entry(frm, textvariable=se_var, width=6)),
        ("Missing:",     ttk.Entry(frm, textvariable=miss_var, width=6)),
        ("Injuries:",    ttk.Entry(frm, textvariable=inj_var, width=6)),
        ("Services called:", ttk.Checkbutton(frm, variable=es_var)),
        ("Services attended:", ttk.Entry(frm, textvariable=svc_var,
                                            width=22)),
        ("Outcome:",     ttk.Combobox(frm, textvariable=outcome_var,
                                         values=list(OUTCOMES),
                                         state="readonly", width=18)),
        ("Status:",      ttk.Combobox(frm, textvariable=status_var,
                                         values=list(STATUSES),
                                         state="readonly", width=18)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                          pady=2)
        widget.grid(row=i, column=1, sticky="w", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Lessons learned:", "lessons_learned", 2),
                    ("Follow-up actions:", "follow_up_actions", 2),
                    ("Notes:", "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for i, (label, key, lines) in enumerate(text_fields,
                                              start=len(rows)):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw",
                                          pady=2)
        t = tk.Text(frm, width=48, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.grid(row=i, column=1, sticky="ew", pady=2)
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "kind":               kind_var.get().strip(),
            "event_type":         type_var.get().strip(),
            "event_date":         date_var.get().strip(),
            "start_time":         start_var.get().strip(),
            "end_time":           end_var.get().strip(),
            "duration_min":       dur_var.get().strip(),
            "location":           loc_var.get().strip(),
            "trigger":            trigger_var.get().strip(),
            "reported_by":        reported_var.get().strip(),
            "incident_commander": cmdr_var.get().strip(),
            "pupils_evacuated":   pe_var.get().strip(),
            "staff_evacuated":    se_var.get().strip(),
            "missing_count":      miss_var.get().strip(),
            "injuries_count":     inj_var.get().strip(),
            "emergency_services": bool(es_var.get()),
            "services_attended":  svc_var.get().strip(),
            "outcome":            outcome_var.get().strip(),
            "status":             status_var.get().strip(),
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
def open_emergency(host) -> None:
    logger.debug("GUI: open_emergency")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Emergency & Drills",
                font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var,
                foreground="#666").pack(anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Kind:").pack(side="left", padx=(0, 4))
    kind_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=kind_var,
                   values=["", *EVENT_KINDS], state="readonly",
                   width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Type:").pack(side="left", padx=(0, 4))
    type_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=type_var,
                   values=["", *EMERGENCY_TYPES], state="readonly",
                   width=16).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                   values=["", *STATUSES], state="readonly",
                   width=16).pack(side="left", padx=(0, 6))
    out_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Outstanding only",
                      variable=out_var).pack(side="left", padx=4)
    ttk.Button(bar, text="Apply",
                 command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
                 command=lambda: _new(host, on_done=_refresh)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
                 command=lambda: _edit(host, tree, on_done=_refresh)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Close",
                 command=lambda: _close(host, tree, on_done=_refresh)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
                 command=lambda: _delete(host, tree, on_done=_refresh)
                 ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
                 command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "date", "kind", "type", "dur", "pups",
             "miss", "inj", "outcome", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 90),
        ("kind", "Kind", 80), ("type", "Type", 140),
        ("dur", "Min", 50), ("pups", "Pups", 50),
        ("miss", "Miss", 50), ("inj", "Inj", 50),
        ("outcome", "Outcome", 160), ("status", "Status", 160),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.tag_configure("real",        background="#fde7e7")
    tree.tag_configure("outstanding", background="#fff7d6")
    tree.tag_configure("closed",      foreground="#888")

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_events(
                kind=kind_var.get().strip() or None,
                event_type=type_var.get().strip() or None,
                status=status_var.get().strip() or None,
                outstanding_only=out_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Emergency", str(e),
                                  parent=host.root)
            return
        except Exception as e:
            logger.exception("emergency refresh failed")
            messagebox.showerror("Emergency",
                                  f"Could not load:\n\n{e}",
                                  parent=host.root)
            return
        for r in rows:
            tags = []
            if r.kind == "Real":
                tags.append("real")
            if r.status in ("Under review", "Actions outstanding"):
                tags.append("outstanding")
            if r.status == "Closed":
                tags.append("closed")
            tree.insert("", "end", iid=str(r.event_id), values=(
                r.event_id, r.event_date, r.kind, r.event_type,
                r.duration_min if r.duration_min is not None else "-",
                r.pupils_evacuated if r.pupils_evacuated is not None
                    else "-",
                r.missing_count, r.injuries_count,
                r.outcome, r.status,
            ), tags=tuple(tags))
        try:
            s = data.cohort_summary()
            avg = s["avg_duration_min"]
            summary_var.set(
                f"Events: {s['total']}    "
                f"Drills: {s['drills']}    Real: {s['real']}    "
                f"Outstanding: {s['outstanding']}    "
                f"Avg dur: "
                f"{f'{avg:.1f}' if avg is not None else '-'} min")
        except Exception:
            summary_var.set(f"{len(rows)} event(s)")
        host.status_var.set(
            f"Emergency: {len(rows)} record(s)")

    tree.bind("<Double-1>",
                lambda _e: _edit(host, tree, on_done=_refresh))
    kind_var.trace_add("write", lambda *_: _refresh())
    type_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    out_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Emergency",
                             "Select an event first.",
                             parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _event_dialog(host, "New emergency / drill")
    if not fields:
        return
    r = data.create(fields)
    messagebox.showinfo(
        "Emergency",
        f"Created event #{r.event_id}: {r.kind} {r.event_type} "
        f"on {r.event_date} ({r.outcome})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    eid = _selected_id(tree, host)
    if eid is None:
        return
    existing = data.get(eid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "kind", "event_type", "event_date", "start_time",
        "end_time", "duration_min", "location", "trigger",
        "reported_by", "incident_commander", "pupils_evacuated",
        "staff_evacuated", "missing_count", "injuries_count",
        "emergency_services", "services_attended",
        "outcome", "status", "lessons_learned",
        "follow_up_actions", "notes")}
    fields = _event_dialog(host, f"Edit event #{eid}",
                              initial=initial)
    if not fields:
        return
    data.update(eid, fields)
    if on_done:
        on_done()


@_safe_view
def _close(host, tree: ttk.Treeview, *, on_done=None) -> None:
    eid = _selected_id(tree, host)
    if eid is None:
        return
    data.close_event(eid)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    eid = _selected_id(tree, host)
    if eid is None:
        return
    existing = data.get(eid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete event",
            f"Delete event #{eid} "
            f"({existing.kind} {existing.event_type}, "
            f"{existing.event_date})?",
            parent=host.root):
        return
    data.delete(eid)
    if on_done:
        on_done()
