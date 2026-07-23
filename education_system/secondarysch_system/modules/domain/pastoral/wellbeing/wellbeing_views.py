"""Tk views for wellbeing check-ins."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.pastoral.wellbeing import (
    wellbeing as data,
)
from education_system.secondarysch_system.modules.domain.pastoral.wellbeing.wellbeing import (
    CHECKIN_STATUSES, CHECKIN_SOURCES, MIN_RATING, MAX_RATING,
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
                messagebox.showerror("Wellbeing", str(e),
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


def _checkin_dialog(host, title: str,
                     initial: dict[str, Any] | None = None
                     ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("560x680")
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
    date_var   = tk.StringVar(value=str(initial.get("checkin_date")
                                          or ""))
    src_var    = tk.StringVar(value=str(initial.get("source")
                                          or "Form tutor"))
    mood_var   = tk.StringVar(value=str(initial.get("mood_rating")
                                          if initial.get("mood_rating")
                                          is not None else ""))
    conf_var   = tk.StringVar(value=str(initial.get("confidence_rating")
                                          if initial.get("confidence_rating")
                                          is not None else ""))
    conn_var   = tk.StringVar(value=str(initial.get("connection_rating")
                                          if initial.get("connection_rating")
                                          is not None else ""))
    action_var = tk.BooleanVar(value=bool(initial.get("action_needed")))
    recorder_var = tk.StringVar(value=str(initial.get("recorded_by")
                                             or ""))
    status_var = tk.StringVar(value=str(initial.get("status") or "Open"))
    fudate_var = tk.StringVar(value=str(initial.get("follow_up_date")
                                           or ""))
    fuwith_var = tk.StringVar(value=str(initial.get("follow_up_with")
                                           or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",    ttk.Entry(frm, textvariable=pupil_var,
                                      width=14)),
        ("Date:",        ttk.Entry(frm, textvariable=date_var,
                                      width=14)),
        ("Source:",      ttk.Combobox(frm, textvariable=src_var,
                                        values=list(CHECKIN_SOURCES),
                                        state="readonly", width=22)),
        (f"Mood ({MIN_RATING}-{MAX_RATING}):",
         ttk.Spinbox(frm, from_=MIN_RATING, to=MAX_RATING,
                      textvariable=mood_var, width=4)),
        (f"Confidence ({MIN_RATING}-{MAX_RATING}):",
         ttk.Spinbox(frm, from_=MIN_RATING, to=MAX_RATING,
                      textvariable=conf_var, width=4)),
        (f"Connection ({MIN_RATING}-{MAX_RATING}):",
         ttk.Spinbox(frm, from_=MIN_RATING, to=MAX_RATING,
                      textvariable=conn_var, width=4)),
        ("Action needed:", ttk.Checkbutton(frm, variable=action_var)),
        ("Recorded by:",   ttk.Entry(frm, textvariable=recorder_var,
                                        width=24)),
        ("Status:",        ttk.Combobox(frm, textvariable=status_var,
                                         values=list(CHECKIN_STATUSES),
                                         state="readonly", width=14)),
        ("Follow-up date:", ttk.Entry(frm, textvariable=fudate_var,
                                        width=14)),
        ("Follow-up with:", ttk.Entry(frm, textvariable=fuwith_var,
                                        width=24)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Stressors:", "stressors", 3),
                   ("Supports:", "supports", 3),
                   ("Action summary:", "action_summary", 3),
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
            "pupil_id":          pupil_var.get().strip(),
            "checkin_date":      date_var.get().strip(),
            "source":            src_var.get().strip(),
            "mood_rating":       mood_var.get().strip(),
            "confidence_rating": conf_var.get().strip(),
            "connection_rating": conn_var.get().strip(),
            "action_needed":     bool(action_var.get()),
            "recorded_by":       recorder_var.get().strip(),
            "status":            status_var.get().strip(),
            "follow_up_date":    fudate_var.get().strip(),
            "follow_up_with":    fuwith_var.get().strip(),
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
def open_wellbeing(host) -> None:
    logger.debug("GUI: open_wellbeing")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Wellbeing",
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
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *CHECKIN_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 6))
    act_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Action only",
                    variable=act_var,
                    command=lambda: _refresh()).pack(side="left",
                                                     padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="Log",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Status",
               command=lambda: _status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Low ratings",
               command=lambda: _low(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Pupil summary",
               command=lambda: _pupil_summary(host)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "date", "pupil", "year", "source", "mood",
            "conf", "conn", "avg", "act", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 90),
        ("pupil", "Pupil", 90), ("year", "Yr", 50),
        ("source", "Source", 140),
        ("mood", "Mood", 60), ("conf", "Conf", 60),
        ("conn", "Conn", 60), ("avg", "Avg", 60),
        ("act", "Action", 60), ("status", "Status", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.tag_configure("action", background="#fff2cc")
    tree.tag_configure("low", background="#fde7e7")

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_checkins(
                year_group=year_var.get().strip() or None,
                pupil_id=pupil_var.get().strip() or None,
                status=status_var.get().strip() or None,
                action_needed=(True if act_var.get() else None),
            )
        except ValidationError as e:
            messagebox.showerror("Wellbeing", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("wellbeing refresh failed")
            messagebox.showerror("Wellbeing",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for c in rows:
            tags = ()
            if c.action_needed:
                tags = ("action",)
            scores = [v for v in (c.mood_rating, c.confidence_rating,
                                    c.connection_rating)
                      if v is not None]
            if scores and min(scores) <= 2:
                tags = ("low",)
            avg = (f"{c.average_rating:.2f}"
                   if c.average_rating is not None else "-")
            tree.insert("", "end", iid=str(c.checkin_id), values=(
                c.checkin_id, c.checkin_date, c.pupil_id,
                c.pupil_year or "-", c.source,
                c.mood_rating if c.mood_rating is not None else "-",
                c.confidence_rating if c.confidence_rating is not None
                else "-",
                c.connection_rating if c.connection_rating is not None
                else "-",
                avg, "Yes" if c.action_needed else "No",
                c.status,
            ), tags=tags)
        try:
            s = data.cohort_summary(
                year_group=year_var.get().strip() or None)
            summary_var.set(
                f"Total: {s['total']}    "
                f"Action: {s['action_needed']}    "
                f"Avg mood: {s['avg_mood'] if s['avg_mood'] is not None else '-'}    "
                f"Avg conf: {s['avg_confidence'] if s['avg_confidence'] is not None else '-'}    "
                f"Avg conn: {s['avg_connection'] if s['avg_connection'] is not None else '-'}")
        except Exception:
            summary_var.set(f"{len(rows)} check-in(s)")
        host.status_var.set(f"Wellbeing: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Wellbeing",
                            "Select a check-in first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _checkin_dialog(host, "Log wellbeing check-in")
    if not fields:
        return
    c = data.log_checkin(fields)
    messagebox.showinfo(
        "Wellbeing",
        f"Logged #{c.checkin_id} for {c.pupil_id} "
        f"(avg "
        f"{c.average_rating if c.average_rating is not None else '-'})",
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
        "pupil_id", "checkin_date", "source",
        "mood_rating", "confidence_rating", "connection_rating",
        "stressors", "supports", "action_needed", "action_summary",
        "recorded_by", "status", "follow_up_date",
        "follow_up_with", "notes")}
    fields = _checkin_dialog(host, f"Edit check-in #{cid}",
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
    dlg.geometry("340x140")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{c.pupil_id} on {c.checkin_date}").pack(
        anchor="w")
    ttk.Label(frm, text=f"Current: {c.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=c.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(CHECKIN_STATUSES),
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(cid, new_var.get())
        except ValidationError as ex:
            messagebox.showerror("Wellbeing", str(ex), parent=dlg)
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
            "Delete check-in",
            f"Delete check-in #{cid} ({existing.pupil_id})?",
            parent=host.root):
        return
    data.delete(cid)
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
        f"Check-ins: {s['count']}    "
        f"Action needed: {s['action_needed']}",
        "",
        f"Avg mood: {s['avg_mood'] if s['avg_mood'] is not None else '-'}",
        f"Avg confidence: {s['avg_confidence'] if s['avg_confidence'] is not None else '-'}",
        f"Avg connection: {s['avg_connection'] if s['avg_connection'] is not None else '-'}",
    ]
    if s["by_status"]:
        lines.append("")
        lines.append("By status:")
        for k, v in s["by_status"].items():
            lines.append(f"  {k:<12} {v}")
    messagebox.showinfo("Wellbeing — pupil summary",
                        "\n".join(lines), parent=host.root)


@_safe_view
def _low(host) -> None:
    thr = simpledialog.askinteger(
        "Threshold",
        "Show pupils whose latest rating is at or below "
        "(1–5):",
        initialvalue=2, parent=host.root,
        minvalue=MIN_RATING, maxvalue=MAX_RATING)
    if thr is None:
        return
    pupils = data.low_wellbeing(threshold=thr)
    dlg = tk.Toplevel(host.root)
    dlg.title("Pupils with low wellbeing")
    dlg.transient(host.root)
    dlg.geometry("520x420")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{len(pupils)} pupil(s) with latest rating ≤ {thr}",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))
    t = ttk.Treeview(frm,
                       columns=("pupil", "date", "mood", "conf",
                                 "conn"),
                       show="headings", height=14)
    for c, label, w in [
        ("pupil", "Pupil", 120), ("date", "Latest date", 110),
        ("mood", "Mood", 60), ("conf", "Conf", 60),
        ("conn", "Conn", 60),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)
    for pid, checkins in pupils.items():
        c = checkins[0]
        t.insert("", "end", values=(
            pid, c.checkin_date,
            c.mood_rating if c.mood_rating is not None else "-",
            c.confidence_rating if c.confidence_rating is not None
            else "-",
            c.connection_rating if c.connection_rating is not None
            else "-",
        ))
    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(side="right", pady=(10, 0))
