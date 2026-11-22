"""Rollover history (with Undo) and the Year 12 → 13 return-intention
screen."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data

from .enrolment_common import (
    _clear,
    _default_academic_year,
    _heading,
    _student_name_map,
    _year_choices,
    back_to_directory,
    show_error,
)
from .enrolment_withdraw_dialog import undo_rollover_lines

logger = logging.getLogger(__name__)


def _tree(parent, cols: list[tuple[str, str, int]], height: int = 14,
          selectmode: str = "browse") -> ttk.Treeview:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    tree = ttk.Treeview(holder, columns=[c for c, _t, _w in cols],
                        show="headings", height=height, selectmode=selectmode)
    for col, text, width in cols:
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor="w")
    sb = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return tree


# ── Rollover history ────────────────────────────────────────────────

def undo_run(gui, run_id: int, *, confirm: bool = True):
    """Undo one rollover run; shows the UndoRolloverResult."""
    if confirm and not messagebox.askyesno(
            "Undo rollover",
            f"Undo rollover run #{run_id}?\n\nThe Year 13 enrolments it "
            "created are archived, the ones it completed go back to Enrolled "
            "and the aims it completed are reopened. Rows changed since the "
            "run are left alone and listed.", parent=gui.root):
        return None
    try:
        result = data.undo_rollover(run_id)
    except Exception as exc:  # ValidationError / AccessDenied / DB
        show_error(gui.root, "Could not undo rollover", exc)
        return None
    (messagebox.showwarning if result.kept or result.aim_problems
     else messagebox.showinfo)("Rollover undone",
                               "\n".join(undo_rollover_lines(result)),
                               parent=gui.root)
    gui.status_var.set(f"Undid rollover run #{run_id}")
    return result


def open_rollover_history(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Rollover History")
    ttk.Label(frame, foreground="#555", wraplength=900, justify="left", text=(
        "Every rollover run, newest first. Undo puts a run back; a later run "
        "must be undone first.")).pack(anchor="w", pady=(0, 6))
    bar = ttk.Frame(frame)
    bar.pack(side="bottom", anchor="w", pady=(8, 0))
    tree = _tree(frame, [("run", "Run", 50), ("from", "From", 80),
                         ("to", "To", 80), ("at", "Run at", 150),
                         ("by", "By", 100), ("completed", "Completed", 90),
                         ("created", "Created", 80), ("restored", "Restored", 80),
                         ("aims", "Aims completed", 110),
                         ("undone", "Undone", 220)])

    def fill() -> None:
        tree.delete(*tree.get_children())
        try:
            runs = data.list_rollovers()
        except Exception as exc:  # noqa: BLE001 — shown
            show_error(gui.root, "Rollover history", exc)
            return
        for r in runs:
            undone = (f"{r['undone_at']} by {r.get('undone_by') or '—'}"
                      if r.get("undone_at") else "")
            tree.insert("", "end", iid=str(r["run_id"]), values=(
                r["run_id"], r["from_year"], r["to_year"], r.get("run_at") or "",
                r.get("run_by") or "—", r.get("completed", 0),
                r.get("created", 0), r.get("restored", 0),
                r.get("aims_completed", 0), undone))
        gui.status_var.set(f"{len(runs)} rollover run(s)")

    def undo() -> None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Undo rollover", "Pick a run first.",
                                parent=gui.root)
            return
        if undo_run(gui, int(sel[0])) is not None:
            fill()

    ttk.Button(bar, text="Undo Selected Run", command=undo,
               state="normal" if data.can_write() else "disabled"
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Refresh", command=fill).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(side="left")
    fill()


# ── Return intentions ───────────────────────────────────────────────

def open_return_intentions(gui, academic_year: str | None = None) -> None:
    """Year 12 learners of a year and their answer to "coming back for
    Year 13?", with counts; set one or many."""
    from .enrolment_bulk_actions import open_bulk_return_intention

    frame = _clear(gui)
    _heading(frame, "Year 12 Return Intentions")
    year_var = tk.StringVar(value=academic_year or _default_academic_year())
    top = ttk.Frame(frame)
    top.pack(anchor="w", pady=(0, 6))
    ttk.Label(top, text="Academic year:").pack(side="left")
    box = ttk.Combobox(top, textvariable=year_var, values=_year_choices(),
                       state="readonly", width=10)
    box.pack(side="left", padx=(4, 12))
    summary = ttk.Label(top, foreground="#555")
    summary.pack(side="left")
    bar = ttk.Frame(frame)
    bar.pack(side="bottom", anchor="w", pady=(8, 0))
    tree = _tree(frame, [("id", "#", 50), ("sid", "Student", 90),
                         ("name", "Name", 200), ("tutor", "Tutor", 70),
                         ("status", "Status", 90), ("intent", "Intention", 110),
                         ("note", "Note", 320)], selectmode="extended")

    def fill() -> None:
        tree.delete(*tree.get_children())
        year = year_var.get().strip()
        try:
            rows = data.list_enrolments(academic_year=year, year_group=12)
            counts = data.reintention_summary(year)
        except Exception as exc:  # noqa: BLE001 — shown
            show_error(gui.root, "Return intentions", exc)
            return
        names = _student_name_map()
        for e in rows:
            tree.insert("", "end", iid=str(e.enrolment_id), values=(
                e.enrolment_id, e.student_id, names.get(e.student_id, "—"),
                e.tutor_group or "—", e.status, e.return_intention or "—",
                e.return_intention_note or ""))
        summary.configure(text="Enrolled Year 12s — " + ", ".join(
            f"{k}: {v}" for k, v in counts.items()))
        gui.status_var.set(f"Return intentions {year}: {len(rows)} Year 12 row(s)")

    def set_selected() -> None:
        ids = [int(i) for i in tree.selection()]
        if not ids:
            messagebox.showinfo("Return intention", "Pick one or more rows "
                                "first.", parent=gui.root)
            return
        open_bulk_return_intention(gui, ids, after=lambda: open_return_intentions(
            gui, year_var.get().strip()))

    box.bind("<<ComboboxSelected>>", lambda _e: fill())
    ttk.Button(bar, text="Set Intention…", command=set_selected,
               state="normal" if data.can_write() else "disabled"
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Refresh", command=fill).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(side="left")
    fill()
