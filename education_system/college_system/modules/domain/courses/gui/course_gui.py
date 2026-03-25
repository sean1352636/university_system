"""Course management GUI for the Sixth Form College Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.core.exceptions import CourseError, ValidationError
from education_system.college_system.core.i18n import t


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
        self.bind("<Escape>", lambda e: self.destroy())

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
            (t("course.course_code"),          "course_code"),
            (t("course.title"),                "title"),
            (t("course.description"),          "description"),
            (t("course.guided_learning_hours"), "credits"),
            (t("course.capacity"),             "capacity"),
            (t("course.subject_area"),         "subject_area"),
            (t("course.teacher"),              "teacher"),
            (t("course.schedule"),             "schedule"),
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
        tk.Label(container, text=t("course.qualification_type"), anchor="w",
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
        tk.Label(container, text=t("course.term"), anchor="w",
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
            tk.Label(container, text=t("course.status"), anchor="w",
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
        ttk.Button(btn_frame, text=t("common.save"), command=self._on_save).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(
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

        # Pagination state
        self._page = 0
        self._page_size = 50
        self._total_count = 0

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
        tk.Label(header, text=t("course.management"), font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Toolbar
        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)

        self._add_btn = ttk.Button(toolbar, text=t("course.add"), command=self._on_add)
        self._add_btn.pack(side="left", padx=4)
        self._edit_btn = ttk.Button(toolbar, text=t("common.edit_selected"), command=self._on_edit)
        self._edit_btn.pack(side="left", padx=4)
        self._delete_btn = ttk.Button(toolbar, text=t("common.delete_selected"), command=self._on_delete)
        self._delete_btn.pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_courses).pack(
            side="left", padx=4)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(
            side="right", padx=4)

        # Treeview
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("course_code", "title", "qualification_type", "capacity", "status")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  selectmode="browse")

        headings = {
            "course_code":       (t("course.col_code"),          100),
            "title":             (t("course.col_title"),         220),
            "qualification_type": (t("course.col_qualification"),  110),
            "capacity":          (t("course.col_capacity"),       90),
            "status":            (t("course.col_status"),        100),
        }
        for col, (heading, width) in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Pagination bar
        self._pag_frame = tk.Frame(self, bg="#ecf0f1")
        self._pag_frame.pack(fill="x", padx=15, pady=(0, 4))

        self._prev_btn = ttk.Button(self._pag_frame, text="Previous",
                                     command=self._prev_page, state="disabled")
        self._prev_btn.pack(side="left", padx=4)

        self._page_label_var = tk.StringVar(value="Page 1 of 1")
        tk.Label(self._pag_frame, textvariable=self._page_label_var,
                 bg="#ecf0f1", font=("Helvetica", 9)).pack(side="left", padx=8)

        self._next_btn = ttk.Button(self._pag_frame, text="Next",
                                     command=self._next_page, state="disabled")
        self._next_btn.pack(side="left", padx=4)

        self._record_count_var = tk.StringVar(value="")
        tk.Label(self._pag_frame, textvariable=self._record_count_var,
                 bg="#ecf0f1", font=("Helvetica", 9), fg="#7f8c8d").pack(
            side="right", padx=8)

        # Status bar
        self._status_var = tk.StringVar(value=t("common.ready"))
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

        # --- Keyboard shortcuts for accessibility ---
        self._tree.bind("<Return>", lambda e: self._on_edit())
        self._tree.bind("<Delete>", lambda e: self._on_delete())
        self._bind_when_visible("<Control-n>", lambda e: self._on_add())

    def _bind_when_visible(self, sequence, callback):
        """Bind a keyboard shortcut that only fires when this frame is visible."""
        def _handler(event):
            if self.winfo_ismapped():
                callback(event)
                return "break"
        self.bind(sequence, _handler)
        top = self.winfo_toplevel()
        top.bind(sequence, _handler, add=True)

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
            self._total_count = self._svc.count_courses()
            courses = self._svc.list_courses(
                limit=self._page_size,
                offset=self._page * self._page_size,
            )
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"Failed to load courses:\n{exc}")
            return

        for c in courses:
            self._tree.insert("", "end", iid=c["id"], values=(
                c.get("course_code", ""),
                c.get("title", ""),
                c.get("qualification_type", "") or "",
                c.get("capacity", ""),
                c.get("status", ""),
            ))

        self._update_pagination()
        count = len(courses)
        self._status_var.set(t("course.count_loaded", count=count))

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _update_pagination(self):
        """Update pagination controls based on current state."""
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        current = self._page + 1
        self._page_label_var.set(f"Page {current} of {total_pages}")

        start = self._page * self._page_size + 1
        end = min((self._page + 1) * self._page_size, self._total_count)
        if self._total_count == 0:
            self._record_count_var.set("No records")
        else:
            self._record_count_var.set(
                f"Showing {start}-{end} of {self._total_count} records")

        self._prev_btn.configure(
            state="normal" if self._page > 0 else "disabled")
        self._next_btn.configure(
            state="normal" if current < total_pages else "disabled")

    def _next_page(self):
        self._page += 1
        self._load_courses()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
        self._load_courses()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("course.select_first"))
            return None
        return int(sel[0])

    def _on_add(self):
        dlg = _CourseDialog(self, title="Add Course")
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        if not data.get("course_code") or not data.get("title"):
            messagebox.showwarning(t("common.validation"),
                                   t("course.code_and_title_required"))
            return

        try:
            glh_val = int(data["credits"]) if data.get("credits") else 3
            capacity_val = int(data["capacity"]) if data.get("capacity") else 30
        except ValueError:
            messagebox.showwarning(t("common.validation"),
                                   t("course.glh_capacity_integers"))
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
            messagebox.showinfo(t("common.success"), t("course.created"))
            self._load_courses()
        except (CourseError, ValidationError) as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return

        course = self._svc.get_course(pk)
        if not course:
            messagebox.showerror(t("common.error"), t("course.not_found"))
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
                messagebox.showinfo(t("common.success"), t("course.updated"))
                self._load_courses()
        except (CourseError, ValidationError, ValueError) as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, default_filename="courses.csv")

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return

        if not messagebox.askyesno(t("common.confirm_delete"),
                                   t("course.delete_confirm")):
            return

        try:
            self._svc.delete_course(pk)
            messagebox.showinfo(t("common.success"), t("course.deleted"))
            self._load_courses()
        except (CourseError, ValidationError) as exc:
            messagebox.showerror(t("common.error"), str(exc))
