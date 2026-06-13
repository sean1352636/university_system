"""Tk views for the weekly timetable."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.timetable import (
    timetable as data,
)
from education_system.primarysch_system.modules.domain.timetable.timetable import (
    DAYS_OF_WEEK, MIN_PERIOD, MAX_PERIOD,
)
from education_system.primarysch_system.modules.domain.subjects import (
    subjects as subjects_data,
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
                messagebox.showerror("Timetable", str(e),
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


def _form_dialog(host, title: str, initial: dict[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("480x500")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    year_var    = tk.StringVar(value=str(initial.get("year_group") or "7"))
    form_var    = tk.StringVar(value=str(initial.get("form_group") or ""))
    day_var     = tk.StringVar(value=str(initial.get("day_of_week") or "Mon"))
    period_var  = tk.StringVar(value=str(initial.get("period") or MIN_PERIOD))
    start_var   = tk.StringVar(value=str(initial.get("start_time") or ""))
    end_var     = tk.StringVar(value=str(initial.get("end_time") or ""))
    room_var    = tk.StringVar(value=str(initial.get("room") or ""))
    teacher_var = tk.StringVar(value=str(initial.get("teacher") or ""))
    notes_var   = tk.StringVar(value=str(initial.get("notes") or ""))

    try:
        subjects = subjects_data.list_all(active_only=True)
    except Exception:
        subjects = []
    subject_labels = [f"#{s.subject_id} {s.code} — {s.name}"
                      for s in subjects]
    initial_sid = initial.get("subject_id")
    subject_var = tk.StringVar(value="")
    if initial_sid is not None:
        for s in subjects:
            if s.subject_id == int(initial_sid):
                subject_var.set(f"#{s.subject_id} {s.code} — {s.name}")
                break

    rows: list[tuple[str, tk.Widget]] = [
        ("Year:",     ttk.Combobox(frm, textvariable=year_var,
                                    values=list(YEAR_GROUPS),
                                    state="readonly", width=8)),
        ("Form:",     ttk.Entry(frm, textvariable=form_var, width=12)),
        ("Subject:",  ttk.Combobox(frm, textvariable=subject_var,
                                    values=subject_labels,
                                    state="readonly", width=36)),
        ("Day:",      ttk.Combobox(frm, textvariable=day_var,
                                    values=list(DAYS_OF_WEEK),
                                    state="readonly", width=8)),
        ("Period:",   ttk.Spinbox(frm, from_=MIN_PERIOD, to=MAX_PERIOD,
                                   textvariable=period_var, width=6)),
        ("Start time:", ttk.Entry(frm, textvariable=start_var, width=10)),
        ("End time:",   ttk.Entry(frm, textvariable=end_var, width=10)),
        ("Room:",     ttk.Entry(frm, textvariable=room_var, width=14)),
        ("Teacher:",  ttk.Entry(frm, textvariable=teacher_var, width=24)),
        ("Notes:",    ttk.Entry(frm, textvariable=notes_var, width=36)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _parse_subject(label: str) -> str:
        label = (label or "").strip()
        if not label.startswith("#"):
            return ""
        return label.split()[0][1:]

    def _save() -> None:
        nonlocal result
        result = {
            "year_group":  year_var.get().strip(),
            "form_group":  form_var.get().strip(),
            "subject_id":  _parse_subject(subject_var.get()),
            "day_of_week": day_var.get().strip(),
            "period":      period_var.get().strip(),
            "start_time":  start_var.get().strip(),
            "end_time":    end_var.get().strip(),
            "room":        room_var.get().strip(),
            "teacher":     teacher_var.get().strip(),
            "notes":       notes_var.get().strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows), column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                               padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_timetable(host) -> None:
    logger.debug("GUI: open_timetable")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Timetable",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    year_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=year_var,
                 values=["", *YEAR_GROUPS], state="readonly", width=6).pack(
        side="left", padx=(0, 8))
    ttk.Label(bar, text="Form:").pack(side="left", padx=(0, 4))
    form_var = tk.StringVar(value="")
    ttk.Entry(bar, textvariable=form_var, width=10).pack(side="left",
                                                         padx=(0, 8))
    ttk.Label(bar, text="Teacher:").pack(side="left", padx=(0, 4))
    teacher_var = tk.StringVar(value="")
    ttk.Entry(bar, textvariable=teacher_var, width=16).pack(side="left",
                                                            padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)).pack(side="left",
                                                                   padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    # Two views: a flat list (left) and a weekly grid (right).
    pane = ttk.PanedWindow(root, orient="horizontal")
    pane.pack(fill="both", expand=True)

    list_frm = ttk.Frame(pane)
    grid_frm = ttk.LabelFrame(pane, text="Weekly grid", padding=6)
    pane.add(list_frm, weight=1)
    pane.add(grid_frm, weight=2)

    cols = ("id", "day", "period", "year", "form", "subject", "room",
            "teacher", "time")
    tree = ttk.Treeview(list_frm, columns=cols, show="headings", height=22)
    for c, label, w in [
        ("id", "ID", 50), ("day", "Day", 50), ("period", "P", 40),
        ("year", "Yr", 50), ("form", "Form", 60),
        ("subject", "Subject", 90), ("room", "Room", 70),
        ("teacher", "Teacher", 140), ("time", "Time", 110),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    host._tt_tree = tree  # used by edit/delete helpers

    grid_cells: dict[tuple[str, int], tk.Widget] = {}
    grid_inner = ttk.Frame(grid_frm)
    grid_inner.pack(fill="both", expand=True)

    def _build_grid(max_period: int) -> None:
        for w in grid_inner.winfo_children():
            w.destroy()
        grid_cells.clear()
        ttk.Label(grid_inner, text="", width=6).grid(row=0, column=0,
                                                      padx=1, pady=1)
        for p in range(MIN_PERIOD, max_period + 1):
            ttk.Label(grid_inner, text=f"P{p}", anchor="center",
                      relief="ridge", padding=2, width=18).grid(
                row=0, column=p - MIN_PERIOD + 1, sticky="nsew",
                padx=1, pady=1)
        for r_idx, day in enumerate(DAYS_OF_WEEK, start=1):
            ttk.Label(grid_inner, text=day, anchor="center",
                      relief="ridge", padding=2, width=6).grid(
                row=r_idx, column=0, sticky="nsew", padx=1, pady=1)
            for p in range(MIN_PERIOD, max_period + 1):
                lbl = tk.Label(grid_inner, text="-", anchor="w",
                               relief="ridge", padx=4, pady=2,
                               width=18, bg="#fafafa", justify="left")
                lbl.grid(row=r_idx, column=p - MIN_PERIOD + 1,
                         sticky="nsew", padx=1, pady=1)
                grid_cells[(day, p)] = lbl
        for col in range(0, max_period - MIN_PERIOD + 2):
            grid_inner.columnconfigure(col, weight=1)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_slots(
                year_group=year_var.get().strip() or None,
                form_group=form_var.get().strip() or None,
                teacher=teacher_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Timetable", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("timetable refresh failed")
            messagebox.showerror("Timetable",
                                 f"Could not load timetable:\n\n{e}",
                                 parent=host.root)
            return
        max_p = MIN_PERIOD
        for s in rows:
            timestr = ("-" if not s.start_time
                       else f"{s.start_time}–{s.end_time or '?'}")
            tree.insert("", "end", iid=str(s.slot_id), values=(
                s.slot_id, s.day_of_week, s.period, s.year_group,
                s.form_group or "-", s.subject_code or "?",
                s.room or "-", s.teacher or "-", timestr))
            max_p = max(max_p, s.period)
        _build_grid(max_p)
        cell_map: dict[tuple[str, int], list[data.TimetableSlot]] = {}
        for s in rows:
            cell_map.setdefault((s.day_of_week, s.period), []).append(s)
        for (day, p), slots in cell_map.items():
            lbl = grid_cells.get((day, p))
            if not lbl:
                continue
            s = slots[0]
            txt = f"{s.subject_code or '?'}"
            if s.form_group:
                txt += f" {s.form_group}"
            if s.room:
                txt += f"\n@{s.room}"
            if s.teacher:
                txt += f" · {s.teacher.split()[-1]}"
            if len(slots) > 1:
                txt += f"  (+{len(slots) - 1})"
            lbl.config(text=txt, bg="#e6f2ff")
        try:
            c = data.counts()
            summary_var.set(
                f"Slots: {c['total']}    Distinct teachers: {c['teachers']}")
        except Exception:
            logger.exception("timetable counts failed")
            summary_var.set("(counts unavailable)")
        host.status_var.set(f"Timetable: {len(rows)} slot(s)")

    tree.bind("<Double-1>", lambda _e: _edit_selected(host, on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(host) -> int | None:
    tree = getattr(host, "_tt_tree", None)
    sel = tree.focus() if tree else None
    if not sel:
        messagebox.showinfo("Timetable", "Select a slot first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _form_dialog(host, "New slot")
    if not fields:
        return
    s = data.create_slot(fields)
    messagebox.showinfo(
        "Timetable",
        f"Created slot #{s.slot_id}: Yr{s.year_group} "
        f"{s.day_of_week} P{s.period} ({s.subject_code})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit_selected(host, *, on_done=None) -> None:
    sid = _selected_id(host)
    if sid is None:
        return
    existing = data.get_slot(sid)
    if existing is None:
        return
    initial = {
        "year_group":  existing.year_group, "form_group": existing.form_group,
        "subject_id":  existing.subject_id,
        "day_of_week": existing.day_of_week, "period": existing.period,
        "start_time":  existing.start_time, "end_time": existing.end_time,
        "room":        existing.room, "teacher": existing.teacher,
        "notes":       existing.notes,
    }
    fields = _form_dialog(host, f"Edit slot #{sid}", initial=initial)
    if not fields:
        return
    data.update_slot(sid, fields)
    if on_done:
        on_done()


@_safe_view
def _delete_selected(host, *, on_done=None) -> None:
    sid = _selected_id(host)
    if sid is None:
        return
    existing = data.get_slot(sid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete slot",
            f"Delete slot #{sid}: Yr{existing.year_group} "
            f"{existing.day_of_week} P{existing.period} "
            f"({existing.subject_code})?",
            parent=host.root):
        return
    data.delete_slot(sid)
    if on_done:
        on_done()
