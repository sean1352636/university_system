"""Enrollment management GUI for the College Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.enrollment.services.enrollment_service import EnrollmentService
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.core.exceptions import EnrollmentError
from education_system.college_system.core.i18n import t


class EnrollmentFrame(tk.Frame):
    """Enrollment management screen.

    Provides enroll / drop actions, a Treeview of current enrollments and a
    secondary panel showing waitlist information for a selected course.
    """

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._enrollment_svc = EnrollmentService(db_path)
        self._student_svc = StudentService(db_path)
        self._course_svc = CourseService(db_path)

        # Pagination state
        self._page = 0
        self._page_size = 50
        self._total_count = 0
        self._current_status_filter: str | None = None

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
        tk.Label(header, text=t("enrollment.management"),
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # --- Enroll / Drop form ---
        form_frame = tk.LabelFrame(self, text=t("enrollment.enroll_drop"), padx=12, pady=8,
                                   bg="#ecf0f1", font=("Helvetica", 10, "bold"))
        form_frame.pack(fill="x", padx=15, pady=(10, 5))

        tk.Label(form_frame, text=t("enrollment.student_id_colon"), bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=5, pady=4)
        self._student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._student_id_var,
                  width=16).grid(row=0, column=1, padx=5, pady=4)

        tk.Label(form_frame, text=t("enrollment.course_code_colon"), bg="#ecf0f1").grid(
            row=0, column=2, sticky="w", padx=5, pady=4)
        self._course_code_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._course_code_var,
                  width=16).grid(row=0, column=3, padx=5, pady=4)

        ttk.Button(form_frame, text=t("enrollment.enroll"),
                   command=self._on_enroll).grid(row=0, column=4, padx=8, pady=4)
        ttk.Button(form_frame, text=t("enrollment.drop"),
                   command=self._on_drop).grid(row=0, column=5, padx=4, pady=4)

        # --- Main content: enrollments tree + waitlist panel side-by-side ---
        content = tk.Frame(self, bg="#ecf0f1")
        content.pack(fill="both", expand=True, padx=15, pady=5)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Enrollments Treeview
        enroll_lf = tk.LabelFrame(content, text=t("enrollment.enrollments"), bg="#ecf0f1",
                                  font=("Helvetica", 10, "bold"))
        enroll_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        tree_frame = tk.Frame(enroll_lf)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)

        columns = ("sid", "student_name", "course_code", "course_title",
                   "status", "enrolled_at")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  selectmode="browse")

        headings = {
            "sid":          (t("enrollment.col_student_id"),  90),
            "student_name": (t("enrollment.col_name"),       140),
            "course_code":  (t("enrollment.col_course"),      80),
            "course_title": (t("enrollment.col_title"),      160),
            "status":       (t("enrollment.col_status"),      80),
            "enrolled_at":  (t("enrollment.col_date"),       130),
        }
        for col, (heading, width) in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Filter bar below tree
        filter_bar = tk.Frame(enroll_lf, bg="#ecf0f1")
        filter_bar.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Button(filter_bar, text=t("enrollment.show_all"),
                   command=self._on_show_all).pack(side="left", padx=4)
        ttk.Button(filter_bar, text=t("enrollment.active_only"),
                   command=self._on_active_only).pack(side="left", padx=4)
        ttk.Button(filter_bar, text="Export CSV", command=self._export_csv).pack(
            side="right", padx=4)

        # Pagination bar
        pag_frame = tk.Frame(enroll_lf, bg="#ecf0f1")
        pag_frame.pack(fill="x", padx=4, pady=(0, 4))

        self._prev_btn = ttk.Button(pag_frame, text="Previous",
                                     command=self._prev_page, state="disabled")
        self._prev_btn.pack(side="left", padx=4)

        self._page_label_var = tk.StringVar(value="Page 1 of 1")
        tk.Label(pag_frame, textvariable=self._page_label_var,
                 bg="#ecf0f1", font=("Helvetica", 9)).pack(side="left", padx=8)

        self._next_btn = ttk.Button(pag_frame, text="Next",
                                     command=self._next_page, state="disabled")
        self._next_btn.pack(side="left", padx=4)

        self._record_count_var = tk.StringVar(value="")
        tk.Label(pag_frame, textvariable=self._record_count_var,
                 bg="#ecf0f1", font=("Helvetica", 9), fg="#7f8c8d").pack(
            side="right", padx=8)

        # Waitlist panel
        wl_lf = tk.LabelFrame(content, text=t("enrollment.waitlist"), bg="#ecf0f1",
                               font=("Helvetica", 10, "bold"))
        wl_lf.grid(row=0, column=1, sticky="nsew")

        wl_inner = tk.Frame(wl_lf, bg="#ecf0f1")
        wl_inner.pack(fill="both", expand=True, padx=4, pady=4)

        tk.Label(wl_inner, text=t("enrollment.course_code_colon"), bg="#ecf0f1").pack(anchor="w")
        self._wl_course_var = tk.StringVar()
        ttk.Entry(wl_inner, textvariable=self._wl_course_var, width=16).pack(
            anchor="w", pady=(0, 4))
        ttk.Button(wl_inner, text=t("enrollment.view_waitlist"),
                   command=self._on_view_waitlist).pack(anchor="w", pady=(0, 8))

        wl_cols = ("position", "sid", "name")
        self._wl_tree = ttk.Treeview(wl_inner, columns=wl_cols,
                                     show="headings", height=8)
        for col, heading, w in [("position", "#", 40),
                                ("sid", t("enrollment.col_student_id"), 90),
                                ("name", t("enrollment.col_name"), 130)]:
            self._wl_tree.heading(col, text=heading)
            self._wl_tree.column(col, width=w, anchor="center")
        self._wl_tree.pack(fill="both", expand=True)

        # Status bar
        self._status_var = tk.StringVar(value=t("common.ready"))
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1",
                 anchor="w", font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

        # --- Keyboard shortcuts for accessibility ---
        self._tree.bind("<Return>", lambda e: self._on_view_selected_enrollment())
        self._tree.bind("<Delete>", lambda e: self._on_drop_selected())
        self._bind_when_visible("<Control-n>", lambda e: self._on_enroll())

    def _bind_when_visible(self, sequence, callback):
        """Bind a keyboard shortcut that only fires when this frame is visible."""
        def _handler(event):
            if self.winfo_ismapped():
                callback(event)
                return "break"
        self.bind(sequence, _handler)
        top = self.winfo_toplevel()
        top.bind(sequence, _handler, add=True)

    def _on_view_selected_enrollment(self):
        """Handle Return key on enrollment treeview -- show enrollment details."""
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], "values")
        if values:
            detail = (
                f"Student ID: {values[0]}\n"
                f"Name: {values[1]}\n"
                f"Course: {values[2]} - {values[3]}\n"
                f"Status: {values[4]}\n"
                f"Enrolled: {values[5]}"
            )
            messagebox.showinfo("Enrollment Details", detail)

    def _on_drop_selected(self):
        """Handle Delete key -- drop the selected enrollment after confirmation."""
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], "values")
        if not values:
            return
        # Pre-fill the drop form with the selected enrollment's IDs
        self._student_id_var.set(values[0])  # student_id
        self._course_code_var.set(values[2])  # course_code
        self._on_drop()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh(self):
        self._load_enrollments()

    def _load_enrollments(self, status: str | None = None):
        if status is not None:
            self._current_status_filter = status if status else None
        self._tree.delete(*self._tree.get_children())
        try:
            self._total_count = self._enrollment_svc.count_enrollments(
                status=self._current_status_filter)
            enrollments = self._enrollment_svc.list_enrollments(
                status=self._current_status_filter,
                limit=self._page_size,
                offset=self._page * self._page_size,
            )
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"Failed to load enrollments:\n{exc}")
            return

        for e in enrollments:
            name = f"{e.get('first_name', '')} {e.get('last_name', '')}"
            self._tree.insert("", "end", values=(
                e.get("sid", ""),
                name.strip(),
                e.get("course_code", ""),
                e.get("title", ""),
                e.get("status", ""),
                e.get("enrolled_at", ""),
            ))

        self._update_pagination()
        count = len(enrollments)
        self._status_var.set(t("enrollment.count_loaded", count=count))

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
        self._load_enrollments()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
        self._load_enrollments()

    def _on_show_all(self):
        self._page = 0
        self._current_status_filter = None
        self._load_enrollments()

    def _on_active_only(self):
        self._page = 0
        self._load_enrollments(status="enrolled")

    # ------------------------------------------------------------------
    # Resolve helpers
    # ------------------------------------------------------------------

    def _resolve_ids(self):
        """Resolve student ID string and course code to their PKs.

        Returns (student_pk, course_pk) or raises EnrollmentError.
        """
        sid_str = self._student_id_var.get().strip()
        code_str = self._course_code_var.get().strip().upper()

        if not sid_str or not code_str:
            raise EnrollmentError("Both student ID and course code are required.")

        student = self._student_svc.get_student_by_student_id(sid_str)
        if not student:
            raise EnrollmentError(f"Student '{sid_str}' not found.")

        course = self._course_svc.get_course_by_code(code_str)
        if not course:
            raise EnrollmentError(f"Course '{code_str}' not found.")

        return student["id"], course["id"]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_enroll(self):
        try:
            student_pk, course_pk = self._resolve_ids()
            result = self._enrollment_svc.enroll_student(student_pk, course_pk)
        except EnrollmentError as exc:
            messagebox.showerror(t("enrollment.error"), str(exc))
            return
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"Unexpected error:\n{exc}")
            return

        status = result.get("status", "unknown")
        if status == "waitlisted":
            messagebox.showinfo(
                t("enrollment.waitlisted"),
                t("enrollment.waitlisted_msg", position=result.get('position', '?')),
            )
        else:
            messagebox.showinfo(t("enrollment.enrolled"),
                                t("enrollment.enrolled_msg"))

        self._load_enrollments()

    def _on_drop(self):
        try:
            student_pk, course_pk = self._resolve_ids()
        except EnrollmentError as exc:
            messagebox.showerror(t("common.error"), str(exc))
            return

        if not messagebox.askyesno(t("enrollment.confirm_drop"),
                                   t("enrollment.confirm_drop_msg")):
            return

        try:
            result = self._enrollment_svc.drop_student(student_pk, course_pk)
        except EnrollmentError as exc:
            messagebox.showerror(t("enrollment.drop_error"), str(exc))
            return

        msg = t("enrollment.dropped_msg")
        if result.get("promoted_student_pk"):
            msg += "\n" + t("enrollment.promoted_msg")
        messagebox.showinfo(t("enrollment.dropped"), msg)
        self._load_enrollments()

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, default_filename="enrollments.csv")

    def _on_view_waitlist(self):
        code = self._wl_course_var.get().strip().upper()
        if not code:
            messagebox.showwarning(t("common.input"), t("enrollment.enter_course_code"))
            return

        course = self._course_svc.get_course_by_code(code)
        if not course:
            messagebox.showerror(t("common.error"), f"Course '{code}' not found.")
            return

        self._wl_tree.delete(*self._wl_tree.get_children())
        try:
            waitlist = self._enrollment_svc.get_waitlist(course["id"])
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"Failed to load waitlist:\n{exc}")
            return

        for w in waitlist:
            name = f"{w.get('first_name', '')} {w.get('last_name', '')}"
            self._wl_tree.insert("", "end", values=(
                w.get("position", ""),
                w.get("sid", ""),
                name.strip(),
            ))

        if not waitlist:
            self._status_var.set(f"No students on waitlist for {code}")
        else:
            self._status_var.set(f"{len(waitlist)} student(s) on waitlist for {code}")
