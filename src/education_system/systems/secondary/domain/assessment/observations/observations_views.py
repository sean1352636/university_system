"""Tk views for lesson observations."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.observations import (
    observations as data,
)
from education_system.systems.secondary.domain.assessment.observations.observations import (
    OBSERVATION_TYPES, JUDGEMENTS, OBSERVATION_STATUSES,
    MIN_PERIOD, MAX_PERIOD,
)
from education_system.systems.secondary.domain.academics.subjects import (
    subjects as subjects_data,
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
                messagebox.showerror("Observations", str(e),
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


def _obs_dialog(host, title: str,
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
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    teacher_var  = tk.StringVar(value=str(initial.get("teacher") or ""))
    year_var     = tk.StringVar(value=str(initial.get("year_group") or ""))
    form_var     = tk.StringVar(value=str(initial.get("form_group") or ""))
    date_var     = tk.StringVar(value=str(initial.get("observation_date")
                                            or ""))
    period_var   = tk.StringVar(value=str(initial.get("period") or ""))
    observer_var = tk.StringVar(value=str(initial.get("observer") or ""))
    type_var     = tk.StringVar(value=str(initial.get("observation_type")
                                            or "Learning walk"))
    focus_var    = tk.StringVar(value=str(initial.get("focus") or ""))
    judgement_var = tk.StringVar(value=str(initial.get("judgement")
                                              or "Not judged"))
    follow_var   = tk.StringVar(value=str(initial.get("follow_up_date")
                                             or ""))
    status_var   = tk.StringVar(value=str(initial.get("status")
                                             or "Scheduled"))

    try:
        subjects = subjects_data.list_all(active_only=True)
    except Exception:
        subjects = []
    subject_labels = [""] + [f"#{s.subject_id} {s.code} — {s.name}"
                              for s in subjects]
    subject_var = tk.StringVar(value="")
    initial_sid = initial.get("subject_id")
    if initial_sid is not None:
        for s in subjects:
            if s.subject_id == int(initial_sid):
                subject_var.set(f"#{s.subject_id} {s.code} — {s.name}")
                break

    rows: list[tuple[str, tk.Widget]] = [
        ("Teacher:",     ttk.Entry(frm, textvariable=teacher_var,
                                     width=28)),
        ("Subject:",     ttk.Combobox(frm, textvariable=subject_var,
                                       values=subject_labels,
                                       state="readonly", width=42)),
        ("Year:",        ttk.Combobox(frm, textvariable=year_var,
                                       values=["", *YEAR_GROUPS],
                                       state="readonly", width=8)),
        ("Form:",        ttk.Entry(frm, textvariable=form_var,
                                     width=12)),
        ("Date:",        ttk.Entry(frm, textvariable=date_var,
                                     width=14)),
        ("Period:",      ttk.Entry(frm, textvariable=period_var,
                                     width=6)),
        ("Observer:",    ttk.Entry(frm, textvariable=observer_var,
                                     width=28)),
        ("Type:",        ttk.Combobox(frm, textvariable=type_var,
                                       values=list(OBSERVATION_TYPES),
                                       state="readonly", width=18)),
        ("Focus:",       ttk.Entry(frm, textvariable=focus_var,
                                     width=44)),
        ("Judgement:",   ttk.Combobox(frm, textvariable=judgement_var,
                                       values=list(JUDGEMENTS),
                                       state="readonly", width=22)),
        ("Follow-up date:", ttk.Entry(frm, textvariable=follow_var,
                                        width=14)),
        ("Status:",      ttk.Combobox(frm, textvariable=status_var,
                                       values=list(OBSERVATION_STATUSES),
                                       state="readonly", width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Strengths:", "strengths", 3),
                   ("Development areas:", "development_areas", 3),
                   ("Action points:", "action_points", 3),
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

    def _parse_subject(label: str) -> str:
        label = (label or "").strip()
        if not label.startswith("#"):
            return ""
        return label.split()[0][1:]

    def _save() -> None:
        nonlocal result
        result = {
            "teacher":          teacher_var.get().strip(),
            "subject_id":       _parse_subject(subject_var.get()),
            "year_group":       year_var.get().strip(),
            "form_group":       form_var.get().strip(),
            "observation_date": date_var.get().strip(),
            "period":           period_var.get().strip(),
            "observer":         observer_var.get().strip(),
            "observation_type": type_var.get().strip(),
            "focus":            focus_var.get().strip(),
            "judgement":        judgement_var.get().strip(),
            "follow_up_date":   follow_var.get().strip(),
            "status":           status_var.get().strip(),
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
def open_observations(host) -> None:
    logger.debug("GUI: open_observations")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Observations",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Teacher:").pack(side="left", padx=(0, 4))
    teacher_var = tk.StringVar(value="")
    ttk.Entry(bar, textvariable=teacher_var, width=16).pack(
        side="left", padx=(0, 6))
    ttk.Label(bar, text="Type:").pack(side="left", padx=(0, 4))
    type_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=type_var,
                 values=["", *OBSERVATION_TYPES], state="readonly",
                 width=14).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Judgement:").pack(side="left", padx=(0, 4))
    jud_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=jud_var,
                 values=["", *JUDGEMENTS], state="readonly",
                 width=18).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *OBSERVATION_STATUSES], state="readonly",
                 width=10).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Status",
               command=lambda: _status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Summary",
               command=lambda: _summary(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "date", "p", "teacher", "subj", "yr", "observer",
            "type", "jud", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100), ("p", "P", 40),
        ("teacher", "Teacher", 160), ("subj", "Subj", 70),
        ("yr", "Yr", 50), ("observer", "Observer", 140),
        ("type", "Type", 110), ("jud", "Judgement", 160),
        ("status", "Status", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_observations(
                teacher=teacher_var.get().strip() or None,
                observation_type=type_var.get().strip() or None,
                judgement=jud_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Observations", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("observations refresh failed")
            messagebox.showerror("Observations",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for o in rows:
            tree.insert("", "end", iid=str(o.observation_id), values=(
                o.observation_id, o.observation_date,
                o.period if o.period else "-",
                o.teacher, o.subject_code or "-",
                o.year_group or "-", o.observer,
                o.observation_type, o.judgement, o.status,
            ))
        try:
            s = data.cohort_summary()
            summary_var.set(
                f"Total: {s['total']}    Follow-ups: {s['follow_ups']}    "
                + "    ".join(f"{k}: {v}"
                                for k, v in s["by_judgement"].items()))
        except Exception:
            summary_var.set(f"{len(rows)} observation(s) listed")
        host.status_var.set(f"Observations: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    type_var.trace_add("write", lambda *_: _refresh())
    jud_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Observations",
                            "Select an observation first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _obs_dialog(host, "New observation")
    if not fields:
        return
    o = data.create(fields)
    messagebox.showinfo(
        "Observations",
        f"Created observation #{o.observation_id} for {o.teacher}",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    oid = _selected_id(tree, host)
    if oid is None:
        return
    existing = data.get(oid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "teacher", "subject_id", "year_group", "form_group",
        "observation_date", "period", "observer",
        "observation_type", "focus", "judgement",
        "strengths", "development_areas", "action_points",
        "follow_up_date", "status", "notes")}
    fields = _obs_dialog(host, f"Edit observation #{oid}",
                          initial=initial)
    if not fields:
        return
    data.update(oid, fields)
    if on_done:
        on_done()


@_safe_view
def _status(host, tree: ttk.Treeview, *, on_done=None) -> None:
    oid = _selected_id(tree, host)
    if oid is None:
        return
    o = data.get(oid)
    if o is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — #{oid}")
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
              text=f"{o.teacher} ({o.observation_date})").pack(
        anchor="w")
    ttk.Label(frm, text=f"Current: {o.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=o.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(OBSERVATION_STATUSES),
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(oid, new_var.get())
        except ValidationError as ex:
            messagebox.showerror("Observations", str(ex),
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
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    oid = _selected_id(tree, host)
    if oid is None:
        return
    existing = data.get(oid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete observation",
            f"Delete observation #{oid} ({existing.teacher}, "
            f"{existing.observation_date})?",
            parent=host.root):
        return
    data.delete(oid)
    if on_done:
        on_done()


@_safe_view
def _summary(host) -> None:
    teacher = simpledialog.askstring(
        "Summary",
        "Teacher name (blank = cohort summary):", parent=host.root)
    if teacher and teacher.strip():
        s = data.teacher_summary(teacher.strip())
        title = f"Observations — {teacher}"
        total_line = f"Total observations for {teacher}: {s['total']}"
    else:
        s = data.cohort_summary()
        title = "Observations — cohort summary"
        total_line = (f"Total observations: {s['total']}    "
                      f"Follow-ups due: {s['follow_ups']}")
    lines = [total_line]
    if s["by_judgement"]:
        lines.append("")
        lines.append("By judgement:")
        for k, v in s["by_judgement"].items():
            lines.append(f"  {k:<22} {v}")
    if s["by_type"]:
        lines.append("")
        lines.append("By type:")
        for k, v in s["by_type"].items():
            lines.append(f"  {k:<18} {v}")
    if s["by_status"]:
        lines.append("")
        lines.append("By status:")
        for k, v in s["by_status"].items():
            lines.append(f"  {k:<12} {v}")
    messagebox.showinfo(title, "\n".join(lines), parent=host.root)
