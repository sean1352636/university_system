"""GUI panels for the Sixth Form UCAS Workflow.

Two-tab Notebook:

* Cohort — applicants for a cycle with a completion bar; double-click
  to load their pipeline.
* Pipeline — the eight-stage checklist for one student, with inline
  sign-off of manual stages.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.sixth_form.domain.progression.ucas_workflow import (
    ucas_workflow as data,
)

logger = logging.getLogger(__name__)

_STATUS_COLOUR = {
    "Complete": "#2e7d32", "In Progress": "#f9a825",
    "Pending": "#9e9e9e", "N/A": "#607d8b",
}


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))


def open_directory(gui) -> None:
    parent = _clear(gui)
    _heading(parent, "UCAS Workflow")
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)
    cohort = ttk.Frame(nb, padding=10)
    pipe = ttk.Frame(nb, padding=10)
    nb.add(cohort, text="Cohort")
    nb.add(pipe, text="Student Pipeline")

    state = {"year": data.default_cycle_year(), "sid": tk.StringVar()}
    _build_pipeline_tab(gui, pipe, state)
    _build_cohort_tab(gui, cohort, state, nb, pipe)


def _build_cohort_tab(gui, parent, state, nb, pipe) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Cycle year:").pack(side="left")
    year_var = tk.StringVar(value=str(state["year"]))
    ttk.Spinbox(bar, from_=2000, to=2100, textvariable=year_var, width=6).pack(
        side="left", padx=(4, 10))

    cols = ("student", "progress", "next")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=18)
    for c, t, w in (("student", "Student", 220), ("progress", "Progress", 110),
                    ("next", "Next stage", 240)):
        tree.heading(c, text=t)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def refresh() -> None:
        tree.delete(*tree.get_children())
        try:
            year = int(year_var.get())
        except ValueError:
            return
        for r in data.overview(year):
            tree.insert("", "end", iid=r["student_id"],
                        values=(r["full_name"],
                                f"{r['complete']}/{r['total']} ({r['percent']}%)",
                                r["next_stage"]))

    def open_pipe(_evt=None) -> None:
        sel = tree.selection()
        if sel:
            state["sid"].set(sel[0])
            state["year"] = int(year_var.get())
            nb.select(pipe)
            pipe.event_generate("<<LoadPipeline>>")

    ttk.Button(bar, text="Refresh", command=refresh).pack(side="right")
    tree.bind("<Double-1>", open_pipe)
    refresh()


def _build_pipeline_tab(gui, parent, state) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Student ID:").pack(side="left")
    entry = ttk.Entry(bar, textvariable=state["sid"], width=16)
    entry.pack(side="left", padx=(4, 8))

    body = ttk.Frame(parent)
    body.pack(fill="both", expand=True)

    def load() -> None:
        for w in body.winfo_children():
            w.destroy()
        sid = state["sid"].get().strip()
        if not sid:
            return
        try:
            p = data.get_pipeline(sid, state["year"])
        except ValueError as e:
            ttk.Label(body, text=str(e), foreground="#c62828").pack(anchor="w")
            return
        ttk.Label(body, text=f"{p['full_name']} — UCAS {p['cycle_year']}  "
                             f"({p['complete']}/{p['total']}, {p['percent']}%)",
                  font=("", 13, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Progressbar(body, maximum=100, value=p["percent"], length=300).pack(
            anchor="w", pady=(0, 10))

        for s in p["stages"]:
            row = ttk.Frame(body)
            row.pack(fill="x", pady=1)
            dot = "✓" if s["status"] == "Complete" else (
                "~" if s["status"] == "In Progress" else ("–" if s["status"] == "N/A" else "○"))
            ttk.Label(row, text=dot, width=3,
                      foreground=_STATUS_COLOUR.get(s["status"])).pack(side="left")
            txt = s["label"]
            if s["due_date"]:
                txt += f"  (due {s['due_date']})"
            if s["signed_off_by"]:
                txt += f"  ✎ {s['signed_off_by']}"
            ttk.Label(row, text=txt, width=44, anchor="w").pack(side="left")
            ttk.Label(row, text=s["status"], width=12,
                      foreground=_STATUS_COLOUR.get(s["status"])).pack(side="left")
            if not s["auto"]:
                ttk.Button(row, text="Sign off",
                           command=lambda st=s: _signoff(sid, state["year"], st, load)
                           ).pack(side="left", padx=4)
            else:
                ttk.Label(row, text="auto", foreground="#9e9e9e").pack(side="left", padx=4)

    parent.bind("<<LoadPipeline>>", lambda _e: load())
    ttk.Button(bar, text="Load", command=load).pack(side="left")
    entry.bind("<Return>", lambda _e: load())


def _signoff(sid: str, year: int, stage: dict, after) -> None:
    top = tk.Toplevel()
    top.title(f"Sign off — {stage['label']}")
    top.geometry("360x260")
    frm = ttk.Frame(top, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text=stage["label"], font=("", 12, "bold")).pack(anchor="w")
    ttk.Label(frm, text="Status:").pack(anchor="w", pady=(8, 0))
    status_var = tk.StringVar(value="Complete")
    ttk.Combobox(frm, textvariable=status_var, state="readonly",
                 values=list(data.STATUSES)).pack(fill="x")
    ttk.Label(frm, text="Signed off by:").pack(anchor="w", pady=(8, 0))
    by_var = tk.StringVar()
    ttk.Entry(frm, textvariable=by_var).pack(fill="x")
    ttk.Label(frm, text="Due date (YYYY-MM-DD):").pack(anchor="w", pady=(8, 0))
    due_var = tk.StringVar(value=stage.get("due_date") or "")
    ttk.Entry(frm, textvariable=due_var).pack(fill="x")

    def save() -> None:
        try:
            data.set_stage(sid, stage["key"], cycle_year=year,
                           status=status_var.get(), signed_off_by=by_var.get().strip() or None,
                           due_date=due_var.get().strip() or None)
        except data.ValidationError as e:
            messagebox.showerror("Sign off", str(e), parent=top)
            return
        top.destroy()
        after()

    ttk.Button(frm, text="Save", command=save).pack(pady=12)
