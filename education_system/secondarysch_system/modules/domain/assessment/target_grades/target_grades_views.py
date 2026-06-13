"""Tk views for target grades."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.assessment.target_grades import (
    target_grades as data,
)
from education_system.secondarysch_system.modules.domain.assessment.target_grades.target_grades import (
    GRADE_SOURCES,
)
from education_system.secondarysch_system.modules.domain.academics.subjects import (
    subjects as subjects_data,
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
                messagebox.showerror("Target Grades", str(e),
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


def _target_dialog(host, title: str,
                   initial: dict[str, Any] | None = None
                   ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x440")
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
    target_var = tk.StringVar(value=str(initial.get("target_grade") or ""))
    min_var    = tk.StringVar(value=str(initial.get("minimum_grade") or ""))
    asp_var    = tk.StringVar(value=str(initial.get("aspirational_grade")
                                          or ""))
    src_var    = tk.StringVar(value=str(initial.get("source") or "Teacher"))
    setby_var  = tk.StringVar(value=str(initial.get("set_by") or ""))
    date_var   = tk.StringVar(value=str(initial.get("set_date") or ""))

    try:
        subjects = subjects_data.list_all(active_only=True)
    except Exception:
        subjects = []
    subject_labels = [f"#{s.subject_id} {s.code} — {s.name}"
                      for s in subjects]
    subject_var = tk.StringVar(value="")
    initial_sid = initial.get("subject_id")
    if initial_sid is not None:
        for s in subjects:
            if s.subject_id == int(initial_sid):
                subject_var.set(f"#{s.subject_id} {s.code} — {s.name}")
                break

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:", ttk.Entry(frm, textvariable=pupil_var, width=14,
                                  state=("readonly" if initial.get("pupil_id")
                                          else "normal"))),
        ("Subject:",  ttk.Combobox(frm, textvariable=subject_var,
                                    values=subject_labels,
                                    state="readonly", width=42)),
        ("Target grade:",       ttk.Entry(frm, textvariable=target_var,
                                            width=8)),
        ("Minimum grade:",      ttk.Entry(frm, textvariable=min_var,
                                            width=8)),
        ("Aspirational grade:", ttk.Entry(frm, textvariable=asp_var,
                                            width=8)),
        ("Source:",   ttk.Combobox(frm, textvariable=src_var,
                                    values=list(GRADE_SOURCES),
                                    state="readonly", width=14)),
        ("Set by:",   ttk.Entry(frm, textvariable=setby_var, width=24)),
        ("Set date:", ttk.Entry(frm, textvariable=date_var, width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Notes:").grid(row=len(rows), column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=40, height=4, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _parse_subject(label: str) -> str:
        label = (label or "").strip()
        if not label.startswith("#"):
            return ""
        return label.split()[0][1:]

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":           pupil_var.get().strip(),
            "subject_id":         _parse_subject(subject_var.get()),
            "target_grade":       target_var.get().strip(),
            "minimum_grade":      min_var.get().strip(),
            "aspirational_grade": asp_var.get().strip(),
            "source":             src_var.get().strip(),
            "set_by":             setby_var.get().strip(),
            "set_date":           date_var.get().strip(),
            "notes":              notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_target_grades(host) -> None:
    logger.debug("GUI: open_target_grades")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Target Grades",
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
    ttk.Label(bar, text="Source:").pack(side="left", padx=(0, 4))
    src_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=src_var,
                 values=["", *GRADE_SOURCES], state="readonly",
                 width=10).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New / update",
               command=lambda: _new(host, on_done=_refresh)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "pupil", "year", "name", "subj", "target", "min",
            "asp", "source", "set")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 90),
        ("year", "Yr", 50), ("name", "Name", 180),
        ("subj", "Subj", 80), ("target", "Target", 70),
        ("min", "Min", 60), ("asp", "Asp", 60),
        ("source", "Source", 100), ("set", "Set on", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_targets(
                year_group=year_var.get().strip() or None,
                pupil_id=pupil_var.get().strip() or None,
                source=src_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Target Grades", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("targets refresh failed")
            messagebox.showerror("Target Grades",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for t in rows:
            tree.insert("", "end", iid=str(t.target_id), values=(
                t.target_id, t.pupil_id, t.pupil_year or "-",
                t.pupil_name or "-", t.subject_code or "?",
                t.target_grade, t.minimum_grade or "-",
                t.aspirational_grade or "-", t.source, t.set_date,
            ))
        summary_var.set(f"{len(rows)} target(s) listed")
        host.status_var.set(f"Target Grades: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    src_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Target Grades",
                            "Select a target first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _target_dialog(host, "Set target grade")
    if not fields:
        return
    rec = data.upsert(fields)
    messagebox.showinfo(
        "Target Grades",
        f"Saved {rec.pupil_id} / {rec.subject_code} = {rec.target_grade}",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    tid = _selected_id(tree, host)
    if tid is None:
        return
    existing = data.get(tid)
    if existing is None:
        return
    initial = {
        "pupil_id": existing.pupil_id,
        "subject_id": existing.subject_id,
        "target_grade": existing.target_grade,
        "minimum_grade": existing.minimum_grade,
        "aspirational_grade": existing.aspirational_grade,
        "source": existing.source, "set_by": existing.set_by,
        "set_date": existing.set_date, "notes": existing.notes,
    }
    fields = _target_dialog(host, f"Edit target #{tid}", initial=initial)
    if not fields:
        return
    data.upsert(fields)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    tid = _selected_id(tree, host)
    if tid is None:
        return
    existing = data.get(tid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete target",
            f"Delete target for {existing.pupil_id} / "
            f"{existing.subject_code}?",
            parent=host.root):
        return
    data.delete(tid)
    if on_done:
        on_done()
