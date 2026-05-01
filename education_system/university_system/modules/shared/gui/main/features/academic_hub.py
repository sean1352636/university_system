"""Academic Operations Hub — landing dashboard for the 6 linked modules.

Shows a tile grid + a numbered workflow (plan → schedule → run → track).
Each tile / workflow step opens the matching module via the parent
``UnifiedManagementGUI``.
"""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.shared.gui.main.features.academic_link_bar import (
    _dispatch,
    attach_quickbar,
)

logger = logging.getLogger(__name__)


_TILES = [
    ("🎓", "Course Management",
     "Define and edit courses",
     "show_course_management"),
    ("🗓", "Module Scheduling",
     "Place modules into rooms and timeslots",
     "show_module_scheduling"),
    ("📅", "Timetable",
     "Student / staff weekly view",
     "show_student_timetable_gui"),
    ("🏢", "Building Management",
     "Buildings, rooms, utilities, maintenance",
     "show_new_feature_building_management"),
    ("✅", "Attendance",
     "Record and review attendance",
     "open_attendance_gui"),
    ("🤝", "Study Matching",
     "Pair students into study groups",
     "show_study_matching_gui"),
]

_WORKFLOW = [
    ("1. Set up the course",
     "Open Course Management to add or edit a course.",
     "show_course_management"),
    ("2. Schedule its modules",
     "Open Module Scheduling and place each module into a room and "
     "timeslot.",
     "show_module_scheduling"),
    ("3. Confirm rooms exist",
     "Open Building Management to verify the room is registered "
     "and available.",
     "show_new_feature_building_management"),
    ("4. Publish timetable",
     "Open Timetable to confirm student/staff schedules look right.",
     "show_student_timetable_gui"),
    ("5. Track attendance",
     "Open Attendance once each session has run.",
     "open_attendance_gui"),
    ("6. (Optional) Match study groups",
     "Open Study Matching to pair students within the cohort.",
     "show_study_matching_gui"),
]


def show_academic_hub(self):
    """Open the Academic Operations Hub as a Toplevel window."""
    try:
        win = tk.Toplevel(self.root)
        win.title("Academic Operations Hub")
        win.geometry("1100x780")
        win.minsize(900, 520)
        try:
            win.transient(self.root)
        except Exception:
            pass

        attach_quickbar(win, self, current="hub")

        header = tk.Frame(win, bg="#2c3e50", height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🏛 Academic Operations Hub",
                 font=("Arial", 16, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=16)
        tk.Label(header, text="Plan → Schedule → Run → Track",
                 font=("Arial", 10, "italic"),
                 bg="#2c3e50", fg="#bdc3c7").pack(side="right", padx=16)

        body = ttk.Frame(win, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # ---- Tile grid -----------------------------------------------------
        tiles = ttk.LabelFrame(body, text="Modules", padding=10)
        tiles.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        for c in range(3):
            tiles.columnconfigure(c, weight=1)
        for r in range(2):
            tiles.rowconfigure(r, weight=1)

        for idx, (emoji, name, desc, attr) in enumerate(_TILES):
            r, c = divmod(idx, 3)
            tile = tk.Frame(tiles, bg="#ecf0f1", bd=1, relief="solid",
                            cursor="hand2")
            tile.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            tk.Label(tile, text=emoji, font=("Arial", 28),
                     bg="#ecf0f1").pack(pady=(12, 0))
            tk.Label(tile, text=name, font=("Arial", 11, "bold"),
                     bg="#ecf0f1", fg="#2c3e50").pack()
            tk.Label(tile, text=desc, font=("Arial", 9),
                     wraplength=180, justify="center",
                     bg="#ecf0f1", fg="#7f8c8d").pack(pady=(2, 12), padx=8)
            for w in (tile, *tile.winfo_children()):
                w.bind("<Button-1>",
                       lambda e, a=attr: _dispatch(self, a))
                w.bind("<Enter>", lambda e, t=tile: t.configure(bg="#d5dbdb"))
                w.bind("<Leave>", lambda e, t=tile: t.configure(bg="#ecf0f1"))

        # ---- Workflow (scrollable so step 6 isn't clipped on short displays)
        wf = ttk.LabelFrame(body, text="Suggested workflow", padding=4)
        wf.grid(row=0, column=1, sticky="nsew")
        wf.columnconfigure(0, weight=1)
        wf.rowconfigure(0, weight=1)

        wf_canvas = tk.Canvas(wf, highlightthickness=0,
                              borderwidth=0)
        wf_canvas.grid(row=0, column=0, sticky="nsew")
        wf_sb = ttk.Scrollbar(wf, orient="vertical",
                              command=wf_canvas.yview)
        wf_sb.grid(row=0, column=1, sticky="ns")
        wf_canvas.configure(yscrollcommand=wf_sb.set)

        wf_inner = ttk.Frame(wf_canvas, padding=6)
        wf_window = wf_canvas.create_window(
            (0, 0), window=wf_inner, anchor="nw")

        def _wf_resize_inner(_e):
            wf_canvas.configure(scrollregion=wf_canvas.bbox("all"))
        wf_inner.bind("<Configure>", _wf_resize_inner)

        def _wf_resize_canvas(e):
            wf_canvas.itemconfig(wf_window, width=e.width)
        wf_canvas.bind("<Configure>", _wf_resize_canvas)

        # Mousewheel scrolling while pointer is over the workflow.
        def _wf_on_mousewheel(e):
            wf_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        wf_canvas.bind(
            "<Enter>",
            lambda e: wf_canvas.bind_all("<MouseWheel>", _wf_on_mousewheel))
        wf_canvas.bind(
            "<Leave>",
            lambda e: wf_canvas.unbind_all("<MouseWheel>"))

        for step, hint, attr in _WORKFLOW:
            row = ttk.Frame(wf_inner)
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=step,
                      font=("Arial", 10, "bold")).pack(anchor="w")
            ttk.Label(row, text=hint, font=("Arial", 9),
                      foreground="#555", wraplength=300,
                      justify="left").pack(anchor="w")
            ttk.Button(row, text="Open →",
                       command=(lambda a=attr: _dispatch(self, a))).pack(
                anchor="e", pady=(2, 4))
    except Exception:
        logger.exception("show_academic_hub failed")
        try:
            messagebox.showerror("Hub", "Could not open Academic Hub.")
        except Exception:
            pass
