"""Staff Onboarding GUI module."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.onboarding.services.onboarding_service import (
    OnboardingService,
)


# ── Dialogs ─────────────────────────────────────────────────────

class _ChecklistDialog(tk.Toplevel):
    """Dialog for creating / editing an onboarding checklist."""

    def __init__(self, parent, title="Checklist", item=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._item = item or {}
        self._build()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px - w // 2}+{py - h // 2}")

    def _build(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)
        self._vars: dict[str, tk.StringVar] = {}

        fields = [
            ("staff_id", "Staff ID"),
            ("start_date", "Start Date (YYYY-MM-DD)"),
            ("mentor_id", "Mentor ID"),
            ("probation_end_date", "Probation End Date"),
            ("notes", "Notes"),
        ]
        for row, (key, label) in enumerate(fields):
            tk.Label(c, text=label, anchor="w", font=("Helvetica", 9, "bold")).grid(
                row=row, column=0, sticky="w", **pad
            )
            var = tk.StringVar(value=str(self._item.get(key, "") or ""))
            ttk.Entry(c, textvariable=var, width=36).grid(
                row=row, column=1, sticky="ew", **pad
            )
            self._vars[key] = var

        btn = tk.Frame(c)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class _TaskDialog(tk.Toplevel):
    """Dialog for creating / editing an onboarding task."""

    CATEGORIES = [
        "general", "it_setup", "hr_paperwork", "induction",
        "training", "safeguarding", "department", "health_safety",
    ]

    def __init__(self, parent, title="Task", item=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._item = item or {}
        self._build()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px - w // 2}+{py - h // 2}")

    def _build(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)
        self._vars: dict[str, tk.StringVar] = {}

        row = 0
        tk.Label(c, text="Checklist ID", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=str(self._item.get("checklist_id", "") or ""))
        ttk.Entry(c, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
        self._vars["checklist_id"] = var

        row += 1
        tk.Label(c, text="Task Name", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=str(self._item.get("task_name", "") or ""))
        ttk.Entry(c, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
        self._vars["task_name"] = var

        row += 1
        tk.Label(c, text="Category", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=str(self._item.get("category", "general") or "general"))
        ttk.Combobox(c, textvariable=var, values=self.CATEGORIES, width=34,
                     state="readonly").grid(row=row, column=1, sticky="ew", **pad)
        self._vars["category"] = var

        row += 1
        tk.Label(c, text="Assigned To (ID)", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=str(self._item.get("assigned_to", "") or ""))
        ttk.Entry(c, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
        self._vars["assigned_to"] = var

        row += 1
        tk.Label(c, text="Due Date (YYYY-MM-DD)", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=str(self._item.get("due_date", "") or ""))
        ttk.Entry(c, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
        self._vars["due_date"] = var

        row += 1
        tk.Label(c, text="Notes", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=str(self._item.get("notes", "") or ""))
        ttk.Entry(c, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
        self._vars["notes"] = var

        row += 1
        btn = tk.Frame(c)
        btn.grid(row=row, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class _ReviewDialog(tk.Toplevel):
    """Dialog for creating / editing a probation review."""

    RECOMMENDATIONS = ["continue", "extend", "pass", "fail"]

    def __init__(self, parent, title="Review", item=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._item = item or {}
        self._build()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px - w // 2}+{py - h // 2}")

    def _build(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)
        self._vars: dict[str, tk.StringVar] = {}

        fields = [
            ("checklist_id", "Checklist ID", None),
            ("review_date", "Review Date (YYYY-MM-DD)", None),
            ("reviewer_id", "Reviewer ID", None),
            ("review_number", "Review Number", None),
            ("performance_rating", "Performance Rating", None),
            ("areas_of_strength", "Areas of Strength", None),
            ("areas_for_development", "Areas for Development", None),
            ("targets", "Targets", None),
            ("recommendation", "Recommendation", self.RECOMMENDATIONS),
        ]
        for row, (key, label, options) in enumerate(fields):
            tk.Label(c, text=label, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            default = str(self._item.get(key, "") or "")
            if key == "recommendation" and not default:
                default = "continue"
            if key == "review_number" and not default:
                default = "1"
            var = tk.StringVar(value=default)
            if options:
                ttk.Combobox(c, textvariable=var, values=options, width=34,
                             state="readonly").grid(row=row, column=1, sticky="ew", **pad)
            else:
                ttk.Entry(c, textvariable=var, width=36).grid(
                    row=row, column=1, sticky="ew", **pad
                )
            self._vars[key] = var

        btn = tk.Frame(c)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class _DetailDialog(tk.Toplevel):
    """Read-only dialog showing all fields of a record."""

    def __init__(self, parent, title, data: dict):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)
        for row, (k, v) in enumerate(data.items()):
            tk.Label(c, text=f"{k}:", anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", padx=10, pady=3)
            tk.Label(c, text=str(v or ""), anchor="w",
                     font=("Helvetica", 9)).grid(row=row, column=1, sticky="w", padx=10, pady=3)
        ttk.Button(c, text="Close", command=self.destroy).grid(
            row=len(data), column=0, columnspan=2, pady=(15, 0)
        )
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px - w // 2}+{py - h // 2}")


# ── Main Frame ──────────────────────────────────────────────────

class OnboardingFrame(tk.Frame):
    """Staff Onboarding management frame with tabbed interface."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = OnboardingService(db_path)
        self._build_ui()
        self.refresh()

    # ── UI Construction ─────────────────────────────────────────

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Staff Onboarding",
            font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_checklists_tab()
        self._build_tasks_tab()
        self._build_reviews_tab()
        self._build_stats_tab()

    # ── Tab 0: Checklists ───────────────────────────────────────

    def _build_checklists_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Checklists")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))
        tk.Label(filt, text="Status:", bg="#ecf0f1",
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(0, 5))
        self._cl_status_var = tk.StringVar(value="All")
        ttk.Combobox(
            filt, textvariable=self._cl_status_var, width=14, state="readonly",
            values=["All", "in_progress", "completed", "extended", "failed"],
        ).pack(side="left", padx=2)
        ttk.Button(filt, text="Filter", command=self._load_checklists).pack(side="left", padx=4)

        # Buttons
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))
        for txt, cmd in [
            ("New", self._on_new_checklist),
            ("View", self._on_view_checklist),
            ("Update", self._on_update_checklist),
            ("Complete", self._on_complete_checklist),
            ("Delete", self._on_delete_checklist),
            ("Refresh", self._load_checklists),
        ]:
            ttk.Button(toolbar, text=txt, command=cmd).pack(side="left", padx=3)

        # Treeview
        cols = ("id", "staff_id", "start_date", "mentor_id",
                "probation_end_date", "probation_outcome", "overall_status")
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        self._tree_cl = ttk.Treeview(
            tree_frame, columns=cols, show="headings", selectmode="browse",
        )
        headings = {
            "id": ("ID", 40), "staff_id": ("Staff ID", 70),
            "start_date": ("Start Date", 90), "mentor_id": ("Mentor ID", 70),
            "probation_end_date": ("Probation End", 100),
            "probation_outcome": ("Outcome", 90),
            "overall_status": ("Status", 90),
        }
        for col, (text, width) in headings.items():
            self._tree_cl.heading(col, text=text)
            self._tree_cl.column(col, width=width, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree_cl.yview)
        self._tree_cl.configure(yscrollcommand=vsb.set)
        self._tree_cl.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._cl_status = tk.StringVar(value="Ready")
        tk.Label(tab, textvariable=self._cl_status, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x")

    def _load_checklists(self):
        self._tree_cl.delete(*self._tree_cl.get_children())
        try:
            status = self._cl_status_var.get()
            status_filter = None if status == "All" else status
            items = self._svc.list_checklists(status=status_filter)
            for item in items:
                self._tree_cl.insert("", "end", iid=item["id"], values=(
                    item.get("id", ""),
                    item.get("staff_id", ""),
                    item.get("start_date", ""),
                    item.get("mentor_id", ""),
                    item.get("probation_end_date", ""),
                    item.get("probation_outcome", ""),
                    item.get("overall_status", ""),
                ))
            self._cl_status.set(f"{len(items)} checklist(s) loaded")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load checklists:\n{exc}")

    def _selected_cl_id(self) -> int | None:
        sel = self._tree_cl.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a checklist first.")
            return None
        return int(sel[0])

    def _on_new_checklist(self):
        dlg = _ChecklistDialog(self, title="New Checklist")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            staff_id = int(data.pop("staff_id"))
            clean = {k: v for k, v in data.items() if v}
            self._svc.create_checklist(staff_id, **clean)
            messagebox.showinfo("Success", "Checklist created.")
            self._load_checklists()
        except ValueError:
            messagebox.showerror("Error", "Staff ID must be a number.")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_view_checklist(self):
        pk = self._selected_cl_id()
        if pk is None:
            return
        item = self._svc.get_checklist(pk)
        if not item:
            messagebox.showerror("Error", "Checklist not found.")
            return
        _DetailDialog(self, "Checklist Details", item)

    def _on_update_checklist(self):
        pk = self._selected_cl_id()
        if pk is None:
            return
        item = self._svc.get_checklist(pk)
        if not item:
            messagebox.showerror("Error", "Checklist not found.")
            return
        dlg = _ChecklistDialog(self, title="Update Checklist", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            clean = {k: v for k, v in dlg.result.items() if v}
            self._svc.update_checklist(pk, **clean)
            messagebox.showinfo("Success", "Checklist updated.")
            self._load_checklists()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_complete_checklist(self):
        pk = self._selected_cl_id()
        if pk is None:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Complete Checklist")
        dlg.resizable(False, False)
        dlg.grab_set()
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        tk.Label(c, text="Outcome:", font=("Helvetica", 9, "bold")).pack(anchor="w")
        var = tk.StringVar(value="completed")
        ttk.Combobox(
            c, textvariable=var, values=["completed", "extended", "failed"],
            state="readonly", width=20,
        ).pack(pady=5)

        def _save():
            try:
                self._svc.complete_checklist(pk, outcome=var.get())
                messagebox.showinfo("Success", "Checklist completed.")
                dlg.destroy()
                self._load_checklists()
            except Exception as exc:
                messagebox.showerror("Error", str(exc))

        ttk.Button(c, text="Save", command=_save).pack(pady=(10, 0))
        dlg.update_idletasks()
        px = self.winfo_rootx() + self.winfo_width() // 2
        py = self.winfo_rooty() + self.winfo_height() // 2
        w, h = dlg.winfo_width(), dlg.winfo_height()
        dlg.geometry(f"+{px - w // 2}+{py - h // 2}")

    def _on_delete_checklist(self):
        pk = self._selected_cl_id()
        if pk is None:
            return
        if not messagebox.askyesno(
            "Confirm", "Delete this checklist and all its tasks/reviews?"
        ):
            return
        try:
            self._svc.delete_checklist(pk)
            messagebox.showinfo("Success", "Checklist deleted.")
            self._load_checklists()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    # ── Tab 1: Tasks ────────────────────────────────────────────

    def _build_tasks_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Tasks")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text="Checklist ID:", bg="#ecf0f1",
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(0, 3))
        self._task_cl_var = tk.StringVar()
        ttk.Entry(filt, textvariable=self._task_cl_var, width=8).pack(side="left", padx=2)

        tk.Label(filt, text="Category:", bg="#ecf0f1",
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(10, 3))
        self._task_cat_var = tk.StringVar(value="All")
        ttk.Combobox(
            filt, textvariable=self._task_cat_var, width=14, state="readonly",
            values=["All", "general", "it_setup", "hr_paperwork", "induction",
                    "training", "safeguarding", "department", "health_safety"],
        ).pack(side="left", padx=2)

        tk.Label(filt, text="Completed:", bg="#ecf0f1",
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(10, 3))
        self._task_done_var = tk.StringVar(value="All")
        ttk.Combobox(
            filt, textvariable=self._task_done_var, width=8, state="readonly",
            values=["All", "Yes", "No"],
        ).pack(side="left", padx=2)

        ttk.Button(filt, text="Filter", command=self._load_tasks).pack(side="left", padx=6)

        # Buttons
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))
        for txt, cmd in [
            ("New", self._on_new_task),
            ("Complete", self._on_complete_task),
            ("Update", self._on_update_task),
            ("Delete", self._on_delete_task),
            ("Show Pending", self._on_show_pending),
            ("Refresh", self._load_tasks),
        ]:
            ttk.Button(toolbar, text=txt, command=cmd).pack(side="left", padx=3)

        # Treeview
        cols = ("id", "checklist_id", "task_name", "category",
                "assigned_to", "due_date", "completed", "completed_date")
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        self._tree_tasks = ttk.Treeview(
            tree_frame, columns=cols, show="headings", selectmode="browse",
        )
        headings = {
            "id": ("ID", 40), "checklist_id": ("Checklist ID", 85),
            "task_name": ("Task", 180), "category": ("Category", 100),
            "assigned_to": ("Assigned To", 85), "due_date": ("Due Date", 90),
            "completed": ("Completed", 70), "completed_date": ("Completed Date", 110),
        }
        for col, (text, width) in headings.items():
            self._tree_tasks.heading(col, text=text)
            self._tree_tasks.column(col, width=width, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree_tasks.yview)
        self._tree_tasks.configure(yscrollcommand=vsb.set)
        self._tree_tasks.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._task_status = tk.StringVar(value="Ready")
        tk.Label(tab, textvariable=self._task_status, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x")

    def _load_tasks(self):
        self._tree_tasks.delete(*self._tree_tasks.get_children())
        try:
            kwargs: dict = {}
            cl_id = self._task_cl_var.get().strip()
            if cl_id:
                kwargs["checklist_id"] = int(cl_id)
            cat = self._task_cat_var.get()
            if cat != "All":
                kwargs["category"] = cat
            done = self._task_done_var.get()
            if done == "Yes":
                kwargs["completed"] = 1
            elif done == "No":
                kwargs["completed"] = 0
            items = self._svc.list_tasks(**kwargs)
            for item in items:
                completed_display = "Yes" if item.get("completed") else "No"
                self._tree_tasks.insert("", "end", iid=item["id"], values=(
                    item.get("id", ""),
                    item.get("checklist_id", ""),
                    item.get("task_name", ""),
                    item.get("category", ""),
                    item.get("assigned_to", ""),
                    item.get("due_date", ""),
                    completed_display,
                    item.get("completed_date", ""),
                ))
            self._task_status.set(f"{len(items)} task(s) loaded")
        except ValueError:
            messagebox.showerror("Error", "Checklist ID must be a number.")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load tasks:\n{exc}")

    def _selected_task_id(self) -> int | None:
        sel = self._tree_tasks.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a task first.")
            return None
        return int(sel[0])

    def _on_new_task(self):
        dlg = _TaskDialog(self, title="New Task")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            checklist_id = int(data.pop("checklist_id"))
            task_name = data.pop("task_name")
            clean = {k: v for k, v in data.items() if v}
            if clean.get("assigned_to"):
                clean["assigned_to"] = int(clean["assigned_to"])
            self._svc.create_task(checklist_id, task_name, **clean)
            messagebox.showinfo("Success", "Task created.")
            self._load_tasks()
        except ValueError:
            messagebox.showerror("Error", "Checklist ID and Assigned To must be numbers.")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_complete_task(self):
        pk = self._selected_task_id()
        if pk is None:
            return
        try:
            self._svc.complete_task(pk)
            messagebox.showinfo("Success", "Task marked as completed.")
            self._load_tasks()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_update_task(self):
        pk = self._selected_task_id()
        if pk is None:
            return
        item = self._svc.get_task(pk)
        if not item:
            messagebox.showerror("Error", "Task not found.")
            return
        dlg = _TaskDialog(self, title="Update Task", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            clean = {k: v for k, v in dlg.result.items() if v}
            clean.pop("checklist_id", None)  # don't reassign checklist
            if clean.get("assigned_to"):
                clean["assigned_to"] = int(clean["assigned_to"])
            self._svc.update_task(pk, **clean)
            messagebox.showinfo("Success", "Task updated.")
            self._load_tasks()
        except ValueError:
            messagebox.showerror("Error", "Assigned To must be a number.")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete_task(self):
        pk = self._selected_task_id()
        if pk is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this task?"):
            return
        try:
            self._svc.delete_task(pk)
            messagebox.showinfo("Success", "Task deleted.")
            self._load_tasks()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_show_pending(self):
        """Show all pending tasks across all checklists."""
        self._tree_tasks.delete(*self._tree_tasks.get_children())
        try:
            items = self._svc.get_pending_tasks()
            for item in items:
                self._tree_tasks.insert("", "end", iid=item["id"], values=(
                    item.get("id", ""),
                    item.get("checklist_id", ""),
                    item.get("task_name", ""),
                    item.get("category", ""),
                    item.get("assigned_to", ""),
                    item.get("due_date", ""),
                    "No",
                    "",
                ))
            self._task_status.set(f"{len(items)} pending task(s)")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load pending tasks:\n{exc}")

    # ── Tab 2: Probation Reviews ────────────────────────────────

    def _build_reviews_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Probation Reviews")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))
        tk.Label(filt, text="Checklist ID:", bg="#ecf0f1",
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(0, 3))
        self._rev_cl_var = tk.StringVar()
        ttk.Entry(filt, textvariable=self._rev_cl_var, width=8).pack(side="left", padx=2)
        ttk.Button(filt, text="Filter", command=self._load_reviews).pack(side="left", padx=6)

        # Buttons
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))
        for txt, cmd in [
            ("New", self._on_new_review),
            ("View", self._on_view_review),
            ("Update", self._on_update_review),
            ("Delete", self._on_delete_review),
            ("Refresh", self._load_reviews),
        ]:
            ttk.Button(toolbar, text=txt, command=cmd).pack(side="left", padx=3)

        # Treeview
        cols = ("id", "checklist_id", "review_date", "reviewer_id",
                "review_number", "performance_rating", "recommendation")
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        self._tree_rev = ttk.Treeview(
            tree_frame, columns=cols, show="headings", selectmode="browse",
        )
        headings = {
            "id": ("ID", 40), "checklist_id": ("Checklist ID", 85),
            "review_date": ("Review Date", 95), "reviewer_id": ("Reviewer", 70),
            "review_number": ("Review #", 65),
            "performance_rating": ("Rating", 90),
            "recommendation": ("Recommendation", 110),
        }
        for col, (text, width) in headings.items():
            self._tree_rev.heading(col, text=text)
            self._tree_rev.column(col, width=width, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree_rev.yview)
        self._tree_rev.configure(yscrollcommand=vsb.set)
        self._tree_rev.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._rev_status = tk.StringVar(value="Ready")
        tk.Label(tab, textvariable=self._rev_status, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x")

    def _load_reviews(self):
        self._tree_rev.delete(*self._tree_rev.get_children())
        try:
            cl_id = self._rev_cl_var.get().strip()
            checklist_id = int(cl_id) if cl_id else None
            items = self._svc.list_reviews(checklist_id=checklist_id)
            for item in items:
                self._tree_rev.insert("", "end", iid=item["id"], values=(
                    item.get("id", ""),
                    item.get("checklist_id", ""),
                    item.get("review_date", ""),
                    item.get("reviewer_id", ""),
                    item.get("review_number", ""),
                    item.get("performance_rating", ""),
                    item.get("recommendation", ""),
                ))
            self._rev_status.set(f"{len(items)} review(s) loaded")
        except ValueError:
            messagebox.showerror("Error", "Checklist ID must be a number.")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load reviews:\n{exc}")

    def _selected_rev_id(self) -> int | None:
        sel = self._tree_rev.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a review first.")
            return None
        return int(sel[0])

    def _on_new_review(self):
        dlg = _ReviewDialog(self, title="New Review")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            checklist_id = int(data.pop("checklist_id"))
            review_date = data.pop("review_date")
            clean = {k: v for k, v in data.items() if v}
            if clean.get("reviewer_id"):
                clean["reviewer_id"] = int(clean["reviewer_id"])
            if clean.get("review_number"):
                clean["review_number"] = int(clean["review_number"])
            self._svc.create_review(checklist_id, review_date, **clean)
            messagebox.showinfo("Success", "Review created.")
            self._load_reviews()
        except ValueError:
            messagebox.showerror("Error", "Checklist ID, Reviewer ID, and Review Number must be numbers.")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_view_review(self):
        pk = self._selected_rev_id()
        if pk is None:
            return
        item = self._svc.get_review(pk)
        if not item:
            messagebox.showerror("Error", "Review not found.")
            return
        _DetailDialog(self, "Review Details", item)

    def _on_update_review(self):
        pk = self._selected_rev_id()
        if pk is None:
            return
        item = self._svc.get_review(pk)
        if not item:
            messagebox.showerror("Error", "Review not found.")
            return
        dlg = _ReviewDialog(self, title="Update Review", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            clean = {k: v for k, v in dlg.result.items() if v}
            clean.pop("checklist_id", None)
            if clean.get("reviewer_id"):
                clean["reviewer_id"] = int(clean["reviewer_id"])
            if clean.get("review_number"):
                clean["review_number"] = int(clean["review_number"])
            self._svc.update_review(pk, **clean)
            messagebox.showinfo("Success", "Review updated.")
            self._load_reviews()
        except ValueError:
            messagebox.showerror("Error", "Reviewer ID and Review Number must be numbers.")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete_review(self):
        pk = self._selected_rev_id()
        if pk is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this review?"):
            return
        try:
            self._svc.delete_review(pk)
            messagebox.showinfo("Success", "Review deleted.")
            self._load_reviews()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    # ── Tab 3: Statistics ───────────────────────────────────────

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Statistics")
        self._stats_frame = tab

        ttk.Button(tab, text="Refresh Statistics", command=self._load_stats).pack(
            anchor="w", pady=(0, 10)
        )
        self._stats_container = tk.Frame(tab, bg="#ecf0f1")
        self._stats_container.pack(fill="both", expand=True)

    def _load_stats(self):
        for w in self._stats_container.winfo_children():
            w.destroy()
        try:
            stats = self._svc.get_stats()
            c = self._stats_container
            lbl_font = ("Helvetica", 10)
            hdr_font = ("Helvetica", 11, "bold")

            row = 0
            tk.Label(c, text="Checklists", font=hdr_font, bg="#ecf0f1").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(5, 2)
            )
            for label, key in [
                ("Total:", "total_checklists"),
                ("In Progress:", "in_progress"),
                ("Completed:", "completed"),
                ("Failed:", "failed"),
            ]:
                row += 1
                tk.Label(c, text=label, font=lbl_font, bg="#ecf0f1", anchor="w").grid(
                    row=row, column=0, sticky="w", padx=(20, 10), pady=1
                )
                tk.Label(c, text=str(stats.get(key, 0)), font=lbl_font,
                         bg="#ecf0f1", anchor="w").grid(
                    row=row, column=1, sticky="w", pady=1
                )

            row += 1
            tk.Label(c, text="Tasks", font=hdr_font, bg="#ecf0f1").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(15, 2)
            )
            for label, key in [
                ("Total:", "total_tasks"),
                ("Completed:", "tasks_completed"),
                ("Pending:", "tasks_pending"),
                ("Completion Rate:", "completion_rate"),
            ]:
                row += 1
                tk.Label(c, text=label, font=lbl_font, bg="#ecf0f1", anchor="w").grid(
                    row=row, column=0, sticky="w", padx=(20, 10), pady=1
                )
                val = stats.get(key, 0)
                display = f"{val}%" if key == "completion_rate" else str(val)
                tk.Label(c, text=display, font=lbl_font, bg="#ecf0f1", anchor="w").grid(
                    row=row, column=1, sticky="w", pady=1
                )

            row += 1
            tk.Label(c, text="Probation Reviews", font=hdr_font, bg="#ecf0f1").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(15, 2)
            )
            row += 1
            tk.Label(c, text="Total:", font=lbl_font, bg="#ecf0f1", anchor="w").grid(
                row=row, column=0, sticky="w", padx=(20, 10), pady=1
            )
            tk.Label(c, text=str(stats.get("total_reviews", 0)), font=lbl_font,
                     bg="#ecf0f1", anchor="w").grid(row=row, column=1, sticky="w", pady=1)

            by_rec = stats.get("by_recommendation", {})
            if by_rec:
                row += 1
                tk.Label(c, text="By Recommendation:", font=lbl_font, bg="#ecf0f1",
                         anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 10), pady=1)
                for rec_name, cnt in by_rec.items():
                    row += 1
                    tk.Label(c, text=f"  {rec_name}:", font=lbl_font, bg="#ecf0f1",
                             anchor="w").grid(row=row, column=0, sticky="w", padx=(40, 10), pady=1)
                    tk.Label(c, text=str(cnt), font=lbl_font, bg="#ecf0f1",
                             anchor="w").grid(row=row, column=1, sticky="w", pady=1)

        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load statistics:\n{exc}")

    # ── Public ──────────────────────────────────────────────────

    def refresh(self):
        """Reload all tabs."""
        self._load_checklists()
        self._load_tasks()
        self._load_reviews()
