"""Course management GUI for the Sixth Form College Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.core.exceptions import CourseError, ValidationError


class _CourseDialog(tk.Toplevel):
    """Modal dialog for adding or editing a course record."""

    def __init__(self, parent, title="Course", course=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()

        self.result: dict | None = None
        self._course = course

        self._build_ui()
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        container = tk.Frame(self, padx=20, pady=15)
        container.pack(fill="both", expand=True)

        entry_fields = [
            ("Course Code",          "course_code"),
            ("Title",                "title"),
            ("Description",          "description"),
            ("Guided Learning Hours", "credits"),
            ("Capacity",             "capacity"),
            ("Subject Area",         "subject_area"),
            ("Teacher",              "teacher"),
            ("Schedule",             "schedule"),
        ]

        self._vars: dict[str, tk.StringVar] = {}
        row_idx = 0
        for row_idx, (label_text, key) in enumerate(entry_fields):
            tk.Label(container, text=label_text, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(
                row=row_idx, column=0, sticky="w", **pad)

            default = ""
            if self._course and self._course.get(key) is not None:
                default = str(self._course[key])

            var = tk.StringVar(value=default)

            # Disable course_code editing for existing courses
            state = "readonly" if (key == "course_code" and self._course) else "normal"
            ttk.Entry(container, textvariable=var, width=36,
                      state=state).grid(row=row_idx, column=1, sticky="ew", **pad)
            self._vars[key] = var

        # Qualification Type (Combobox)
        row_idx += 1
        tk.Label(container, text="Qualification Type", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(
            row=row_idx, column=0, sticky="w", **pad)
        self._vars["qualification_type"] = tk.StringVar(
            value=self._course.get("qualification_type", "A-Level") if self._course else "A-Level"
        )
        ttk.Combobox(container, textvariable=self._vars["qualification_type"],
                     values=["A-Level", "BTEC", "T-Level", "GCSE", "Core Maths", "EPQ"],
                     state="readonly", width=33).grid(
            row=row_idx, column=1, sticky="ew", **pad)

        # Term (Combobox)
        row_idx += 1
        tk.Label(container, text="Term", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(
            row=row_idx, column=0, sticky="w", **pad)
        self._vars["term"] = tk.StringVar(
            value=self._course.get("term", "") if self._course and self._course.get("term") else ""
        )
        ttk.Combobox(container, textvariable=self._vars["term"],
                     values=["", "Autumn", "Spring", "Summer"],
                     width=33).grid(
            row=row_idx, column=1, sticky="ew", **pad)

        # Status (edit mode only)
        if self._course:
            row_idx += 1
            tk.Label(container, text="Status", anchor="w",
                     font=("Helvetica", 9, "bold")).grid(
                row=row_idx, column=0, sticky="w", **pad)
            self._status_var = tk.StringVar(
                value=self._course.get("status", "active"))
            ttk.Combobox(container, textvariable=self._status_var,
                         values=["active", "inactive", "cancelled"],
                         state="readonly", width=33).grid(
                row=row_idx, column=1, sticky="ew", **pad)
        else:
            self._status_var = None

        # Buttons
        btn_frame = tk.Frame(container)
        btn_frame.grid(row=row_idx + 1, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
            side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        if self._status_var:
            self.result["status"] = self._status_var.get()
        self.destroy()


class CourseFrame(tk.Frame):
    """Course management screen with Treeview and CRUD controls."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = CourseService(db_path)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Course Management", font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Toolbar
        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)

        self._add_btn = ttk.Button(toolbar, text="Add Course", command=self._on_add)
        self._add_btn.pack(side="left", padx=4)
        self._edit_btn = ttk.Button(toolbar, text="Edit Selected", command=self._on_edit)
        self._edit_btn.pack(side="left", padx=4)
        self._delete_btn = ttk.Button(toolbar, text="Delete Selected", command=self._on_delete)
        self._delete_btn.pack(side="left", padx=4)
        ttk.Button(toolbar, text="Refresh", command=self._load_courses).pack(
            side="left", padx=4)

        # Treeview
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("course_code", "title", "qualification_type", "capacity", "status")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  selectmode="browse")

        headings = {
            "course_code":       ("Code",          100),
            "title":             ("Title",         220),
            "qualification_type": ("Qualification",  110),
            "capacity":          ("Capacity",       90),
            "status":            ("Status",        100),
        }
        for col, (heading, width) in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh(self):
        self._apply_permissions()
        self._load_courses()

    def _apply_permissions(self):
        """Show or hide editing controls based on user role."""
        role = ""
        if self._auth and self._auth.current_user:
            role = self._auth.current_user.get("role", "student")
        can_edit = role in ("admin", "staff", "instructor", "teacher")
        for btn in (self._add_btn, self._edit_btn, self._delete_btn):
            if can_edit:
                btn.pack(side="left", padx=4)
            else:
                btn.pack_forget()

    def _load_courses(self):
        self._tree.delete(*self._tree.get_children())
        try:
            courses = self._svc.list_courses(limit=500)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load courses:\n{exc}")
            return

        for c in courses:
            self._tree.insert("", "end", iid=c["id"], values=(
                c.get("course_code", ""),
                c.get("title", ""),
                c.get("qualification_type", "") or "",
                c.get("capacity", ""),
                c.get("status", ""),
            ))

        self._status_var.set(f"{len(courses)} course(s) loaded")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a course first.")
            return None
        return int(sel[0])

    def _on_add(self):
        dlg = _CourseDialog(self, title="Add Course")
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        if not data.get("course_code") or not data.get("title"):
            messagebox.showwarning("Validation",
                                   "Course code and title are required.")
            return

        try:
            glh_val = int(data["credits"]) if data.get("credits") else 3
            capacity_val = int(data["capacity"]) if data.get("capacity") else 30
        except ValueError:
            messagebox.showwarning("Validation",
                                   "Guided Learning Hours and capacity must be integers.")
            return

        try:
            self._svc.create_course(
                course_code=data["course_code"],
                title=data["title"],
                guided_learning_hours=glh_val,
                capacity=capacity_val,
                description=data.get("description") or None,
                subject_area=data.get("subject_area") or None,
                teacher=data.get("teacher") or None,
                term=data.get("term") or None,
                schedule=data.get("schedule") or None,
                qualification_type=data.get("qualification_type") or "A-Level",
            )
            messagebox.showinfo("Success", "Course created successfully.")
            self._load_courses()
        except (CourseError, ValidationError) as exc:
            messagebox.showerror("Error", str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return

        course = self._svc.get_course(pk)
        if not course:
            messagebox.showerror("Error", "Course not found.")
            return

        dlg = _CourseDialog(self, title="Edit Course", course=course)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        try:
            update_fields = {}
            for key in ("title", "description", "subject_area", "teacher",
                        "term", "schedule", "status", "qualification_type"):
                val = data.get(key)
                if val:
                    update_fields[key] = val

            # Numeric fields
            if data.get("credits"):
                update_fields["credits"] = int(data["credits"])
            if data.get("capacity"):
                update_fields["capacity"] = int(data["capacity"])

            if update_fields:
                self._svc.update_course(pk, **update_fields)
                messagebox.showinfo("Success", "Course updated successfully.")
                self._load_courses()
        except (CourseError, ValidationError, ValueError) as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return

        if not messagebox.askyesno("Confirm Delete",
                                   "This will permanently delete the course and all related data "
                                   "(enrollments, grades, attendance, timetable slots, assignments).\n\n"
                                   "This cannot be undone. Continue?"):
            return

        try:
            self._svc.delete_course(pk)
            messagebox.showinfo("Success", "Course deleted permanently.")
            self._load_courses()
        except (CourseError, ValidationError) as exc:
            messagebox.showerror("Error", str(exc))
