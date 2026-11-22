"""Tk views for the behaviour log."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.pastoral.behaviour import (
    behaviour as data,
)
from education_system.systems.primary.domain.pastoral.behaviour.behaviour import (
    INCIDENT_TYPES, SEVERITIES, INCIDENT_STATUSES,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
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
                messagebox.showerror("Behaviour Log", str(e),
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


def _owner(host, owner=None):
    """The window a pop-up belongs to: the page's own window when the page
    was popped out, else the main window."""
    return owner if owner is not None else host.root


def _ask_value(owner, title: str, prompt: str,
               make: Callable[[tk.Misc, tk.StringVar], tk.Widget],
               initial: str = "") -> str | None:
    """A small modal pop-up holding one picker; the picked value ("" when
    left blank) or None when cancelled."""
    dlg = tk.Toplevel(owner)
    dlg.title(title)
    dlg.transient(owner)
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=prompt).pack(anchor="w", pady=(0, 6))
    var = tk.StringVar(value=initial)
    make(frm, var).pack(anchor="w")
    result: str | None = None

    def _ok() -> None:
        nonlocal result
        result = var.get().strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                              padx=4)
    ttk.Button(btns, text="OK", command=_ok).pack(side="right")
    dlg.wait_window()
    return result


def _incident_dialog(host, title: str,
                      initial: dict[str, Any] | None = None, *,
                      owner=None) -> dict[str, Any] | None:
    master = _owner(host, owner)
    dlg = tk.Toplevel(master)
    dlg.title(title)
    dlg.transient(master)
    dlg.geometry("600x600")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm, footer = kit.scrolled_form(dlg)

    pupil_var  = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    date_var   = tk.StringVar(value=str(initial.get("incident_date")
                                          or ""))
    time_var   = tk.StringVar(value=str(initial.get("incident_time")
                                          or ""))
    loc_var    = tk.StringVar(value=str(initial.get("location") or ""))
    type_var   = tk.StringVar(value=str(initial.get("incident_type")
                                          or ""))
    points_var = tk.StringVar(value=str(initial.get("points")
                                          if initial.get("points") is not None
                                          else ""))
    sev_var    = tk.StringVar(value=str(initial.get("severity") or "Low"))
    raisedby_var = tk.StringVar(value=str(initial.get("raised_by")
                                             or ""))
    status_var = tk.StringVar(value=str(initial.get("status") or "Open"))

    initial_sid = initial.get("subject_id")
    subject_var = tk.StringVar(
        value="" if initial_sid in (None, "") else str(initial_sid))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil:",      kit.PupilPicker(frm, pupil_var)),
        ("Date:",       kit.DateField(frm, date_var)),
        ("Time:",       kit.TimeField(frm, time_var)),
        ("Location:",   ttk.Entry(frm, textvariable=loc_var,
                                    width=24)),
        ("Subject:",    kit.SubjectPicker(frm, subject_var, width=42)),
        ("Type:",       kit.ChoiceField(frm, type_var,
                                        choices=list(INCIDENT_TYPES.keys()),
                                        width=22)),
        ("Points:",     kit.NumberField(frm, points_var, from_=-100,
                                        to=100, width=6)),
        ("Severity:",   kit.ChoiceField(frm, sev_var, choices=SEVERITIES,
                                        width=10)),
        ("Raised by:",  kit.StaffPicker(frm, raisedby_var, by="name")),
        ("Status:",     kit.ChoiceField(frm, status_var,
                                        choices=INCIDENT_STATUSES,
                                        width=12)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="w", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Description (required):").grid(
        row=len(rows), column=0, sticky="nw", pady=2)
    desc_w = tk.Text(frm, width=44, height=4, wrap="word")
    desc_w.insert("1.0", str(initial.get("description") or ""))
    desc_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="Action taken:").grid(row=len(rows) + 1,
                                                column=0, sticky="nw",
                                                pady=2)
    action_w = tk.Text(frm, width=44, height=3, wrap="word")
    action_w.insert("1.0", str(initial.get("action_taken") or ""))
    action_w.grid(row=len(rows) + 1, column=1, sticky="ew", pady=2)

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
            "incident_date": date_var.get().strip(),
            "incident_time": time_var.get().strip(),
            "location":      loc_var.get().strip(),
            "subject_id":    subject_var.get().strip(),
            "incident_type": type_var.get().strip(),
            "points":        points_var.get().strip(),
            "severity":      sev_var.get().strip(),
            "raised_by":     raisedby_var.get().strip(),
            "status":        status_var.get().strip(),
            "description":   desc_w.get("1.0", "end").strip(),
            "action_taken":  action_w.get("1.0", "end").strip(),
            "notes":         notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    ttk.Button(footer, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(footer, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_behaviour(host) -> None:
    logger.debug("GUI: open_behaviour")
    kit.show_page(host, "Behaviour Log",
                  lambda parent: _draw_behaviour(parent, host))


def _draw_behaviour(parent, host) -> None:
    root = parent
    win = parent.winfo_toplevel()
    kit.page_heading(root, "Behaviour Log",
                     "Positive recognitions and behaviour incidents.")

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    year_var = tk.StringVar(value="")
    kit.YearGroupPicker(bar, year_var, blank=True,
                        width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Pupil:").pack(side="left", padx=(0, 4))
    pupil_var = tk.StringVar(value="")
    pupil_pick = kit.PupilPicker(bar, pupil_var, width=30)
    pupil_pick.pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Polarity:").pack(side="left", padx=(0, 4))
    polarity_var = tk.StringVar(value="")
    kit.ChoiceField(bar, polarity_var, choices=("positive", "negative"),
                    blank=True, width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Severity:").pack(side="left", padx=(0, 4))
    sev_var = tk.StringVar(value="")
    kit.ChoiceField(bar, sev_var, choices=SEVERITIES, blank=True,
                    width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    kit.ChoiceField(bar, status_var, choices=INCIDENT_STATUSES, blank=True,
                    width=10).pack(side="left", padx=(0, 8))
    # The toolbar is wide; its buttons get a row of their own.
    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="Log",
               command=lambda: _new(host, on_done=_refresh,
                                owner=win)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh,
                                owner=win)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Status",
               command=lambda: _status(host, tree, on_done=_refresh,
                                owner=win)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Pupil summary",
               command=lambda: _pupil_summary(host, owner=win,
                                              pupil_id=pupil_var.get())
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Threshold",
               command=lambda: _threshold(host,
                                            year_var.get().strip()
                                            or None, owner=win)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh,
                                owner=win)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    tree = kit.tree(root, [
        ("id", "ID", 50), ("date", "Date", 90),
        ("time", "Time", 60), ("pupil", "Pupil", 90),
        ("year", "Yr", 50), ("type", "Type", 140),
        ("pol", "Pol", 60), ("pts", "Pts", 50),
        ("sev", "Severity", 80), ("status", "Status", 90),
        ("desc", "Description", 260),
    ], height=18, stretch=("desc",),
        tags={"positive": "#e6f7ec", "negative": "#fde7e7"})

    def _refresh() -> None:
        if not tree.winfo_exists():
            return
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_incidents(
                pupil_id=pupil_var.get().strip() or None,
                year_group=year_var.get().strip() or None,
                polarity=polarity_var.get().strip() or None,
                severity=sev_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Behaviour Log", str(e),
                                 parent=win)
            return
        except Exception as e:
            logger.exception("behaviour refresh failed")
            messagebox.showerror("Behaviour Log",
                                 f"Could not load:\n\n{e}",
                                 parent=win)
            return
        for i in rows:
            tree.insert("", "end", iid=str(i.incident_id), values=(
                i.incident_id, i.incident_date, i.incident_time or "-",
                i.pupil_id, i.pupil_year or "-",
                i.incident_type, i.polarity,
                f"{'+' if i.points > 0 else ''}{i.points}",
                i.severity, i.status, i.description,
            ), tags=(i.polarity,))
        try:
            s = data.cohort_summary(
                year_group=year_var.get().strip() or None)
            summary_var.set(
                f"Total: {s['total']}    +: {s['positive']}    "
                f"-: {s['negative']}    Open: {s['open']}")
        except Exception:
            summary_var.set(f"{len(rows)} incident(s)")
        status_bar = getattr(host, "status_var", None)
        if status_bar is not None:
            status_bar.set(f"Behaviour: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh, owner=win))
    pupil_pick.bind_change(lambda _v: _refresh())
    year_var.trace_add("write", lambda *_: _refresh())
    polarity_var.trace_add("write", lambda *_: _refresh())
    sev_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host, owner=None) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Behaviour Log",
                            "Select an incident first.",
                            parent=_owner(host, owner))
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None, owner=None) -> None:
    fields = _incident_dialog(host, "Log behaviour incident", owner=owner)
    if not fields:
        return
    i = data.log_incident(fields)
    messagebox.showinfo(
        "Behaviour Log",
        f"Logged #{i.incident_id}: {i.pupil_id} — "
        f"{i.incident_type} ({'+' if i.points > 0 else ''}"
        f"{i.points} pts)",
        parent=_owner(host, owner),
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None, owner=None) -> None:
    iid = _selected_id(tree, host, owner)
    if iid is None:
        return
    existing = data.get(iid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "incident_date", "incident_time", "location",
        "subject_id", "incident_type", "points", "severity",
        "description", "raised_by", "action_taken", "status",
        "notes")}
    fields = _incident_dialog(host, f"Edit incident #{iid}",
                                initial=initial, owner=owner)
    if not fields:
        return
    data.update(iid, fields)
    if on_done:
        on_done()


@_safe_view
def _status(host, tree: ttk.Treeview, *, on_done=None, owner=None) -> None:
    iid = _selected_id(tree, host, owner)
    if iid is None:
        return
    i = data.get(iid)
    if i is None:
        return
    dlg = tk.Toplevel(_owner(host, owner))
    dlg.title(f"Status — #{iid}")
    dlg.transient(_owner(host, owner))
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
              text=f"{i.pupil_id} — {i.incident_type}").pack(
        anchor="w")
    ttk.Label(frm, text=f"Current: {i.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=i.status)
    kit.ChoiceField(frm, new_var, choices=INCIDENT_STATUSES).pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(iid, new_var.get())
        except ValidationError as ex:
            messagebox.showerror("Behaviour Log", str(ex),
                                 parent=dlg)
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
def _delete(host, tree: ttk.Treeview, *, on_done=None, owner=None) -> None:
    iid = _selected_id(tree, host, owner)
    if iid is None:
        return
    existing = data.get(iid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete incident",
            f"Delete incident #{iid} ({existing.pupil_id}, "
            f"{existing.incident_type})?",
            parent=_owner(host, owner)):
        return
    data.delete(iid)
    if on_done:
        on_done()


@_safe_view
def _pupil_summary(host, *, owner=None, pupil_id: str = "") -> None:
    pid = _ask_value(_owner(host, owner), "Pupil summary", "Pupil:",
                     lambda m, v: kit.PupilPicker(m, v),
                     initial=pupil_id or "")
    if not pid:
        return
    s = data.pupil_summary(pid.strip())
    lines = [
        f"Pupil: {pid}",
        f"Total: {s['total']}    "
        f"Positive: {s['positive']}    "
        f"Negative: {s['negative']}",
        f"Net points: {'+' if s['total_points'] >= 0 else ''}"
        f"{s['total_points']}",
    ]
    if s["by_severity"]:
        lines.append("")
        lines.append("By severity:")
        for k, v in s["by_severity"].items():
            lines.append(f"  {k:<10} {v}")
    if s["by_type"]:
        lines.append("")
        lines.append("By type (top):")
        for k, v in sorted(s["by_type"].items(),
                            key=lambda kv: -kv[1])[:10]:
            lines.append(f"  {k:<22} {v}")
    messagebox.showinfo("Behaviour — pupil summary",
                        "\n".join(lines), parent=_owner(host, owner))


@_safe_view
def _threshold(host, year_group: str | None, *, owner=None) -> None:
    raw = _ask_value(_owner(host, owner), "Threshold",
                     "Show pupils with net points at or below:",
                     lambda m, v: kit.NumberField(m, v, from_=-500, to=500),
                     initial="-10")
    if raw is None:
        return
    try:
        thr = int(float(raw))
    except ValueError:
        messagebox.showerror("Threshold", "Enter a whole number.",
                             parent=_owner(host, owner))
        return
    rows = data.pupils_above_threshold(points_below=thr,
                                          year_group=year_group)
    dlg = tk.Toplevel(_owner(host, owner))
    dlg.title("Pupils on threshold")
    dlg.transient(_owner(host, owner))
    dlg.geometry("420x380")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{len(rows)} pupil(s) at or below {thr} points",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))
    t = ttk.Treeview(frm, columns=("pupil", "points"),
                       show="headings", height=14)
    t.heading("pupil", text="Pupil")
    t.heading("points", text="Net points")
    t.column("pupil", width=180)
    t.column("points", width=100, anchor="e")
    t.pack(fill="both", expand=True)
    for pid, pts in rows:
        t.insert("", "end", values=(pid, pts))
    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(side="right", pady=(10, 0))
