"""Integrations manager — surfaces parent_portal / library / attendance
data inside the assignment GUI.

Other managers (submission, grading, dashboard) call into this rather
than re-fetching, so the cross-domain dependency lives in one place.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.domain.academics.gui.assignment_system.integrations import (
    fetch_child_assignments,
    fetch_parent_children,
    fetch_module_resources,
    fetch_module_attendance,
    fetch_attendance_warning,
)


class IntegrationsManager:
    """Dialogs + helpers wiring assignment GUI into other domains."""

    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth

    # ------------------------------------------------------------------
    # Library
    # ------------------------------------------------------------------

    def show_module_resources(self, module_code: str, student_id=None):
        """Open a dialog listing reading-list items for ``module_code``."""
        if not module_code:
            messagebox.showinfo("Resources", "No module selected.")
            return

        data = fetch_module_resources(module_code, student_id=student_id)
        win = tk.Toplevel(self.root)
        win.title(f"Resources — {module_code}")
        win.geometry("700x500")

        header = ttk.Label(
            win,
            text=f"Library resources for {module_code}",
            font=("Helvetica", 13, "bold"),
        )
        header.pack(anchor="w", padx=15, pady=(15, 5))

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Reading list items
        items_tab = ttk.Frame(nb)
        nb.add(items_tab, text=f"Reading List ({len(data['items'])})")
        cols = ("list", "title", "author", "notes")
        items_tree = ttk.Treeview(items_tab, columns=cols, show="headings")
        for c, w in zip(cols, (160, 220, 140, 180)):
            items_tree.heading(c, text=c.capitalize())
            items_tree.column(c, width=w, anchor="w")
        for it in data["items"]:
            items_tree.insert(
                "", "end",
                values=(
                    it.get("list_name", ""),
                    it.get("title") or it.get("book_id") or "",
                    it.get("author") or "",
                    (it.get("notes") or "")[:120],
                ),
            )
        items_tree.pack(fill="both", expand=True)
        if not data["items"]:
            ttk.Label(
                items_tab,
                text="No reading-list items linked to this module yet.",
                foreground="#7f8c8d",
            ).pack(pady=20)

        # Recommendations
        rec_tab = ttk.Frame(nb)
        nb.add(
            rec_tab,
            text=f"Recommendations ({len(data['recommendations'])})",
        )
        if data["recommendations"]:
            cols = ("title", "author", "confidence", "type")
            rec_tree = ttk.Treeview(rec_tab, columns=cols, show="headings")
            for c, w in zip(cols, (260, 160, 100, 120)):
                rec_tree.heading(c, text=c.capitalize())
                rec_tree.column(c, width=w, anchor="w")
            for r in data["recommendations"]:
                conf = r.get("confidence_score")
                rec_tree.insert(
                    "", "end",
                    values=(
                        r.get("title") or r.get("book_id") or "",
                        r.get("author") or "",
                        f"{conf:.2f}" if isinstance(conf, (int, float)) else "",
                        r.get("recommendation_type") or "",
                    ),
                )
            rec_tree.pack(fill="both", expand=True)
        else:
            ttk.Label(
                rec_tab,
                text=(
                    "No personalised recommendations available."
                    if student_id
                    else "Sign in as a student to see personalised recommendations."
                ),
                foreground="#7f8c8d",
            ).pack(pady=20)

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))

    # ------------------------------------------------------------------
    # Attendance
    # ------------------------------------------------------------------

    def show_student_attendance(self, student_id, module_code: str):
        """Open a dialog with the student's attendance for the module."""
        if not student_id or not module_code:
            messagebox.showinfo(
                "Attendance",
                "Need both a student and a module to look up attendance.",
            )
            return

        summary = fetch_module_attendance(student_id, module_code)
        win = tk.Toplevel(self.root)
        win.title(f"Attendance — {student_id} / {module_code}")
        win.geometry("420x220")

        ttk.Label(
            win,
            text=f"Attendance for {student_id} in {module_code}",
            font=("Helvetica", 12, "bold"),
        ).pack(anchor="w", padx=15, pady=(15, 10))

        if not summary:
            ttk.Label(
                win,
                text="No attendance records found for this student/module.",
                foreground="#7f8c8d",
            ).pack(padx=15, pady=10)
        else:
            pct = summary["percentage"]
            colour = "#27ae60" if pct >= 75 else "#c0392b"
            ttk.Label(
                win,
                text=f"Sessions attended: {summary['attended']} / {summary['total_sessions']}",
            ).pack(anchor="w", padx=15, pady=2)
            tk.Label(
                win,
                text=f"Attendance: {pct:.1f}%",
                fg=colour,
                font=("Helvetica", 14, "bold"),
            ).pack(anchor="w", padx=15, pady=(2, 8))

            warning = fetch_attendance_warning(student_id, module_code)
            if warning:
                tk.Label(
                    win,
                    text=warning,
                    fg="#c0392b",
                    wraplength=380,
                    justify="left",
                ).pack(anchor="w", padx=15, pady=(0, 8))

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))

    def attendance_warning(self, student_id, module_code: str) -> str | None:
        """Convenience pass-through for managers that just want the string."""
        return fetch_attendance_warning(student_id, module_code)

    # ------------------------------------------------------------------
    # Parent portal
    # ------------------------------------------------------------------

    def show_parent_assignments_view(self):
        """Parent-only dashboard: pick a child, list their assignments."""
        user = self.auth.current_user if self.auth else None
        if not user:
            messagebox.showerror("Parent View", "You must be logged in.")
            return
        role = (user.get("role") or "").lower()
        if role != "parent":
            messagebox.showinfo(
                "Parent View",
                "This dashboard is only available for parent accounts.",
            )
            return

        children = fetch_parent_children(user.get("id"))
        win = tk.Toplevel(self.root)
        win.title("My Children — Assignments")
        win.geometry("760x520")

        ttk.Label(
            win,
            text="Children's Assignments",
            font=("Helvetica", 13, "bold"),
        ).pack(anchor="w", padx=15, pady=(15, 5))

        if not children:
            ttk.Label(
                win,
                text="No children registered to this parent account.",
                foreground="#7f8c8d",
            ).pack(padx=15, pady=20)
            return

        top = ttk.Frame(win)
        top.pack(fill="x", padx=15, pady=5)
        ttk.Label(top, text="Child:").pack(side="left")
        child_map = {
            f"{c['first_name']} {c['last_name']} ({c['student_id']})": c
            for c in children
        }
        var = tk.StringVar()
        combo = ttk.Combobox(
            top,
            textvariable=var,
            values=list(child_map.keys()),
            state="readonly",
            width=50,
        )
        combo.pack(side="left", padx=(8, 0))
        combo.current(0)

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=15, pady=10)
        trees: dict[str, ttk.Treeview] = {}
        for key, label in (
            ("upcoming", "Upcoming"),
            ("overdue", "Overdue"),
            ("completed", "Recent Completed"),
        ):
            tab = ttk.Frame(nb)
            nb.add(tab, text=label)
            cols = ("module", "title", "due_date", "status")
            tree = ttk.Treeview(tab, columns=cols, show="headings")
            for c, w in zip(cols, (140, 320, 150, 120)):
                tree.heading(c, text=c.replace("_", " ").capitalize())
                tree.column(c, width=w, anchor="w")
            tree.pack(fill="both", expand=True)
            trees[key] = tree

        def reload(*_):
            child = child_map.get(var.get())
            if not child or child.get("access_level") == "minimal":
                for t in trees.values():
                    for i in t.get_children():
                        t.delete(i)
                return
            data = fetch_child_assignments(child["student_id"])
            for key, tree in trees.items():
                for i in tree.get_children():
                    tree.delete(i)
                for row in data[key]:
                    tree.insert(
                        "", "end",
                        values=(
                            f"{row.get('module_code', '')} — {row.get('module_name', '')}",
                            row.get("title", ""),
                            row.get("due_date", ""),
                            row.get("status", ""),
                        ),
                    )

        combo.bind("<<ComboboxSelected>>", reload)
        reload()
