"""Reusable Tk dialogs for the cross-GUI services.

Each helper renders one of the views in ``_cross_services.py`` so a
caller can wire a button without rebuilding the dialog every time.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.domain.academics.gui._cross_services import (
    find_conflicts_for_module,
    find_conflicts_for_course,
    instructor_workload,
    list_instructors,
    at_risk_students_unified,
    module_timeline,
)


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------

def show_conflicts_dialog(parent: tk.Misc, *,
                          module_code: str | None = None,
                          course_code: str | None = None,
                          title: str | None = None) -> None:
    """Render the conflict report scoped to a module or course."""
    if module_code:
        rows = find_conflicts_for_module(module_code)
        scope = f"module {module_code}"
    elif course_code:
        rows = find_conflicts_for_course(course_code)
        scope = f"course {course_code}"
    else:
        messagebox.showinfo("Conflicts", "No module or course supplied.")
        return

    win = tk.Toplevel(parent)
    win.title(title or f"Schedule conflicts — {scope}")
    win.geometry("760x420")
    ttk.Label(
        win,
        text=f"Conflicts touching {scope}",
        font=("Helvetica", 12, "bold"),
    ).pack(anchor="w", padx=15, pady=(15, 5))

    if not rows:
        ttk.Label(
            win, text="No conflicts detected.",
            foreground="#27ae60",
        ).pack(padx=15, pady=20)
    else:
        cols = ("type", "severity", "description")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c, w in zip(cols, (140, 90, 480)):
            tree.heading(c, text=c.capitalize())
            tree.column(c, width=w, anchor="w")
        for r in rows:
            tree.insert("", "end", values=(
                r.get("type", ""), r.get("severity", ""), r.get("description", ""),
            ))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))


# ---------------------------------------------------------------------------
# Instructor workload
# ---------------------------------------------------------------------------

def show_instructor_workload_dialog(parent: tk.Misc,
                                    instructor_id: int | None = None) -> None:
    """Workload-for-instructor dialog — picker on top, details below."""
    win = tk.Toplevel(parent)
    win.title("Instructor Workload")
    win.geometry("780x540")

    top = ttk.Frame(win, padding=(15, 15, 15, 5))
    top.pack(fill="x")
    ttk.Label(top, text="Instructor:").pack(side="left")
    var = tk.StringVar()
    rows = list_instructors()
    items = {r["label"]: r["id"] for r in rows}
    combo = ttk.Combobox(top, textvariable=var, values=list(items),
                         state="readonly", width=55)
    combo.pack(side="left", padx=(8, 0))
    if rows:
        combo.current(0)

    body = ttk.Frame(win, padding=15)
    body.pack(fill="both", expand=True)
    summary_var = tk.StringVar(value="Pick an instructor to view workload.")
    ttk.Label(body, textvariable=summary_var, font=("Helvetica", 11)).pack(
        anchor="w", pady=(0, 8))

    notebook = ttk.Notebook(body)
    notebook.pack(fill="both", expand=True)

    slots_tab = ttk.Frame(notebook)
    notebook.add(slots_tab, text="Teaching slots")
    slots_cols = ("module_code", "day_of_week", "start_time", "end_time", "room")
    slots_tree = ttk.Treeview(slots_tab, columns=slots_cols, show="headings")
    for c, w in zip(slots_cols, (110, 110, 90, 90, 200)):
        slots_tree.heading(c, text=c.replace("_", " ").title())
        slots_tree.column(c, width=w, anchor="w")
    slots_tree.pack(fill="both", expand=True)

    panels_tab = ttk.Frame(notebook)
    notebook.add(panels_tab, text="Examiner panels")
    panel_cols = ("exam_id", "module_code", "role")
    panels_tree = ttk.Treeview(panels_tab, columns=panel_cols, show="headings")
    for c, w in zip(panel_cols, (90, 130, 160)):
        panels_tree.heading(c, text=c.replace("_", " ").title())
        panels_tree.column(c, width=w, anchor="w")
    panels_tree.pack(fill="both", expand=True)

    def reload(*_):
        instr_id = items.get(var.get())
        if not instr_id:
            return
        data = instructor_workload(instructor_id=int(instr_id))
        info = data["instructor"]
        totals = data["totals"]
        summary_var.set(
            f"{info['name']}  ·  {info['department'] or '—'}  ·  "
            f"{totals['teaching_hours_per_week']}h/week across "
            f"{totals['slot_count']} slots in {totals['modules']} modules  ·  "
            f"{totals['exam_panels']} exam panel(s)  ·  "
            f"{data['recent_grades']} grades entered (30d)"
        )
        for tree in (slots_tree, panels_tree):
            for i in tree.get_children():
                tree.delete(i)
        for s in data["teaching_slots"]:
            slots_tree.insert("", "end", values=tuple(s.get(c, "") for c in slots_cols))
        for p in data["examiner_assignments"]:
            panels_tree.insert("", "end", values=tuple(p.get(c, "") for c in panel_cols))

    combo.bind("<<ComboboxSelected>>", reload)
    if instructor_id is not None:
        for label, iid in items.items():
            if int(iid) == int(instructor_id):
                var.set(label)
                break
    reload()
    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))


# ---------------------------------------------------------------------------
# Unified at-risk list (Grade Tracking → Exam Scheduler)
# ---------------------------------------------------------------------------

def show_at_risk_dialog(parent: tk.Misc, *,
                        module_code: str | None = None,
                        threshold: int = 30) -> None:
    rows = at_risk_students_unified(module_code=module_code, threshold=threshold)
    win = tk.Toplevel(parent)
    title = "At-risk (unified)" + (f" — {module_code}" if module_code else "")
    win.title(title)
    win.geometry("820x420")
    ttk.Label(
        win,
        text=f"Students flagged ≥ {threshold} risk score "
             f"by Grade Tracking{' for ' + module_code if module_code else ''}",
        font=("Helvetica", 11, "bold"),
    ).pack(anchor="w", padx=15, pady=(15, 5))
    if not rows:
        ttk.Label(
            win, text="No students currently flagged at this threshold.",
            foreground="#27ae60",
        ).pack(padx=15, pady=20)
    else:
        cols = ("student_id", "name", "course", "risk_score", "severity",
                "detected_at", "notes")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c, w in zip(cols, (90, 180, 80, 90, 80, 150, 200)):
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=w, anchor="w")
        for r in rows:
            tree.insert("", "end", values=tuple(str(r.get(c, "")) for c in cols))
        tree.pack(fill="both", expand=True, padx=10, pady=10)
    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))


# ---------------------------------------------------------------------------
# Module timeline
# ---------------------------------------------------------------------------

def show_module_timeline_dialog(parent: tk.Misc, module_code: str) -> None:
    rows = module_timeline(module_code)
    win = tk.Toplevel(parent)
    win.title(f"Module timeline — {module_code}")
    win.geometry("820x500")
    ttk.Label(
        win,
        text=f"All scheduled events for {module_code}",
        font=("Helvetica", 12, "bold"),
    ).pack(anchor="w", padx=15, pady=(15, 5))

    if not rows:
        ttk.Label(
            win, text="No events recorded for this module.",
            foreground="#7f8c8d",
        ).pack(padx=15, pady=20)
    else:
        cols = ("kind", "date", "label", "detail")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c, w in zip(cols, (90, 110, 280, 320)):
            tree.heading(c, text=c.capitalize())
            tree.column(c, width=w, anchor="w")
        for r in rows:
            tree.insert("", "end", values=tuple(r.get(c, "") for c in cols))
        tree.pack(fill="both", expand=True, padx=10, pady=10)
    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))


__all__ = [
    "show_conflicts_dialog",
    "show_instructor_workload_dialog",
    "show_at_risk_dialog",
    "show_module_timeline_dialog",
]
