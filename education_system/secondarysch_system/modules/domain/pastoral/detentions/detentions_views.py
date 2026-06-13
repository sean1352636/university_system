"""Tk views for detentions."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.pastoral.detentions import (
    detentions as data,
)
from education_system.secondarysch_system.modules.domain.pastoral.detentions.detentions import (
    DETENTION_TYPES, DETENTION_STATUSES,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
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
                messagebox.showerror("Detentions", str(e),
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


def _detention_dialog(host, title: str,
                       initial: dict[str, Any] | None = None
                       ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("520x540")
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
    date_var   = tk.StringVar(value=str(initial.get("detention_date")
                                          or ""))
    time_var   = tk.StringVar(value=str(initial.get("start_time")
                                          or ""))
    dur_var    = tk.StringVar(value=str(initial.get("duration_min")
                                          or 30))
    type_var   = tk.StringVar(value=str(initial.get("detention_type")
                                          or "After school"))
    loc_var    = tk.StringVar(value=str(initial.get("location") or ""))
    sup_var    = tk.StringVar(value=str(initial.get("supervisor")
                                          or ""))
    setby_var  = tk.StringVar(value=str(initial.get("set_by") or ""))
    status_var = tk.StringVar(value=str(initial.get("status")
                                          or "Scheduled"))
    inc_var    = tk.StringVar(value=str(initial.get("related_incident_id")
                                          or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",    ttk.Entry(frm, textvariable=pupil_var,
                                      width=14)),
        ("Date:",        ttk.Entry(frm, textvariable=date_var,
                                      width=14)),
        ("Start time:",  ttk.Entry(frm, textvariable=time_var,
                                      width=10)),
        ("Duration (min):", ttk.Spinbox(frm, from_=5, to=480,
                                          textvariable=dur_var,
                                          width=6)),
        ("Type:",        ttk.Combobox(frm, textvariable=type_var,
                                        values=list(DETENTION_TYPES),
                                        state="readonly", width=18)),
        ("Location:",    ttk.Entry(frm, textvariable=loc_var,
                                      width=24)),
        ("Supervisor:",  ttk.Entry(frm, textvariable=sup_var,
                                      width=24)),
        ("Set by:",      ttk.Entry(frm, textvariable=setby_var,
                                      width=24)),
        ("Status:",      ttk.Combobox(frm, textvariable=status_var,
                                        values=list(DETENTION_STATUSES),
                                        state="readonly", width=14)),
        ("Incident ID:", ttk.Entry(frm, textvariable=inc_var,
                                      width=10)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Reason (required):").grid(
        row=len(rows), column=0, sticky="nw", pady=2)
    reason_w = tk.Text(frm, width=44, height=3, wrap="word")
    reason_w.insert("1.0", str(initial.get("reason") or ""))
    reason_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="Notes:").grid(row=len(rows) + 1, column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=44, height=2, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows) + 1, column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":            pupil_var.get().strip(),
            "detention_date":      date_var.get().strip(),
            "start_time":          time_var.get().strip(),
            "duration_min":        dur_var.get().strip(),
            "detention_type":      type_var.get().strip(),
            "location":            loc_var.get().strip(),
            "supervisor":          sup_var.get().strip(),
            "set_by":              setby_var.get().strip(),
            "status":              status_var.get().strip(),
            "related_incident_id": inc_var.get().strip(),
            "reason":              reason_w.get("1.0", "end").strip(),
            "notes":               notes_w.get("1.0", "end").strip(),
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


@_safe_view
def open_detentions(host) -> None:
    logger.debug("GUI: open_detentions")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Detentions",
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
    ttk.Label(bar, text="Pupil:").pack(side="left", padx=(0, 4))
    pupil_var = tk.StringVar(value="")
    ttk.Entry(bar, textvariable=pupil_var, width=12).pack(
        side="left", padx=(0, 6))
    ttk.Label(bar, text="Type:").pack(side="left", padx=(0, 4))
    type_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=type_var,
                 values=["", *DETENTION_TYPES], state="readonly",
                 width=14).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *DETENTION_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="Schedule",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Status",
               command=lambda: _status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Reschedule",
               command=lambda: _reschedule(host, tree,
                                             on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Pupil summary",
               command=lambda: _pupil_summary(host)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "date", "time", "pupil", "year", "type", "dur",
            "supervisor", "status", "reason")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100),
        ("time", "Time", 60), ("pupil", "Pupil", 90),
        ("year", "Yr", 50), ("type", "Type", 110),
        ("dur", "Min", 50), ("supervisor", "Supervisor", 160),
        ("status", "Status", 100), ("reason", "Reason", 280),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.tag_configure("missed", background="#fde7e7")
    tree.tag_configure("attended", background="#e6f7ec")

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_detentions(
                year_group=year_var.get().strip() or None,
                pupil_id=pupil_var.get().strip() or None,
                detention_type=type_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Detentions", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("detentions refresh failed")
            messagebox.showerror("Detentions",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for d in rows:
            tags = ()
            if d.status == "Missed":
                tags = ("missed",)
            elif d.status == "Attended":
                tags = ("attended",)
            tree.insert("", "end", iid=str(d.detention_id), values=(
                d.detention_id, d.detention_date,
                d.start_time or "-", d.pupil_id,
                d.pupil_year or "-", d.detention_type,
                d.duration_min, d.supervisor or "-",
                d.status, d.reason,
            ), tags=tags)
        try:
            s = data.cohort_summary(
                year_group=year_var.get().strip() or None)
            summary_var.set(
                f"Total: {s['total']}    Attended: {s['attended']}    "
                f"Missed: {s['missed']}    "
                f"Minutes served: {s['minutes_served']}")
        except Exception:
            summary_var.set(f"{len(rows)} detention(s)")
        host.status_var.set(f"Detentions: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    type_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Detentions",
                            "Select a detention first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _detention_dialog(host, "Schedule detention")
    if not fields:
        return
    d = data.create(fields)
    messagebox.showinfo(
        "Detentions",
        f"Scheduled #{d.detention_id} for {d.pupil_id} on "
        f"{d.detention_date}",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    did = _selected_id(tree, host)
    if did is None:
        return
    existing = data.get(did)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "detention_date", "start_time", "duration_min",
        "detention_type", "location", "supervisor", "reason",
        "set_by", "status", "related_incident_id", "notes")}
    fields = _detention_dialog(host, f"Edit detention #{did}",
                                  initial=initial)
    if not fields:
        return
    data.update(did, fields)
    if on_done:
        on_done()


@_safe_view
def _status(host, tree: ttk.Treeview, *, on_done=None) -> None:
    did = _selected_id(tree, host)
    if did is None:
        return
    d = data.get(did)
    if d is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — #{did}")
    dlg.transient(host.root)
    dlg.geometry("340x140")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{d.pupil_id} on {d.detention_date}").pack(
        anchor="w")
    ttk.Label(frm, text=f"Current: {d.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=d.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(DETENTION_STATUSES),
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(did, new_var.get())
        except ValidationError as ex:
            messagebox.showerror("Detentions", str(ex), parent=dlg)
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
def _reschedule(host, tree: ttk.Treeview, *, on_done=None) -> None:
    did = _selected_id(tree, host)
    if did is None:
        return
    existing = data.get(did)
    if existing is None:
        return
    new_date = simpledialog.askstring(
        "Reschedule",
        f"New date for {existing.pupil_id}'s detention (YYYY-MM-DD):",
        parent=host.root)
    if not new_date:
        return
    new = data.reschedule(did, new_date=new_date.strip())
    messagebox.showinfo(
        "Detentions",
        f"Rescheduled #{did} → new detention #{new.detention_id} "
        f"on {new.detention_date}",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    did = _selected_id(tree, host)
    if did is None:
        return
    existing = data.get(did)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete detention",
            f"Delete detention #{did} ({existing.pupil_id}, "
            f"{existing.detention_date})?",
            parent=host.root):
        return
    data.delete(did)
    if on_done:
        on_done()


@_safe_view
def _pupil_summary(host) -> None:
    pid = simpledialog.askstring("Pupil summary", "Pupil ID:",
                                  parent=host.root)
    if not pid:
        return
    s = data.pupil_summary(pid.strip())
    lines = [
        f"Pupil: {pid}",
        f"Total: {s['total']}",
        f"Attended: {s['attended']}    "
        f"Missed: {s['missed']}    "
        f"Excused: {s['excused']}    "
        f"Scheduled: {s['scheduled']}",
        f"Minutes served: {s['minutes_served']}",
    ]
    messagebox.showinfo("Detentions — pupil summary",
                        "\n".join(lines), parent=host.root)
