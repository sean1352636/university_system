"""GUI panel for the Sixth Form Timetable Optimiser.

Single screen: a controls bar (plan name, lessons/week, Generate &
Save), a list of saved plans, and a weekly grid preview of the
selected plan with a Commit-to-live button.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.post_16.sixthform_system.modules.domain.academics.timetable.timetable import (
    DAY_NUMBERS,
    DAYS,
    PERIODS,
)
from education_system.post_16.sixthform_system.modules.domain.academics.timetable_optimiser import (
    timetable_optimiser as data,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))


def open_directory(gui) -> None:
    parent = _clear(gui)
    _heading(parent, "Timetable Optimiser")

    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Name:").pack(side="left")
    name_var = tk.StringVar(value="Auto plan")
    ttk.Entry(bar, textvariable=name_var, width=18).pack(side="left", padx=(4, 10))
    ttk.Label(bar, text="Lessons/week:").pack(side="left")
    lpw_var = tk.StringVar(value=str(data.DEFAULT_LESSONS_PER_WEEK))
    ttk.Spinbox(bar, from_=1, to=30, textvariable=lpw_var, width=4).pack(side="left", padx=(4, 10))

    panes = ttk.Panedwindow(parent, orient="horizontal")
    panes.pack(fill="both", expand=True)

    left = ttk.Frame(panes, padding=(0, 0, 8, 0))
    right = ttk.Frame(panes)
    panes.add(left, weight=1)
    panes.add(right, weight=2)

    cols = ("id", "name", "status", "placed", "unplaced")
    plans = ttk.Treeview(left, columns=cols, show="headings", height=16)
    for c, t, w in (("id", "ID", 40), ("name", "Name", 130), ("status", "Status", 80),
                    ("placed", "Placed", 60), ("unplaced", "Unpl.", 55)):
        plans.heading(c, text=t)
        plans.column(c, width=w, anchor="w" if c == "name" else "center")
    plans.pack(fill="both", expand=True)

    grid_holder = ttk.Frame(right)
    grid_holder.pack(fill="both", expand=True)

    def refresh_plans() -> None:
        plans.delete(*plans.get_children())
        for p in data.list_plans():
            st = p["stats"]
            plans.insert("", "end", iid=str(p["plan_id"]),
                         values=(p["plan_id"], p["name"], p["status"],
                                 st.get("placed", 0), st.get("unplaced", 0)))

    def render_grid(plan_id: int) -> None:
        for w in grid_holder.winfo_children():
            w.destroy()
        slots = data.plan_slots(plan_id)
        cell_map: dict[tuple[int, int], list[str]] = {}
        for s in slots:
            label = s.group_label + (f"\n@{s.room}" if s.room else "")
            cell_map.setdefault((s.day, s.period), []).append(label)
        ttk.Label(grid_holder, text="", width=4).grid(row=0, column=0)
        for di, day in enumerate(DAY_NUMBERS):
            ttk.Label(grid_holder, text=DAYS[di], font=("", 10, "bold"),
                      borderwidth=1, relief="solid", width=18, anchor="center").grid(
                row=0, column=di + 1, sticky="nsew")
        for period in PERIODS:
            ttk.Label(grid_holder, text=f"P{period}", font=("", 10, "bold"),
                      borderwidth=1, relief="solid").grid(row=period, column=0, sticky="nsew")
            for di, day in enumerate(DAY_NUMBERS):
                txt = "\n".join(cell_map.get((day, period), []))
                ttk.Label(grid_holder, text=txt, borderwidth=1, relief="solid",
                          width=18, anchor="center", justify="center",
                          wraplength=150).grid(row=period, column=di + 1, sticky="nsew")
        for c in range(len(DAY_NUMBERS) + 1):
            grid_holder.columnconfigure(c, weight=1)

    def on_select(_evt=None) -> None:
        sel = plans.selection()
        if sel:
            render_grid(int(sel[0]))

    def generate() -> None:
        try:
            result = data.generate(lessons_per_week=int(lpw_var.get()),
                                    name=name_var.get().strip() or "Auto plan")
        except ValueError as e:
            messagebox.showerror("Optimiser", str(e))
            return
        pid = data.save_plan(result)
        msg = f"Plan #{pid}: {result.placed} slots placed."
        if result.unplaced:
            msg += f"\n{len(result.unplaced)} lesson(s) unplaced."
        if result.student_clashes:
            msg += f"\n{len(result.student_clashes)} soft student clash(es)."
        messagebox.showinfo("Optimiser", msg)
        refresh_plans()
        plans.selection_set(str(pid))
        render_grid(pid)

    def commit() -> None:
        sel = plans.selection()
        if not sel:
            messagebox.showinfo("Optimiser", "Select a plan first.")
            return
        if not messagebox.askyesno(
                "Commit plan",
                "Overwrite live timetable slots for this plan's groups?"):
            return
        try:
            n = data.commit_plan(int(sel[0]))
        except ValueError as e:
            messagebox.showerror("Optimiser", str(e))
            return
        messagebox.showinfo("Optimiser", f"Wrote {n} live timetable slots.")
        refresh_plans()

    def delete() -> None:
        sel = plans.selection()
        if sel and messagebox.askyesno("Delete", f"Delete plan #{sel[0]}?"):
            data.delete_plan(int(sel[0]))
            refresh_plans()
            for w in grid_holder.winfo_children():
                w.destroy()

    ttk.Button(bar, text="Generate & save", command=generate).pack(side="left")
    ttk.Button(bar, text="Commit to live", command=commit).pack(side="right")
    ttk.Button(bar, text="Delete", command=delete).pack(side="right", padx=(0, 6))
    plans.bind("<<TreeviewSelect>>", on_select)
    refresh_plans()
